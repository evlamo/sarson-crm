"""
Test configuration and fixtures.
Uses SQLite in-memory for fast, isolated tests.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.auth.security import hash_password
from app.models.user import User
import uuid


SQLALCHEMY_TEST_URL = "sqlite://"

engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(autouse=True)
def setup_db():
    """Create all tables before each test, drop after."""
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def db():
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        try:
            yield db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def admin_user(db) -> User:
    user = User(
        id=uuid.uuid4(),
        email="admin@sarsonfunds.com",
        name="Admin User",
        hashed_password=hash_password("Admin123!"),
        role="admin",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def member_user(db) -> User:
    user = User(
        id=uuid.uuid4(),
        email="member@sarsonfunds.com",
        name="Member User",
        hashed_password=hash_password("Member123!"),
        role="member",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_token(client, admin_user) -> str:
    resp = client.post("/api/v1/auth/login", json={
        "email": "admin@sarsonfunds.com",
        "password": "Admin123!",
    })
    return resp.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token) -> dict:
    return {"Authorization": f"Bearer {admin_token}"}
