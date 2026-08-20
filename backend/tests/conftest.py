"""
Tests run against a real PostgreSQL database (not SQLite, not mocks) - the
same code path production uses, including the FOR UPDATE SKIP LOCKED
queries and unique constraints that this project's correctness depends on.
SQLite doesn't support those the same way, so faking the DB layer here
would let bugs through that only show up on Postgres.

Before running tests you need a Postgres database for them to use. See the
README "Running tests" section. By default we point at
`postgresql+psycopg2://linkplease:linkplease@localhost:5432/linkplease_test`;
override with the TEST_DATABASE_URL environment variable.
"""
import os

os.environ.setdefault(
    "DATABASE_URL",
    os.environ.get(
        "TEST_DATABASE_URL",
        "postgresql+psycopg2://linkplease:1234@localhost:5432/linkplease_test",
    ),
)
os.environ.setdefault("MOCK_API_KEY", "test-mock-api-key")

import pytest
from fastapi.testclient import TestClient

from app.database.session import Base, engine, SessionLocal
import app.models  # noqa: F401 - registers tables on Base.metadata
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _create_schema():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture(autouse=True)
def _clean_tables():
    """Runs before every test so tests don't see each other's data."""
    with SessionLocal() as db:
        for table in reversed(Base.metadata.sorted_tables):
            db.execute(table.delete())
        db.commit()
    yield


@pytest.fixture
def db():
    with SessionLocal() as session:
        yield session


@pytest.fixture
def client():
    return TestClient(app)
