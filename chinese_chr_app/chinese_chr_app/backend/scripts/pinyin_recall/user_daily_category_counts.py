#!/usr/bin/env python3
"""
Compute daily pinyin-recall category counts (难字 / 普通在学字 / 普通已学字 / 掌握字) for one user.

This replays that user's `pinyin_recall_item_answered` history and produces, for each day,
the number of characters whose score falls into each of the four score bands at end-of-day.

Run from backend/:
  python3 scripts/pinyin_recall/user_daily_category_counts.py --email "emma@example.com" [--days 30]
  python3 scripts/pinyin_recall/user_daily_category_counts.py --user-id "uuid-here" [--days 30]

Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.
Uses auth.users to resolve --email to user_id (Supabase Postgres).
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv

    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    # Optional; fine if dotenv is not installed.
    pass

# Ensure the backend directory (where database.py lives) is on sys.path
BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.append(str(BACKEND_DIR))


def get_user_id_by_email(cur, email: str) -> Optional[str]:
    """Resolve user_id from auth.users by email. Returns None if not found."""
    cur.execute(
        "SELECT id FROM auth.users WHERE email = %s LIMIT 1",
        (email.strip(),),
    )
    row = cur.fetchone()
    return str(row["id"]) if row and row.get("id") else None


@dataclass
class Event:
    character: str
    score_after: int
    day: date


def score_to_band(
    score: int,
    learning_hard_max: int,
    learned_mastered_min: int,
) -> str:
    """
    Map a pinyin-recall score to one of the four bands used in the profile:

    - 难字: score <= learning_hard_max (typically -20)
    - 普通在学字: learning_hard_max < score <= 0
    - 普通已学字: 0 < score < learned_mastered_min (typically 20)
    - 掌握字: score >= learned_mastered_min
    """
    if score <= learning_hard_max:
        return "难字"
    if score <= 0:
        return "普通在学字"
    if score < learned_mastered_min:
        return "普通已学字"
    return "掌握字"


def compute_daily_counts(
    events: List[Event],
    learning_hard_max: int,
    learned_mastered_min: int,
    days: int,
) -> List[Dict[str, object]]:
    """
    Replay events in chronological order and compute end-of-day band membership counts.

    Returns a list of dicts:
      {
        "date": "YYYY-MM-DD",
        "hard": int,             # 难字
        "learning_normal": int,  # 普通在学字
        "learned_normal": int,   # 普通已学字
        "mastered": int,         # 掌握字
      }
    Limited to the last `days` days of available history.
    """
    if not events:
        return []

    # Track current band per character and global band counts.
    band_keys = ["难字", "普通在学字", "普通已学字", "掌握字"]
    band_counts: Dict[str, int] = {k: 0 for k in band_keys}
    per_char_band: Dict[str, str] = {}

    # Raw snapshots for days that actually had events.
    daily_snapshots: Dict[date, Dict[str, int]] = {}
    current_day: Optional[date] = None

    for ev in events:
        ev_day = ev.day
        if current_day is None:
            current_day = ev_day
        elif ev_day != current_day:
            # Snapshot counts at end of previous day before moving on.
            daily_snapshots[current_day] = dict(band_counts)
            current_day = ev_day

        ch = ev.character
        prev_band = per_char_band.get(ch)
        new_band = score_to_band(ev.score_after, learning_hard_max, learned_mastered_min)

        if prev_band == new_band:
            continue

        if prev_band is not None:
            # Character moved out of a previous band.
            band_counts[prev_band] = max(0, band_counts.get(prev_band, 0) - 1)
        band_counts[new_band] = band_counts.get(new_band, 0) + 1
        per_char_band[ch] = new_band

    # Snapshot final day.
    if current_day is not None and current_day not in daily_snapshots:
        daily_snapshots[current_day] = dict(band_counts)

    # Fill in gaps for days without events by carrying forward the last known counts.
    all_days_sorted = sorted(daily_snapshots.keys())
    if not all_days_sorted:
        return []

    start = all_days_sorted[0]
    end = all_days_sorted[-1]

    filled: Dict[date, Dict[str, int]] = {}
    last_counts: Dict[str, int] = {k: 0 for k in band_keys}
    d = start
    while d <= end:
        if d in daily_snapshots:
            last_counts = daily_snapshots[d]
        filled[d] = dict(last_counts)
        d += timedelta(days=1)

    # Restrict to the last `days` days relative to `end`.
    cutoff = end - timedelta(days=days - 1)
    output: List[Dict[str, object]] = []
    for d in sorted(filled.keys()):
        if d < cutoff:
            continue
        counts = filled[d]
        output.append(
            {
                "date": d.isoformat(),
                "hard": counts.get("难字", 0),
                "learning_normal": counts.get("普通在学字", 0),
                "learned_normal": counts.get("普通已学字", 0),
                "mastered": counts.get("掌握字", 0),
            }
        )

    return output


def fetch_events_for_user(cur, user_id: str) -> Tuple[List[Event], Optional[date], Optional[date]]:
    """
    Fetch all pinyin_recall_item_answered events for the user, ordered by created_at ASC.

    Returns (events, first_day, last_day).
    """
    cur.execute(
        """
        SELECT character, score_after, created_at
        FROM pinyin_recall_item_answered
        WHERE user_id = %s
        ORDER BY created_at ASC
        """,
        (user_id.strip(),),
    )
    rows = cur.fetchall()
    events: List[Event] = []
    first_day: Optional[date] = None
    last_day: Optional[date] = None
    for r in rows:
        ch = (r.get("character") or "").strip()
        score_after = r.get("score_after")
        created_at = r.get("created_at")
        if not ch or score_after is None or created_at is None:
            continue
        day = created_at.date()
        events.append(Event(character=ch, score_after=int(score_after), day=day))
        if first_day is None or day < first_day:
            first_day = day
        if last_day is None or day > last_day:
            last_day = day
    return events, first_day, last_day


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Compute daily pinyin-recall category counts "
            "(难字 / 普通在学字 / 普通已学字 / 掌握字) for one user."
        ),
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--email",
        help="User email (e.g. Emma's) to resolve to user_id",
    )
    group.add_argument(
        "--user-id",
        help="User UUID (from Supabase Auth)",
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of recent days to include in the output (default: 30)",
    )
    args = parser.parse_args()

    try:
        import psycopg
        from psycopg.rows import dict_row
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    # Import thresholds from the main database module so they match the app.
    try:
        import database as db  # type: ignore[import-not-found]
    except Exception as e:  # pragma: no cover - script-only context
        print(f"Error importing database module: {e}")
        sys.exit(1)

    learning_hard_max = getattr(db, "PROFILE_LEARNING_HARD_MAX_SCORE", -20)
    learned_mastered_min = getattr(db, "PROFILE_LEARNED_MASTERED_MIN_SCORE", 20)

    conn = psycopg.connect(url, row_factory=dict_row)
    user_id = args.user_id
    try:
        with conn.cursor() as cur:
            if args.email:
                user_id = get_user_id_by_email(cur, args.email)
                if not user_id:
                    print(f"No user found for email: {args.email!r}")
                    sys.exit(1)
                print(f"Resolved email to user_id: {user_id}\n")

            if not user_id:
                print("User id could not be determined.")
                sys.exit(1)

            events, first_day, last_day = fetch_events_for_user(cur, user_id)

        if not events or first_day is None or last_day is None:
            print("No pinyin_recall_item_answered events found for this user.")
            return

        daily = compute_daily_counts(
            events=events,
            learning_hard_max=learning_hard_max,
            learned_mastered_min=learned_mastered_min,
            days=max(1, args.days),
        )

        print(
            json.dumps(
                {
                    "user_id": user_id,
                    "first_day": first_day.isoformat(),
                    "last_day": last_day.isoformat(),
                    "days_returned": len(daily),
                    "daily_counts": daily,
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()

