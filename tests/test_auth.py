"""Registration, login and /auth/me through the real HTTP layer."""

import pytest

from tests.conftest import PASSWORD, register_and_login


def test_register_returns_user_without_password_hash(client):
    response = client.post("/auth/register", json={"email": "New@Example.com", "password": PASSWORD})
    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "new@example.com"
    assert set(body) == {"id", "email", "created_at"}


def test_duplicate_email_is_rejected_case_insensitively(client):
    client.post("/auth/register", json={"email": "dup@example.com", "password": PASSWORD})
    response = client.post("/auth/register", json={"email": "DUP@example.com", "password": PASSWORD})
    assert response.status_code == 409


@pytest.mark.parametrize(
    "payload",
    [
        {"email": "bad", "password": PASSWORD},
        {"email": "ok@example.com", "password": "short"},
        {"email": "ok@example.com"},
        {"email": "ok@example.com", "password": PASSWORD, "is_admin": True},
    ],
)
def test_invalid_registration_is_422(client, payload):
    assert client.post("/auth/register", json=payload).status_code == 422


def test_login_returns_bearer_token(client):
    client.post("/auth/register", json={"email": "a@example.com", "password": PASSWORD})
    response = client.post("/auth/login", data={"username": " A@Example.com ", "password": PASSWORD})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer" and body["access_token"] and body["expires_in"] > 0


def test_wrong_password_and_unknown_email_look_identical(client):
    client.post("/auth/register", json={"email": "a@example.com", "password": PASSWORD})
    wrong_pw = client.post("/auth/login", data={"username": "a@example.com", "password": "nope-nope-nope"})
    no_user = client.post("/auth/login", data={"username": "ghost@example.com", "password": PASSWORD})
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_me_requires_a_valid_token(client):
    headers = register_and_login(client, "me@example.com")
    assert client.get("/auth/me", headers=headers).json()["email"] == "me@example.com"
    assert client.get("/auth/me").status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Bearer garbage"}).status_code == 401


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}
