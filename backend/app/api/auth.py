import uuid
from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field

from app.api.deps import ConfigDep, DbDep, auth_rate_limit
from app.config import Config
from app.infra.identity import (
    GoogleVerifier,
    Identity,
    IdentityVerifier,
    InvalidIdentityError,
    dev_identity,
)
from app.infra.tokens import (
    InvalidTokenError,
    create_access_token,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.infra.users_repo import get_or_create_user

REFRESH_COOKIE = "refresh_token"

router = APIRouter(prefix="/auth", tags=["auth"])
# Лимит только на вход: /auth/refresh вызывается при каждой загрузке страницы и защищён ротацией.
SIGN_IN_LIMIT = [Depends(auth_rate_limit)]


class AuthConfig(BaseModel):
    google_client_id: str | None
    dev_login_enabled: bool


class GoogleSignIn(BaseModel):
    id_token: str = Field(min_length=1)


class DevSignIn(BaseModel):
    email: EmailStr
    name: str = Field(min_length=1, max_length=100)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user_id: uuid.UUID


def get_google_verifier(cfg: ConfigDep) -> IdentityVerifier:
    if not cfg.google_client_id:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Вход через Google не настроен")
    return GoogleVerifier(cfg.google_client_id)


def _set_refresh_cookie(response: Response, raw: str, cfg: Config) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=cfg.refresh_token_ttl_s,
        httponly=True,
        secure=cfg.cookie_secure,
        samesite="strict",
        path="/",
    )


def _sign_in(identity: Identity, response: Response, cfg: Config, db: DbDep) -> TokenResponse:
    user = get_or_create_user(db, identity)
    refresh = issue_refresh_token(db, user.id, cfg)
    db.commit()
    _set_refresh_cookie(response, refresh, cfg)
    return TokenResponse(
        access_token=create_access_token(user.id, cfg),
        expires_in=cfg.access_token_ttl_s,
        user_id=user.id,
    )


@router.get("/config")
def auth_config(cfg: ConfigDep) -> AuthConfig:
    return AuthConfig(google_client_id=cfg.google_client_id, dev_login_enabled=cfg.auth_dev_login)


@router.post(
    "/google",
    dependencies=SIGN_IN_LIMIT,
    responses={401: {"description": "Недействительный токен Google"}},
)
def sign_in_google(
    body: GoogleSignIn,
    response: Response,
    cfg: ConfigDep,
    db: DbDep,
    verifier: Annotated[IdentityVerifier, Depends(get_google_verifier)],
) -> TokenResponse:
    try:
        identity = verifier.verify(body.id_token)
    except InvalidIdentityError:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Не удалось войти через Google") from None
    return _sign_in(identity, response, cfg, db)


@router.post(
    "/dev-login",
    dependencies=SIGN_IN_LIMIT,
    responses={404: {"description": "Dev-вход выключен"}},
)
def sign_in_dev(body: DevSignIn, response: Response, cfg: ConfigDep, db: DbDep) -> TokenResponse:
    if not cfg.auth_dev_login:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not Found")
    return _sign_in(dev_identity(str(body.email), body.name), response, cfg, db)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"description": "Сессия недействительна"}},
)
def refresh(
    response: Response,
    cfg: ConfigDep,
    db: DbDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenResponse | JSONResponse:
    if not refresh_token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Нет сессии")
    try:
        rotation = rotate_refresh_token(db, refresh_token, cfg)
    except InvalidTokenError:
        # HTTPException отбросил бы заголовки response — удаляем cookie в собственном ответе
        expired = JSONResponse({"detail": "Сессия недействительна"}, status_code=401)
        expired.delete_cookie(REFRESH_COOKIE, path="/")
        return expired
    _set_refresh_cookie(response, rotation.refresh_token, cfg)
    return TokenResponse(
        access_token=create_access_token(rotation.user_id, cfg),
        expires_in=cfg.access_token_ttl_s,
        user_id=rotation.user_id,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    db: DbDep,
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> None:
    if refresh_token:
        revoke_refresh_token(db, refresh_token)
    response.delete_cookie(REFRESH_COOKIE, path="/")
