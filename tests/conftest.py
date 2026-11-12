"""Shared test setup. Env vars are set BEFORE any app module is imported."""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-0123456789-abcdefghijklmnopqrstuvwxyz")
os.environ.setdefault("SCRYPT_N", "1024")  # cheap hashing so the suite stays fast
os.environ.setdefault("DATABASE_URL", "sqlite://")

import pytest  # noqa: E402

PASSWORD = "correct-horse-battery"


@pytest.fixture
def client():
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool

    from app.database import Base, get_db
    from app.main import app

    # One fresh in-memory database per test; StaticPool keeps it alive across connections.
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    engine.dispose()


def register_and_login(client, email: str, password: str = PASSWORD) -> dict[str, str]:
    response = client.post("/auth/register", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    response = client.post("/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


@pytest.fixture
def alice(client):
    return register_and_login(client, "alice@example.com")


@pytest.fixture
def bob(client):
    return register_and_login(client, "bob@example.com")
