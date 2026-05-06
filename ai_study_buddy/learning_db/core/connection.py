from __future__ import annotations

import os
import sqlite3
from pathlib import Path


def _repo_root() -> Path:
    p = Path(__file__).resolve().parent
    for _ in range(6):
        if (p / "ai_study_buddy").is_dir():
            return p
        p = p.parent
    return Path.cwd()


def default_db_path() -> Path:
    env = os.environ.get("STUDY_BUDDY_DB_PATH", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return _repo_root() / "ai_study_buddy" / "db" / "study_buddy.db"


def default_context_root() -> Path:
    env = os.environ.get("STUDY_BUDDY_CONTEXT_ROOT", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return _repo_root() / "ai_study_buddy" / "context"


def get_connection(db_path: Path | str | None = None) -> sqlite3.Connection:
    resolved = Path(db_path).expanduser().resolve() if db_path else default_db_path()
    resolved.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(resolved))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

