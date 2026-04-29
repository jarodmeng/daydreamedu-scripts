#!/usr/bin/env python3
from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_study_buddy.learning_db.connection import default_db_path, get_connection
from ai_study_buddy.learning_db.migrate import apply_migrations

SINGAPORE_TZ = ZoneInfo("Asia/Singapore")


@dataclass
class Stats:
    total: int
    succeeded: int
    failed: int
    started: int

    @property
    def success_rate(self) -> float:
        denom = self.succeeded + self.failed
        if denom <= 0:
            return 0.0
        return self.succeeded / denom


def _parse_since(hours: int | None, since_iso: str | None) -> str | None:
    if since_iso:
        # Validate timestamp early so CLI errors are explicit.
        datetime.fromisoformat(since_iso)
        return since_iso
    if hours is None:
        return None
    return (datetime.now(SINGAPORE_TZ) - timedelta(hours=hours)).isoformat()


def _base_where(since: str | None) -> tuple[str, tuple]:
    where = "operation_type = ?"
    params: list[object] = ["dual_write_snapshot"]
    if since is not None:
        where += " AND occurred_at >= ?"
        params.append(since)
    return where, tuple(params)


def _fetch_stats(db_path: Path, since: str | None) -> tuple[Stats, list[tuple[str, Stats]]]:
    apply_migrations(db_path=db_path)
    conn = get_connection(db_path)
    try:
        where, params = _base_where(since)
        row = conn.execute(
            f"""
            SELECT
              COUNT(*) AS total,
              SUM(CASE WHEN status='succeeded' THEN 1 ELSE 0 END) AS succeeded,
              SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,
              SUM(CASE WHEN status='started' THEN 1 ELSE 0 END) AS started
            FROM operation_log
            WHERE {where}
            """,
            params,
        ).fetchone()
        overall = Stats(
            total=int(row["total"] or 0),
            succeeded=int(row["succeeded"] or 0),
            failed=int(row["failed"] or 0),
            started=int(row["started"] or 0),
        )

        fam_rows = conn.execute(
            f"""
            SELECT
              COALESCE(entity_type, 'unknown') AS family,
              COUNT(*) AS total,
              SUM(CASE WHEN status='succeeded' THEN 1 ELSE 0 END) AS succeeded,
              SUM(CASE WHEN status='failed' THEN 1 ELSE 0 END) AS failed,
              SUM(CASE WHEN status='started' THEN 1 ELSE 0 END) AS started
            FROM operation_log
            WHERE {where}
            GROUP BY COALESCE(entity_type, 'unknown')
            ORDER BY family
            """,
            params,
        ).fetchall()
        by_family = [
            (
                str(r["family"]),
                Stats(
                    total=int(r["total"] or 0),
                    succeeded=int(r["succeeded"] or 0),
                    failed=int(r["failed"] or 0),
                    started=int(r["started"] or 0),
                ),
            )
            for r in fam_rows
        ]
        return overall, by_family
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="Report dual-write success/failure stats from operation_log.")
    parser.add_argument("--db-path", help="Optional DB path override.")
    parser.add_argument(
        "--hours",
        type=int,
        help="Only include operations in the trailing N hours (SGT wall clock).",
    )
    parser.add_argument(
        "--since-iso",
        help="Only include operations since this ISO timestamp (overrides --hours).",
    )
    parser.add_argument(
        "--target-min-ops",
        type=int,
        default=200,
        help="Gate threshold for minimum operation count (default: 200).",
    )
    parser.add_argument(
        "--target-success-rate",
        type=float,
        default=0.999,
        help="Gate threshold for success rate over succeeded+failed operations (default: 0.999).",
    )
    args = parser.parse_args()

    db_path = Path(args.db_path).expanduser().resolve() if args.db_path else default_db_path()
    since = _parse_since(args.hours, args.since_iso)
    overall, by_family = _fetch_stats(db_path=db_path, since=since)

    scope = f"since {since}" if since else "all-time"
    print(f"Dual-write stats ({scope})")
    print(
        f"- overall: total={overall.total} succeeded={overall.succeeded} failed={overall.failed} "
        f"started={overall.started} success_rate={overall.success_rate:.4%}"
    )
    for family, item in by_family:
        print(
            f"- family[{family}]: total={item.total} succeeded={item.succeeded} failed={item.failed} "
            f"started={item.started} success_rate={item.success_rate:.4%}"
        )

    op_gate_ok = overall.total >= int(args.target_min_ops)
    rate_gate_ok = overall.success_rate >= float(args.target_success_rate)
    print(
        f"- gate_check: min_ops({args.target_min_ops})={'PASS' if op_gate_ok else 'FAIL'} "
        f"success_rate({args.target_success_rate:.4%})={'PASS' if rate_gate_ok else 'FAIL'}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
