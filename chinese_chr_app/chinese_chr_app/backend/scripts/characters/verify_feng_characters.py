#!/usr/bin/env python3
"""
Verify feng_characters table data matches the first 10 entries in characters.json.
"""

import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
CHARACTERS_JSON = OUTER_APP_DIR / "data" / "characters.json"


def get_has_words_by_pinyin_column(cur) -> bool:
    cur.execute(
        """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = current_schema()
              AND table_name = 'feng_characters'
              AND column_name = 'words_by_pinyin'
        )
        """
    )
    return bool(cur.fetchone()[0])


def main():
    try:
        import psycopg
    except ImportError:
        print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
        sys.exit(1)

    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("Set DATABASE_URL or SUPABASE_DB_URL")
        sys.exit(1)

    if not CHARACTERS_JSON.exists():
        print(f"Not found: {CHARACTERS_JSON}")
        sys.exit(1)

    with open(CHARACTERS_JSON, "r", encoding="utf-8") as f:
        expected_list = json.load(f)[:10]

    conn = psycopg.connect(url)
    try:
        with conn.cursor() as cur:
            has_words_by_pinyin = get_has_words_by_pinyin_column(cur)
            select_words_by_pinyin = ", words_by_pinyin" if has_words_by_pinyin else ""
            cur.execute(
                """
                SELECT character, index, zibiao_index, pinyin, radical, strokes,
                       structure, sentence, words
                       {select_words_by_pinyin}
                FROM feng_characters
                ORDER BY index
                LIMIT 10
                """.format(select_words_by_pinyin=select_words_by_pinyin)
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if len(rows) != 10:
        print(f"Expected 10 rows, got {len(rows)}")
        sys.exit(1)

    errors = []
    for i, row in enumerate(rows):
        if has_words_by_pinyin:
            char, index, zibiao_index, pinyin, radical, strokes, structure, sentence, words, words_by_pinyin = row
        else:
            char, index, zibiao_index, pinyin, radical, strokes, structure, sentence, words = row
            words_by_pinyin = None
        exp = expected_list[i]
        exp_char = (exp.get("Character") or "").strip()
        exp_index = (exp.get("Index") or "").strip()
        exp_zibiao = exp.get("zibiao_index")
        exp_strokes = int(exp["Strokes"]) if exp.get("Strokes") and str(exp["Strokes"]).strip().isdigit() else None
        exp_radical = (exp.get("Radical") or "").strip() or None
        exp_structure = (exp.get("Structure") or "").strip() or None
        exp_sentence = (exp.get("Sentence") or "").strip() or None
        exp_pinyin = exp.get("Pinyin") or []
        exp_words = exp.get("Words") or []
        exp_words_by_pinyin = exp.get("WordsByPinyin") or []

        if char != exp_char:
            errors.append(f"index {index}: character DB={char!r} JSON={exp_char!r}")
        if index != exp_index:
            errors.append(f"index {index}: index DB={index!r} JSON={exp_index!r}")
        if zibiao_index != exp_zibiao:
            errors.append(f"index {index}: zibiao_index DB={zibiao_index} JSON={exp_zibiao}")
        if strokes != exp_strokes:
            errors.append(f"index {index}: strokes DB={strokes} JSON={exp_strokes}")
        if radical != exp_radical:
            errors.append(f"index {index}: radical DB={radical!r} JSON={exp_radical!r}")
        if structure != exp_structure:
            errors.append(f"index {index}: structure DB={structure!r} JSON={exp_structure!r}")
        if sentence != exp_sentence:
            errors.append(f"index {index}: sentence mismatch (DB len={len(sentence or '')} JSON len={len(exp_sentence or '')})")
        if (pinyin or []) != exp_pinyin:
            errors.append(f"index {index}: pinyin DB={pinyin} JSON={exp_pinyin}")
        if (words or []) != exp_words:
            errors.append(f"index {index}: words length DB={len(words or [])} JSON={len(exp_words)}")
        if has_words_by_pinyin and (words_by_pinyin or []) != exp_words_by_pinyin:
            errors.append(
                f"index {index}: words_by_pinyin length DB={len(words_by_pinyin or [])} JSON={len(exp_words_by_pinyin)}"
            )

    if errors:
        print("Mismatches found:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    print("Verified: all 10 rows in feng_characters match the first 10 entries in characters.json.")
    if has_words_by_pinyin:
        print("  character, index, zibiao_index, strokes, radical, structure, sentence, pinyin, words, words_by_pinyin — all match.")
    else:
        print("  character, index, zibiao_index, strokes, radical, structure, sentence, pinyin, words — all match.")


if __name__ == "__main__":
    main()
