"""Access JWT и refresh-токены с ротацией и отзывом семейства."""

import hashlib
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

import jwt
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.config import Config
from app.infra.models import RefreshToken

ALGORITHM = "HS256"


class InvalidTokenError(Exception):
    pass


def _now() -> datetime:
    return datetime.now(UTC)


def create_access_token(user_id: uuid.UUID, cfg: Config, now: datetime | None = None) -> str:
    issued = now or _now()
    payload = {
        "sub": str(user_id),
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(seconds=cfg.access_token_ttl_s)).timestamp()),
        "typ": "access",
    }
    return jwt.encode(payload, cfg.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str, cfg: Config) -> uuid.UUID:
    try:
        payload = jwt.decode(token, cfg.jwt_secret, algorithms=[ALGORITHM])
        if payload.get("typ") != "access":
            raise InvalidTokenError("wrong token type")
        return uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise InvalidTokenError(str(exc)) from exc


def _hash(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue_refresh_token(
    session: Session, user_id: uuid.UUID, cfg: Config, family_id: uuid.UUID | None = None
) -> str:
    raw = secrets.token_urlsafe(32)
    session.add(
        RefreshToken(
            user_id=user_id,
            family_id=family_id or uuid.uuid4(),
            token_hash=_hash(raw),
            expires_at=_now() + timedelta(seconds=cfg.refresh_token_ttl_s),
        )
    )
    return raw


@dataclass(frozen=True)
class Rotation:
    user_id: uuid.UUID
    refresh_token: str


def _revoke_family(session: Session, family_id: uuid.UUID) -> None:
    session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=_now())
    )


def rotate_refresh_token(session: Session, raw: str, cfg: Config) -> Rotation:
    """Обменивает refresh-токен на новый. Повторное использование отзывает всю сессию."""
    token = session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == _hash(raw)).with_for_update()
    ).scalar_one_or_none()
    if token is None:
        raise InvalidTokenError("unknown refresh token")
    if token.used_at is not None or token.revoked_at is not None:
        _revoke_family(session, token.family_id)
        session.commit()
        raise InvalidTokenError("refresh token reuse")
    if token.expires_at <= _now():
        raise InvalidTokenError("refresh token expired")
    token.used_at = _now()
    new_raw = issue_refresh_token(session, token.user_id, cfg, family_id=token.family_id)
    session.commit()
    return Rotation(user_id=token.user_id, refresh_token=new_raw)


def revoke_refresh_token(session: Session, raw: str) -> None:
    token = session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == _hash(raw))
    ).scalar_one_or_none()
    if token is not None:
        _revoke_family(session, token.family_id)
        session.commit()
