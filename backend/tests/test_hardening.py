"""Защита от некорректного ввода, гонок и сбоев (замечания ревью кода)."""

import uuid
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient
from sqlalchemy import update
from sqlalchemy.orm import Session

from app.api.auth import REFRESH_COOKIE
from app.config import Config
from app.domain.tracks.privacy import JITTER_SHARE, visible_range
from app.infra.models import Track, TrackStatus
from app.infra.track_processing import GIVE_UP_AFTER, STUCK_AFTER, requeue_stuck
from tests.helpers import dev_login, unique_run, upload


def test_invalid_refresh_clears_cookie(client: TestClient) -> None:
    client.cookies.set(REFRESH_COOKIE, "garbage")
    resp = client.post("/auth/refresh")
    assert resp.status_code == 401
    assert f"{REFRESH_COOKIE}=" in resp.headers["set-cookie"]
    assert "Max-Age=0" in resp.headers["set-cookie"]


def test_garbage_content_length_rejected(client: TestClient) -> None:
    resp = client.post("/tracks", headers={"content-length": "abc"}, content=b"")
    assert resp.status_code == 413


def test_world_bbox_clamped(client: TestClient) -> None:
    resp = client.get("/tracks/search", params={"bbox": "-540,-95,540,95", "zoom": 0})
    assert resp.status_code == 200


def test_bad_bbox_rejected(client: TestClient) -> None:
    assert client.get("/tracks/search", params={"bbox": "10,50,5,40"}).status_code == 422
    assert client.get("/tracks/search", params={"bbox": "1.2.3,4,5,6"}).status_code == 422


def test_same_file_after_delete(client: TestClient, db: Session) -> None:
    me = dev_login(client)
    data = unique_run()
    first = upload(client, me, data).json()
    # мягко удалённый исходный трек остаётся в базе ради группы — но не мешает загрузке
    db.execute(update(Track).where(Track.id == first["id"]).values(deleted_at=datetime.now(UTC)))
    db.commit()
    again = upload(client, me, data)
    assert again.status_code == 202, again.text


def test_zone_jitter_is_stable_and_outside() -> None:
    xy = [(float(x), 0.0) for x in range(0, 2001, 10)]
    cum = [x for x, _ in xy]
    home, radius = (0.0, 0.0), 200.0
    plain = visible_range(xy, cum, home, radius)
    a = visible_range(xy, cum, home, radius, seed="track-a")
    assert plain is not None and a is not None
    assert a == visible_range(xy, cum, home, radius, seed="track-a")  # пересчёт не дрожит
    assert plain.from_m <= a.from_m <= plain.from_m + radius * JITTER_SHARE
    starts = {visible_range(xy, cum, home, radius, seed=str(i)).from_m for i in range(10)}  # type: ignore[union-attr]
    assert len(starts) > 1  # края разных треков не лежат на одной окружности


class _Queue:
    def __init__(self) -> None:
        self.queued: list[uuid.UUID] = []

    def process_track(self, track_id: uuid.UUID) -> None:
        self.queued.append(track_id)

    def recompute_visibility(self, user_id: uuid.UUID) -> None:
        pass


def test_stuck_tracks_requeued_then_given_up(
    client: TestClient, db: Session, migrated: Config
) -> None:
    me = dev_login(client)
    ids = [upload(client, me, unique_run()).json()["id"] for _ in range(2)]
    now = datetime.now(UTC)
    for track_id, age in zip(ids, (STUCK_AFTER, GIVE_UP_AFTER), strict=True):
        db.execute(
            update(Track)
            .where(Track.id == track_id)
            .values(
                status=TrackStatus.processing.value, created_at=now - age - timedelta(minutes=1)
            )
        )
    db.commit()
    queue = _Queue()
    requeue_stuck(migrated, queue, now)
    assert [str(x) for x in queue.queued] == [ids[0]]
    db.expire_all()
    assert db.get(Track, uuid.UUID(ids[1])).status == TrackStatus.rejected.value  # type: ignore[union-attr]
