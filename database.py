"""Database layer. Uniqueness is enforced at the DB level as well as in code,
so duplicates cannot slip in even under concurrent requests."""
import os
import sqlite3

DB_PATH = os.environ.get("DB_PATH", "records.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT NOT NULL,
    email        TEXT NOT NULL,
    phone        TEXT,
    name_norm    TEXT NOT NULL,
    email_norm   TEXT NOT NULL UNIQUE,
    phone_norm   TEXT,
    fingerprint  TEXT NOT NULL UNIQUE,
    created_at   TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_records_phone
    ON records(phone_norm) WHERE phone_norm IS NOT NULL AND phone_norm != '';

CREATE TABLE IF NOT EXISTS rejected_log (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    payload        TEXT NOT NULL,
    classification TEXT NOT NULL,
    reason         TEXT NOT NULL,
    matched_id     INTEGER,
    created_at     TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


def get_conn(path: str = None) -> sqlite3.Connection:
    conn = sqlite3.connect(path or DB_PATH, timeout=10, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(path: str = None):
    conn = get_conn(path)
    conn.executescript(SCHEMA)
    conn.close()
