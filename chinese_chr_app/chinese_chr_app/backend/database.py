"""
Database layer for feng_characters and hwxnet_characters (Supabase/Postgres).

Returns dict shapes compatible with the rest of the app (same as JSON-based responses).
Uses Psycopg 3 (psycopg[binary]>=3.1) for Python 3.13+ compatibility.
"""

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
