from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_study_buddy.learning_db.connection import default_db_path, get_connection

SINGAPORE_TZ = ZoneInfo("Asia/Singapore")


def _migration_dir() -> Path:
    return Path(__file__).resolve().parent / "migrations"


def apply_migrations(db_path: Path | None = None) -> list[str]:
    conn = get_connection(db_path or default_db_path())
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            version TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL
        )
        """
    )
    applied = {row["version"] for row in conn.execute("SELECT version FROM schema_migrations")}
    applied_now: list[str] = []
    for sql_file in sorted(_migration_dir().glob("*.sql")):
        version = sql_file.name
        if version in applied:
            continue
        sql = sql_file.read_text(encoding="utf-8")
        with conn:
            conn.executescript(sql)
            conn.execute(
                "INSERT INTO schema_migrations(version, applied_at) VALUES (?, ?)",
                (version, datetime.now(SINGAPORE_TZ).isoformat()),
            )
        applied_now.append(version)
    conn.close()
    return applied_now


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply study_buddy.db migrations.")
    parser.add_argument("--db-path", help="Optional override DB path.")
    args = parser.parse_args()
    db_path = Path(args.db_path).expanduser().resolve() if args.db_path else default_db_path()
    applied = apply_migrations(db_path=db_path)
    if applied:
        print("Applied migrations:")
        for version in applied:
            print(f"- {version}")
    else:
        print("No pending migrations.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

