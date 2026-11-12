"""Password hashing (scrypt) and access tokens (JWT). No web framework imports here."""

import base64
import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from functools import cache

import jwt

from .config import settings

SCRYPT_R = 8
SCRYPT_P = 1
SALT_BYTES = 16
KEY_BYTES = 32


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int, dklen: int) -> bytes:
    # scrypt needs about 128 * n * r bytes of RAM; Python's default cap is 32 MiB, too low for n = 2**17.
    maxmem = 128 * n * r + 1024 * 1024
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, maxmem=maxmem, dklen=dklen)


def hash_password(password: str, n: int | None = None) -> str:
    n = n or settings.scrypt_n
    salt = os.urandom(SALT_BYTES)
    key = _scrypt(password, salt, n, SCRYPT_R, SCRYPT_P, KEY_BYTES)
    salt_b64 = base64.b64encode(salt).decode()
    key_b64 = base64.b64encode(key).decode()
    return f"scrypt${n}${SCRYPT_R}${SCRYPT_P}${salt_b64}${key_b64}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        algorithm, n, r, p, salt_b64, key_b64 = stored_hash.split("$")
        salt = base64.b64decode(salt_b64, validate=True)
        expected = base64.b64decode(key_b64, validate=True)
        n, r, p = int(n), int(r), int(p)
    except ValueError:
        return False
    if algorithm != "scrypt":
        return False
    actual = _scrypt(password, salt, n, r, p, len(expected))
    return hmac.compare_digest(actual, expected)


def needs_rehash(stored_hash: str) -> bool:
    """True when a hash was made with older cost settings than the current ones."""
    parts = stored_hash.split("$")
    return len(parts) != 6 or parts[1] != str(settings.scrypt_n) or parts[2] != str(SCRYPT_R)


@cache
def dummy_hash() -> str:
    """A real hash to check against when the email doesn't exist, so both paths take the same time."""
    return hash_password("timing-equaliser-not-a-real-password")


def create_access_token(user_id: int) -> tuple[str, int]:
    now = datetime.now(UTC)
    lifetime = timedelta(minutes=settings.access_token_minutes)
    payload = {"sub": str(user_id), "iat": now, "exp": now + lifetime, "type": "access"}
    token = jwt.encode(payload, settings.secret_key, algorithm=settings.jwt_algorithm)
    return token, int(lifetime.total_seconds())


def decode_access_token(token: str) -> int | None:
    """Return the user id inside a valid token, or None for anything forged, expired or malformed."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "iat", "sub"]},
        )
    except jwt.PyJWTError:
        return None
    if payload.get("type") != "access":
        return None
    try:
        return int(payload["sub"])
    except (TypeError, ValueError):
        return None
