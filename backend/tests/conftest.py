import os
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, StaticPool
from sqlalchemy.orm import sessionmaker

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret-key-for-testing"

from backend.database import Base, get_db
from backend.main import app

test_engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSession = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


def override_get_db():
    db = TestSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=test_engine)
    yield
    Base.metadata.drop_all(bind=test_engine)


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def test_user(client):
    res = client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "testpass123",
        "name": "Test User",
    })
    data = res.json()
    return {
        "id": data["user_id"],
        "token": data["access_token"],
        "email": "test@example.com",
        "name": "Test User",
    }


@pytest.fixture
def second_user(client):
    res = client.post("/api/v1/auth/register", json={
        "email": "other@example.com",
        "password": "otherpass123",
        "name": "Other User",
    })
    data = res.json()
    return {
        "id": data["user_id"],
        "token": data["access_token"],
        "email": "other@example.com",
        "name": "Other User",
    }
