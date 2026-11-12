"""Unit tests for hashing and tokens. These need no web framework or database."""

from datetime import UTC, datetime, timedelta

import jwt

from app.config import settings
from app.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    needs_rehash,
    verify_password,
)


def test_hash_has_expected_format_and_never_contains_the_password():
    stored = hash_password("correct-horse-battery")
    parts = stored.split("$")
    assert parts[0] == "scrypt" and len(parts) == 6
    assert "correct-horse-battery" not in stored


def test_verify_accepts_right_password_and_rejects_wrong_one():
    stored = hash_password("correct-horse-battery")
    assert verify_password("correct-horse-battery", stored)
    assert not verify_password("correct-horse-batterY", stored)


def test_same_password_gets_different_hashes_because_of_salt():
    assert hash_password("same-password-1") != hash_password("same-password-1")


def test_whitespace_in_passwords_is_significant():
    stored = hash_password("  padded-password  ")
    assert not verify_password("padded-password", stored)


def test_malformed_hashes_are_rejected_not_crashing():
    for bad in ["", "plaintext", "bcrypt$1$2$3$4$5", "scrypt$x$8$1$AAAA$AAAA", "scrypt$1024$8$1$!!$!!"]:
        assert verify_password("anything-at-all", bad) is False


def test_needs_rehash_when_cost_changes():
    assert not needs_rehash(hash_password("pw-for-rehash-test"))
    assert needs_rehash(hash_password("pw-for-rehash-test", n=settings.scrypt_n // 2))


def test_token_round_trip():
    token, expires_in = create_access_token(42)
    assert decode_access_token(token) == 42
    assert expires_in == settings.access_token_minutes * 60


def _forge(payload, key=None, algorithm="HS256"):
    return jwt.encode(payload, key or settings.secret_key, algorithm=algorithm)


def _claims(**overrides):
    now = datetime.now(UTC)
    claims = {"sub": "1", "iat": now, "exp": now + timedelta(minutes=5), "type": "access"}
    claims.update(overrides)
    return {k: v for k, v in claims.items() if v is not None}


def test_rejects_token_signed_with_another_key():
    assert decode_access_token(_forge(_claims(), key="attacker-key-0123456789-abcdefghijklmn")) is None


def test_rejects_expired_token():
    past = datetime.now(UTC) - timedelta(hours=1)
    assert decode_access_token(_forge(_claims(iat=past, exp=past + timedelta(minutes=1)))) is None


def test_rejects_unsigned_alg_none_token():
    assert decode_access_token(jwt.encode(_claims(), key=None, algorithm="none")) is None


def test_rejects_tampered_payload():
    header, _, signature = create_access_token(1)[0].split(".")
    other_payload = _forge(_claims(sub="2")).split(".")[1]
    assert decode_access_token(f"{header}.{other_payload}.{signature}") is None


def test_rejects_wrong_type_missing_claims_and_bad_subject():
    assert decode_access_token(_forge(_claims(type="refresh"))) is None
    assert decode_access_token(_forge(_claims(exp=None))) is None
    assert decode_access_token(_forge(_claims(sub="not-a-number"))) is None
    assert decode_access_token("not.a.jwt") is None
