"""
SQLAlchemy engine + session factory.

We use a plain synchronous SQLAlchemy session (not the async flavor).
FastAPI runs regular `def` route functions in a thread pool automatically,
so sync DB calls don't block the event loop. This keeps the code much
simpler to read for anyone not already familiar with async SQLAlchemy.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a DB session and always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
