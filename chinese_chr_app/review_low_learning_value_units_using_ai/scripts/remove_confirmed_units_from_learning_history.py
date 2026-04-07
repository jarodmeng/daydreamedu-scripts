#!/usr/bin/env python3
"""Remove confirmed low-learning-value units from user learning-state/history tables."""

from __future__ import annotations

import argparse
from collections import defaultdict
from pathlib import Path
from typing import Any

from common import (
    CONFIRMED_TRUE_POSITIVES_JSON,
    DEFAULT_CANDIDATE_ARTIFACT,
    DEFAULT_HISTORY_CLEANUP_SUMMARY,
    load_confirmed_units_with_candidates,
    load_env_local,
    save_json,
    utc_timestamp_slug,
)


def _import_psycopg():
    try:
        import psycopg
        from psycopg import sql

        return psycopg, sql
    except ImportError as exc:
        raise SystemExit("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'") from exc


def get_connection():
    import os

    load_env_local()
    psycopg, _sql = _import_psycopg()
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise SystemExit("DATABASE_URL or SUPABASE_DB_URL is not set.")
    return psycopg.connect(url)


def build_priority_cleanup_map(
    confirmed_units: list[dict[str, Any]],
) -> dict[str, list[str]]:
    grouped: dict[str, set[str]] = defaultdict(set)
    for row in confirmed_units:
        character = str(row.get("character") or "").strip()
        reading_display = str(row.get("reading_display") or "").strip()
        reading_key = str(row.get("reading_key") or "").strip()
        if not character:
            raise ValueError(f"Confirmed unit missing character: {row}")
        if reading_display:
            grouped[character].add(reading_display)
        if reading_key:
            grouped[character].add(reading_key)
    return {character: sorted(values) for character, values in grouped.items()}


def create_backup_table(cur: Any, sql_module: Any, source_table: str, backup_table: str) -> None:
    cur.execute(
        sql_module.SQL("CREATE TABLE {} AS SELECT * FROM {}").format(
            sql_module.Identifier(backup_table),
            sql_module.Identifier(source_table),
        )
    )


def count_rows_matching_unit_ids(cur: Any, table_name: str, unit_ids: list[str]) -> int:
    cur.execute(f"SELECT COUNT(*) FROM {table_name} WHERE unit_id = ANY(%s)", (unit_ids,))
    return int(cur.fetchone()[0])


def cleanup_learning_history(
    confirmed_units: list[dict[str, Any]],
    *,
    apply_changes: bool,
) -> dict[str, Any]:
    psycopg, sql_module = _import_psycopg()
    del psycopg

    unit_ids = sorted({str(row.get("unit_id") or "").strip() for row in confirmed_units if str(row.get("unit_id") or "").strip()})
    if not unit_ids:
        raise ValueError("No unit_ids found in confirmed units.")
    priority_cleanup_map = build_priority_cleanup_map(confirmed_units)

    conn = get_connection()
    timestamp = utc_timestamp_slug()
    backup_tables = {
        "pinyin_recall_unit_bank": f"pinyin_recall_unit_bank_backup_{timestamp}",
        "pinyin_recall_item_presented": f"pinyin_recall_item_presented_backup_{timestamp}",
        "pinyin_recall_item_answered": f"pinyin_recall_item_answered_backup_{timestamp}",
        "user_prioritized_characters": f"user_prioritized_characters_backup_{timestamp}",
    }

    summary = {
        "confirmed_units_count": len(unit_ids),
        "removed_unit_ids": unit_ids,
        "backups": {},
        "deleted_rows": {
            "pinyin_recall_unit_bank": 0,
            "pinyin_recall_item_presented": 0,
            "pinyin_recall_item_answered": 0,
            "user_prioritized_characters": 0,
        },
        "priority_cleanup_map": priority_cleanup_map,
        "mode": "apply" if apply_changes else "dry_run",
    }

    try:
        with conn.cursor() as cur:
            for table_name in ("pinyin_recall_unit_bank", "pinyin_recall_item_presented", "pinyin_recall_item_answered"):
                summary["deleted_rows"][table_name] = count_rows_matching_unit_ids(cur, table_name, unit_ids)

            priority_count = 0
            for character, readings in priority_cleanup_map.items():
                cur.execute(
                    """
                    SELECT COUNT(*)
                    FROM user_prioritized_characters
                    WHERE character = %s
                      AND reading = ANY(%s)
                    """,
                    (character, readings),
                )
                priority_count += int(cur.fetchone()[0])
            summary["deleted_rows"]["user_prioritized_characters"] = priority_count

            if not apply_changes:
                return summary

            for source_table, backup_table in backup_tables.items():
                create_backup_table(cur, sql_module, source_table, backup_table)
                summary["backups"][source_table] = backup_table
            conn.commit()

            cur.execute("DELETE FROM pinyin_recall_unit_bank WHERE unit_id = ANY(%s)", (unit_ids,))
            summary["deleted_rows"]["pinyin_recall_unit_bank"] = cur.rowcount

            cur.execute("DELETE FROM pinyin_recall_item_presented WHERE unit_id = ANY(%s)", (unit_ids,))
            summary["deleted_rows"]["pinyin_recall_item_presented"] = cur.rowcount

            cur.execute("DELETE FROM pinyin_recall_item_answered WHERE unit_id = ANY(%s)", (unit_ids,))
            summary["deleted_rows"]["pinyin_recall_item_answered"] = cur.rowcount

            priority_deleted = 0
            for character, readings in priority_cleanup_map.items():
                cur.execute(
                    """
                    DELETE FROM user_prioritized_characters
                    WHERE character = %s
                      AND reading = ANY(%s)
                    """,
                    (character, readings),
                )
                priority_deleted += cur.rowcount
            summary["deleted_rows"]["user_prioritized_characters"] = priority_deleted
            conn.commit()
            return summary
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove confirmed low-learning-value units from Pinyin Recall learning-state/history tables.",
    )
    parser.add_argument("--confirmed-json", type=Path, default=CONFIRMED_TRUE_POSITIVES_JSON)
    parser.add_argument("--candidate-artifact", type=Path, default=DEFAULT_CANDIDATE_ARTIFACT)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_HISTORY_CLEANUP_SUMMARY)
    parser.add_argument("--apply", action="store_true", help="Create Supabase backups and delete matching rows.")
    args = parser.parse_args()

    confirmed_units = load_confirmed_units_with_candidates(args.confirmed_json, args.candidate_artifact)
    summary = cleanup_learning_history(confirmed_units, apply_changes=args.apply)
    save_json(args.summary_json, summary)
    print(
        "Learning-history cleanup "
        f"({summary['mode']}): unit_bank={summary['deleted_rows']['pinyin_recall_unit_bank']} "
        f"presented={summary['deleted_rows']['pinyin_recall_item_presented']} "
        f"answered={summary['deleted_rows']['pinyin_recall_item_answered']} "
        f"priorities={summary['deleted_rows']['user_prioritized_characters']}"
    )
    if summary["backups"]:
        print(f"Supabase backups: {summary['backups']}")
    print(f"Summary: {args.summary_json}")


if __name__ == "__main__":
    main()
