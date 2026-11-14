"""Spec track-upload через API: загрузка, обработка, приватность, видимость, фото, профиль."""

import io
import math
import uuid

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Config
from app.infra.models import Track
from app.infra.s3 import s3_client
from app.infra.settings_repo import get_setting, set_setting
from tests.gpx_factory import ORIGIN, circle, offset, straight, to_gpx
from tests.helpers import (
    FIXTURES,
    dev_login,
    haversine,
    jpeg_with_gps,
    publish,
    set_home,
    unique_run,
    upload,
    uploaded,
)


def s3_keys(cfg: Config, prefix: str) -> list[str]:
    listed = s3_client(cfg, timeout_s=30).list_objects_v2(Bucket=cfg.s3_bucket, Prefix=prefix)
    return [o["Key"] for o in listed.get("Contents", [])]


# --- Supported Files ----------------------------------------------------------------


def test_valid_gpx(client: TestClient) -> None:
    me = dev_login(client)
    data = (FIXTURES / "run_20250524.gpx").read_bytes()
    resp = upload(client, me, data)
    assert resp.status_code == 202
    assert resp.json()["status"] == "processing"

    track = client.get(f"/tracks/{resp.json()['id']}", headers=me).json()
    assert track["status"] == "draft"
    assert track["title"].startswith("Пробежка ")
    assert track["category"] == "10"
    assert track["distance_m"] == pytest.approx(9046, rel=0.01)
    assert len(track["splits"]) == 10
    assert track["geometry"]["type"] == "LineString"


def test_same_run_in_three_formats(client: TestClient) -> None:
    me = dev_login(client)
    tracks = [
        uploaded(client, me, (FIXTURES / f"run_20261026.{ext}").read_bytes(), f"r.{ext}")
        for ext in ("gpx", "tcx", "fit")
    ]
    for t in tracks:
        assert t["status"] == "draft"
        assert t["distance_m"] == pytest.approx(tracks[0]["distance_m"], rel=0.01)
        assert t["total_time_s"] == pytest.approx(tracks[0]["total_time_s"], rel=0.01)


def test_file_too_large(client: TestClient) -> None:
    me = dev_login(client)
    resp = upload(client, me, b"<gpx>" + b" " * (20 * 1024 * 1024))
    assert resp.status_code == 413
    assert resp.json()["detail"] == "файл больше 20 МБ"
    assert client.get("/me/tracks", headers=me).json() == []


def test_oversized_body_rejected_before_parsing(client: TestClient) -> None:
    me = dev_login(client)
    resp = upload(client, me, b"x" * (22 * 1024 * 1024))
    assert resp.status_code == 413


def test_unsupported_format(client: TestClient) -> None:
    me = dev_login(client)
    resp = upload(client, me, b"%PDF-1.7 definitely not a track", "run.gpx")
    assert resp.status_code == 415
    assert resp.json()["detail"] == "формат не поддерживается"


def test_upload_requires_sign_in(client: TestClient) -> None:
    assert upload(client, {}, unique_run()).status_code == 401


# --- Implausible / Duplicate ----------------------------------------------------------


def test_no_timestamps_rejected(client: TestClient) -> None:
    me = dev_login(client)
    pts = straight(1000, start=offset(*ORIGIN, 777, 0))
    for p in pts:
        p.t = None
    track = uploaded(client, me, to_gpx(pts))
    assert track["status"] == "rejected"
    assert track["reject_message"] == "в файле нет времени"


def test_too_fast_rejected(client: TestClient) -> None:
    me = dev_login(client)
    track = uploaded(client, me, unique_run(5000, pace_s_per_km=130))
    assert track["status"] == "rejected"
    assert track["reject_message"] == "похоже на транспорт"


def test_same_file_again(client: TestClient) -> None:
    me = dev_login(client)
    data = unique_run()
    first = upload(client, me, data).json()
    again = upload(client, me, data)
    assert again.status_code == 409
    assert again.json()["track_id"] == first["id"]
    assert again.json()["detail"] == "Этот трек уже есть"
    assert len(client.get("/me/tracks", headers=me).json()) == 1


# --- Upload Rate Limit ----------------------------------------------------------------


def test_upload_limit_exceeded(client: TestClient) -> None:
    me = dev_login(client)
    for _ in range(20):
        assert upload(client, me, unique_run(300)).status_code == 202
    resp = upload(client, me, unique_run(300))
    assert resp.status_code == 429
    body = resp.json()
    assert body["retry_after_s"] > 0 and "Можно продолжить через" in body["detail"]
    assert int(resp.headers["Retry-After"]) == body["retry_after_s"]


# --- Home Privacy Zones -----------------------------------------------------------------


def test_start_inside_zone_hidden_from_others(client: TestClient) -> None:
    owner, other = dev_login(client), dev_login(client)
    start = offset(*ORIGIN, 3000, 3000)
    home = offset(*start, 0, 150)
    set_home(client, owner, home, 300)
    track = uploaded(client, owner, to_gpx(straight(3000, start=start)))
    publish(client, owner, track["id"], "public")

    for viewer in (other, {}):
        resp = client.get(f"/tracks/{track['id']}", headers=viewer)
        assert resp.status_code == 200
        body = resp.json()
        assert body["owner"] is None and body["is_owner"] is False
        coords = body["geometry"]["coordinates"]
        assert min(haversine(home, (lat, lon)) for lon, lat in coords) >= 300
        assert f"{home[0]:.4f}" not in resp.text


def test_owner_preview_shows_full_track_and_zone(client: TestClient) -> None:
    owner = dev_login(client)
    start = offset(*ORIGIN, -3000, 3000)
    home = offset(*start, 0, 150)
    set_home(client, owner, home, 300)
    track = uploaded(client, owner, to_gpx(straight(3000, start=start)))

    assert track["is_owner"] is True
    full = track["owner"]["full_geometry"]["coordinates"]
    assert full[0] == pytest.approx([start[1], start[0]], abs=1e-6)
    zone = track["owner"]["hidden_zone"]
    assert (zone["lat"], zone["lon"], zone["radius_m"]) == pytest.approx((*home, 300))


def test_no_home_whole_track_visible(client: TestClient) -> None:
    owner = dev_login(client)
    start = offset(*ORIGIN, 6000, 0)
    track = uploaded(client, owner, to_gpx(straight(2000, start=start)))
    first = track["geometry"]["coordinates"][0]
    assert haversine(start, (first[1], first[0])) < 1
    assert track["owner"]["hidden_zone"] is None


def test_zone_changed_later(client: TestClient) -> None:
    owner = dev_login(client)
    start = offset(*ORIGIN, -6000, 0)
    track = uploaded(client, owner, to_gpx(straight(3000, start=start)))
    before = track["geometry"]["coordinates"][0]
    assert haversine(start, (before[1], before[0])) < 1

    set_home(client, owner, start, 400)  # дом ровно на старте
    after = client.get(f"/tracks/{track['id']}", headers=owner).json()["geometry"]["coordinates"]
    assert haversine(start, (after[0][1], after[0][0])) >= 400


def test_track_entirely_inside_zone(client: TestClient) -> None:
    owner = dev_login(client)
    center = offset(*ORIGIN, 9000, 9000)
    set_home(client, owner, center, 500)
    track = uploaded(client, owner, to_gpx(circle(center, 200, laps=3)))
    assert track["status"] == "draft"
    assert track["owner"]["fully_hidden"] is True and track["geometry"] is None

    resp = client.patch(f"/tracks/{track['id']}", headers=owner, json={"visibility": "public"})
    assert resp.status_code == 422
    assert "только как приватный" in resp.json()["detail"]
    publish(client, owner, track["id"], "private")


# --- Publication and Visibility -------------------------------------------------------------


def test_publish_public_track(client: TestClient) -> None:
    owner, other = dev_login(client), dev_login(client)
    track = uploaded(client, owner, unique_run())
    owner_id = client.get("/me", headers=owner).json()["id"]

    assert client.get(f"/tracks/{track['id']}", headers=other).status_code == 404  # черновик
    publish(client, owner, track["id"], "public")
    assert client.get(f"/tracks/{track['id']}", headers=other).status_code == 200
    listed = [t["id"] for t in client.get(f"/users/{owner_id}/tracks").json()]
    assert track["id"] in listed


@pytest.mark.parametrize(("visibility", "by_link"), [("private", 404), ("link", 200)])
def test_private_and_link_tracks(client: TestClient, visibility: str, by_link: int) -> None:
    owner, other = dev_login(client), dev_login(client)
    track = uploaded(client, owner, unique_run())
    publish(client, owner, track["id"], visibility)
    owner_id = client.get("/me", headers=owner).json()["id"]

    assert client.get(f"/tracks/{track['id']}", headers=other).status_code == by_link
    assert client.get(f"/tracks/{track['id']}").status_code == by_link
    assert client.get(f"/users/{owner_id}/tracks").json() == []


def test_publish_requires_title(client: TestClient) -> None:
    owner = dev_login(client)
    track = uploaded(client, owner, unique_run())
    resp = client.patch(
        f"/tracks/{track['id']}", headers=owner, json={"title": "  ", "publish": True}
    )
    assert resp.status_code == 422


# --- Edit and Delete ----------------------------------------------------------------------


def test_edit_track(client: TestClient) -> None:
    owner, other = dev_login(client), dev_login(client)
    track = uploaded(client, owner, unique_run())
    publish(client, owner, track["id"], "public")

    resp = client.patch(
        f"/tracks/{track['id']}",
        headers=owner,
        json={"title": "Набережная", "description": "Вечерняя", "visibility": "private"},
    )
    assert resp.status_code == 200
    assert (resp.json()["title"], resp.json()["description"]) == ("Набережная", "Вечерняя")
    assert client.get(f"/tracks/{track['id']}", headers=other).status_code == 404


def test_delete_track(client: TestClient, migrated: Config, db: Session) -> None:
    owner = dev_login(client)
    track = uploaded(client, owner, unique_run())
    client.post(f"/tracks/{track['id']}/photos", headers=owner, files={"file": ("a.jpg", _jpeg())})
    owner_id = client.get("/me", headers=owner).json()["id"]
    prefix = f"users/{owner_id}/tracks/{track['id']}/"
    assert len(s3_keys(migrated, prefix)) == 2  # исходный файл и фото

    assert client.delete(f"/tracks/{track['id']}", headers=owner).status_code == 204
    assert client.get(f"/tracks/{track['id']}", headers=owner).status_code == 404
    assert s3_keys(migrated, prefix) == []
    assert db.get(Track, uuid.UUID(track["id"])) is None


def test_foreign_track(client: TestClient) -> None:
    owner, other = dev_login(client), dev_login(client)
    track = uploaded(client, owner, unique_run())
    publish(client, owner, track["id"], "public")
    url = f"/tracks/{track['id']}"
    assert client.patch(url, headers=other, json={"title": "Моё"}).status_code == 404
    assert client.delete(url, headers=other).status_code == 404
    photo = client.post(f"{url}/photos", headers=other, files={"file": ("a.jpg", _jpeg())})
    assert photo.status_code == 404
    assert client.get(url, headers=owner).json()["title"] != "Моё"


# --- Track Photos -------------------------------------------------------------------------


def _jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (10, 120, 200)).save(buf, format="JPEG")
    return buf.getvalue()


def test_sixth_photo_rejected(client: TestClient) -> None:
    owner = dev_login(client)
    track = uploaded(client, owner, unique_run())
    url = f"/tracks/{track['id']}/photos"
    for _ in range(5):
        assert (
            client.post(url, headers=owner, files={"file": ("p.jpg", _jpeg())}).status_code == 201
        )
    sixth = client.post(url, headers=owner, files={"file": ("p.jpg", _jpeg())})
    assert sixth.status_code == 422
    assert sixth.json()["detail"] == "не больше 5 фото"


def test_photo_location_stripped(client: TestClient) -> None:
    owner, other = dev_login(client), dev_login(client)
    track = uploaded(client, owner, unique_run())
    photo = client.post(
        f"/tracks/{track['id']}/photos", headers=owner, files={"file": ("p.jpg", jpeg_with_gps())}
    ).json()
    publish(client, owner, track["id"], "public")

    resp = client.get(photo["url"], headers=other)
    assert resp.status_code == 200 and resp.headers["content-type"] == "image/jpeg"
    assert not Image.open(io.BytesIO(resp.content)).getexif()


def test_photo_not_an_image(client: TestClient) -> None:
    owner = dev_login(client)
    track = uploaded(client, owner, unique_run())
    resp = client.post(
        f"/tracks/{track['id']}/photos", headers=owner, files={"file": ("p.jpg", b"not an image")}
    )
    assert resp.status_code == 415


def test_draft_photo_hidden_from_others(client: TestClient) -> None:
    owner, other = dev_login(client), dev_login(client)
    track = uploaded(client, owner, unique_run())
    photo = client.post(
        f"/tracks/{track['id']}/photos", headers=owner, files={"file": ("p.jpg", _jpeg())}
    ).json()
    assert client.get(photo["url"], headers=other).status_code == 404
    assert client.get(photo["url"], headers=owner).status_code == 200


# --- Profile Statistics ---------------------------------------------------------------------


def test_guest_sees_only_public_tracks(client: TestClient) -> None:
    owner = dev_login(client)
    ids = {}
    for visibility, dist in (("public", 5200), ("link", 3500), ("private", 4000)):
        track = uploaded(client, owner, unique_run(dist))
        publish(client, owner, track["id"], visibility)
        ids[visibility] = track["id"]
    owner_id = client.get("/me", headers=owner).json()["id"]

    profile = client.get(f"/users/{owner_id}").json()
    assert profile["stats"]["runs"] == 1
    assert profile["stats"]["total_distance_m"] == pytest.approx(5200, rel=0.01)
    assert [t["id"] for t in client.get(f"/users/{owner_id}/tracks").json()] == [ids["public"]]

    own = client.get("/me", headers=owner).json()
    assert own["stats"]["runs"] == 3
    assert len(client.get("/me/tracks", headers=owner).json()) == 3


def test_personal_record(client: TestClient) -> None:
    owner = dev_login(client)
    for pace in (302, 294):  # 5 км за 25:10 и 24:30
        track = uploaded(client, owner, unique_run(5000, pace_s_per_km=pace))
        publish(client, owner, track["id"], "public")
    owner_id = client.get("/me", headers=owner).json()["id"]
    records = client.get(f"/users/{owner_id}").json()["stats"]["records"]
    assert records["5"] == pytest.approx(24 * 60 + 30, abs=2)


# --- Account Deletion Cleanup ----------------------------------------------------------------


def test_delete_account_with_tracks(client: TestClient, migrated: Config, db: Session) -> None:
    owner = dev_login(client)
    owner_id = client.get("/me", headers=owner).json()["id"]
    track = uploaded(client, owner, unique_run())
    client.post(f"/tracks/{track['id']}/photos", headers=owner, files={"file": ("a.jpg", _jpeg())})
    assert s3_keys(migrated, f"users/{owner_id}/")

    assert client.delete("/me", headers=owner).status_code == 204
    assert s3_keys(migrated, f"users/{owner_id}/") == []
    db.expire_all()
    assert db.execute(select(Track).where(Track.user_id == uuid.UUID(owner_id))).first() is None


# --- Settings-driven thresholds --------------------------------------------------------------


def test_category_bounds_from_settings(client: TestClient, db: Session) -> None:
    original = get_setting(db, "categories.bounds_m")
    set_setting(db, "categories.bounds_m", [6000, 7500, 15000, 25000])
    try:
        owner = dev_login(client)
        track = uploaded(client, owner, unique_run(5200))
        assert track["category"] == "1"
    finally:
        set_setting(db, "categories.bounds_m", original)
    assert math.isclose(track["distance_m"], 5200, rel_tol=0.01)
