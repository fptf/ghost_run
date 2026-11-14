"""Spec profile: Public Profile, Own Profile, Home Privacy Zone, Account Deletion."""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import REFRESH_COOKIE
from app.config import Config
from app.domain.privacy import RadiusBounds, RadiusOutOfRangeError, validate_hide_radius
from app.infra.account_cleanup import user_s3_prefix
from app.infra.models import RefreshToken, User
from app.infra.s3 import s3_client
from tests.helpers import dev_login

PUBLIC_KEYS = {"id", "name", "avatar_url", "city", "about", "stats"}


def _me(client: TestClient, headers: dict[str, str]) -> dict:  # type: ignore[type-arg]
    return client.get("/me", headers=headers).json()  # type: ignore[no-any-return]


# --- Requirement: Public Profile -------------------------------------------------


def test_guest_views_profile(client: TestClient) -> None:
    headers = dev_login(client, name="Анна")
    client.patch(
        "/me",
        headers=headers,
        json={
            "city": "Казань",
            "about": "Бегаю по утрам",
            "home": {"lat": 55.79, "lon": 49.12},
            "hide_radius_m": 300,
        },
    )
    user_id = _me(client, headers)["id"]

    resp = client.get(f"/users/{user_id}")  # без токена — гость
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == PUBLIC_KEYS
    assert body["name"] == "Анна" and body["city"] == "Казань"
    assert body["stats"] == {"runs": 0, "total_distance_m": 0, "records": {}}
    for secret in ("email", "home", "hide_radius_m", "55.79", "49.12"):
        assert secret not in resp.text


def test_unknown_profile_404(client: TestClient) -> None:
    assert client.get("/users/00000000-0000-0000-0000-000000000000").status_code == 404


def test_me_requires_auth(client: TestClient) -> None:
    assert client.get("/me").status_code == 401


# --- Requirement: Own Profile ----------------------------------------------------


def test_edit_profile(client: TestClient) -> None:
    headers = dev_login(client, name="Старое имя")
    resp = client.patch(
        "/me", headers=headers, json={"name": "Новое имя", "city": "Пермь", "about": "10 км"}
    )
    assert resp.status_code == 200
    me = resp.json()
    assert (me["name"], me["city"], me["about"]) == ("Новое имя", "Пермь", "10 км")

    public = client.get(f"/users/{me['id']}").json()
    assert (public["name"], public["city"], public["about"]) == ("Новое имя", "Пермь", "10 км")


# --- Requirement: Home Privacy Zone ----------------------------------------------


@pytest.mark.parametrize("radius", [100, 199, 501])
def test_radius_out_of_range(client: TestClient, radius: int) -> None:
    headers = dev_login(client)
    resp = client.patch(
        "/me", headers=headers, json={"home": {"lat": 55.0, "lon": 37.0}, "hide_radius_m": radius}
    )
    assert resp.status_code == 422
    assert "от 200 до 500 м" in resp.json()["detail"]
    assert _me(client, headers)["home"] is None


def test_radius_bounds_come_from_settings(client: TestClient, db: Session) -> None:
    from app.infra.settings_repo import get_setting, set_setting

    original = get_setting(db, "privacy.hide_radius_m")
    set_setting(db, "privacy.hide_radius_m", {"min": 100, "max": 500})
    try:
        headers = dev_login(client)
        resp = client.patch(
            "/me", headers=headers, json={"home": {"lat": 55.0, "lon": 37.0}, "hide_radius_m": 100}
        )
        assert resp.status_code == 200
    finally:
        set_setting(db, "privacy.hide_radius_m", original)


def test_home_requires_radius(client: TestClient) -> None:
    headers = dev_login(client)
    resp = client.patch("/me", headers=headers, json={"home": {"lat": 55.0, "lon": 37.0}})
    assert resp.status_code == 422


def test_home_point_stays_private(client: TestClient) -> None:
    owner = dev_login(client)
    resp = client.patch(
        "/me",
        headers=owner,
        json={"home": {"lat": 55.7512345, "lon": 37.6187654}, "hide_radius_m": 300},
    )
    assert resp.status_code == 200
    me = resp.json()
    assert me["home"] == pytest.approx({"lat": 55.7512345, "lon": 37.6187654})
    assert me["hide_radius_m"] == 300

    other = dev_login(client)
    for headers in (other, {}):
        public = client.get(f"/users/{me['id']}", headers=headers)
        assert "home" not in public.json() and "55.751" not in public.text

    cleared = client.patch("/me", headers=owner, json={"home": None}).json()
    assert cleared["home"] is None and cleared["hide_radius_m"] is None


def test_validate_hide_radius_domain() -> None:
    bounds = RadiusBounds.from_setting({"min": 200, "max": 500})
    validate_hide_radius(200, bounds)
    validate_hide_radius(500, bounds)
    with pytest.raises(RadiusOutOfRangeError, match="от 200 до 500 м"):
        validate_hide_radius(100, bounds)


# --- Requirement: Account Deletion -----------------------------------------------


def test_delete_account(client: TestClient, migrated: Config, db: Session) -> None:
    headers = dev_login(client)
    user_id = _me(client, headers)["id"]
    refresh = client.cookies[REFRESH_COOKIE]

    s3 = s3_client(migrated, timeout_s=30)
    key = f"{user_s3_prefix(user_id)}avatar.jpg"  # type: ignore[arg-type]
    s3.put_object(Bucket=migrated.s3_bucket, Key=key, Body=b"x")
    other_key = "users/someone-else/keep.jpg"
    s3.put_object(Bucket=migrated.s3_bucket, Key=other_key, Body=b"y")

    assert client.delete("/me", headers=headers).status_code == 204

    assert client.get("/me", headers=headers).status_code == 401
    client.cookies.set(REFRESH_COOKIE, refresh)
    assert client.post("/auth/refresh").status_code == 401
    assert client.get(f"/users/{user_id}").status_code == 404

    listed = s3.list_objects_v2(Bucket=migrated.s3_bucket, Prefix=f"users/{user_id}/")
    assert listed.get("KeyCount", 0) == 0
    assert s3.head_object(Bucket=migrated.s3_bucket, Key=other_key)  # чужие файлы на месте

    db.expire_all()
    assert db.get(User, user_id) is None
    tokens = db.execute(
        select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == user_id)
    ).scalar_one()
    assert tokens == 0
