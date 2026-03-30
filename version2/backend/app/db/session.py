"""
Database session factory and FastAPI dependency.
Uses synchronous SQLAlchemy with psycopg2 (psycopg2-binary).
"""
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

from config import settings

# ---------------------------------------------------------------------------
# Engine — synchronous (psycopg2) to keep uvicorn compat simple
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
    echo=settings.DEBUG,
)

SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def get_db() -> Generator[Session, None, None]:
    """Yield a SQLAlchemy session and guarantee it is closed after each request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
