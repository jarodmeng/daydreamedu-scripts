#!/usr/bin/env python3
"""
Backfill category for pinyin_recall_item_answered using item_answered data only.

Category is derived from chronological order per (user_id, character):
- 新字: First answer ever for this (user_id, character)
- 巩固: Prior answers exist, all were correct
- 重测: Prior answers exist, at least one was wrong (correct=false or i_dont_know=true)

Requires category column to exist. Run add_pinyin_recall_category_column.py first.

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python scripts/backfill_pinyin_recall_category.py
  python scripts/backfill_pinyin_recall_category.py --dry-run
"""

import os
import sys
from collections import defaultdict
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

CATEGORY_NEW = "新字"
CATEGORY_CONFIRM = "巩固"
CATEGORY_REVISE = "重测"


def main():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("psycopg is required. Install with: pip install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT id, user_id, character, correct, i_dont_know, created_at
                FROM pinyin_recall_item_answered
                ORDER BY user_id, character, created_at
            """)
            rows = cur.fetchall()

        # Group by (user_id, character), process in chronological order
        # key: (user_id, character) -> list of (id, correct, i_dont_know) in order
        by_user_char: dict[tuple, list] = defaultdict(list)
        for r in rows:
            key = (r["user_id"], r["character"])
            by_user_char[key].append({
                "id": r["id"],
                "correct": bool(r["correct"]),
                "i_dont_know": bool(r["i_dont_know"]),
            })

        updates = []
        for (user_id, character), items in by_user_char.items():
            had_prior_wrong = False
            for i, item in enumerate(items):
                if i == 0:
                    category = CATEGORY_NEW
                else:
                    if had_prior_wrong:
                        category = CATEGORY_REVISE
                    else:
                        category = CATEGORY_CONFIRM
                if not item["correct"] or item["i_dont_know"]:
                    had_prior_wrong = True
                updates.append((category, item["id"]))

        if dry_run:
            print(f"[dry-run] Would update {len(updates)} rows")
            for cat in (CATEGORY_NEW, CATEGORY_CONFIRM, CATEGORY_REVISE):
                n = sum(1 for c, _ in updates if c == cat)
                print(f"  {cat}: {n}")
            return

        with conn.cursor() as cur:
            cur.executemany(
                "UPDATE pinyin_recall_item_answered SET category = %s WHERE id = %s",
                updates,
            )
        conn.commit()
        print(f"Backfilled category for {len(updates)} rows.")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
