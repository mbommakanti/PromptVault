import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models  # noqa: F401 - ensures models are registered on Base.metadata
from database import Base, get_db
from main import app
from rate_limit import limiter

limiter.enabled = False
API_PREFIX = "/api/v1"

# --- Isolated, in-memory SQLite database used only for tests ---
SQLALCHEMY_TEST_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Replace the real get_db (MySQL) with the test version (SQLite) for every test
app.dependency_overrides[get_db] = override_get_db


@pytest.fixture()
def client():
    """A fresh DB schema + TestClient for each test function."""
    Base.metadata.create_all(bind=engine)
    with TestClient(app) as c:
        yield c
    Base.metadata.drop_all(bind=engine)


@pytest.fixture()
def test_user_data():
    return {
        "username": "testuser",
        "email": "testuser@example.com",
        "password": "password123",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture()
def auth_headers(client, test_user_data):
    """Signs up and logs in a user, returns ready-to-use auth headers."""
    client.post(f"{API_PREFIX}/users/signup", json=test_user_data)
    response = client.post(
        f"{API_PREFIX}/users/token",
        data={
            "username": test_user_data["username"],
            "password": test_user_data["password"],
        },
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def create_and_login(client, username):
    """Helper (not a fixture) for tests that need a SECOND distinct user."""
    user_data = {
        "username": username,
        "email": f"{username}@example.com",
        "password": "password123",
        "first_name": "Other",
        "last_name": "User",
    }
    client.post(f"{API_PREFIX}/users/signup", json=user_data)
    response = client.post(
        f"{API_PREFIX}/users/token",
        data={"username": username, "password": "password123"},
    )
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}