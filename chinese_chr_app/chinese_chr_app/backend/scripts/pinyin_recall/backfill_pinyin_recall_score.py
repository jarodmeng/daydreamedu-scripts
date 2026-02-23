#!/usr/bin/env python3
"""
Backfill pinyin recall scores using symmetric +10/−10 scheme (floor −50).

Replays pinyin_recall_item_answered per (user_id, character) in chronological order,
recomputes score with correct +10 (cap 100), wrong/我不知道 −10 (floor −50).
Updates:
  1. pinyin_recall_character_bank.score
  2. pinyin_recall_item_answered.score_before, score_after

Creates backup tables before modifying:
  - pinyin_recall_character_bank_backup_YYYYMMDD_HHMMSS
  - pinyin_recall_item_answered_backup_YYYYMMDD_HHMMSS
Use --no-backup to skip.

Requires DATABASE_URL (or SUPABASE_DB_URL). Run from backend/:
  python scripts/backfill_pinyin_recall_score.py
  python scripts/backfill_pinyin_recall_score.py --dry-run
  python scripts/backfill_pinyin_recall_score.py --dry-run --exclude-user local-dev   # only non-local-dev changes
  python scripts/backfill_pinyin_recall_score.py --no-backup
"""

import os
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

SCORE_CORRECT_DELTA = 10
SCORE_WRONG_DELTA = 10
SCORE_MIN = -50
SCORE_MAX = 100


def main():
    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("psycopg is required. Install with: pip install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    no_backup = "--no-backup" in sys.argv

    exclude_user = None
    for i, arg in enumerate(sys.argv):
        if arg == "--exclude-user" and i + 1 < len(sys.argv):
            exclude_user = sys.argv[i + 1].strip()
            break

    if dry_run:
        print("Dry run: no updates applied.")
    elif no_backup:
        print("--no-backup: skipping backup table creation.")

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, user_id, character, correct, i_dont_know, created_at
                FROM pinyin_recall_item_answered
                ORDER BY user_id, character, created_at, id
                """
            )
            rows = cur.fetchall()

        if not rows:
            print("No rows in pinyin_recall_item_answered. Nothing to backfill.")
            return

        # Group by (user_id, character), replay score
        by_user_char: dict[tuple, list] = defaultdict(list)
        for r in rows:
            key = (r["user_id"], r["character"])
            by_user_char[key].append({
                "id": r["id"],
                "correct": bool(r["correct"]),
                "i_dont_know": bool(r["i_dont_know"]),
            })

        bank_updates = []
        answered_updates = []

        for (user_id, character), items in by_user_char.items():
            score = 0
            for item in items:
                score_before = score
                if item["correct"]:
                    score = min(score + SCORE_CORRECT_DELTA, SCORE_MAX)
                else:
                    score = max(score - SCORE_WRONG_DELTA, SCORE_MIN)
                score_after = score
                answered_updates.append((score_before, score_after, item["id"]))
            bank_updates.append((score, user_id, character))

        if dry_run:
            # Fetch current bank scores for verification
            cur_scores = {}
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT user_id, character, score FROM pinyin_recall_character_bank"
                )
                for r in cur.fetchall():
                    cur_scores[(r["user_id"], r["character"])] = int(r["score"] or 0)

            changes = [(s, uid, ch) for s, uid, ch in bank_updates if cur_scores.get((uid, ch), -1) != s]
            if exclude_user:
                changes_filtered = [(s, uid, ch) for s, uid, ch in changes if uid != exclude_user]
            else:
                changes_filtered = changes

            changed = len(changes)
            same = len(bank_updates) - changed

            negative_count = sum(1 for s, _, _ in bank_updates if s < 0)
            min_score = min(s for s, _, _ in bank_updates) if bank_updates else 0
            floor_hits = [(uid, ch, cur_scores.get((uid, ch), "N/A")) for s, uid, ch in bank_updates if s == SCORE_MIN]
            print(f"[dry-run] Would update {len(bank_updates)} bank rows, {len(answered_updates)} item_answered rows")
            print(f"  Score changes: {changed} would change, {same} would stay same")
            print(f"  Characters with negative score after backfill: {negative_count}")
            print(f"  Lowest score after backfill: {min_score}")
            if floor_hits:
                print(f"  Characters at floor ({SCORE_MIN}): {len(floor_hits)}")
                for uid, ch, old in floor_hits[:30]:
                    print(f"    ({uid!r}, {ch!r}): {old} -> {SCORE_MIN}")
                if len(floor_hits) > 30:
                    print(f"    ... and {len(floor_hits) - 30} more")
            if exclude_user:
                print(f"  (excluding user {exclude_user!r}: {len(changes_filtered)} changes)")

            if changes_filtered:
                display = changes_filtered[:20] if exclude_user else changes_filtered[:5]
                label = "Rows that would change" + (f" (excluding {exclude_user!r})" if exclude_user else "")
                print(f"  {label} (user_id, character, old -> new):")
                for new_score, uid, ch in display:
                    old_score = cur_scores.get((uid, ch), "N/A")
                    print(f"    ({uid!r}, {ch!r}): {old_score} -> {new_score}")

            if bank_updates and not exclude_user:
                sample = bank_updates[:5]
                print("  Sample of all updates (may include unchanged):")
                for new_score, uid, ch in sample:
                    old_score = cur_scores.get((uid, ch), "N/A")
                    print(f"    ({ch!r}): {old_score} -> {new_score}")
            return

        # Create backup tables before modifying
        if not no_backup:
            ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            bank_backup = f"pinyin_recall_character_bank_backup_{ts}"
            answered_backup = f"pinyin_recall_item_answered_backup_{ts}"
            with conn.cursor() as cur:
                cur.execute(f'CREATE TABLE "{bank_backup}" AS SELECT * FROM pinyin_recall_character_bank')
                cur.execute(f'CREATE TABLE "{answered_backup}" AS SELECT * FROM pinyin_recall_item_answered')
            conn.commit()
            print(f"Backup tables created: {bank_backup}, {answered_backup}")

        # Update character bank
        with conn.cursor() as cur:
            cur.executemany(
                """
                UPDATE pinyin_recall_character_bank
                SET score = %s
                WHERE user_id = %s AND character = %s
                """,
                [(score, uid, ch) for score, uid, ch in bank_updates],
            )
            bank_updated = cur.rowcount

        # Update item_answered (score_before, score_after)
        with conn.cursor() as cur:
            cur.executemany(
                """
                UPDATE pinyin_recall_item_answered
                SET score_before = %s, score_after = %s
                WHERE id = %s
                """,
                answered_updates,
            )
            answered_updated = cur.rowcount

        conn.commit()
        print(f"Backfilled: {bank_updated} bank rows, {answered_updated} item_answered rows.")
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    main()
