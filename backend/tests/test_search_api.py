"""Spec map-search: карта, фильтры, сортировка, текстовый поиск, GPX, отметки км."""

import random
import uuid
import xml.etree.ElementTree as ET

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.infra.models import Track, TrackDownload
from app.infra.ratings_service import recalc
from tests.gpx_factory import GEOD, offset, straight, to_gpx
from tests.helpers import Headers, dev_login, haversine, publish, set_home, uploaded


def area() -> tuple[float, float]:
    """Своя точка для каждого теста: треки других тестов не попадают в выдачу."""
    return (random.uniform(-60, 60), random.uniform(-170, 170))


def bbox(center: tuple[float, float], half_m: float = 20_000) -> str:
    south, west = offset(*center, -half_m, -half_m)
    north, east = offset(*center, half_m, half_m)
    return f"{west},{south},{east},{north}"


def run_at(
    client: TestClient,
    headers: Headers,
    start: tuple[float, float],
    distance: float = 3000,
    visibility: str | None = "public",
    title: str | None = None,
    **kw,  # type: ignore[no-untyped-def]
) -> dict:  # type: ignore[type-arg]
    track = uploaded(client, headers, to_gpx(straight(distance, start=start, **kw)))
    if title:
        client.patch(f"/tracks/{track['id']}", headers=headers, json={"title": title})
    if visibility:
        publish(client, headers, track["id"], visibility)
    return track  # type: ignore[no-any-return]


def search(client: TestClient, **params) -> dict:  # type: ignore[no-untyped-def, type-arg]
    resp = client.get("/tracks/search", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()  # type: ignore[no-any-return]


def ids(result: dict) -> set[str]:  # type: ignore[type-arg]
    return {i["id"] for i in result["items"]}


# --- Map Display --------------------------------------------------------------------


def test_close_zoom_shows_lines(client: TestClient) -> None:
    me, center = dev_login(client), area()
    a = run_at(client, me, center)
    b = run_at(client, me, offset(*center, 2000, 0))
    result = search(client, bbox=bbox(center), zoom=14)
    assert result["mode"] == "lines" and result["clusters"] == []
    assert {ln["id"] for ln in result["lines"]} == {a["id"], b["id"]}
    assert all(len(ln["coordinates"]) >= 2 for ln in result["lines"])


def test_city_wide_zoom_shows_clusters(client: TestClient) -> None:
    me, center = dev_login(client), area()
    for i in range(3):
        run_at(client, me, offset(*center, i * 50, 0), distance=1000)
    far = offset(*center, 15_000, 15_000)
    run_at(client, me, far, distance=1000)
    result = search(client, bbox=bbox(center), zoom=11)
    assert result["mode"] == "clusters" and result["lines"] == []
    counts = sorted(c["count"] for c in result["clusters"])
    assert counts == [1, 3]
    assert result["total"] == 4


def test_attempts_hidden(client: TestClient, db: Session) -> None:
    me, center = dev_login(client), area()
    root = run_at(client, me, center)
    attempts = [run_at(client, me, offset(*center, 5, 5 * i)) for i in range(1, 6)]
    db.execute(
        update(Track)
        .where(Track.id.in_([uuid.UUID(a["id"]) for a in attempts]))
        .values(parent_track_id=uuid.UUID(root["id"]))
    )
    db.commit()
    result = search(client, bbox=bbox(center), zoom=14)
    assert ids(result) == {root["id"]}
    assert {ln["id"] for ln in result["lines"]} == {root["id"]}
    assert result["items"][0]["attempts_count"] == 5


def test_not_public_tracks_hidden(client: TestClient) -> None:
    me, center = dev_login(client), area()
    public = run_at(client, me, center)
    run_at(client, me, offset(*center, 100, 0), visibility="private")
    run_at(client, me, offset(*center, 200, 0), visibility="link")
    run_at(client, me, offset(*center, 300, 0), visibility=None)  # черновик
    result = search(client, bbox=bbox(center), zoom=14)
    assert ids(result) == {public["id"]}


def test_lines_hide_home_zone(client: TestClient) -> None:
    me, center = dev_login(client), area()
    home = offset(*center, 0, 150)
    set_home(client, me, home, 300)
    run_at(client, me, center)
    line = search(client, bbox=bbox(center), zoom=15)["lines"][0]["coordinates"]
    assert min(haversine(home, (lat, lon)) for lon, lat in line) >= 299
    start = search(client, bbox=bbox(center), zoom=15)["items"][0]["start"]
    assert haversine(home, (start[1], start[0])) >= 299


def test_bbox_or_text_required(client: TestClient) -> None:
    assert client.get("/tracks/search").status_code == 422


# --- Distance Filter / Other Filters --------------------------------------------------------


def test_category_5_km(client: TestClient) -> None:
    me, center = dev_login(client), area()
    by_dist = {d: run_at(client, me, offset(*center, i * 300, 0), distance=d)["id"]
               for i, d in enumerate((2900, 3100, 5200, 7400, 7600))}  # fmt: skip
    result = search(client, bbox=bbox(center), zoom=14, category="5")
    assert ids(result) == {by_dist[3100], by_dist[5200], by_dist[7400]}


def test_custom_range(client: TestClient) -> None:
    me, center = dev_login(client), area()
    by_dist = {d: run_at(client, me, offset(*center, i * 300, 0), distance=d)["id"]
               for i, d in enumerate((7000, 9000, 13000))}  # fmt: skip
    result = search(client, bbox=bbox(center), zoom=14, dist_min_km=8, dist_max_km=12)
    assert ids(result) == {by_dist[9000]}


def test_pace_range(client: TestClient) -> None:
    me, center = dev_login(client), area()
    by_pace = {p: run_at(client, me, offset(*center, i * 300, 0), pace_s_per_km=p)["id"]
               for i, p in enumerate((250, 300, 340))}  # 4:10, 5:00, 5:40  # fmt: skip
    result = search(client, bbox=bbox(center), zoom=14, pace_min_s=270, pace_max_s=330)
    assert ids(result) == {by_pace[300]}


def test_date_range(client: TestClient, db: Session) -> None:
    me, center = dev_login(client), area()
    oct_ = run_at(client, me, center)  # фабрика пишет 1 октября 2026
    nov = run_at(client, me, offset(*center, 500, 0))
    db.execute(
        update(Track)
        .where(Track.id == uuid.UUID(nov["id"]))
        .values(started_at=func.now() - func.make_interval(0, 0, 0, 0))
    )
    db.commit()
    result = search(
        client, bbox=bbox(center), zoom=14, date_from="2026-10-01", date_to="2026-10-31"
    )
    assert ids(result) == {oct_["id"]}


def test_has_attempts_filter(client: TestClient, db: Session) -> None:
    me, center = dev_login(client), area()
    root = run_at(client, me, center)
    lonely = run_at(client, me, offset(*center, 800, 0))
    attempt = run_at(client, me, offset(*center, 5, 5))
    db.execute(
        update(Track)
        .where(Track.id == uuid.UUID(attempt["id"]))
        .values(parent_track_id=uuid.UUID(root["id"]))
    )
    db.commit()
    assert ids(search(client, bbox=bbox(center), zoom=14, has_attempts=True)) == {root["id"]}
    assert ids(search(client, bbox=bbox(center), zoom=14, has_attempts=False)) == {lonely["id"]}


def test_new_tracks(client: TestClient, db: Session) -> None:
    me, center = dev_login(client), area()
    fresh = run_at(client, me, center)
    old = run_at(client, me, offset(*center, 800, 0))
    db.execute(
        update(Track)
        .where(Track.id == uuid.UUID(old["id"]))
        .values(published_at=func.now() - func.make_interval(0, 0, 0, 8))  # 8 дней назад
    )
    db.commit()
    result = search(client, bbox=bbox(center), zoom=14, is_new=True)
    assert ids(result) == {fresh["id"]}
    assert result["items"][0]["is_new"] is True
    everything = {i["id"]: i["is_new"] for i in search(client, bbox=bbox(center), zoom=14)["items"]}
    assert everything == {fresh["id"]: True, old["id"]: False}


# --- Sorting ----------------------------------------------------------------------------


def test_sort_by_pace(client: TestClient) -> None:
    me, center = dev_login(client), area()
    for i, pace in enumerate((330, 250, 290)):
        run_at(client, me, offset(*center, i * 300, 0), pace_s_per_km=pace)
    items = search(client, bbox=bbox(center), zoom=14, sort="pace")["items"]
    paces = [i["avg_pace_s_per_km"] for i in items]
    assert paces == sorted(paces) and len(paces) == 3


def test_sort_by_distance_and_popularity(client: TestClient, db: Session) -> None:
    me, center = dev_login(client), area()
    short = run_at(client, me, center, distance=2000)
    long = run_at(client, me, offset(*center, 300, 0), distance=6000)
    assert [i["id"] for i in search(client, bbox=bbox(center), zoom=14, sort="distance")[
        "items"]] == [short["id"], long["id"]]  # fmt: skip
    client.get(f"/tracks/{long['id']}/gpx")  # скачивание поднимает популярность
    recalc(db)  # популярность — из почасового пересчёта (add-ratings)
    popular = search(client, bbox=bbox(center), zoom=14, sort="popular")["items"]
    assert popular[0]["id"] == long["id"]


# --- Text Search ----------------------------------------------------------------------------


def test_search_by_author(client: TestClient) -> None:
    name = f"Аркадий {uuid.uuid4().hex[:6]}"
    me = dev_login(client, name=name)
    a = run_at(client, me, area())
    b = run_at(client, me, area())  # в другой части света
    run_at(client, me, area(), visibility="private")
    result = search(client, q=name.split()[1])
    assert ids(result) == {a["id"], b["id"]}


def test_search_by_title_and_city(client: TestClient) -> None:
    tag = uuid.uuid4().hex[:8]
    me = dev_login(client)
    client.patch("/me", headers=me, json={"city": f"Город{tag}"})
    track = run_at(client, me, area(), title=f"Набережная {tag}")
    assert ids(search(client, q=f"набережная {tag}")) == {track["id"]}
    assert ids(search(client, q=f"город{tag}")) == {track["id"]}
    assert search(client, q="100%_нет")["items"] == []


# --- Live Results ---------------------------------------------------------------------------


def test_pan_map(client: TestClient) -> None:
    me, center = dev_login(client), area()
    here = run_at(client, me, center)
    there_center = offset(*center, 60_000, 0)
    there = run_at(client, me, there_center)
    assert ids(search(client, bbox=bbox(center), zoom=14)) == {here["id"]}
    assert ids(search(client, bbox=bbox(there_center), zoom=14)) == {there["id"]}


def test_pagination(client: TestClient) -> None:
    me, center = dev_login(client), area()
    for i in range(5):
        run_at(client, me, offset(*center, i * 200, 0), distance=1000)
    first = search(client, bbox=bbox(center), zoom=14, limit=2, sort="date")
    rest = search(client, bbox=bbox(center), zoom=14, limit=10, offset=2, sort="date")
    assert first["total"] == 5 and len(first["items"]) == 2 and len(rest["items"]) == 3
    assert not ids(first) & ids(rest)


# --- Track Card ------------------------------------------------------------------------------


def test_download_gpx(client: TestClient, db: Session) -> None:
    me, other, center = dev_login(client), dev_login(client), area()
    home = offset(*center, 0, 150)
    set_home(client, me, home, 300)
    track = run_at(client, me, center, title="Набережная до маяка")

    resp = client.get(f"/tracks/{track['id']}/gpx", headers=other)
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/gpx+xml")
    assert "attachment" in resp.headers["content-disposition"]
    root = ET.fromstring(resp.content)
    ns = {"g": "http://www.topografix.com/GPX/1/1"}
    pts = root.findall(".//g:trkpt", ns)
    assert len(pts) > 10
    assert root.findall(".//g:time", ns) == []
    for p in pts:
        assert haversine(home, (float(p.get("lat")), float(p.get("lon")))) >= 299  # type: ignore[arg-type]
    assert root.find(".//g:name", ns).text == "Набережная до маяка"  # type: ignore[union-attr]

    client.get(f"/tracks/{track['id']}/gpx")  # гость
    count = db.execute(
        select(func.count()).where(TrackDownload.track_id == uuid.UUID(track["id"]))
    ).scalar_one()
    assert count == 2


def test_private_track_gpx_hidden(client: TestClient) -> None:
    me, other = dev_login(client), dev_login(client)
    track = run_at(client, me, area(), visibility="private")
    assert client.get(f"/tracks/{track['id']}/gpx", headers=other).status_code == 404
    assert client.get(f"/tracks/{track['id']}/gpx", headers=me).status_code == 200


def test_kilometre_marks(client: TestClient) -> None:
    me = dev_login(client)
    start = area()
    track = run_at(client, me, start, distance=5200)
    detail = client.get(f"/tracks/{track['id']}").json()
    marks = detail["km_marks"]
    assert [m["km"] for m in marks] == [1, 2, 3, 4, 5]
    for m in marks:
        _, _, dist = GEOD.inv(start[1], start[0], m["lon"], m["lat"])  # точно, по эллипсоиду
        assert dist == pytest.approx(m["km"] * 1000, abs=5)


def test_kilometre_marks_skip_hidden_part(client: TestClient) -> None:
    me = dev_login(client)
    start = area()
    set_home(client, me, start, 400)
    track = run_at(client, me, start, distance=3500)
    marks = client.get(f"/tracks/{track['id']}").json()["km_marks"]
    assert [m["km"] for m in marks] == [1, 2, 3]  # 1-й км за границей зоны (400 м)
