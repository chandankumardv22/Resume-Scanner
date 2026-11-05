# ==============================================================================
# TECH STACK: [SQLAlchemy 2.0 Engine & Session Management]
# Cloud Database Adapter supporting Amazon RDS PostgreSQL & SQLite
# ==============================================================================
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from logger import logger
from models import Base

_DATABASE_URL = os.getenv("DATABASE_URL", "").strip()

# Normalize Heroku/AWS legacy 'postgres://' scheme to SQLAlchemy 'postgresql://'
if _DATABASE_URL.startswith("postgres://"):
    _DATABASE_URL = _DATABASE_URL.replace("postgres://", "postgresql://", 1)

_engine = None
_SessionFactory = None

if _DATABASE_URL:
    try:
        connect_args = {}
        if _DATABASE_URL.startswith("sqlite"):
            connect_args["check_same_thread"] = False

        _engine = create_engine(
            _DATABASE_URL,
            connect_args=connect_args,
            pool_pre_ping=True,
            echo=False,
        )
        _SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        logger.info(f"[Database] Configured relational database connection: {_DATABASE_URL.split('@')[-1] if '@' in _DATABASE_URL else 'local'}")
    except Exception as exc:
        logger.error(f"[Database] Failed to initialize engine: {exc}")
        _engine = None
        _SessionFactory = None


def is_database_configured() -> bool:
    """Returns True if a relational database (PostgreSQL/SQLite) is configured and active."""
    return _engine is not None and _SessionFactory is not None


def init_db() -> bool:
    """Creates database schema and tables if relational database is enabled."""
    if not is_database_configured():
        return False
    try:
        Base.metadata.create_all(bind=_engine)
        logger.info("[Database] Schema tables initialized successfully.")
        return True
    except Exception as exc:
        logger.error(f"[Database] Error during schema initialization: {exc}")
        return False


@contextmanager
def get_db_session() -> Generator[Session | None, None, None]:
    """Context manager yielding a transactional database session."""
    if not is_database_configured():
        yield None
        return

    session: Session = _SessionFactory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db() -> Generator[Session | None, None, None]:
    """FastAPI dependency for injecting database session into route handlers."""
    with get_db_session() as session:
        yield session