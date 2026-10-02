"""SQLite connection helpers. No ORM: the schema is small and explicit SQL
keeps the deterministic/LLM boundary easy to audit (see spec §4.1).
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path

from app.config import settings

SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def _connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path or settings.db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: Path | str | None = None) -> None:
    """Create all tables/indexes/FTS5 virtual tables if they don't exist."""
    conn = _connect(db_path)
    try:
        conn.executescript(SCHEMA_PATH.read_text())
        conn.commit()
    finally:
        conn.close()


@contextmanager
def get_db(db_path: Path | str | None = None):
    """Context manager yielding a connection; commits on success, rolls
    back on exception. Use as `with get_db() as db:`.
    """
    conn = _connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
