"""Soft-delete marking_artifacts rows with no on-disk marking_results JSON.

One-off cleanup: DB rows whose artifact_path has no file under context/marking_results/.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from pathlib import Path

from ai_study_buddy.learning_db.core.connection import default_context_root, default_db_path, get_connection

DELETE_REASON = "json_missing_orphan"


def _list_db_only_paths(*, context_root: Path, conn) -> list[str]:
    json_paths = {
        p.relative_to(context_root).as_posix()
        for p in (context_root / "marking_results").rglob("*.json")
    }
    rows = conn.execute(
        """
        SELECT artifact_path
        FROM marking_artifacts
        WHERE is_deleted = 0
        ORDER BY artifact_path
        """
    ).fetchall()
    return [str(r["artifact_path"]) for r in rows if r["artifact_path"] not in json_paths]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db-path", type=Path, default=None)
    parser.add_argument("--context-root", type=Path, default=None)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Apply soft-delete (default is dry-run only).",
    )
    args = parser.parse_args()

    context_root = args.context_root or default_context_root()
    db_path = args.db_path or default_db_path()
    conn = get_connection(db_path)
    try:
        targets = _list_db_only_paths(context_root=context_root, conn=conn)
        print(f"context_root={context_root}")
        print(f"db_path={db_path}")
        print(f"db_only_active_rows={len(targets)}")
        for path in targets:
            print(f"  would_soft_delete: {path}")

        if not args.execute:
            print("\nDry-run only. Re-run with --execute to soft-delete.")
            return 0

        if not targets:
            print("\nNothing to soft-delete.")
            return 0

        deleted_at = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        conn.executemany(
            """
            UPDATE marking_artifacts
            SET is_deleted = 1,
                deleted_at = ?,
                deleted_by = 'cli:_prune_db_only_marking_artifacts',
                delete_reason = ?,
                row_version = row_version + 1
            WHERE artifact_path = ? AND is_deleted = 0
            """,
            [(deleted_at, DELETE_REASON, path) for path in targets],
        )
        conn.commit()

        remaining_active = conn.execute(
            "SELECT COUNT(*) AS c FROM marking_artifacts WHERE is_deleted = 0"
        ).fetchone()["c"]
        json_count = len(
            list((context_root / "marking_results").rglob("*.json"))
        )
        print(f"\nSoft-deleted {len(targets)} rows.")
        print(f"Active marking_artifacts rows: {remaining_active}")
        print(f"On-disk marking_results JSON files: {json_count}")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
