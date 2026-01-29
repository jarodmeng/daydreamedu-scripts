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
    env_file = Path(__file__).resolve().parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
CHARACTERS_JSON = OUTER_APP_DIR / "data" / "characters.json"


def main():
    try:
        import psycopg
    except ImportError:
        print("psycopg is required. Install with: pip install 'psycopg[binary]>=3.1'")
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
            cur.execute(
                """
                SELECT character, index, zibiao_index, pinyin, radical, strokes,
                       structure, sentence, words
                FROM feng_characters
                ORDER BY index
                LIMIT 10
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()

    if len(rows) != 10:
        print(f"Expected 10 rows, got {len(rows)}")
        sys.exit(1)

    errors = []
    for i, row in enumerate(rows):
        char, index, zibiao_index, pinyin, radical, strokes, structure, sentence, words = row
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

    if errors:
        print("Mismatches found:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    print("Verified: all 10 rows in feng_characters match the first 10 entries in characters.json.")
    print("  character, index, zibiao_index, strokes, radical, structure, sentence, pinyin, words — all match.")


if __name__ == "__main__":
    main()
