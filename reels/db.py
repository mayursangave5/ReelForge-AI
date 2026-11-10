from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from .config import DB_PATH

SCHEMA_VERSION = 3

SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS topics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_hash TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    source TEXT,
    url TEXT,
    score REAL NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'new',
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    published_at TEXT
);

CREATE TABLE IF NOT EXISTS scripts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    topic_id INTEGER REFERENCES topics(id),
    language TEXT NOT NULL DEFAULT 'hi',
    hook TEXT,
    scenes_json TEXT NOT NULL,
    model TEXT,
    style TEXT NOT NULL DEFAULT '3d_cartoon',
    storyboard_json TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS videos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    script_id INTEGER REFERENCES scripts(id),
    run_id TEXT NOT NULL UNIQUE,
    path TEXT NOT NULL,
    duration_s REAL,
    width INTEGER,
    height INTEGER,
    style TEXT,
    quality_score REAL,
    quality_report_json TEXT,
    status TEXT NOT NULL DEFAULT 'rendered',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS captions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER REFERENCES videos(id),
    platform TEXT NOT NULL,
    title TEXT,
    caption TEXT,
    hashtags TEXT,
    tags TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (video_id, platform)
);

CREATE TABLE IF NOT EXISTS publications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER REFERENCES videos(id),
    platform TEXT NOT NULL,
    remote_id TEXT,
    url TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    idempotency_key TEXT NOT NULL UNIQUE,
    error TEXT,
    published_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER REFERENCES videos(id),
    platform TEXT NOT NULL,
    captured_on TEXT NOT NULL,
    views INTEGER,
    likes INTEGER,
    comments INTEGER,
    shares INTEGER,
    retention REAL,
    raw_json TEXT,
    fetched_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (video_id, platform, captured_on)
);

CREATE TABLE IF NOT EXISTS cloud_uploads (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id INTEGER REFERENCES videos(id),
    key TEXT NOT NULL UNIQUE,
    url TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',
    error TEXT,
    uploaded_at TEXT NOT NULL DEFAULT (datetime('now')),
    deleted_at TEXT
);

CREATE TABLE IF NOT EXISTS errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    stage TEXT NOT NULL,
    message TEXT NOT NULL,
    context TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


@contextmanager
def session(path: Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    conn = connect(path)
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_column(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> None:
    cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
    if column not in cols:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")


def init_db(path: Path = DB_PATH) -> Path:
    with session(path) as conn:
        conn.executescript(SCHEMA)
        # Migrate existing tables if needed
        _ensure_column(conn, "scripts", "style", "TEXT NOT NULL DEFAULT '3d_cartoon'")
        _ensure_column(conn, "scripts", "storyboard_json", "TEXT")
        _ensure_column(conn, "videos", "style", "TEXT")
        _ensure_column(conn, "videos", "quality_score", "REAL")
        _ensure_column(conn, "videos", "quality_report_json", "TEXT")

        row = conn.execute("SELECT version FROM schema_version").fetchone()
        if row is None:
            conn.execute("INSERT INTO schema_version (version) VALUES (?)", (SCHEMA_VERSION,))
        elif row["version"] < SCHEMA_VERSION:
            conn.execute("UPDATE schema_version SET version = ?", (SCHEMA_VERSION,))
    return path


def topic_hash(title: str) -> str:
    normalized = " ".join(title.lower().split())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def was_published(title: str, path: Path = DB_PATH) -> bool:
    with session(path) as conn:
        row = conn.execute(
            "SELECT 1 FROM topics WHERE topic_hash = ? AND status = 'published'",
            (topic_hash(title),),
        ).fetchone()
    return row is not None


def log_error(stage: str, message: str, context: Any = None, path: Path = DB_PATH) -> None:
    with session(path) as conn:
        conn.execute(
            "INSERT INTO errors (stage, message, context) VALUES (?, ?, ?)",
            (stage, message, json.dumps(context, ensure_ascii=False) if context is not None else None),
        )


def set_setting(key: str, value: str, path: Path = DB_PATH) -> None:
    with session(path) as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


def get_setting(key: str, default: str | None = None, path: Path = DB_PATH) -> str | None:
    with session(path) as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
    return row["value"] if row else default
