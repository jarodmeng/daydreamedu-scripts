#!/usr/bin/env python3
"""
Verify hwxnet_characters table data matches the first 10 entries in
extracted_characters_hwxnet.json.
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
HWXNET_JSON = OUTER_APP_DIR / "data" / "extracted_characters_hwxnet.json"


def norm_index(v):
    if v is None:
        return None
    s = str(v).strip()
    return s if s else None


def norm_strokes(entry):
    v = entry.get("总笔画")
    if v is None:
        return None
    if isinstance(v, int):
        return v
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


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

    if not HWXNET_JSON.exists():
        print(f"Not found: {HWXNET_JSON}")
        sys.exit(1)

    with open(HWXNET_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = list(data.items())[:10]
    expected_list = [v for _k, v in items]
    expected_by_key = {}
    for e in expected_list:
        z = e.get("zibiao_index")
        if z is not None:
            if not isinstance(z, int):
                try:
                    z = int(z)
                except (TypeError, ValueError):
                    continue
            key = ((e.get("character") or "").strip(), z)
            expected_by_key[key] = e

    conn = psycopg.connect(url)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT character, zibiao_index, index, source_url, classification,
                       pinyin, radical, strokes, basic_meanings, english_translations
                FROM hwxnet_characters
                ORDER BY zibiao_index
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
    for row in rows:
        (char, zibiao_index, index, source_url, classification, pinyin, radical, strokes,
         basic_meanings, english_translations) = row
        key = (char, zibiao_index)
        exp = expected_by_key.get(key)
        if not exp:
            errors.append(f"({char}, zibiao_index={zibiao_index}): no expected entry in JSON")
            continue

        exp_index = norm_index(exp.get("index"))
        exp_url = (exp.get("source_url") or "").strip() or None
        exp_class = exp.get("分类") or []
        exp_pinyin = exp.get("拼音") or []
        exp_radical = (exp.get("部首") or "").strip() or None
        exp_strokes = norm_strokes(exp)
        exp_meanings = exp.get("基本字义解释") or []
        exp_eng = exp.get("英文翻译") or []

        if index != exp_index:
            errors.append(f"{char} zibiao={zibiao_index}: index DB={index!r} JSON={exp_index!r}")
        if source_url != exp_url:
            errors.append(f"{char} zibiao={zibiao_index}: source_url mismatch")
        if (classification or []) != exp_class:
            errors.append(f"{char} zibiao={zibiao_index}: classification mismatch")
        if (pinyin or []) != exp_pinyin:
            errors.append(f"{char} zibiao={zibiao_index}: pinyin DB={pinyin} JSON={exp_pinyin}")
        if radical != exp_radical:
            errors.append(f"{char} zibiao={zibiao_index}: radical DB={radical!r} JSON={exp_radical!r}")
        if strokes != exp_strokes:
            errors.append(f"{char} zibiao={zibiao_index}: strokes DB={strokes} JSON={exp_strokes}")
        if (basic_meanings or []) != exp_meanings:
            errors.append(f"{char} zibiao={zibiao_index}: basic_meanings length DB={len(basic_meanings or [])} JSON={len(exp_meanings)}")
        if (english_translations or []) != exp_eng:
            errors.append(f"{char} zibiao={zibiao_index}: english_translations DB={english_translations} JSON={exp_eng}")

    if errors:
        print("Mismatches found:")
        for e in errors:
            print(f"  {e}")
        sys.exit(1)

    print("Verified: all 10 rows in hwxnet_characters match the first 10 entries in extracted_characters_hwxnet.json.")
    print("  character, zibiao_index, index, source_url, classification, pinyin, radical, strokes, basic_meanings, english_translations — all match.")


if __name__ == "__main__":
    main()
