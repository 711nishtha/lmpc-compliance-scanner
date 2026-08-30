"""SQLAlchemy engine/session. Defaults to a local SQLite file; set DATABASE_URL for Postgres
(e.g. postgresql+psycopg2://user:pass@host/db) — swappable via a single env var, per the build
spec, so Postgres friction never blocks the demo."""
from __future__ import annotations

import logging
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

DEFAULT_SQLITE_PATH = Path(__file__).resolve().parents[1] / "data" / "compliance.db"
DEFAULT_SQLITE_PATH.parent.mkdir(parents=True, exist_ok=True)

DATABASE_URL = os.environ.get("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")

connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create tables directly — DEVELOPMENT ONLY.

    Alembic owns the schema (see backend/alembic/). In production the schema must be applied with
    `alembic upgrade head` so that local dev and any redeployed instance cannot drift apart;
    create_all() would happily build a schema no migration describes. This stays for zero-friction
    local/demo startup only.
    """
    from app.config import IS_PRODUCTION

    from app.models import orm  # noqa: F401  (registers models on Base.metadata)

    if IS_PRODUCTION:
        logging.getLogger(__name__).info(
            "APP_ENV=production — skipping create_all(); apply schema with `alembic upgrade head`."
        )
        return
    Base.metadata.create_all(bind=engine)
