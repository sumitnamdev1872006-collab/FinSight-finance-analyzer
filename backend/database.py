"""
FinSight — database.py
Sets up the SQLite database and creates the transactions table.
Uses Python's built-in sqlite3 — no ORM needed.
"""

import sqlite3
from pathlib import Path

DATABASE_FILE = str(Path(__file__).resolve().with_name("finsight.db"))


def get_connection():
    """Open and return a connection to the SQLite database."""
    conn = sqlite3.connect(DATABASE_FILE)
    conn.row_factory = sqlite3.Row   # rows behave like dicts
    return conn


def init_db():
    """Create the transactions table if it doesn't exist yet."""
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            date        TEXT    NOT NULL,
            description TEXT    NOT NULL,
            amount      REAL    NOT NULL,
            type        TEXT    NOT NULL CHECK(type IN ('income','expense')),
            category    TEXT    NOT NULL DEFAULT 'Other'
        )
    """)
    conn.commit()
    conn.close()
