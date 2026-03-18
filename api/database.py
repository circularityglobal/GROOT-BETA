"""
REFINET Cloud — Database Layer
Two physically separate SQLite databases in WAL mode.
public.db  → user-facing data (accessible via API)
internal.db → admin-only data (NEVER exposed via public API)
"""

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session, DeclarativeBase
from contextlib import contextmanager
from typing import Generator

from api.config import get_settings


class PublicBase(DeclarativeBase):
    """Base class for all public database models."""
    pass


class InternalBase(DeclarativeBase):
    """Base class for all internal database models."""
    pass


def _enable_wal_mode(dbapi_conn, connection_record):
    """Enable WAL mode and performance pragmas for SQLite."""
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.execute("PRAGMA cache_size=-32000")  # 32MB page cache
    cursor.execute("PRAGMA temp_store=MEMORY")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def _create_engine(url: str):
    """Create a SQLAlchemy engine with SQLite WAL mode."""
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False},
        pool_pre_ping=True,
    )
    event.listen(engine, "connect", _enable_wal_mode)
    return engine


# Engines — created lazily on first access
_public_engine = None
_internal_engine = None
_PublicSessionLocal = None
_InternalSessionLocal = None


def get_public_engine():
    global _public_engine
    if _public_engine is None:
        settings = get_settings()
        _public_engine = _create_engine(settings.public_db_url)
    return _public_engine


def get_internal_engine():
    global _internal_engine
    if _internal_engine is None:
        settings = get_settings()
        _internal_engine = _create_engine(settings.internal_db_url)
    return _internal_engine


def get_public_session_factory():
    global _PublicSessionLocal
    if _PublicSessionLocal is None:
        _PublicSessionLocal = sessionmaker(
            bind=get_public_engine(),
            autocommit=False,
            autoflush=False,
        )
    return _PublicSessionLocal


def get_internal_session_factory():
    global _InternalSessionLocal
    if _InternalSessionLocal is None:
        _InternalSessionLocal = sessionmaker(
            bind=get_internal_engine(),
            autocommit=False,
            autoflush=False,
        )
    return _InternalSessionLocal


@contextmanager
def get_public_db() -> Generator[Session, None, None]:
    """Yield a public database session."""
    session = get_public_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def get_internal_db() -> Generator[Session, None, None]:
    """Yield an internal database session."""
    session = get_internal_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


# FastAPI dependency — yields session per request
def public_db_dependency() -> Generator[Session, None, None]:
    session = get_public_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def internal_db_dependency() -> Generator[Session, None, None]:
    session = get_internal_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_public_session() -> Generator[Session, None, None]:
    """
    Yield a public session for non-FastAPI contexts (GraphQL, SOAP, gRPC, WebSocket).
    Caller is responsible for calling .close() when done.
    """
    session = get_public_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_internal_session() -> Generator[Session, None, None]:
    """
    Yield an internal session for non-FastAPI contexts (monitoring, background tasks).
    Caller is responsible for calling .close() when done.
    """
    session = get_internal_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def create_public_session() -> Session:
    """Create a standalone public session (for scripts, not request-scoped)."""
    return get_public_session_factory()()


def init_databases():
    """Create all tables in both databases. Idempotent."""
    PublicBase.metadata.create_all(bind=get_public_engine())
    InternalBase.metadata.create_all(bind=get_internal_engine())
