"""Spec route-matching через API: группы, плашка, видимость, удаление, проверка."""

import random
import uuid
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.infra.matching_service import hide_by_moderator
from app.infra.models import Attempt, Track
from app.scripts.rematch_all import rematch_all
from tests.conftest import dev_login
from tests.gpx_factory import T0, P, offset, straight, to_gpx
from tests.test_matching_domain import fx, path_before
from tests.test_tracks_api import Headers, publish, uploaded

Points = list[tuple[float, float, float]]  # lon, lat, секунды от старта


def place() -> tuple[float, float]:
    """Сдвиг (Δlat, Δlon) в своё место для каждого теста."""
    return random.uniform(-20, 20), random.uniform(-60, 60)


def fixture_points(date: str) -> Points:
    return [(x, y, m) for x, y, _, m in fx(date).full]


def gpx(points: Points, where: tuple[float, float], scale: float = 1.0, days_ago: float = 0,
        jitter_m: float = 0.0) -> bytes:  # fmt: skip
    """GPX из точек, перенесённых в своё место, с темпом ×scale и датой days_ago дней назад."""
    dlat, dlon = where
    start = T0 - timedelta(days=days_ago)
    out = []
    for i, (lon, lat, t) in enumerate(points):
        lat2, lon2 = lat + dlat, lon + dlon
        if jitter_m:
            lat2, lon2 = offset(lat2, lon2, jitter_m * ((i % 3) - 1), 0)
        out.append(P(lat2, lon2, start + timedelta(seconds=t * scale)))
    return to_gpx(out)


def published(client: TestClient, h: Headers, data: bytes, visibility: str = "public") -> dict:
    track = uploaded(client, h, data)
    assert track["status"] == "draft", track
    publish(client, h, track["id"], visibility)
    return client.get(f"/tracks/{track['id']}", headers=h).json()  # type: ignore[no-any-return]


def group(client: TestClient, track_id: str) -> dict:
    resp = client.get(f"/tracks/{track_id}/group")
    assert resp.status_code == 200, resp.text
    return resp.json()  # type: ignore[no-any-return]


ROOT, SAME = "20261026", "20261101"  # одна «пятёрка», 01.11 быстрее на ~1,5 мин


# --- Automatic Matching --------------------------------------------------------------------


def test_same_route_faster(client: TestClient) -> None:
    author, runner, where = (
        dev_login(client, name="Автор"),
        dev_login(client, name="Бегун"),
        place(),
    )
    root = published(client, author, gpx(fixture_points(ROOT), where))
    attempt = published(client, runner, gpx(fixture_points(ROOT), where, scale=0.95, jitter_m=2))

    assert attempt["attempt_of"]["id"] == root["id"]
    assert attempt["match"]["state"] == "active" and attempt["match"]["beat"] is True
    assert attempt["match"]["diff_s"] < -60
    g = group(client, root["id"])
    assert g["runners"] == 2
    assert [r["runner"]["name"] for r in g["rows"]] == ["Бегун", "Автор"]
    assert g["rows"][0]["beat"] is True and g["rows"][1]["is_author"] is True
    # на карте — только исходный трек, с числом бегунов
    lat, lon = attempt["geometry"]["coordinates"][0][1], attempt["geometry"]["coordinates"][0][0]
    found = client.get(
        "/tracks/search",
        params={"bbox": f"{lon - .05},{lat - .05},{lon + .05},{lat + .05}", "zoom": 14},
    ).json()
    assert [i["id"] for i in found["items"]] == [root["id"]]
    assert found["items"][0]["runners_count"] == 2


def test_preview_shows_match(client: TestClient) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    draft = uploaded(client, runner, gpx(fixture_points(SAME), where))
    assert draft["status"] == "draft"
    m = draft["match"]
    assert m["state"] == "pending" and m["root"]["id"] == root["id"]
    assert m["result_time_s"] > 0 and m["diff_s"] < 0
    assert draft["attempt_of"] is None  # в группе — только после публикации
    assert group(client, root["id"])["runners"] == 1


def test_link_visibility_not_grouped(client: TestClient) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    link = published(client, runner, gpx(fixture_points(SAME), where), visibility="link")
    assert link["attempt_of"] is None
    assert group(client, root["id"])["runners"] == 1


def test_real_series_grouped(client: TestClient) -> None:
    a, b, c, where = dev_login(client), dev_login(client), dev_login(client), place()
    root = published(client, a, gpx(fixture_points("20250522"), where))
    second = published(client, b, gpx(fixture_points("20250529"), where))
    other = published(client, c, gpx(fixture_points("20260617"), where))  # другой маршрут
    assert second["attempt_of"]["id"] == root["id"]
    assert other["attempt_of"] is None


# --- Candidate Selection -------------------------------------------------------------------


def test_warm_up_crossing_category(client: TestClient) -> None:
    author, runner = dev_login(client), dev_login(client)
    start = (random.uniform(-50, 50), random.uniform(-170, 170))
    pts = [(p.lon, p.lat, (p.t - T0).total_seconds()) for p in straight(7400, start=start)]  # type: ignore[operator]
    root = published(client, author, gpx(pts, (0, 0)))
    warm = path_before((pts[0][0], pts[0][1]), 650)
    attempt_pts = warm[:-1] + [(x, y, t + warm[-1][2] + 1) for x, y, t in pts]
    attempt = published(client, runner, gpx(attempt_pts, (0, 0)))
    assert (root["category"], attempt["category"]) == ("5", "10")
    assert attempt["attempt_of"]["id"] == root["id"]
    assert attempt["match"]["trimmed"] is True


# --- Root Track -----------------------------------------------------------------------------


def test_older_run_uploaded_later(client: TestClient) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    old = published(client, runner, gpx(fixture_points(SAME), where, days_ago=730))
    assert old["started_at"] < root["started_at"]
    assert old["attempt_of"]["id"] == root["id"]


def test_root_hidden_by_moderator(client: TestClient, db: Session) -> None:
    a, b, c, where = dev_login(client), dev_login(client), dev_login(client), place()
    root = published(client, a, gpx(fixture_points(ROOT), where))
    first = published(client, b, gpx(fixture_points(SAME), where))
    second = published(client, c, gpx(fixture_points(ROOT), where, scale=1.02, jitter_m=2))
    hide_by_moderator(db, db.get(Track, uuid.UUID(root["id"])))  # type: ignore[arg-type]

    g = group(client, second["id"])
    assert g["root"]["id"] == first["id"]
    assert {r["track_id"] for r in g["rows"]} == {first["id"], second["id"]}
    assert client.get(f"/tracks/{root['id']}", headers=b).status_code == 404


# --- Root Removal and Visibility --------------------------------------------------------------


def test_author_deletes_root_with_attempts(client: TestClient) -> None:
    author, runner, late, where = dev_login(client), dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    attempt = published(client, runner, gpx(fixture_points(SAME), where))
    assert client.delete(f"/tracks/{root['id']}", headers=author).status_code == 204

    assert client.get(f"/tracks/{root['id']}").status_code == 404
    g = group(client, attempt["id"])  # группа и строка автора остались
    assert g["root"]["id"] == root["id"] and g["runners"] == 2
    lat, lon = attempt["geometry"]["coordinates"][0][1], attempt["geometry"]["coordinates"][0][0]
    found = client.get(
        "/tracks/search",
        params={"bbox": f"{lon - .05},{lat - .05},{lon + .05},{lat + .05}", "zoom": 14},
    ).json()
    assert root["id"] not in {i["id"] for i in found["items"]}
    # новые треки с удалённым маршрутом не сопоставляются
    newcomer = published(client, late, gpx(fixture_points(ROOT), where, scale=0.99, jitter_m=2))
    assert newcomer["attempt_of"] is None or newcomer["attempt_of"]["id"] != root["id"]


def test_root_without_attempts_deleted_fully(client: TestClient, db: Session) -> None:
    author = dev_login(client)
    root = published(client, author, gpx(fixture_points(ROOT), place()))
    assert client.delete(f"/tracks/{root['id']}", headers=author).status_code == 204
    db.expire_all()
    assert db.get(Track, uuid.UUID(root["id"])) is None


def test_author_deletes_account(client: TestClient, db: Session) -> None:
    author, b, c, where = dev_login(client), dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    first = published(client, b, gpx(fixture_points(SAME), where))
    second = published(client, c, gpx(fixture_points(ROOT), where, scale=0.98, jitter_m=2))
    assert client.delete("/me", headers=author).status_code == 204

    db.expire_all()
    assert db.get(Track, uuid.UUID(root["id"])) is None
    g = group(client, second["id"])
    assert g["root"]["id"] == first["id"]
    assert [r["track_id"] for r in g["rows"] if r["is_root"]] == [first["id"]]
    assert g["runners"] == 2


def test_attempt_made_private_leaves_group(client: TestClient) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    attempt = published(client, runner, gpx(fixture_points(SAME), where))
    assert group(client, root["id"])["runners"] == 2
    client.patch(f"/tracks/{attempt['id']}", headers=runner, json={"visibility": "private"})
    assert group(client, root["id"])["runners"] == 1
    # снова публичная — снова в группе
    client.patch(f"/tracks/{attempt['id']}", headers=runner, json={"visibility": "public"})
    assert group(client, root["id"])["runners"] == 2


def test_root_made_private_closes_group(client: TestClient) -> None:
    author, runner, late, where = dev_login(client), dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    attempt = published(client, runner, gpx(fixture_points(SAME), where))
    client.patch(f"/tracks/{root['id']}", headers=author, json={"visibility": "private"})
    assert group(client, attempt["id"])["runners"] == 2  # группа осталась
    newcomer = published(client, late, gpx(fixture_points(ROOT), where, scale=1.01, jitter_m=2))
    assert newcomer["attempt_of"] is None or newcomer["attempt_of"]["id"] != root["id"]


# --- Result Comparison -----------------------------------------------------------------------


def test_equal_result(client: TestClient) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    pts = fixture_points(ROOT)
    published(client, author, gpx(pts, where))
    # тот же путь и время от другого бегуна — разница 0 с (время в GPX целое; порог 0,6 с
    # проверен в доменном тесте сравнения)
    attempt = published(client, runner, gpx(pts, where))
    m = attempt["match"]
    assert m["state"] == "active" and m["equal"] is True and m["beat"] is False
    assert abs(m["diff_s"]) < 1


def test_author_repeats_own_route(client: TestClient) -> None:
    author, where = dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    again = published(client, author, gpx(fixture_points(ROOT), where, scale=0.9, jitter_m=2))
    m = again["match"]
    assert again["attempt_of"]["id"] == root["id"]
    assert m["by_author"] is True and m["beat"] is False and m["diff_s"] < 0
    g = group(client, root["id"])
    assert g["runners"] == 1 and g["rows"][0]["runs"] == 2  # лучшая из двух — автора


# --- Group Table -----------------------------------------------------------------------------


def test_two_attempts_by_one_runner(client: TestClient) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    slow = published(client, runner, gpx(fixture_points(ROOT), where, scale=1.05, jitter_m=2))
    fast = published(client, runner, gpx(fixture_points(ROOT), where, scale=0.9, jitter_m=1))
    g = group(client, root["id"])
    mine = [r for r in g["rows"] if r["track_id"] in (slow["id"], fast["id"])]
    assert len(mine) == 1 and mine[0]["track_id"] == fast["id"] and mine[0]["runs"] == 2
    assert mine[0]["place"] == 1
    row = mine[0]
    assert row["pace_s_per_km"] == pytest.approx(row["time_s"] / (g["root_distance_m"] / 1000))


# --- Detach Attempt --------------------------------------------------------------------------


def test_detach_at_preview(client: TestClient) -> None:
    author, runner, late, where = dev_login(client), dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    draft = uploaded(client, runner, gpx(fixture_points(SAME), where))
    assert draft["match"]["state"] == "pending"
    resp = client.patch(
        f"/tracks/{draft['id']}",
        headers=runner,
        json={"detach": True, "visibility": "public", "publish": True},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["attempt_of"] is None and body["match"]["state"] == "detached"
    assert group(client, root["id"])["runners"] == 1
    # отвязанный трек не становится исходным: следующий бегун попадёт в группу автора
    newcomer = published(client, late, gpx(fixture_points(ROOT), where, scale=0.97, jitter_m=2))
    assert newcomer["attempt_of"]["id"] == root["id"]


def test_detach_later(client: TestClient) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    attempt = published(client, runner, gpx(fixture_points(SAME), where))
    client.patch(f"/tracks/{attempt['id']}", headers=runner, json={"detach": True})
    assert group(client, root["id"])["runners"] == 1
    assert client.get(f"/tracks/{attempt['id']}", headers=runner).json()["attempt_of"] is None


# --- Match Check -----------------------------------------------------------------------------


def test_check_explains_failure(client: TestClient) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    pts = fixture_points(SAME)
    n = len(pts)
    mine = uploaded(client, runner, gpx(pts[: int(n * 0.4)] + pts[int(n * 0.59) :], where))
    resp = client.post(f"/tracks/{root['id']}/check", headers=runner, json={"track_id": mine["id"]})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["matched"] is False
    rules = {r["code"]: r for r in body["rules"]}
    assert rules["corridor"]["ok"] is False and 0.7 < rules["corridor"]["value"] < 0.9
    assert rules["corridor"]["required"] == 0.9
    assert rules["start"]["ok"] is True
    dev = body["deviation"]
    assert dev and 1 < dev["km"] < 5.5 and dev["lat"] and dev["lon"]
    assert body["corridor"]["type"] in ("Polygon", "MultiPolygon")
    assert body["route_line"]["type"] == "LineString" and body["track_line"]["type"] == "LineString"


def test_check_success_and_access(client: TestClient) -> None:
    author, runner, stranger, where = (
        dev_login(client),
        dev_login(client),
        dev_login(client),
        place(),
    )
    root = published(client, author, gpx(fixture_points(ROOT), where))
    mine = uploaded(client, runner, gpx(fixture_points(SAME), where))
    ok = client.post(f"/tracks/{root['id']}/check", headers=runner, json={"track_id": mine["id"]})
    assert ok.json()["matched"] is True and ok.json()["diff_s"] < 0
    foreign = client.post(
        f"/tracks/{root['id']}/check", headers=stranger, json={"track_id": mine["id"]}
    )
    assert foreign.status_code == 404
    guest = client.post(f"/tracks/{root['id']}/check", json={"track_id": mine["id"]})
    assert guest.status_code == 401


# --- Rematch Existing Tracks -----------------------------------------------------------------


def test_rematch_dump(client: TestClient, db: Session) -> None:
    a, b, c, where = dev_login(client), dev_login(client), dev_login(client), place()
    first = published(client, a, gpx(fixture_points(ROOT), where))
    second = published(client, b, gpx(fixture_points(SAME), where))
    third = published(client, c, gpx(fixture_points(ROOT), where, scale=1.03, jitter_m=2))
    ids = [uuid.UUID(t["id"]) for t in (first, second, third)]
    # как будто треки загружены до появления сопоставления
    db.execute(update(Track).where(Track.id.in_(ids)).values(parent_track_id=None))
    db.query(Attempt).filter(Attempt.track_id.in_(ids)).delete(synchronize_session=False)
    db.commit()
    assert group(client, first["id"])["runners"] == 1

    rematch_all(db)
    g = group(client, third["id"])
    assert g["root"]["id"] == first["id"] and g["runners"] == 3
    parents = dict(
        db.execute(select(Track.id, Track.parent_track_id).where(Track.id.in_(ids))).all()
    )
    assert parents[ids[0]] is None and parents[ids[1]] == ids[0] and parents[ids[2]] == ids[0]
