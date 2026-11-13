"""Проверка личности: Google `id_token` и dev-вход."""

from dataclasses import dataclass
from typing import Any, Protocol

import google.auth.transport.requests
from google.oauth2 import id_token as google_id_token

GOOGLE_ISSUERS = {"accounts.google.com", "https://accounts.google.com"}


@dataclass(frozen=True)
class Identity:
    subject: str
    email: str
    name: str
    avatar_url: str | None


class InvalidIdentityError(Exception):
    pass


class IdentityVerifier(Protocol):
    def verify(self, credential: str) -> Identity: ...


class GoogleVerifier:
    """Проверяет подпись, `aud`, `iss`, срок действия и подтверждённость email."""

    def __init__(self, client_id: str, request: Any | None = None) -> None:
        self.client_id = client_id
        self.request = request or google.auth.transport.requests.Request()

    def verify(self, credential: str) -> Identity:
        try:
            claims = google_id_token.verify_oauth2_token(  # type: ignore[no-untyped-call]
                credential, self.request, self.client_id
            )
        except Exception as exc:  # библиотека бросает ValueError и ошибки транспорта
            raise InvalidIdentityError(str(exc)) from exc
        if claims.get("iss") not in GOOGLE_ISSUERS:
            raise InvalidIdentityError("wrong issuer")
        if not claims.get("email") or not claims.get("email_verified"):
            raise InvalidIdentityError("email not verified")
        return Identity(
            subject=f"google:{claims['sub']}",
            email=str(claims["email"]).lower(),
            name=str(claims.get("name") or claims["email"].split("@")[0])[:100],
            avatar_url=claims.get("picture"),
        )


def dev_identity(email: str, name: str) -> Identity:
    return Identity(subject=f"dev:{email.lower()}", email=email.lower(), name=name, avatar_url=None)
