"""
Quick way to create all tables without running Alembic migrations.
Useful for local dev / a fresh test database. For anything you'd call
"production", use `alembic upgrade head` instead so schema changes are
tracked and reversible.

Run with:  python -m scripts.create_tables
"""
from app.database.session import Base, engine
import app.models  # noqa: F401 - registers all models on Base.metadata

if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    print("Tables created.")
