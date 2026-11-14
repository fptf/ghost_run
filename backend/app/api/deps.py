import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.config import Config, get_config
from app.infra.db import open_session
from app.infra.models import User
from app.infra.rate_limit import RateLimiter
from app.infra.settings_repo import get_setting
from app.infra.tokens import InvalidTokenError, decode_access_token

ConfigDep = Annotated[Config, Depends(get_config)]


def get_db(cfg: ConfigDep) -> Iterator[Session]:
    with open_session(cfg.database_url) as session:
        yield session


DbDep = Annotated[Session, Depends(get_db)]

bearer = HTTPBearer(auto_error=False)
UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Требуется вход",
    headers={"WWW-Authenticate": "Bearer"},
)


def current_user(
    cfg: ConfigDep,
    db: DbDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User:
    if creds is None:
        raise UNAUTHORIZED
    try:
        user_id: uuid.UUID = decode_access_token(creds.credentials, cfg)
    except InvalidTokenError:
        raise UNAUTHORIZED from None
    user = db.get(User, user_id)
    if user is None:
        raise UNAUTHORIZED
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def optional_user(
    cfg: ConfigDep,
    db: DbDep,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> User | None:
    """Пользователь, если передан действительный токен; иначе гость."""
    if creds is None:
        return None
    try:
        return db.get(User, decode_access_token(creds.credentials, cfg))
    except InvalidTokenError:
        return None


OptionalUser = Annotated[User | None, Depends(optional_user)]


def auth_rate_limit(request: Request, cfg: ConfigDep, db: DbDep) -> None:
    limit = int(get_setting(db, "auth.rate_limit_per_minute"))
    ip = request.client.host if request.client else "unknown"
    if not RateLimiter(cfg).hit("auth", ip, limit):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Слишком много попыток, попробуйте через минуту",
        )
