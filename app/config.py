"""Application settings, read once from environment variables."""

import logging
import os
import secrets
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    database_url: str
    secret_key: str
    access_token_minutes: int
    scrypt_n: int
    jwt_algorithm: str = "HS256"


def _read_scrypt_n() -> int:
    n = int(os.getenv("SCRYPT_N", str(2**17)))
    if n < 2 or n & (n - 1):
        raise ValueError("SCRYPT_N must be a power of two greater than 1")
    return n


def load_settings() -> Settings:
    secret = os.getenv("SECRET_KEY")
    if not secret:
        secret = secrets.token_urlsafe(32)
        logger.warning("SECRET_KEY is not set: using a random key. Tokens will stop working on restart.")
    return Settings(
        database_url=os.getenv("DATABASE_URL", "sqlite:///./notes.db"),
        secret_key=secret,
        access_token_minutes=int(os.getenv("ACCESS_TOKEN_MINUTES", "30")),
        scrypt_n=_read_scrypt_n(),
    )


settings = load_settings()
