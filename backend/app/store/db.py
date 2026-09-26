"""SQLite persistence for users, projects and versions (INF-6, PRD §12).

stdlib sqlite3 only. The database path comes from DATABASE_PATH at call time
(compose sets /data/sketchbuild.db); the default is backend/data/sketchbuild.db.
The parent directory and the tables are created lazily on the first connection,
so there is no main.py startup hook.
"""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.config import REPO_ROOT

DEFAULT_DB_PATH = REPO_ROOT / "backend" / "data" / "sketchbuild.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    auth0_sub TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    owner_id INTEGER NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    template TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    thumb_png TEXT
);

CREATE TABLE IF NOT EXISTS versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id INTEGER NOT NULL REFERENCES projects(id),
    n INTEGER NOT NULL,
    spec_json TEXT NOT NULL,
    source TEXT NOT NULL,
    created_at TEXT NOT NULL,
    UNIQUE(project_id, n)
);

CREATE INDEX IF NOT EXISTS idx_projects_owner ON projects(owner_id);
CREATE INDEX IF NOT EXISTS idx_versions_project ON versions(project_id);
"""


def db_path() -> Path:
    """Read DATABASE_PATH at call time so tests can point it at a tmp_path."""
    value = os.environ.get("DATABASE_PATH")
    return Path(value) if value else DEFAULT_DB_PATH


def now_iso() -> str:
    """UTC timestamp, ISO 8601 with a trailing Z."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def connect() -> sqlite3.Connection:
    """Open a connection, creating the parent directory and tables lazily."""
    path = db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(_SCHEMA)
    return conn
