"""Spec achievements: «Превзошёл», экран результата, счётчик новых попыток, витрина, отзыв."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.infra.matching_service import hide_by_moderator, sync_group
from app.infra.models import Track, UserAchievement
from tests.conftest import dev_login
from tests.test_matching_api import ROOT, SAME, fixture_points, gpx, place, published
from tests.test_tracks_api import uploaded


def achievements_of(db: Session, track_id: str) -> int:
    db.expire_all()
    return int(
        db.execute(
            select(func.count()).where(UserAchievement.track_id == uuid.UUID(track_id))
        ).scalar_one()
    )


# --- Outperformed Achievement ----------------------------------------------------------------


def test_beat_the_author(client: TestClient, db: Session) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    published(client, author, gpx(fixture_points(ROOT), where))
    attempt = published(client, runner, gpx(fixture_points(ROOT), where, scale=0.99, jitter_m=2))
    assert attempt["match"]["beat"] is True
    assert [a["code"] for a in attempt["achievements"]] == ["outperformed"]
    assert achievements_of(db, attempt["id"]) == 1


def test_own_route_no_achievement(client: TestClient, db: Session) -> None:
    author, where = dev_login(client), place()
    published(client, author, gpx(fixture_points(ROOT), where))
    again = published(client, author, gpx(fixture_points(ROOT), where, scale=0.9, jitter_m=2))
    assert again["match"]["diff_s"] < 0 and again["achievements"] == []


def test_equal_is_not_outperformed(client: TestClient, db: Session) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    # Тот же файл от другого бегуна: разница 0 с. Порог 0,6 с проверен в доменном тесте —
    # время в GPX фабрики целое, долю секунды через API не передать.
    pts = fixture_points(ROOT)
    published(client, author, gpx(pts, where))
    attempt = published(client, runner, gpx(pts, where))
    assert attempt["match"]["equal"] is True and attempt["achievements"] == []


def test_repeated_processing_no_duplicate(client: TestClient, db: Session) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    published(client, author, gpx(fixture_points(ROOT), where))
    attempt = published(client, runner, gpx(fixture_points(SAME), where))
    track = db.get(Track, uuid.UUID(attempt["id"]))
    assert track is not None
    for _ in range(3):
        sync_group(db, track)
        db.commit()
    assert achievements_of(db, attempt["id"]) == 1


# --- Attempt Result Screen -------------------------------------------------------------------


def test_faster_result(client: TestClient) -> None:
    author, runner, where = dev_login(client, name="Алексей П."), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    attempt = published(client, runner, gpx(fixture_points(ROOT), where, scale=0.99, jitter_m=2))
    r = client.get(f"/tracks/{attempt['id']}/result", headers=runner).json()
    assert r["outcome"] == "beat" and r["diff_s"] < -1
    assert r["route"]["id"] == root["id"] and r["route"]["author"]["name"] == "Алексей П."
    assert r["place"] == 1 and r["runners"] == 2 and r["gap_to_best_s"] == 0
    assert r["root_time_s"] == root["total_time_s"]
    assert [a["code"] for a in r["achievements"]] == ["outperformed"]
    assert any(row["is_viewer"] for row in r["rows"])


def test_slower_result(client: TestClient) -> None:
    author, fast, runner, where = dev_login(client), dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    published(client, fast, gpx(fixture_points(ROOT), where, scale=0.95, jitter_m=2))
    total = root["total_time_s"]
    slow = published(
        client, runner, gpx(fixture_points(ROOT), where, scale=(total + 34) / total, jitter_m=1)
    )
    r = client.get(f"/tracks/{slow['id']}/result", headers=runner).json()
    assert r["outcome"] == "slower" and 33 <= r["diff_s"] <= 35
    assert r["place"] == 3 and r["runners"] == 3
    assert r["gap_to_best_s"] > 34 and r["achievements"] == []


def test_no_match_no_result(client: TestClient) -> None:
    runner = dev_login(client)
    lonely = published(client, runner, gpx(fixture_points(ROOT), place()))
    assert lonely["attempt_of"] is None
    assert client.get(f"/tracks/{lonely['id']}/result", headers=runner).status_code == 404


def test_result_only_for_owner(client: TestClient) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    published(client, author, gpx(fixture_points(ROOT), where))
    attempt = published(client, runner, gpx(fixture_points(SAME), where))
    assert client.get(f"/tracks/{attempt['id']}/result", headers=author).status_code == 404


# --- New Attempts Counter --------------------------------------------------------------------


def test_counter_grows_and_resets(client: TestClient) -> None:
    author, a, b, where = dev_login(client), dev_login(client), dev_login(client), place()
    root = published(client, author, gpx(fixture_points(ROOT), where))
    assert client.get("/me", headers=author).json()["new_attempts"] == 0
    published(client, a, gpx(fixture_points(SAME), where))
    published(client, b, gpx(fixture_points(ROOT), where, scale=1.02, jitter_m=2))
    published(client, author, gpx(fixture_points(ROOT), where, scale=0.97, jitter_m=2))  # своя
    assert client.get("/me", headers=author).json()["new_attempts"] == 2
    mine = {t["id"]: t["new_attempts"] for t in client.get("/me/tracks", headers=author).json()}
    assert mine[root["id"]] == 2

    client.get(f"/tracks/{root['id']}/group", headers=author)  # чтение ничего не меняет
    assert client.get("/me", headers=author).json()["new_attempts"] == 2
    assert client.post(f"/tracks/{root['id']}/group/seen").status_code == 401
    group = client.get(f"/tracks/{root['id']}/group", headers=author).json()
    assert group["viewer_is_author"] is True
    assert client.post(f"/tracks/{root['id']}/group/seen", headers=author).status_code == 204
    assert client.get("/me", headers=author).json()["new_attempts"] == 0


# --- Achievement Showcase --------------------------------------------------------------------


def test_showcase_in_profile(client: TestClient) -> None:
    a1, a2, runner = dev_login(client), dev_login(client), dev_login(client)
    w1, w2 = place(), place()
    published(client, a1, gpx(fixture_points(ROOT), w1))
    published(client, a2, gpx(fixture_points(ROOT), w2))
    t1 = published(client, runner, gpx(fixture_points(ROOT), w1, scale=0.98, jitter_m=2))
    t2 = published(client, runner, gpx(fixture_points(ROOT), w2, scale=0.97, jitter_m=2))
    runner_id = client.get("/me", headers=runner).json()["id"]
    show = client.get(f"/users/{runner_id}/achievements").json()
    assert [(e["code"], e["count"]) for e in show] == [("outperformed", 2)]
    assert {i["track_id"] for i in show[0]["items"]} == {t1["id"], t2["id"]}


# --- Achievement Revocation ------------------------------------------------------------------


def test_fraud_hidden(client: TestClient, db: Session) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    published(client, author, gpx(fixture_points(ROOT), where))
    attempt = published(client, runner, gpx(fixture_points(ROOT), where, scale=0.9, jitter_m=2))
    assert achievements_of(db, attempt["id"]) == 1
    hide_by_moderator(db, db.get(Track, uuid.UUID(attempt["id"])))  # type: ignore[arg-type]
    assert achievements_of(db, attempt["id"]) == 0
    runner_id = client.get("/me", headers=runner).json()["id"]
    assert client.get(f"/users/{runner_id}/achievements", headers=runner).json() == []


def test_attempt_detached_revokes(client: TestClient, db: Session) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    published(client, author, gpx(fixture_points(ROOT), where))
    attempt = published(client, runner, gpx(fixture_points(ROOT), where, scale=0.9, jitter_m=2))
    client.patch(f"/tracks/{attempt['id']}", headers=runner, json={"detach": True})
    assert achievements_of(db, attempt["id"]) == 0


def test_draft_preview_has_no_achievement(client: TestClient, db: Session) -> None:
    author, runner, where = dev_login(client), dev_login(client), place()
    published(client, author, gpx(fixture_points(ROOT), where))
    draft = uploaded(client, runner, gpx(fixture_points(ROOT), where, scale=0.9, jitter_m=2))
    assert draft["match"]["beat"] is True and achievements_of(db, draft["id"]) == 0
