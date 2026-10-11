"""
FinSight — database.py
Per-session in-memory SQLite databases.
Each browser session gets its own isolated database — no data shared between users.
"""

import sqlite3
import threading

# Maps session_id -> sqlite3.Connection (in-memory)
_sessions: dict[str, sqlite3.Connection] = {}
_lock = threading.Lock()

CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS transactions (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        date        TEXT    NOT NULL,
        description TEXT    NOT NULL,
        amount      REAL    NOT NULL,
        type        TEXT    NOT NULL CHECK(type IN ('income','expense')),
        category    TEXT    NOT NULL DEFAULT 'Other'
    )
"""


def _new_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:", check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute(CREATE_TABLE)
    conn.commit()
    return conn


def get_connection(session_id: str = "default") -> sqlite3.Connection:
    """Return the persistent in-memory connection for this session."""
    with _lock:
        if session_id not in _sessions:
            _sessions[session_id] = _new_connection()
        return _sessions[session_id]


def init_db():
    """No-op — kept for compatibility. Sessions are created on first use."""
    pass
