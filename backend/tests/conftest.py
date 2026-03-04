"""
Test configuration and fixtures.
Uses SQLite in-memory for fast, isolated tests.
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from sqlalchemy.ext.compiler import compiles

from app.database import Base, get_db
from app.main import app
from app.auth.security import hash_password
from app.models.user import User
import uuid

# Disable rate limiters in tests
# The auth router has its own limiter instance, separate from app.state.limiter.
# Both must be disabled to prevent rate limiting during test runs.
app.state.limiter.enabled = False
from app.auth.router import limiter as _auth_limiter
_auth_limiter.enabled = False


SQLALCHEMY_TEST_URL = "sqlite://"

# ── SQLite type compatibility ──────────────────────────────────────────────
# PostgreSQL-specific types must compile to SQLite equivalents for tests.

from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.dialects.postgresql import ARRAY as PG_ARRAY


@compiles(JSONB, "sqlite")
def compile_jsonb_sqlite(element, compiler, **kw):
    return "JSON"


@compiles(TSVECTOR, "sqlite")
def compile_tsvector_sqlite(element, compiler, **kw):
    return "TEXT"


@compiles(PG_ARRAY, "sqlite")
def compile_pgarray_sqlite(element, compiler, **kw):
    return "TEXT"


# sqlalchemy core ARRAY (used in campaign.py)
from sqlalchemy import ARRAY as SA_ARRAY


@compiles(SA_ARRAY, "sqlite")
def compile_saarray_sqlite(element, compiler, **kw):
    return "TEXT"


# ── UUID bind/result processor fix for SQLite ─────────────────────────────
# SQLAlchemy's Uuid.bind_processor calls value.hex on non-native dialects.
# But auth code extracts user_id from JWT as a plain string. We patch the
# Uuid type's bind processor to handle strings gracefully on SQLite.
import uuid as _uuid_mod
from sqlalchemy.sql import sqltypes as _sa_sqltypes

_orig_uuid_bind_processor = _sa_sqltypes.Uuid.bind_processor


def _patched_uuid_bind_processor(self, dialect):
    character_based = not getattr(dialect, "supports_native_uuid", True) or not getattr(self, "native_uuid", True)
    if character_based:
        if getattr(self, "as_uuid", True):
            def process(value):
                if value is None:
                    return None
                if isinstance(value, _uuid_mod.UUID):
                    return value.hex
                # value is already a string — normalise to hex for SQLite
                try:
                    return _uuid_mod.UUID(str(value)).hex
                except (ValueError, AttributeError):
                    return str(value)
            return process
    # Fall back to original (e.g. for native-UUID dialects like PostgreSQL)
    return _orig_uuid_bind_processor(self, dialect)


_sa_sqltypes.Uuid.bind_processor = _patched_uuid_bind_processor


# ── ARRAY bind/result processor fix for SQLite ────────────────────────────
# SQLite can't store Python lists. We serialise ARRAY values to JSON strings
# for both INSERT and SELECT, mirroring how JSON columns work.
import json as _json_mod

from sqlalchemy import ARRAY as _SA_ARRAY_CLS
from sqlalchemy.dialects.postgresql import ARRAY as _PG_ARRAY_CLS

def _make_array_bind_processor(original_method):
    def patched_bind_processor(self, dialect):
        if not getattr(dialect, "supports_native_uuid", True) or dialect.name == "sqlite":
            def process(value):
                if value is None:
                    return None
                if isinstance(value, (list, tuple)):
                    return _json_mod.dumps([str(v) if v is not None else None for v in value])
                return value
            return process
        return original_method(self, dialect)
    return patched_bind_processor

def _make_array_result_processor(original_method):
    def patched_result_processor(self, dialect, coltype):
        if dialect.name == "sqlite":
            def process(value):
                if value is None:
                    return None
                if isinstance(value, str):
                    try:
                        return _json_mod.loads(value)
                    except (ValueError, TypeError):
                        return value
                return value
            return process
        return original_method(self, dialect, coltype)
    return patched_result_processor

for _arr_cls in (_SA_ARRAY_CLS, _PG_ARRAY_CLS):
    if hasattr(_arr_cls, "bind_processor"):
        _arr_cls.bind_processor = _make_array_bind_processor(_arr_cls.bind_processor)
    if hasattr(_arr_cls, "result_processor"):
        _arr_cls.result_processor = _make_array_result_processor(_arr_cls.result_processor)


# ── Engine & Session ───────────────────────────────────────────────────────

from sqlalchemy import event as sa_event

engine = create_engine(
    SQLALCHEMY_TEST_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)


@sa_event.listens_for(engine, "before_cursor_execute", retval=True)
def _strip_pg_ddl_for_sqlite(conn, cursor, statement, parameters, context, executemany):
    """Strip PostgreSQL-specific DDL keywords that SQLite doesn't understand."""
    if "DEFERRABLE" in statement:
        statement = statement.replace(" DEFERRABLE INITIALLY DEFERRED", "")
        statement = statement.replace(" DEFERRABLE INITIALLY IMMEDIATE", "")
        statement = statement.replace(" DEFERRABLE", "")
    if "NOT DEFERRABLE" in statement:
        statement = statement.replace(" NOT DEFERRABLE", "")
    return statement, parameters
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


@pytest.fixture
def member_token(client, member_user) -> str:
    resp = client.post("/api/v1/auth/login", json={
        "email": "member@sarsonfunds.com",
        "password": "Member123!",
    })
    assert resp.status_code == 200, f"Member login failed: {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture
def member_headers(member_token) -> dict:
    return {"Authorization": f"Bearer {member_token}"}
