"""SQLite engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from config import get_settings
from models import Base

BACKEND_DIR = Path(__file__).resolve().parent


def _resolve_url(url: str) -> str:
    """Anchor relative SQLite paths to the backend directory.

    This keeps ``sqlite:///./scoutly.db`` pointing at the same file whether the
    server is started from ``backend/`` or from the repository root.
    """
    prefix = "sqlite:///"
    if url.startswith(prefix) and not url.startswith("sqlite:////"):
        raw_path = url[len(prefix) :]
        if raw_path in {":memory:", ""}:
            return url
        candidate = Path(raw_path)
        if not candidate.is_absolute():
            candidate = (BACKEND_DIR / candidate).resolve()
            return f"sqlite:///{candidate.as_posix()}"
    return url


_settings = get_settings()
DATABASE_URL = _resolve_url(_settings.database_url)

_connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=_connect_args, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


def init_db() -> None:
    """Create all tables if they do not exist yet."""
    Base.metadata.create_all(bind=engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency yielding a scoped SQLAlchemy session."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@contextmanager
def session_scope() -> Iterator[Session]:
    """Context manager for use outside request handlers (seed, tests)."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
