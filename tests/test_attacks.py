"""Red-team suite: each test is one attack. Every one must FAIL to succeed.

Bob is the attacker. Alice is the victim with a private note.
"""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import settings


@pytest.fixture
def alice_note(client, alice):
    response = client.post("/notes", json={"title": "Alice's secret", "body": "PIN 1234"}, headers=alice)
    return response.json()["id"]


@pytest.mark.parametrize(
    "method,body",
    [("GET", None), ("PATCH", {"body": "hacked"}), ("DELETE", None)],
)
def test_idor_bob_cannot_touch_alices_note(client, alice, bob, alice_note, method, body):
    response = client.request(method, f"/notes/{alice_note}", json=body, headers=bob)
    assert response.status_code == 404  # same answer as "doesn't exist": nothing leaks
    still_there = client.get(f"/notes/{alice_note}", headers=alice).json()
    assert still_there["body"] == "PIN 1234"


def test_idor_listing_only_shows_own_notes(client, bob, alice_note):
    assert client.get("/notes", headers=bob).json() == []


def test_idor_enumerating_ids_finds_nothing(client, bob, alice_note):
    hits = [i for i in range(1, 50) if client.get(f"/notes/{i}", headers=bob).status_code != 404]
    assert hits == []


def test_mass_assignment_cannot_set_owner(client, alice, bob):
    alice_id = client.get("/auth/me", headers=alice).json()["id"]
    response = client.post("/notes", json={"title": "x", "owner_id": alice_id}, headers=bob)
    assert response.status_code == 422


def _token(sub: str, key: str | None = None, algorithm: str = "HS256", minutes: int = 5) -> dict:
    now = datetime.now(UTC)
    payload = {"sub": sub, "iat": now, "exp": now + timedelta(minutes=minutes), "type": "access"}
    token = jwt.encode(payload, key if algorithm != "none" else None, algorithm=algorithm)
    return {"Authorization": f"Bearer {token}"}


def test_forged_token_with_guessed_key_is_rejected(client, alice, alice_note):
    forged = _token("1", key="secret-guessed-by-attacker-0123456789abc")
    assert client.get(f"/notes/{alice_note}", headers=forged).status_code == 401


def test_unsigned_alg_none_token_is_rejected(client, alice, alice_note):
    assert client.get(f"/notes/{alice_note}", headers=_token("1", algorithm="none")).status_code == 401


def test_expired_token_is_rejected(client, alice):
    expired = _token("1", key=settings.secret_key, minutes=-1)
    assert client.get("/auth/me", headers=expired).status_code == 401


def test_valid_signature_for_nonexistent_user_is_rejected(client):
    assert client.get("/auth/me", headers=_token("9999", key=settings.secret_key)).status_code == 401


@pytest.mark.parametrize("payload", ["' OR '1'='1", "admin@example.com'--", "x@x.com; DROP TABLE users;"])
def test_sql_injection_in_login_is_harmless(client, alice, payload):
    response = client.post("/auth/login", data={"username": payload, "password": payload})
    assert response.status_code == 401
    assert client.get("/auth/me", headers=alice).status_code == 200  # users table survived


def test_sql_injection_in_note_is_stored_as_plain_text(client, alice):
    evil = "'); DELETE FROM notes; --"
    note = client.post("/notes", json={"title": evil}, headers=alice).json()
    assert client.get(f"/notes/{note['id']}", headers=alice).json()["title"] == evil
