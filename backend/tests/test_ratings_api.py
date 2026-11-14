"""Spec ratings: популярность, рейтинги по категориям, почасовой пересчёт, сортировка карты."""

from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import Config
from app.domain.ratings import Weights, popularity
from app.infra import tasks
from app.infra.ratings_service import recalc
from app.infra.settings_repo import get_setting, set_setting
from tests.helpers import ROOT, SAME, dev_login, fixture_points, gpx, place, published


def entry(client: TestClient, category: str, track_id: str) -> dict[str, Any] | None:
    items = client.get("/ratings", params={"category": category, "limit": 100}).json()
    return next((i for i in items if i["track_id"] == track_id), None)


def group_of_four(client: TestClient, downloads: int) -> dict[str, Any]:
    """Маршрут категории 5 км: автор + 3 бегуна, downloads скачиваний GPX."""
    where = place()
    root = published(client, dev_login(client), gpx(fixture_points(ROOT), where))
    for scale in (0.97, 1.0, 1.03):
        published(
            client, dev_login(client), gpx(fixture_points(ROOT), where, scale=scale, jitter_m=2)
        )
    for _ in range(downloads):
        client.get(f"/tracks/{root['id']}/gpx")
    return root


# --- Popularity Score ------------------------------------------------------------------------


def test_score_formula() -> None:
    assert popularity(4, 3, 0, Weights()) == 26
    assert popularity(4, 3, 2, Weights(runners=5, downloads=3, likes=1)) == 31


def test_score_calculation(client: TestClient, db: Session) -> None:
    root = group_of_four(client, downloads=3)
    recalc(db)
    db.commit()
    e = entry(client, "5", root["id"])
    assert e is not None
    assert (e["runners"], e["downloads"], e["value"]) == (4, 3, 26)


def test_weights_from_settings(client: TestClient, db: Session) -> None:
    root = group_of_four(client, downloads=3)
    original = get_setting(db, "popularity.weights")
    set_setting(db, "popularity.weights", {"runners": 5, "downloads": 3, "likes": 1})
    db.commit()
    try:
        recalc(db)
        db.commit()
        assert entry(client, "5", root["id"])["value"] == 29  # type: ignore[index]
    finally:
        set_setting(db, "popularity.weights", original)
        db.commit()
        recalc(db)
        db.commit()


# --- Category Ratings ------------------------------------------------------------------------


def test_category_tab(client: TestClient, db: Session) -> None:
    five = group_of_four(client, downloads=0)  # 5 км (по фикстуре ~4,4 км)
    ten = published(client, dev_login(client), gpx(fixture_points("20260617"), place()))
    recalc(db)
    db.commit()
    tab = client.get("/ratings", params={"category": "10", "limit": 100}).json()
    assert ten["id"] in {i["track_id"] for i in tab}
    assert five["id"] not in {i["track_id"] for i in tab}
    values = [i["value"] for i in tab]
    assert values == sorted(values, reverse=True)
    assert [i["place"] for i in tab] == list(range(1, len(tab) + 1))


def test_attempts_and_private_excluded(client: TestClient, db: Session) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    attempt = published(client, runner, gpx(fixture_points(SAME), where))
    private = published(client, dev_login(client), gpx(fixture_points(ROOT), place()), "private")
    gone_author = dev_login(client)
    gone_root = published(client, gone_author, gpx(fixture_points(ROOT), (where[0] + 1, where[1])))
    published(client, dev_login(client), gpx(fixture_points(SAME), (where[0] + 1, where[1])))
    client.delete(f"/tracks/{gone_root['id']}", headers=gone_author)  # мягкое удаление
    recalc(db)
    db.commit()
    assert entry(client, "5", root["id"]) is not None
    for excluded in (attempt, private, gone_root):
        assert entry(client, "5", excluded["id"]) is None


# --- Hourly Recalculation --------------------------------------------------------------------


def test_new_attempt_after_recalc(client: TestClient, db: Session) -> None:
    where = place()
    root = published(client, dev_login(client), gpx(fixture_points("20260617"), where))
    recalc(db)
    db.commit()
    before = entry(client, "10", root["id"])["value"]  # type: ignore[index]
    published(
        client, dev_login(client), gpx(fixture_points("20260617"), where, scale=0.98, jitter_m=2)
    )
    assert entry(client, "10", root["id"])["value"] == before  # до пересчёта — прежнее
    recalc(db)
    db.commit()
    assert entry(client, "10", root["id"])["value"] == before + 5


def test_schedule_from_settings(migrated: Config, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(tasks, "get_config", lambda: migrated)
    added: list[tuple[float, str, str]] = []

    class Sender:
        def add_periodic_task(self, interval: float, sig: Any, name: str) -> None:
            added.append((interval, sig.task, name))

    tasks.setup_periodic_tasks(Sender())
    assert added == [
        (3600.0, "recalc_popularity", "recalc-popularity"),
        (300, "requeue_stuck_tracks", "requeue-stuck-tracks"),
    ]


# --- Popular Sort on Map ---------------------------------------------------------------------


def test_sort_by_stored_popularity(client: TestClient, db: Session) -> None:
    where = place()
    quiet = published(client, dev_login(client), gpx(fixture_points("20260617"), where))
    busy = published(client, dev_login(client), gpx(fixture_points(ROOT), where))
    for scale in (0.97, 1.03):
        published(
            client, dev_login(client), gpx(fixture_points(ROOT), where, scale=scale, jitter_m=2)
        )
    recalc(db)
    db.commit()
    lons = [c[0] for t in (quiet, busy) for c in t["geometry"]["coordinates"]]
    lats = [c[1] for t in (quiet, busy) for c in t["geometry"]["coordinates"]]
    bbox = f"{min(lons) - 0.01},{min(lats) - 0.01},{max(lons) + 0.01},{max(lats) + 0.01}"
    items = client.get(
        "/tracks/search", params={"bbox": bbox, "zoom": 14, "sort": "popular"}
    ).json()["items"]
    order = [i["id"] for i in items if i["id"] in (quiet["id"], busy["id"])]
    assert order == [busy["id"], quiet["id"]]  # 15 против 5
