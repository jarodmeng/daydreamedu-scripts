#!/usr/bin/env python3
"""
Diagnose why one user's Pinyin Recall mastered growth differs from another's.

Run from backend/:
  python3 scripts/utils/diagnose_pinyin_recall_mastered_growth.py \
    --email-a emma@example.com \
    --email-b winston@example.com \
    --days 30

Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.
Uses auth.users to resolve emails to user ids (Supabase Postgres).
"""

import argparse
import json
import os
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv

    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
    sys.exit(1)


MASTERY_MIN_SCORE = 20
MEMORIZED_MIN_SCORE = 40  # 精通项: deeply-retained subset of mastered (>= 40)
PROFICIENCY_MIN_SCORE = 10


@dataclass
class AnswerEvent:
    unit_id: str
    character: str
    reading_key: str
    correct: bool
    i_dont_know: bool
    score_before: int
    score_after: int
    category: str
    latency_ms: Optional[int]
    created_at: datetime


@dataclass
class PresentedEvent:
    unit_id: str
    from_user_priority: bool
    priority_label: str
    priority_source: str
    batch_mode: str
    batch_character_category: str
    created_at: datetime


def get_user_id_by_email(cur: Any, email: str) -> Optional[str]:
    cur.execute(
        "SELECT id FROM auth.users WHERE email = %s LIMIT 1",
        (email.strip(),),
    )
    row = cur.fetchone()
    return str(row["id"]) if row and row.get("id") else None


def get_public_table_columns(cur: Any, table_name: str) -> set[str]:
    cur.execute(
        """
        SELECT column_name
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
        """,
        (table_name,),
    )
    return {str(row["column_name"]) for row in cur.fetchall()}


def public_table_exists(cur: Any, table_name: str) -> bool:
    cur.execute("SELECT to_regclass(%s) AS regclass_name", (f"public.{table_name}",))
    row = cur.fetchone()
    return bool(row and row.get("regclass_name"))


def fetch_latest_activity_day(cur: Any, user_ids: List[str]) -> Optional[date]:
    cur.execute(
        """
        SELECT MAX(created_at::date) AS latest_day
        FROM pinyin_recall_item_answered
        WHERE user_id = ANY(%s)
        """,
        (user_ids,),
    )
    row = cur.fetchone()
    return row.get("latest_day") if row else None


def fetch_answer_events(cur: Any, user_id: str, end_exclusive: datetime) -> List[AnswerEvent]:
    cur.execute(
        """
        SELECT
            COALESCE(unit_id, '') AS unit_id,
            COALESCE(character, '') AS character,
            COALESCE(reading_key, '') AS reading_key,
            correct,
            i_dont_know,
            COALESCE(score_before, 0) AS score_before,
            COALESCE(score_after, 0) AS score_after,
            COALESCE(category, '') AS category,
            latency_ms,
            created_at
        FROM pinyin_recall_item_answered
        WHERE user_id = %s
          AND created_at < %s
        ORDER BY created_at ASC, id ASC
        """,
        (user_id, end_exclusive),
    )
    rows = cur.fetchall()
    return [
        AnswerEvent(
            unit_id=(row.get("unit_id") or "").strip(),
            character=(row.get("character") or "").strip(),
            reading_key=(row.get("reading_key") or "").strip(),
            correct=bool(row.get("correct")),
            i_dont_know=bool(row.get("i_dont_know")),
            score_before=int(row.get("score_before") or 0),
            score_after=int(row.get("score_after") or 0),
            category=(row.get("category") or "").strip(),
            latency_ms=row.get("latency_ms"),
            created_at=row["created_at"],
        )
        for row in rows
    ]


def fetch_presented_events(
    cur: Any,
    user_id: str,
    start_inclusive: datetime,
    end_exclusive: datetime,
    columns: set[str],
) -> List[PresentedEvent]:
    if not columns:
        return []

    unit_expr = "COALESCE(unit_id, '')" if "unit_id" in columns else "''"
    from_priority_expr = "COALESCE(from_user_priority, false)" if "from_user_priority" in columns else "false"
    priority_label_expr = "COALESCE(priority_label, '')" if "priority_label" in columns else "''"
    priority_source_expr = "COALESCE(priority_source, '')" if "priority_source" in columns else "''"
    batch_mode_expr = "COALESCE(batch_mode, '')" if "batch_mode" in columns else "''"
    batch_category_expr = (
        "COALESCE(batch_character_category, '')" if "batch_character_category" in columns else "''"
    )
    cur.execute(
        f"""
        SELECT
            {unit_expr} AS unit_id,
            {from_priority_expr} AS from_user_priority,
            {priority_label_expr} AS priority_label,
            {priority_source_expr} AS priority_source,
            {batch_mode_expr} AS batch_mode,
            {batch_category_expr} AS batch_character_category,
            created_at
        FROM pinyin_recall_item_presented
        WHERE user_id = %s
          AND created_at >= %s
          AND created_at < %s
        ORDER BY created_at ASC, id ASC
        """,
        (user_id, start_inclusive, end_exclusive),
    )
    rows = cur.fetchall()
    return [
        PresentedEvent(
            unit_id=(row.get("unit_id") or "").strip(),
            from_user_priority=bool(row.get("from_user_priority")),
            priority_label=(row.get("priority_label") or "").strip(),
            priority_source=(row.get("priority_source") or "").strip(),
            batch_mode=(row.get("batch_mode") or "").strip(),
            batch_character_category=(row.get("batch_character_category") or "").strip(),
            created_at=row["created_at"],
        )
        for row in rows
    ]


def fetch_active_priority_count(cur: Any, user_id: str, as_of: datetime) -> int:
    if not public_table_exists(cur, "user_prioritized_characters"):
        return 0
    cur.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM user_prioritized_characters
        WHERE user_id = %s
          AND active = true
          AND (expires_at IS NULL OR expires_at >= %s)
        """,
        (user_id, as_of),
    )
    row = cur.fetchone()
    return int(row.get("cnt") or 0)


def safe_pct(numerator: int, denominator: int) -> Optional[float]:
    if denominator <= 0:
        return None
    return round((numerator / denominator) * 100.0, 1)


def round_or_none(value: Optional[float], digits: int = 1) -> Optional[float]:
    if value is None:
        return None
    return round(value, digits)


def median_or_none(values: List[int]) -> Optional[float]:
    if not values:
        return None
    return round(float(statistics.median(values)), 1)


def build_daily_answer_counts(events: List[AnswerEvent], start_day: date, end_day: date) -> List[Dict[str, Any]]:
    daily_counter: Counter[date] = Counter(ev.created_at.date() for ev in events)
    output: List[Dict[str, Any]] = []
    current = start_day
    while current <= end_day:
        output.append(
            {
                "date": current.isoformat(),
                "answers": int(daily_counter.get(current, 0)),
            }
        )
        current += timedelta(days=1)
    return output


def analyze_user(
    label: str,
    email: str,
    user_id: str,
    answer_events: List[AnswerEvent],
    presented_events: List[PresentedEvent],
    start_inclusive: datetime,
    end_exclusive: datetime,
    active_priority_count: int,
) -> Dict[str, Any]:
    window_events = [ev for ev in answer_events if start_inclusive <= ev.created_at < end_exclusive]
    window_presented = [ev for ev in presented_events if start_inclusive <= ev.created_at < end_exclusive]

    start_day = start_inclusive.date()
    end_day = (end_exclusive - timedelta(microseconds=1)).date()

    scores_before_start: Dict[str, int] = {}
    latest_scores: Dict[str, int] = {}
    first_seen_at: Dict[str, datetime] = {}
    ever_mastered_before_window: set[str] = set()

    for ev in answer_events:
        if ev.unit_id and ev.unit_id not in first_seen_at:
            first_seen_at[ev.unit_id] = ev.created_at
        if ev.unit_id and ev.created_at < start_inclusive:
            scores_before_start[ev.unit_id] = ev.score_after
            if ev.score_after >= MASTERY_MIN_SCORE:
                ever_mastered_before_window.add(ev.unit_id)
        if ev.unit_id:
            latest_scores[ev.unit_id] = ev.score_after

    mastered_start = sum(1 for score in scores_before_start.values() if score >= MASTERY_MIN_SCORE)
    mastered_end = sum(1 for score in latest_scores.values() if score >= MASTERY_MIN_SCORE)
    memorized_start = sum(1 for score in scores_before_start.values() if score >= MEMORIZED_MIN_SCORE)
    memorized_end = sum(1 for score in latest_scores.values() if score >= MEMORIZED_MIN_SCORE)

    correct_count = sum(1 for ev in window_events if ev.correct)
    idk_count = sum(1 for ev in window_events if ev.i_dont_know)
    wrong_count = sum(1 for ev in window_events if (not ev.correct and not ev.i_dont_know))

    distinct_units_answered = len({ev.unit_id for ev in window_events if ev.unit_id})
    answered_days = len({ev.created_at.date() for ev in window_events})

    new_units_started = {
        ev.unit_id
        for ev in window_events
        if ev.unit_id and first_seen_at.get(ev.unit_id) and first_seen_at[ev.unit_id] >= start_inclusive
    }

    first_time_proficient_units: set[str] = set()
    first_time_mastered_units: set[str] = set()
    mastered_entry_events = 0
    mastered_exit_events = 0
    re_mastered_units: set[str] = set()
    ever_proficient: set[str] = set()
    ever_mastered: set[str] = set(ever_mastered_before_window)
    mastered_slip_examples: Counter[str] = Counter()
    new_unit_first_try_correct = 0
    new_unit_first_try_total = 0
    new_unit_ids_seen: set[str] = set()

    category_counts: Counter[str] = Counter()
    category_correct_counts: Counter[str] = Counter()
    mastered_answer_count = 0
    mastered_answer_correct_count = 0
    latency_correct: List[int] = []
    latency_incorrect: List[int] = []

    for ev in answer_events:
        if not (start_inclusive <= ev.created_at < end_exclusive):
            if ev.unit_id and ev.score_after >= PROFICIENCY_MIN_SCORE:
                ever_proficient.add(ev.unit_id)
            if ev.unit_id and ev.score_after >= MASTERY_MIN_SCORE:
                ever_mastered.add(ev.unit_id)
            continue

        if ev.unit_id and ev.unit_id in new_units_started and ev.unit_id not in new_unit_ids_seen:
            new_unit_first_try_total += 1
            if ev.correct:
                new_unit_first_try_correct += 1
            new_unit_ids_seen.add(ev.unit_id)

        category = ev.category or "UNKNOWN"
        category_counts[category] += 1
        if ev.correct:
            category_correct_counts[category] += 1

        if ev.latency_ms is not None:
            if ev.correct:
                latency_correct.append(int(ev.latency_ms))
            else:
                latency_incorrect.append(int(ev.latency_ms))

        if ev.score_before >= MASTERY_MIN_SCORE:
            mastered_answer_count += 1
            if ev.correct:
                mastered_answer_correct_count += 1

        if ev.unit_id and ev.score_before < PROFICIENCY_MIN_SCORE and ev.score_after >= PROFICIENCY_MIN_SCORE:
            if ev.unit_id not in ever_proficient:
                first_time_proficient_units.add(ev.unit_id)
            ever_proficient.add(ev.unit_id)

        if ev.unit_id and ev.score_before < MASTERY_MIN_SCORE and ev.score_after >= MASTERY_MIN_SCORE:
            mastered_entry_events += 1
            if ev.unit_id in ever_mastered:
                re_mastered_units.add(ev.unit_id)
            else:
                first_time_mastered_units.add(ev.unit_id)
            ever_mastered.add(ev.unit_id)

        if ev.unit_id and ev.score_before >= MASTERY_MIN_SCORE and ev.score_after < MASTERY_MIN_SCORE:
            mastered_exit_events += 1
            label_text = ev.unit_id
            if ev.character:
                label_text = f"{ev.character} ({ev.unit_id})"
            mastered_slip_examples[label_text] += 1

        if ev.unit_id and ev.score_after >= PROFICIENCY_MIN_SCORE:
            ever_proficient.add(ev.unit_id)
        if ev.unit_id and ev.score_after >= MASTERY_MIN_SCORE:
            ever_mastered.add(ev.unit_id)

    priority_presented_count = sum(1 for ev in window_presented if ev.from_user_priority)
    priority_presented_units = len({ev.unit_id for ev in window_presented if ev.from_user_priority and ev.unit_id})

    batch_mode_counts = Counter(ev.batch_mode or "UNKNOWN" for ev in window_presented)
    batch_category_counts = Counter(ev.batch_character_category or "UNKNOWN" for ev in window_presented)
    priority_source_counts = Counter(
        ev.priority_source or "UNKNOWN" for ev in window_presented if ev.from_user_priority
    )

    return {
        "label": label,
        "email": email,
        "user_id": user_id,
        "window": {
            "start_date": start_day.isoformat(),
            "end_date": end_day.isoformat(),
            "days": (end_day - start_day).days + 1,
        },
        "mastered_growth": {
            "mastered_start": mastered_start,
            "mastered_end": mastered_end,
            "delta": mastered_end - mastered_start,
            "mastered_entry_events": mastered_entry_events,
            "first_time_mastered_units": len(first_time_mastered_units),
            "re_mastered_units": len(re_mastered_units),
            "mastered_exit_events": mastered_exit_events,
            "net_entries_minus_exits": mastered_entry_events - mastered_exit_events,
            "memorized_start": memorized_start,
            "memorized_end": memorized_end,
            "memorized_delta": memorized_end - memorized_start,
        },
        "activity": {
            "answers": len(window_events),
            "answered_days": answered_days,
            "avg_answers_per_active_day": round_or_none(
                (len(window_events) / answered_days) if answered_days else None
            ),
            "avg_answers_per_calendar_day": round_or_none(
                len(window_events) / (((end_day - start_day).days + 1) or 1)
            ),
            "distinct_units_answered": distinct_units_answered,
            "daily_answer_counts": build_daily_answer_counts(window_events, start_day, end_day),
        },
        "accuracy": {
            "correct": correct_count,
            "wrong": wrong_count,
            "i_dont_know": idk_count,
            "correct_rate_pct": safe_pct(correct_count, len(window_events)),
            "idk_rate_pct": safe_pct(idk_count, len(window_events)),
            "median_latency_ms_correct": median_or_none(latency_correct),
            "median_latency_ms_incorrect": median_or_none(latency_incorrect),
        },
        "learning_flow": {
            "new_units_started": len(new_units_started),
            "first_try_correct_rate_on_new_units_pct": safe_pct(
                new_unit_first_try_correct, new_unit_first_try_total
            ),
            "first_time_proficient_units": len(first_time_proficient_units),
            "first_time_mastered_units": len(first_time_mastered_units),
            "first_time_mastered_from_new_units_pct": safe_pct(
                len(first_time_mastered_units & new_units_started),
                len(first_time_mastered_units),
            ),
        },
        "stability": {
            "answers_on_already_mastered_units": mastered_answer_count,
            "correct_rate_on_already_mastered_units_pct": safe_pct(
                mastered_answer_correct_count,
                mastered_answer_count,
            ),
            "mastered_exit_events": mastered_exit_events,
            "top_mastered_slip_units": [
                {"unit": unit, "slips": count}
                for unit, count in mastered_slip_examples.most_common(10)
            ],
        },
        "category_mix": {
            "counts": dict(category_counts),
            "correct_rate_pct_by_category": {
                key: safe_pct(category_correct_counts.get(key, 0), count)
                for key, count in sorted(category_counts.items())
            },
        },
        "priority_exposure": {
            "active_priority_rows_as_of_window_end": active_priority_count,
            "priority_presented_count": priority_presented_count,
            "priority_presented_share_pct": safe_pct(priority_presented_count, len(window_presented)),
            "priority_presented_distinct_units": priority_presented_units,
            "priority_source_counts": dict(priority_source_counts),
        },
        "presentation_mix": {
            "presented": len(window_presented),
            "batch_mode_counts": dict(batch_mode_counts),
            "batch_character_category_counts": dict(batch_category_counts),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Compare two users' recent Pinyin Recall mastered growth using live Supabase data.",
    )
    parser.add_argument("--email-a", required=True, help="First user's email")
    parser.add_argument("--label-a", default="User A", help="Display label for first user")
    parser.add_argument("--email-b", required=True, help="Second user's email")
    parser.add_argument("--label-b", default="User B", help="Display label for second user")
    parser.add_argument("--days", type=int, default=30, help="Number of recent days to analyze")
    args = parser.parse_args()

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)

    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            user_id_a = get_user_id_by_email(cur, args.email_a)
            user_id_b = get_user_id_by_email(cur, args.email_b)
            if not user_id_a:
                print(f"No user found for email: {args.email_a!r}")
                sys.exit(1)
            if not user_id_b:
                print(f"No user found for email: {args.email_b!r}")
                sys.exit(1)

            latest_day = fetch_latest_activity_day(cur, [user_id_a, user_id_b])
            if latest_day is None:
                print("No pinyin_recall_item_answered rows found for the selected users.")
                sys.exit(1)

            start_day = latest_day - timedelta(days=max(1, args.days) - 1)
            start_inclusive = datetime.combine(start_day, datetime.min.time(), tzinfo=timezone.utc)
            end_exclusive = datetime.combine(latest_day + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc)
            presented_columns = get_public_table_columns(cur, "pinyin_recall_item_presented")

            answer_events_a = fetch_answer_events(cur, user_id_a, end_exclusive)
            answer_events_b = fetch_answer_events(cur, user_id_b, end_exclusive)
            presented_events_a = fetch_presented_events(
                cur, user_id_a, start_inclusive, end_exclusive, presented_columns
            )
            presented_events_b = fetch_presented_events(
                cur, user_id_b, start_inclusive, end_exclusive, presented_columns
            )
            priority_count_a = fetch_active_priority_count(cur, user_id_a, end_exclusive)
            priority_count_b = fetch_active_priority_count(cur, user_id_b, end_exclusive)

        result = {
            "analysis_window": {
                "latest_activity_day": latest_day.isoformat(),
                "start_date": start_day.isoformat(),
                "end_date": latest_day.isoformat(),
                "days": max(1, args.days),
            },
            "users": [
                analyze_user(
                    label=args.label_a,
                    email=args.email_a,
                    user_id=user_id_a,
                    answer_events=answer_events_a,
                    presented_events=presented_events_a,
                    start_inclusive=start_inclusive,
                    end_exclusive=end_exclusive,
                    active_priority_count=priority_count_a,
                ),
                analyze_user(
                    label=args.label_b,
                    email=args.email_b,
                    user_id=user_id_b,
                    answer_events=answer_events_b,
                    presented_events=presented_events_b,
                    start_inclusive=start_inclusive,
                    end_exclusive=end_exclusive,
                    active_priority_count=priority_count_b,
                ),
            ],
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
