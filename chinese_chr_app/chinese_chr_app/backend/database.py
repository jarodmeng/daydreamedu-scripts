"""
Database layer for feng_characters and hwxnet_characters (Supabase/Postgres).

Returns dict shapes compatible with the rest of the app (same as JSON-based responses).
Uses Psycopg 3 (psycopg[binary]>=3.1) for Python 3.13+ compatibility.
"""

import json
import os
from typing import Any, Dict, List, Optional, Tuple

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None


def _get_connection():
    if psycopg is None:
        raise RuntimeError("psycopg is required for database support. Install with: pip install 'psycopg[binary]>=3.1'")
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
                "SELECT character, zibiao_index, index, source_url, classification, pinyin, radical, strokes, basic_meanings, english_translations FROM hwxnet_characters"
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
    """Return daily stats: date, answered, correct. Ordered by date DESC (most recent first)."""
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    DATE(created_at AT TIME ZONE 'UTC') AS day,
                    COUNT(*) AS answered,
                    SUM(CASE WHEN correct THEN 1 ELSE 0 END)::int AS correct
                FROM pinyin_recall_item_answered
                WHERE user_id = %s
                  AND created_at >= (NOW() AT TIME ZONE 'UTC') - (%s || ' days')::interval
                GROUP BY DATE(created_at AT TIME ZONE 'UTC')
                ORDER BY day DESC
                LIMIT %s
                """,
                (user_id.strip(), str(days), days),
            )
            rows = cur.fetchall()
        return [
            {
                "date": str(r.get("day") or ""),
                "answered": int(r.get("answered") or 0),
                "correct": int(r.get("correct") or 0),
            }
            for r in rows
        ]
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


# --- Pinyin recall character bank (MVP1) ---
# Score 0-100; higher = better understanding. Stage ladder same as pinyin_recall.py.
PINYIN_RECALL_SCORE_CORRECT_DELTA = 10
PINYIN_RECALL_SCORE_WRONG_DELTA = 15
PINYIN_RECALL_SCORE_MIN = 0
PINYIN_RECALL_SCORE_MAX = 100
PINYIN_RECALL_STAGE_INTERVAL_DAYS = [0, 1, 3, 7, 14, 30]
PINYIN_RECALL_MAX_STAGE = len(PINYIN_RECALL_STAGE_INTERVAL_DAYS) - 1


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

        # Score: correct +10 (cap 100), wrong/我不知道 -15 (floor 0)
        if correct:
            score_after = min(score_before + PINYIN_RECALL_SCORE_CORRECT_DELTA, PINYIN_RECALL_SCORE_MAX)
        else:
            score_after = max(score_before - PINYIN_RECALL_SCORE_WRONG_DELTA, PINYIN_RECALL_SCORE_MIN)

        # Stage and next_due: same logic as pinyin_recall.update_learning_state
        if i_dont_know or not correct:
            stage = 0
            next_due_utc = None
        else:
            stage = min(stage + 1, PINYIN_RECALL_MAX_STAGE)
            days = PINYIN_RECALL_STAGE_INTERVAL_DAYS[stage]
            if days == 0:
                next_due_utc = now_ts + 60
            else:
                next_due_utc = now_ts + days * 86400

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
    payload: user_id, session_id, character, prompt_type, correct_choice, choices.
    Table must exist (run scripts/create_pinyin_recall_log_tables.py once).
    """
    conn = _get_connection()
    try:
        choices = payload.get("choices")
        choices_json = json.dumps(choices) if choices is not None else "[]"
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pinyin_recall_item_presented (
                    user_id, session_id, character, prompt_type, correct_choice, choices
                ) VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (
                    (payload.get("user_id") or "").strip(),
                    (payload.get("session_id") or "").strip(),
                    (payload.get("character") or "").strip(),
                    (payload.get("prompt_type") or "").strip(),
                    (payload.get("correct_choice") or "").strip(),
                    choices_json,
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
            stage = min(stage + 1, PINYIN_RECALL_MAX_STAGE)
            days = PINYIN_RECALL_STAGE_INTERVAL_DAYS[stage]
            if days == 0:
                next_due_utc = now_ts + 60
            else:
                next_due_utc = now_ts + days * 86400

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
                    user_id, session_id, character, selected_choice, correct, latency_ms, i_dont_know, score_before, score_after
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                ),
                prepare=False,
            )
        conn.commit()
        log_payload["score_before"] = score_before
        log_payload["score_after"] = score_after
        return (score_before, score_after)
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()


def insert_pinyin_recall_item_answered(payload: Dict[str, Any]) -> None:
    """
    Insert one item_answered event into pinyin_recall_item_answered.
    payload: user_id, session_id, character, selected_choice, correct, latency_ms, i_dont_know, score_before?, score_after?.
    Table must exist (run scripts/create_pinyin_recall_log_tables.py once).
    """
    conn = _get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO pinyin_recall_item_answered (
                    user_id, session_id, character, selected_choice, correct, latency_ms, i_dont_know, score_before, score_after
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
        INSERT INTO pinyin_recall_item_presented (user_id, session_id, character, prompt_type, correct_choice, choices)
        VALUES (%s, %s, %s, %s, %s, %s)
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
        INSERT INTO pinyin_recall_item_answered (user_id, session_id, character, selected_choice, correct, latency_ms, i_dont_know, score_before, score_after)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
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
                ), prepare=False)
        conn.commit()
        return len(payloads)
    except Exception as e:
        conn.rollback()
        raise
    finally:
        conn.close()
