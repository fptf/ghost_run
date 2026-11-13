"""Spec auth: Google Sign-in, Dev Sign-in, Token Lifecycle, Auth Rate Limit, Roles."""

import uuid
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.auth import REFRESH_COOKIE, get_google_verifier
from app.config import Config, get_config
from app.infra.identity import GoogleVerifier
from app.infra.models import RefreshToken, User
from app.infra.tokens import create_access_token
from app.main import app
from app.scripts import set_role
from tests.conftest import GOOGLE_CLIENT_ID, dev_login
from tests.google_fake import FakeGoogle, _keypair


@pytest.fixture
def google(client: TestClient) -> Iterator[FakeGoogle]:
    fake = FakeGoogle(GOOGLE_CLIENT_ID)
    app.dependency_overrides[get_google_verifier] = lambda: GoogleVerifier(
        GOOGLE_CLIENT_ID, request=fake
    )
    yield fake
    app.dependency_overrides.pop(get_google_verifier, None)


def _sub() -> str:
    return str(uuid.uuid4().int)[:12]


# --- Requirement: Google Sign-in -------------------------------------------------


def test_first_google_sign_in_creates_runner(
    client: TestClient, google: FakeGoogle, db: Session
) -> None:
    sub = _sub()
    resp = client.post("/auth/google", json={"id_token": google.token(sub)})

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["access_token"] and body["expires_in"] <= 15 * 60
    cookie = resp.headers["set-cookie"].lower()
    assert f"{REFRESH_COOKIE}=" in cookie and "httponly" in cookie and "samesite=strict" in cookie

    me = client.get("/me", headers={"Authorization": f"Bearer {body['access_token']}"}).json()
    assert me["role"] == "runner"
    assert me["email"] == f"user{sub}@gmail.com"
    assert me["name"] == f"Бегун {sub}"
    assert me["avatar_url"].endswith(sub)


def test_returning_user_gets_same_account(
    client: TestClient, google: FakeGoogle, db: Session
) -> None:
    sub = _sub()
    first = client.post("/auth/google", json={"id_token": google.token(sub)}).json()
    second = client.post("/auth/google", json={"id_token": google.token(sub)}).json()

    assert first["user_id"] == second["user_id"]
    count = db.execute(
        select(func.count()).select_from(User).where(User.google_sub == f"google:{sub}")
    ).scalar_one()
    assert count == 1


@pytest.mark.parametrize(
    "case",
    ["wrong_audience", "foreign_signature", "expired", "wrong_issuer", "email_not_verified"],
)
def test_invalid_google_token_rejected(client: TestClient, google: FakeGoogle, case: str) -> None:
    now = int(datetime.now(UTC).timestamp())
    token = {
        "wrong_audience": lambda: google.token(
            _sub(), aud="someone-else.apps.googleusercontent.com"
        ),
        "foreign_signature": lambda: google.token(_sub(), private_key=_keypair()[0]),
        "expired": lambda: google.token(_sub(), iat=now - 7200, exp=now - 3600),
        "wrong_issuer": lambda: google.token(_sub(), iss="https://evil.example.com"),
        "email_not_verified": lambda: google.token(_sub(), email_verified=False),
    }[case]()
    resp = client.post("/auth/google", json={"id_token": token})
    assert resp.status_code == 401


def test_google_not_configured(client: TestClient, migrated: Config) -> None:
    cfg = migrated.model_copy(update={"google_client_id": None})
    app.dependency_overrides[get_config] = lambda: cfg
    assert client.post("/auth/google", json={"id_token": "x"}).status_code == 503
    assert client.get("/auth/config").json()["google_client_id"] is None


# --- Requirement: Dev Sign-in ----------------------------------------------------


def test_dev_sign_in_disabled(client: TestClient, migrated: Config) -> None:
    cfg = migrated.model_copy(update={"auth_dev_login": False})
    app.dependency_overrides[get_config] = lambda: cfg
    resp = client.post("/auth/dev-login", json={"email": "a@example.com", "name": "A"})
    assert resp.status_code == 404
    assert client.get("/auth/config").json()["dev_login_enabled"] is False


def test_dev_sign_in_enabled(client: TestClient) -> None:
    email = f"{_sub()}@example.com"
    headers = dev_login(client, email=email, name="Dev")
    me = client.get("/me", headers=headers).json()
    assert me["email"] == email and me["role"] == "runner"
    # повторный вход — тот же аккаунт
    again = dev_login(client, email=email, name="Dev")
    assert client.get("/me", headers=again).json()["id"] == me["id"]


# --- Requirement: Token Lifecycle ------------------------------------------------


def test_access_token_lifetime_at_most_15_minutes(migrated: Config) -> None:
    assert migrated.access_token_ttl_s <= 15 * 60


def test_expired_access_token_refreshes_with_rotation(client: TestClient, migrated: Config) -> None:
    resp = client.post("/auth/dev-login", json={"email": f"{_sub()}@example.com", "name": "R"})
    user_id = uuid.UUID(resp.json()["user_id"])
    old_refresh = client.cookies[REFRESH_COOKIE]

    expired = create_access_token(user_id, migrated, now=datetime.now(UTC) - timedelta(hours=1))
    assert client.get("/me", headers={"Authorization": f"Bearer {expired}"}).status_code == 401

    refreshed = client.post("/auth/refresh")
    assert refreshed.status_code == 200
    new_access = refreshed.json()["access_token"]
    assert client.get("/me", headers={"Authorization": f"Bearer {new_access}"}).status_code == 200
    assert client.cookies[REFRESH_COOKIE] != old_refresh

    # старый refresh-токен больше не действует
    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, old_refresh)
    assert client.post("/auth/refresh").status_code == 401


def test_refresh_token_reuse_revokes_session(client: TestClient, db: Session) -> None:
    resp = client.post("/auth/dev-login", json={"email": f"{_sub()}@example.com", "name": "R"})
    user_id = uuid.UUID(resp.json()["user_id"])
    stolen = client.cookies[REFRESH_COOKIE]

    assert client.post("/auth/refresh").status_code == 200
    legit = client.cookies[REFRESH_COOKIE]

    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, stolen)
    assert client.post("/auth/refresh").status_code == 401  # повторное использование

    client.cookies.clear()
    client.cookies.set(REFRESH_COOKIE, legit)
    assert client.post("/auth/refresh").status_code == 401  # вся сессия отозвана

    active = db.execute(
        select(func.count())
        .select_from(RefreshToken)
        .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
    ).scalar_one()
    assert active == 0


def test_sign_out_revokes_refresh_token(client: TestClient) -> None:
    client.post("/auth/dev-login", json={"email": f"{_sub()}@example.com", "name": "R"})
    token = client.cookies[REFRESH_COOKIE]

    resp = client.post("/auth/logout")
    assert resp.status_code == 204
    assert REFRESH_COOKIE not in client.cookies

    client.cookies.set(REFRESH_COOKIE, token)
    assert client.post("/auth/refresh").status_code == 401


def test_refresh_without_cookie(client: TestClient) -> None:
    assert client.post("/auth/refresh").status_code == 401


# --- Requirement: Auth Rate Limit ------------------------------------------------


def test_too_many_auth_attempts(client: TestClient) -> None:
    codes = [client.get("/auth/config").status_code for _ in range(11)]
    assert codes[:10] == [200] * 10
    assert codes[10] == 429


# --- Requirement: Roles ----------------------------------------------------------


def test_assign_role_via_cli(client: TestClient, migrated: Config) -> None:
    email = f"{_sub()}@example.com"
    headers = dev_login(client, email=email)
    assert client.get("/me", headers=headers).json()["role"] == "runner"

    assert set_role.main([email, "moderator"], database_url=migrated.database_url) == 0
    assert client.get("/me", headers=headers).json()["role"] == "moderator"

    assert set_role.main(["nobody@example.com", "admin"], migrated.database_url) == 1
    assert set_role.main([email, "superuser"], migrated.database_url) == 2
