"""Поддельный Google: свой RSA-ключ и сертификат вместо https://www.googleapis.com/oauth2/v1/certs.

Позволяет проверять настоящую логику google-auth (подпись, aud, iss, срок) без сети.
"""

import json
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID


def _keypair() -> tuple[bytes, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "fake-google")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    pem_key = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    return pem_key, cert.public_bytes(serialization.Encoding.PEM).decode()


@dataclass
class _Response:
    status: int
    data: bytes
    headers: dict[str, str] = field(default_factory=dict)


class FakeGoogle:
    KID = "fake-kid"

    def __init__(self, client_id: str) -> None:
        self.client_id = client_id
        self.private_key, self.cert = _keypair()

    # Транспорт google-auth: request(url, method=...) -> объект с .status и .data
    def __call__(self, url: str, method: str = "GET", **_: Any) -> _Response:
        return _Response(200, json.dumps({self.KID: self.cert}).encode())

    def token(self, sub: str = "1001", private_key: bytes | None = None, **overrides: Any) -> str:
        now = int(time.time())
        claims: dict[str, Any] = {
            "iss": "https://accounts.google.com",
            "aud": self.client_id,
            "sub": sub,
            "email": f"user{sub}@gmail.com",
            "email_verified": True,
            "name": f"Бегун {sub}",
            "picture": f"https://lh3.googleusercontent.com/a/{sub}",
            "iat": now,
            "exp": now + 3600,
        }
        claims.update(overrides)
        return jwt.encode(
            claims, private_key or self.private_key, algorithm="RS256", headers={"kid": self.KID}
        )
