"""
Database layer for feng_characters and hwxnet_characters (Supabase/Postgres).

Returns dict shapes compatible with the rest of the app (same as JSON-based responses).
Uses Psycopg 3 (psycopg[binary]>=3.1) for Python 3.13+ compatibility.
"""

import json
import os
from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None


def _get_connection():
    if psycopg is None:
        raise RuntimeError("psycopg is required for database support. Install with: pip3 install 'psycopg[binary]>=3.1'")
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("DATABASE_URL or SUPABASE_DB_URL must be set when using database")
    return psycopg.connect(url, row_factory=dict_row)


def _row_to_feng_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map feng_characters row to the dict shape expected by the app (Character, Index, Pinyin, etc.)."""
    strokes = row.get("strokes")
    strokes_str = str(strokes) if strokes is not None else ""
    return {
        "Character": (row.get("character") or "").strip(),
        "Index": (row.get("index") or "").strip(),
        "zibiao_index": row.get("zibiao_index"),
        "Pinyin": row.get("pinyin") or [],
        "Radical": (row.get("radical") or "").strip() or "",
        "Strokes": strokes_str,
        "Structure": (row.get("structure") or "").strip() or "",
        "Sentence": (row.get("sentence") or "").strip() or "",
        "Words": row.get("words") or [],
    }


def _row_to_hwxnet_dict(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map hwxnet_characters row to the dict shape expected by the app (部首, 拼音, 总笔画, etc.)."""
    return {
        "character": (row.get("character") or "").strip(),
        "部首": (row.get("radical") or "").strip() or "",
        "拼音": row.get("pinyin") or [],
        "总笔画": row.get("strokes"),
        "index": row.get("index"),
        "zibiao_index": row.get("zibiao_index"),
        "source_url": row.get("source_url"),
        "基本字义解释": row.get("basic_meanings") or [],
        "英文翻译": row.get("english_translations") or [],
        "分类": row.get("classification") or [],
        "常用词组": row.get("common_phrases") or [],
    }


def get_feng_characters() -> List[Dict[str, Any]]:
    """Return all feng_characters rows as list of dicts (same shape as characters.json entries)."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT character, index, zibiao_index, pinyin, radical, strokes, structure, sentence, words FROM feng_characters ORDER BY index"
            )
            rows = cur.fetchall()
        return [_row_to_feng_dict(r) for r in rows]
    finally:
        conn.close()


def get_feng_character_by_index(index: str) -> Optional[Dict[str, Any]]:
    """Return one feng character by index, or None."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT character, index, zibiao_index, pinyin, radical, strokes, structure, sentence, words FROM feng_characters WHERE index = %s",
                (index.strip(),),
            )
            row = cur.fetchone()
        return _row_to_feng_dict(row) if row else None
    finally:
        conn.close()


def get_feng_character_by_character(ch: str) -> Optional[Dict[str, Any]]:
    """Return one feng character by character (first match if multiple)."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT character, index, zibiao_index, pinyin, radical, strokes, structure, sentence, words FROM feng_characters WHERE character = %s ORDER BY index LIMIT 1",
                (ch.strip(),),
            )
            row = cur.fetchone()
        return _row_to_feng_dict(row) if row else None
    finally:
        conn.close()


def get_hwxnet_lookup() -> Dict[str, Dict[str, Any]]:
    """Return all hwxnet_characters as dict keyed by character (same shape as JSON hwxnet_lookup)."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT character, zibiao_index, index, source_url, classification, pinyin, radical, strokes, basic_meanings, english_translations, common_phrases FROM hwxnet_characters"
            )
            rows = cur.fetchall()
        result = {}
        for r in rows:
            d = _row_to_hwxnet_dict(r)
            ch = d.get("character")
            if ch:
                result[ch] = d
        return result
    finally:
        conn.close()


def get_characters_by_pinyin_search_keys(search_keys: List[str]) -> List[Dict[str, Any]]:
    """
    Return characters whose searchable_pinyin contains any of the given keys.
    Returns list of dicts with character, 部首 (radical), 拼音 (pinyin), 总笔画 (strokes), zibiao_index, index.
    Sorted by 总笔画 ASC, then zibiao_index ASC. One entry per character (deduped).
    """
    if not search_keys:
        return []
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT character, zibiao_index, index, radical, strokes, pinyin
                FROM hwxnet_characters
                WHERE searchable_pinyin ?| %s
                ORDER BY strokes ASC NULLS LAST, zibiao_index ASC NULLS LAST
                """,
                (search_keys,),
            )
            rows = cur.fetchall()
        # Dedupe by character (keep first by sort order)
        seen = set()
        result = []
        for r in rows:
            ch = (r.get("character") or "").strip()
            if not ch or ch in seen:
                continue
            seen.add(ch)
            result.append({
                "character": ch,
                "radical": (r.get("radical") or "").strip() or "",
                "pinyin": r.get("pinyin") or [],
                "strokes": r.get("strokes"),
                "zibiao_index": r.get("zibiao_index"),
                "index": r.get("index"),
            })
        return result
    finally:
        conn.close()


def _field_to_column(field: str) -> str:
    """Map API field name to DB column name."""
    mapping = {
        "Character": "character",
        "Pinyin": "pinyin",
        "Radical": "radical",
        "Strokes": "strokes",
        "Structure": "structure",
        "Sentence": "sentence",
        "Words": "words",
    }
    return mapping.get(field, field.lower())


def _value_for_db(field: str, value: Any) -> Any:
    """Convert API value to DB value (e.g. Strokes string -> int, list -> jsonb)."""
    if field == "Strokes":
        if value is None:
            return None
        s = str(value).strip().replace(" (dictionary)", "").strip()
        if not s:
            return None
        try:
            return int(s)
        except ValueError:
            return None
    # Psycopg 3 adapts list/dict to JSONB automatically
    if field in ("Pinyin", "Words") and isinstance(value, list):
        return value
    return value


def update_feng_character(index: str, field: str, value: Any) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
    """
    Update one field for the feng character with the given index.
    Returns (success, error_message, updated_character_dict).
    """
    if field not in ("Character", "Pinyin", "Radical", "Strokes", "Structure", "Sentence", "Words"):
        return False, f"Unknown field: {field}", None
    col = _field_to_column(field)
    db_value = _value_for_db(field, value)
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                f"UPDATE feng_characters SET {col} = %s WHERE index = %s RETURNING character, index, zibiao_index, pinyin, radical, strokes, structure, sentence, words",
                (db_value, index.strip()),
            )
            row = cur.fetchone()
        conn.commit()
        if not row:
            return False, f"Character with index {index} not found", None
        return True, None, _row_to_feng_dict(row)
    except Exception as e:
        conn.rollback()
        return False, str(e), None
    finally:
        conn.close()


def get_radical_stroke_counts() -> Dict[str, int]:
    """
    Return radical -> stroke_count from radical_stroke_counts table.
    Used for sorting the Radicals page by radical stroke count.
    Raises on connection/query error so caller can fall back to JSON.
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT radical, stroke_count FROM radical_stroke_counts")
            rows = cur.fetchall()
        return {str(r["radical"]).strip(): int(r["stroke_count"]) for r in rows if r.get("radical")}
    finally:
        conn.close()


def log_character_view(user_id: str, character: str, display_name: Optional[str] = None) -> None:
    """
    Insert a row into character_views (user_id, character, viewed_at, display_name).
    Table must exist (run scripts/create_character_views_table.py once).
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO character_views (user_id, character, display_name) VALUES (%s, %s, %s)",
                (user_id.strip(), character.strip(), (display_name or "").strip() or None),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        conn.close()


# --- Profile / progress (Issue #2, user_profiles) ---


def get_profile_display_name(user_id: str) -> Optional[str]:
    """
    Return the display_name for the given user_id from user_profiles, or None if not set.
    """
    user_id = (user_id or "").strip()
    if not user_id:
        return None
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT display_name FROM user_profiles WHERE user_id = %s",
                (user_id,),
            )
            row = cur.fetchone()
        if not row:
            return None
        val = row.get("display_name")
        if val is None:
            return None
        val_str = str(val).strip()
        return val_str or None
    finally:
        conn.close()


def upsert_profile_display_name(user_id: str, display_name: str) -> None:
    """
    Insert or update the display_name for the given user_id in user_profiles.
    """
    user_id = (user_id or "").strip()
    display_name = (display_name or "").strip()
    if not user_id or not display_name:
        return
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO user_profiles (user_id, display_name)
                VALUES (%s, %s)
                ON CONFLICT (user_id) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    updated_at = now()
                """,
                (user_id, display_name),
            )
        conn.commit()
    finally:
        conn.close()


# --- Profile / progress (Issue #2) ---

PROFILE_PROFICIENCY_MIN_SCORE = 10
PROFILE_HWXNET_TOTAL = 3664


def get_character_views_count_for_user(user_id: str) -> int:
    """Return count of distinct characters viewed by user."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT COUNT(DISTINCT character) AS cnt FROM character_views WHERE user_id = %s",
                (user_id.strip(),),
            )
            row = cur.fetchone()
        return int(row.get("cnt") or 0)
    finally:
        conn.close()


def get_character_views_recent_for_user(user_id: str, limit: int = 50) -> List[str]:
    """Return recent viewed characters (most recent first), deduped by character (keeps latest view)."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT character FROM (
                    SELECT character, MAX(viewed_at) AS max_at
                    FROM character_views
                    WHERE user_id = %s
                    GROUP BY character
                ) sub
                ORDER BY max_at DESC
                LIMIT %s
                """,
                (user_id.strip(), limit),
            )
            rows = cur.fetchall()
        return [(r.get("character") or "").strip() for r in rows if (r.get("character") or "").strip()]
    finally:
        conn.close()


def get_pinyin_recall_daily_stats(user_id: str, days: int = 30) -> List[Dict[str, Any]]:
    """Return daily stats: date, answered, correct, by_category. Ordered by date DESC (most recent first)."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    DATE(created_at AT TIME ZONE 'UTC') AS day,
                    COUNT(*) AS answered,
                    SUM(CASE WHEN correct THEN 1 ELSE 0 END)::int AS correct,
                    COUNT(*) FILTER (WHERE category = %s) AS new_answered,
                    COALESCE(SUM(CASE WHEN correct AND category = %s THEN 1 ELSE 0 END), 0)::int AS new_correct,
                    COUNT(*) FILTER (WHERE category = %s) AS confirm_answered,
                    COALESCE(SUM(CASE WHEN correct AND category = %s THEN 1 ELSE 0 END), 0)::int AS confirm_correct,
                    COUNT(*) FILTER (WHERE category = %s) AS revise_answered,
                    COALESCE(SUM(CASE WHEN correct AND category = %s THEN 1 ELSE 0 END), 0)::int AS revise_correct
                FROM pinyin_recall_item_answered
                WHERE user_id = %s
                  AND created_at >= (NOW() AT TIME ZONE 'UTC') - (%s || ' days')::interval
                GROUP BY DATE(created_at AT TIME ZONE 'UTC')
                ORDER BY day DESC
                LIMIT %s
                """,
                (
                    PINYIN_RECALL_CATEGORY_NEW, PINYIN_RECALL_CATEGORY_NEW,
                    PINYIN_RECALL_CATEGORY_CONFIRM, PINYIN_RECALL_CATEGORY_CONFIRM,
                    PINYIN_RECALL_CATEGORY_REVISE, PINYIN_RECALL_CATEGORY_REVISE,
                    user_id.strip(), str(days), days,
                ),
            )
            rows = cur.fetchall()
        return [
            {
                "date": str(r.get("day") or ""),
                "answered": int(r.get("answered") or 0),
                "correct": int(r.get("correct") or 0),
                "by_category": {
                    PINYIN_RECALL_CATEGORY_NEW: {
                        "answered": int(r.get("new_answered") or 0),
                        "correct": int(r.get("new_correct") or 0),
                    },
                    PINYIN_RECALL_CATEGORY_CONFIRM: {
                        "answered": int(r.get("confirm_answered") or 0),
                        "correct": int(r.get("confirm_correct") or 0),
                    },
                    PINYIN_RECALL_CATEGORY_REVISE: {
                        "answered": int(r.get("revise_answered") or 0),
                        "correct": int(r.get("revise_correct") or 0),
                    },
                },
            }
            for r in rows
        ]
    finally:
        conn.close()


def get_pinyin_recall_category_daily_trend(
    user_id: str,
    days: int = 60,
) -> List[Dict[str, Any]]:
    """
    Return daily counts of characters in the four profile bands for a user:

    - hard (难字)
    - learning_normal (普通在学字)
    - learned_normal (普通已学字)
    - mastered (掌握字)

    Counts reflect band membership at end-of-day. Derived at runtime from
    pinyin_recall_item_answered.score_after, without additional logging.
    """
    if days <= 0:
        return []

    conn = _get_connection()
    try:
        with conn.cursor() as cur:
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

        # No activity for this user.
        if not rows:
            return []

        # Track current band per character and global band counts.
        band_keys = ["难字", "普通在学字", "普通已学字", "掌握字"]
        band_counts: Dict[str, int] = {k: 0 for k in band_keys}
        per_char_band: Dict[str, str] = {}

        # Snapshots for days that had at least one event.
        daily_snapshots: Dict[date, Dict[str, int]] = {}
        current_day: Optional[date] = None

        for r in rows:
            ch = (r.get("character") or "").strip()
            score_after = r.get("score_after")
            created_at = r.get("created_at")
            if not ch or score_after is None or created_at is None:
                continue

            ev_day = created_at.date()
            if current_day is None:
                current_day = ev_day
            elif ev_day != current_day:
                # Snapshot counts at end of previous day before moving on.
                daily_snapshots[current_day] = dict(band_counts)
                current_day = ev_day

            prev_band = per_char_band.get(ch)
            score_val = int(score_after)
            if score_val <= PROFILE_LEARNING_HARD_MAX_SCORE:
                new_band = "难字"
            elif score_val <= 0:
                new_band = "普通在学字"
            elif score_val < PROFILE_LEARNED_MASTERED_MIN_SCORE:
                new_band = "普通已学字"
            else:
                new_band = "掌握字"

            if prev_band == new_band:
                continue

            if prev_band is not None:
                band_counts[prev_band] = max(0, band_counts.get(prev_band, 0) - 1)
            band_counts[new_band] = band_counts.get(new_band, 0) + 1
            per_char_band[ch] = new_band

        # Snapshot the final day.
        if current_day is not None and current_day not in daily_snapshots:
            daily_snapshots[current_day] = dict(band_counts)

        if not daily_snapshots:
            return []

        all_days_sorted = sorted(daily_snapshots.keys())
        start = all_days_sorted[0]
        end = all_days_sorted[-1]

        # Fill gaps for days without events by carrying forward the last known counts.
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
        output: List[Dict[str, Any]] = []
        for day_key in sorted(filled.keys()):
            if day_key < cutoff:
                continue
            counts = filled[day_key]
            output.append(
                {
                    "date": day_key.isoformat(),
                    "hard": counts.get("难字", 0),
                    "learning_normal": counts.get("普通在学字", 0),
                    "learned_normal": counts.get("普通已学字", 0),
                    "mastered": counts.get("掌握字", 0),
                }
            )

        return output
    finally:
        conn.close()


def get_proficient_character_count(user_id: str, min_score: int = PROFILE_PROFICIENCY_MIN_SCORE) -> int:
    """Return count of characters with score >= min_score in pinyin_recall_character_bank."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM pinyin_recall_character_bank
                WHERE user_id = %s AND score >= %s
                """,
                (user_id.strip(), min_score),
            )
            row = cur.fetchone()
        return int(row.get("cnt") or 0)
    finally:
        conn.close()


# Sub-category thresholds for profile display (在学字: 难字 <= -20; 已学字: 掌握字 >= 20)
PROFILE_LEARNING_HARD_MAX_SCORE = -20   # 难字: score <= -20
PROFILE_LEARNED_MASTERED_MIN_SCORE = 20  # 掌握字: score >= 20


def get_pinyin_recall_category_counts(user_id: str) -> Dict[str, int]:
    """
    Return counts for 未学字 / 在学字 / 已学字 and sub-categories.
    learned = score >= 10, learning = score < 10, not_tested = PROFILE_HWXNET_TOTAL - (learned + learning).
    Sub: learning_hard (score <= -20), learning_normal (-20 < score < 10),
         learned_mastered (score >= 20), learned_normal (10 <= score < 20).
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    COUNT(*) FILTER (WHERE score >= %s) AS learned,
                    COUNT(*) FILTER (WHERE score < %s) AS learning,
                    COUNT(*) FILTER (WHERE score < %s AND score <= %s) AS learning_hard,
                    COUNT(*) FILTER (WHERE score < %s AND score > %s) AS learning_normal,
                    COUNT(*) FILTER (WHERE score >= %s) AS learned_mastered,
                    COUNT(*) FILTER (WHERE score >= %s AND score < %s) AS learned_normal
                FROM pinyin_recall_character_bank
                WHERE user_id = %s
                """,
                (
                    PROFILE_PROFICIENCY_MIN_SCORE,
                    PROFILE_PROFICIENCY_MIN_SCORE,
                    PROFILE_PROFICIENCY_MIN_SCORE,
                    PROFILE_LEARNING_HARD_MAX_SCORE,
                    PROFILE_PROFICIENCY_MIN_SCORE,
                    PROFILE_LEARNING_HARD_MAX_SCORE,
                    PROFILE_LEARNED_MASTERED_MIN_SCORE,
                    PROFILE_PROFICIENCY_MIN_SCORE,
                    PROFILE_LEARNED_MASTERED_MIN_SCORE,
                    user_id.strip(),
                ),
            )
            row = cur.fetchone()
        learned = int(row.get("learned") or 0)
        learning = int(row.get("learning") or 0)
        not_tested = max(0, PROFILE_HWXNET_TOTAL - learned - learning)
        return {
            "learned": learned,
            "learning": learning,
            "not_tested": not_tested,
            "learning_hard": int(row.get("learning_hard") or 0),
            "learning_normal": int(row.get("learning_normal") or 0),
            "learned_mastered": int(row.get("learned_mastered") or 0),
            "learned_normal": int(row.get("learned_normal") or 0),
        }
    finally:
        conn.close()


# Profile sub-categories for character list (same thresholds as get_pinyin_recall_category_counts)
PROFILE_CATEGORY_LEARNING_HARD = "learning_hard"
PROFILE_CATEGORY_LEARNING_NORMAL = "learning_normal"
PROFILE_CATEGORY_LEARNED_MASTERED = "learned_mastered"
PROFILE_CATEGORY_LEARNED_NORMAL = "learned_normal"


def get_pinyin_recall_characters_by_category(
    user_id: str, category: str
) -> List[Dict[str, Any]]:
    """
    Return characters in the given profile sub-category, ordered by last_answered_at DESC (latest first).
    category: learning_hard | learning_normal | learned_mastered | learned_normal.
    """
    conn = _get_connection()
    try:
        if category == PROFILE_CATEGORY_LEARNING_HARD:
            where = "user_id = %s AND score < %s AND score <= %s"
            params = (user_id.strip(), PROFILE_PROFICIENCY_MIN_SCORE, PROFILE_LEARNING_HARD_MAX_SCORE)
        elif category == PROFILE_CATEGORY_LEARNING_NORMAL:
            where = "user_id = %s AND score < %s AND score > %s"
            params = (user_id.strip(), PROFILE_PROFICIENCY_MIN_SCORE, PROFILE_LEARNING_HARD_MAX_SCORE)
        elif category == PROFILE_CATEGORY_LEARNED_MASTERED:
            where = "user_id = %s AND score >= %s"
            params = (user_id.strip(), PROFILE_LEARNED_MASTERED_MIN_SCORE)
        elif category == PROFILE_CATEGORY_LEARNED_NORMAL:
            where = "user_id = %s AND score >= %s AND score < %s"
            params = (user_id.strip(), PROFILE_PROFICIENCY_MIN_SCORE, PROFILE_LEARNED_MASTERED_MIN_SCORE)
        else:
            return []
        with conn.cursor() as cur:
            cur.execute(
                f"""
                SELECT character, score, last_answered_at
                FROM pinyin_recall_character_bank
                WHERE {where}
                ORDER BY last_answered_at DESC NULLS LAST
                """,
                params,
            )
            rows = cur.fetchall()
        return [
            {
                "character": r.get("character"),
                "score": r.get("score"),
                "last_answered_at": r.get("last_answered_at").isoformat() if r.get("last_answered_at") else None,
            }
            for r in rows
        ]
    finally:
        conn.close()


# --- Pinyin recall character bank (MVP1) ---
# Score 0-100; higher = better understanding. Stage ladder same as pinyin_recall.py.
PINYIN_RECALL_SCORE_CORRECT_DELTA = 10

# Category labels for pinyin recall (新字, 巩固, 重测) - MECE.
PINYIN_RECALL_CATEGORY_NEW = "新字"
PINYIN_RECALL_CATEGORY_CONFIRM = "巩固"
PINYIN_RECALL_CATEGORY_REVISE = "重测"


# 巩固 only for 已学字 (score >= 10); before that, testing is 重测
PINYIN_RECALL_PROFICIENCY_MIN_SCORE = 10


def _category_from_bank_state(
    total_correct: int,
    total_wrong: int,
    total_i_dont_know: int,
    score_before: int = 0,
) -> str:
    """
    Return category based on learning state before current answer.
    New: never tested. Confirm (巩固): tested, all correct, and 已学字 (score_before >= 10).
    Revise (重测): tested with at least one wrong, or score_before < 10.
    """
    total_answered = total_correct + total_wrong + total_i_dont_know
    if total_answered == 0:
        return PINYIN_RECALL_CATEGORY_NEW
    if total_wrong + total_i_dont_know > 0:
        return PINYIN_RECALL_CATEGORY_REVISE
    if score_before >= PINYIN_RECALL_PROFICIENCY_MIN_SCORE:
        return PINYIN_RECALL_CATEGORY_CONFIRM
    return PINYIN_RECALL_CATEGORY_REVISE
PINYIN_RECALL_SCORE_WRONG_DELTA = 10
PINYIN_RECALL_SCORE_MIN = -50
PINYIN_RECALL_SCORE_MAX = 100
PINYIN_RECALL_STAGE_INTERVAL_DAYS = [0, 1, 3, 7, 14, 30]
PINYIN_RECALL_MAX_STAGE = len(PINYIN_RECALL_STAGE_INTERVAL_DAYS) - 1

# Cooling intervals by five-band (Issue #12): 难字 0d, 普通在学字 1d, 普通已学字 5d, 掌握字 22d
PINYIN_RECALL_COOLING_DAYS_HARD = 0
PINYIN_RECALL_COOLING_DAYS_LEARNING_NORMAL = 1
PINYIN_RECALL_COOLING_DAYS_LEARNED_NORMAL = 5
PINYIN_RECALL_COOLING_DAYS_MASTERED = 22


def _cooling_days_for_score(score: int) -> int:
    """Return cooling days for next_due_utc by score band (难字 0, 普通在学字 1, 普通已学字 5, 掌握字 22)."""
    if score <= PROFILE_LEARNING_HARD_MAX_SCORE:
        return PINYIN_RECALL_COOLING_DAYS_HARD
    if score <= 0:
        return PINYIN_RECALL_COOLING_DAYS_LEARNING_NORMAL
    if score < PROFILE_LEARNED_MASTERED_MIN_SCORE:
        return PINYIN_RECALL_COOLING_DAYS_LEARNED_NORMAL
    return PINYIN_RECALL_COOLING_DAYS_MASTERED


def get_pinyin_recall_learning_state(user_id: str) -> Dict[str, Dict[str, Any]]:
    """
    Load learning state for pinyin recall for one user.
    Returns dict: character -> { stage, next_due_utc, score, total_correct, total_wrong, total_i_dont_know }.
    Used by build_session_queue. Table must exist (run create_pinyin_recall_character_bank_table.py once).
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT character, score, stage, next_due_utc, total_correct, total_wrong, total_i_dont_know
                FROM pinyin_recall_character_bank
                WHERE user_id = %s
                """,
                (user_id.strip(),),
            )
            rows = cur.fetchall()
        result: Dict[str, Dict[str, Any]] = {}
        for r in rows:
            ch = (r.get("character") or "").strip()
            if not ch:
                continue
            result[ch] = {
                "stage": int(r.get("stage") or 0),
                "next_due_utc": r.get("next_due_utc"),
                "score": int(r.get("score") or 0),
                "total_correct": int(r.get("total_correct") or 0),
                "total_wrong": int(r.get("total_wrong") or 0),
                "total_i_dont_know": int(r.get("total_i_dont_know") or 0),
            }
        return result
    finally:
        conn.close()


def upsert_pinyin_recall_character_bank(
    user_id: str,
    character: str,
    correct: bool,
    i_dont_know: bool,
) -> Tuple[int, int]:
    """
    Update character bank after one answer. Creates row if missing.
    Returns (score_before, score_after). Table must exist.
    """
    import time as _time
    user_id = user_id.strip()
    character = character.strip()
    now_ts = int(_time.time())

    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT score, stage, next_due_utc, total_correct, total_wrong, total_i_dont_know
                FROM pinyin_recall_character_bank
                WHERE user_id = %s AND character = %s
                """,
                (user_id, character),
            )
            row = cur.fetchone()

        if row:
            score_before = int(row.get("score") or 0)
            stage = int(row.get("stage") or 0)
            total_correct = int(row.get("total_correct") or 0)
            total_wrong = int(row.get("total_wrong") or 0)
            total_i_dont_know = int(row.get("total_i_dont_know") or 0)
        else:
            score_before = 0
            stage = 0
            total_correct = 0
            total_wrong = 0
            total_i_dont_know = 0

        # Update counts
        if correct:
            total_correct += 1
        elif i_dont_know:
            total_i_dont_know += 1
        else:
            total_wrong += 1

        # Score: correct +10 (cap 100), wrong/我不知道 -10 (floor -50)
        if correct:
            score_after = min(score_before + PINYIN_RECALL_SCORE_CORRECT_DELTA, PINYIN_RECALL_SCORE_MAX)
        else:
            score_after = max(score_before - PINYIN_RECALL_SCORE_WRONG_DELTA, PINYIN_RECALL_SCORE_MIN)

        # next_due_utc by band-based cooling (Issue #12); stage kept for compatibility
        if i_dont_know or not correct:
            stage = 0
            next_due_utc = None
        else:
            days = _cooling_days_for_score(score_after)
            if days == 0:
                next_due_utc = now_ts + 60
            else:
                next_due_utc = now_ts + days * 86400
            # Map band to stage for analytics (0–3)
            stage = min(
                (3 if score_after >= PROFILE_LEARNED_MASTERED_MIN_SCORE else
                 2 if score_after > 0 else
                 1 if score_after > PROFILE_LEARNING_HARD_MAX_SCORE else 0),
                PINYIN_RECALL_MAX_STAGE,
            )

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pinyin_recall_character_bank (
                    user_id, character, score, stage, next_due_utc,
                    first_seen_at, last_answered_at, total_correct, total_wrong, total_i_dont_know
                ) VALUES (%s, %s, %s, %s, %s, now(), now(), %s, %s, %s)
                ON CONFLICT (user_id, character) DO UPDATE SET
                    score = EXCLUDED.score,
                    stage = EXCLUDED.stage,
                    next_due_utc = EXCLUDED.next_due_utc,
                    last_answered_at = now(),
                    total_correct = EXCLUDED.total_correct,
                    total_wrong = EXCLUDED.total_wrong,
                    total_i_dont_know = EXCLUDED.total_i_dont_know
                """,
                (user_id, character, score_after, stage, next_due_utc, total_correct, total_wrong, total_i_dont_know),
            )
        conn.commit()
        return (score_before, score_after)
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_pinyin_recall_item_presented(payload: Dict[str, Any]) -> None:
    """
    Insert one item_presented event into pinyin_recall_item_presented.
    payload: user_id, session_id, character, prompt_type, correct_choice, choices, batch_id?, batch_mode?, batch_character_category?.
    Table must exist (run scripts/create_pinyin_recall_log_tables.py once).
    batch_character_category: five-band at batch time (new|hard|learning_normal|learned_normal|mastered).
    """
    conn = _get_connection()
    try:
        choices = payload.get("choices")
        choices_json = json.dumps(choices) if choices is not None else "[]"
        batch_id = payload.get("batch_id")
        batch_mode = payload.get("batch_mode")
        batch_character_category = payload.get("batch_character_category")
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pinyin_recall_item_presented (
                    user_id, session_id, character, prompt_type, correct_choice, choices, batch_id, batch_mode, batch_character_category
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    (payload.get("user_id") or "").strip(),
                    (payload.get("session_id") or "").strip(),
                    (payload.get("character") or "").strip(),
                    (payload.get("prompt_type") or "").strip(),
                    (payload.get("correct_choice") or "").strip(),
                    choices_json,
                    batch_id,
                    batch_mode,
                    batch_character_category,
                ),
                prepare=False,
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_pinyin_recall_report_error(
    user_id: str,
    session_id: str,
    batch_id: Optional[str],
    character: str,
    page: Optional[str] = None,
) -> None:
    """
    Insert one report-error row into pinyin_recall_report_error.
    reported_at is set by DB default (now()). page: question, wrong, or correct.
    Table must exist.
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pinyin_recall_report_error (user_id, session_id, batch_id, character, page)
                VALUES (%s, %s, %s, %s, %s)
                """,
                (
                    (user_id or "").strip(),
                    (session_id or "").strip(),
                    (batch_id or "").strip() or None,
                    (character or "").strip(),
                    (page or "").strip() or None,
                ),
                prepare=False,
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def upsert_pinyin_recall_answer_and_log(
    user_id: str,
    character: str,
    correct: bool,
    i_dont_know: bool,
    log_payload: Dict[str, Any],
) -> Tuple[int, int]:
    """
    Do character-bank upsert and item_answered insert in one connection (faster: one round-trip).
    Returns (score_before, score_after). Mutates log_payload with score_before/score_after.
    """
    import time as _time
    user_id = user_id.strip()
    character = character.strip()
    now_ts = int(_time.time())

    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT score, stage, next_due_utc, total_correct, total_wrong, total_i_dont_know
                FROM pinyin_recall_character_bank
                WHERE user_id = %s AND character = %s
                """,
                (user_id, character),
            )
            row = cur.fetchone()

        if row:
            score_before = int(row.get("score") or 0)
            stage = int(row.get("stage") or 0)
            total_correct = int(row.get("total_correct") or 0)
            total_wrong = int(row.get("total_wrong") or 0)
            total_i_dont_know = int(row.get("total_i_dont_know") or 0)
        else:
            score_before = 0
            stage = 0
            total_correct = 0
            total_wrong = 0
            total_i_dont_know = 0

        category = _category_from_bank_state(total_correct, total_wrong, total_i_dont_know, score_before)

        if correct:
            total_correct += 1
        elif i_dont_know:
            total_i_dont_know += 1
        else:
            total_wrong += 1

        if correct:
            score_after = min(score_before + PINYIN_RECALL_SCORE_CORRECT_DELTA, PINYIN_RECALL_SCORE_MAX)
        else:
            score_after = max(score_before - PINYIN_RECALL_SCORE_WRONG_DELTA, PINYIN_RECALL_SCORE_MIN)

        if i_dont_know or not correct:
            stage = 0
            next_due_utc = None
        else:
            days = _cooling_days_for_score(score_after)
            if days == 0:
                next_due_utc = now_ts + 60
            else:
                next_due_utc = now_ts + days * 86400
            stage = min(
                (3 if score_after >= PROFILE_LEARNED_MASTERED_MIN_SCORE else
                 2 if score_after > 0 else
                 1 if score_after > PROFILE_LEARNING_HARD_MAX_SCORE else 0),
                PINYIN_RECALL_MAX_STAGE,
            )

        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pinyin_recall_character_bank (
                    user_id, character, score, stage, next_due_utc,
                    first_seen_at, last_answered_at, total_correct, total_wrong, total_i_dont_know
                ) VALUES (%s, %s, %s, %s, %s, now(), now(), %s, %s, %s)
                ON CONFLICT (user_id, character) DO UPDATE SET
                    score = EXCLUDED.score,
                    stage = EXCLUDED.stage,
                    next_due_utc = EXCLUDED.next_due_utc,
                    last_answered_at = now(),
                    total_correct = EXCLUDED.total_correct,
                    total_wrong = EXCLUDED.total_wrong,
                    total_i_dont_know = EXCLUDED.total_i_dont_know
                """,
                (user_id, character, score_after, stage, next_due_utc, total_correct, total_wrong, total_i_dont_know),
            )
            cur.execute(
                """
                INSERT INTO pinyin_recall_item_answered (
                    user_id, session_id, character, selected_choice, correct, latency_ms, i_dont_know, score_before, score_after, category
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    (log_payload.get("user_id") or "").strip(),
                    (log_payload.get("session_id") or "").strip(),
                    (log_payload.get("character") or "").strip(),
                    (log_payload.get("selected_choice") or "").strip() if log_payload.get("selected_choice") is not None else None,
                    bool(log_payload.get("correct") is True),
                    log_payload.get("latency_ms"),
                    bool(log_payload.get("i_dont_know") is True),
                    score_before,
                    score_after,
                    category,
                ),
                prepare=False,
            )
        conn.commit()
        log_payload["score_before"] = score_before
        log_payload["score_after"] = score_after
        log_payload["category"] = category
        return (score_before, score_after)
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_pinyin_recall_item_answered(payload: Dict[str, Any]) -> None:
    """
    Insert one item_answered event into pinyin_recall_item_answered.
    payload: user_id, session_id, character, selected_choice, correct, latency_ms, i_dont_know, score_before?, score_after?, category?.
    Table must exist (run scripts/create_pinyin_recall_log_tables.py once).
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pinyin_recall_item_answered (
                    user_id, session_id, character, selected_choice, correct, latency_ms, i_dont_know, score_before, score_after, category
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    (payload.get("user_id") or "").strip(),
                    (payload.get("session_id") or "").strip(),
                    (payload.get("character") or "").strip(),
                    (payload.get("selected_choice") or "").strip() if payload.get("selected_choice") is not None else None,
                    bool(payload.get("correct") is True),
                    payload.get("latency_ms"),
                    bool(payload.get("i_dont_know") is True),
                    payload.get("score_before"),
                    payload.get("score_after"),
                    payload.get("category"),
                ),
                prepare=False,
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def bulk_insert_pinyin_recall_item_presented(payloads: List[Dict[str, Any]]) -> int:
    """Insert multiple item_presented rows in one connection. Returns count inserted."""
    if not payloads:
        return 0
    conn = _get_connection()
    sql = """
        INSERT INTO pinyin_recall_item_presented (user_id, session_id, character, prompt_type, correct_choice, choices, batch_id, batch_mode, batch_character_category)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        with conn.cursor() as cur:
            for p in payloads:
                choices = p.get("choices")
                choices_json = json.dumps(choices) if choices is not None else "[]"
                cur.execute(sql, (
                    (p.get("user_id") or "").strip(),
                    (p.get("session_id") or "").strip(),
                    (p.get("character") or "").strip(),
                    (p.get("prompt_type") or "").strip(),
                    (p.get("correct_choice") or "").strip(),
                    choices_json,
                    p.get("batch_id"),
                    p.get("batch_mode"),
                    p.get("batch_character_category"),
                ), prepare=False)
        conn.commit()
        return len(payloads)
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def bulk_insert_pinyin_recall_item_answered(payloads: List[Dict[str, Any]]) -> int:
    """Insert multiple item_answered rows in one connection. Returns count inserted."""
    if not payloads:
        return 0
    conn = _get_connection()
    sql = """
        INSERT INTO pinyin_recall_item_answered (user_id, session_id, character, selected_choice, correct, latency_ms, i_dont_know, score_before, score_after, category)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """
    try:
        with conn.cursor() as cur:
            for p in payloads:
                cur.execute(sql, (
                    (p.get("user_id") or "").strip(),
                    (p.get("session_id") or "").strip(),
                    (p.get("character") or "").strip(),
                    (p.get("selected_choice") or "").strip() if p.get("selected_choice") is not None else None,
                    bool(p.get("correct") is True),
                    p.get("latency_ms"),
                    bool(p.get("i_dont_know") is True),
                    p.get("score_before"),
                    p.get("score_after"),
                    p.get("category"),
                ), prepare=False)
        conn.commit()
        return len(payloads)
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()
