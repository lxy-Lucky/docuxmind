import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from app.core.config import settings

_init_lock = threading.Lock()
_initialised = False


def init_db() -> None:
    """Run init.sql idempotently. Safe to call on every startup."""
    global _initialised
    with _init_lock:
        if _initialised:
            return
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        sql_path = Path(__file__).parent / "init.sql"
        with sqlite3.connect(settings.db_path) as conn:
            conn.executescript(sql_path.read_text(encoding="utf-8"))
        _initialised = True


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(
        settings.db_path,
        check_same_thread=False,
        timeout=10.0,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    """Short-lived connection per unit of work. WAL mode handles concurrency."""
    conn = _connect()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
