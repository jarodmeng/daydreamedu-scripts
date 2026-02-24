#!/usr/bin/env python3
"""
Count characters that have no example words (词组) for the pinyin recall game.

Stem words come from: Feng Words (feng_characters.words) and HWXNet 例词
(inside hwxnet_characters.basic_meanings → 释义 → 例词). Characters with neither
show no 常见词组 in the game.

Run from backend/: python3 scripts/characters/count_characters_no_stem_words.py
Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.
"""

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


def has_hwxnet_example_words(basic_meanings) -> bool:
    """True if any 例词 exists in basic_meanings (same structure as get_stem_words)."""
    if not basic_meanings or not isinstance(basic_meanings, list):
        return False
    for sense in basic_meanings:
        for definition in (sense.get("释义") or []):
            for ex in (definition.get("例词") or []):
                if ex and (ex.strip() if isinstance(ex, str) else ex):
                    return True
    return False


def main():
    conn = psycopg.connect(url, row_factory=dict_row)
    try:
        with conn.cursor() as cur:
            # Feng: one row per character (first by index), character + words
            cur.execute("""
                SELECT DISTINCT ON (character) character, words
                FROM feng_characters
                ORDER BY character, index
            """)
            feng_by_char = {}
            for row in cur.fetchall():
                ch = (row.get("character") or "").strip()
                if not ch:
                    continue
                words = row.get("words")
                if ch not in feng_by_char:
                    feng_by_char[ch] = words

            # HWXNet: one row per character (first by zibiao_index), character + basic_meanings
            cur.execute("""
                SELECT DISTINCT ON (character) character, basic_meanings
                FROM hwxnet_characters
                ORDER BY character, zibiao_index
            """)
            hwxnet_by_char = {}
            for row in cur.fetchall():
                ch = (row.get("character") or "").strip()
                if not ch:
                    continue
                if ch not in hwxnet_by_char:
                    hwxnet_by_char[ch] = row.get("basic_meanings")

        # Universe: all characters that can appear in pinyin recall (from hwxnet)
        all_chars = set(hwxnet_by_char.keys())
        no_stem_words = []
        for ch in sorted(all_chars):
            feng_words = feng_by_char.get(ch)
            has_feng = bool(
                feng_words
                and isinstance(feng_words, list)
                and any(w and (str(w).strip() if w else False) for w in feng_words)
            )
            has_hwxnet = has_hwxnet_example_words(hwxnet_by_char.get(ch))
            if not has_feng and not has_hwxnet:
                no_stem_words.append(ch)

        total = len(all_chars)
        missing = len(no_stem_words)
        # Of those with no stem words, how many are in the Feng list at all?
        no_stem_in_feng = [ch for ch in no_stem_words if ch in feng_by_char]
        no_stem_not_in_feng = [ch for ch in no_stem_words if ch not in feng_by_char]
        print("Pinyin recall — 常见词组 (stem words: Feng Words + HWXNet 例词)")
        print("=" * 60)
        print(f"  Characters with no example words (词组): {missing:,} / {total:,}")
        print(f"  Of these, in Feng list (empty Words):     {len(no_stem_in_feng):,}")
        print(f"  Of these, not in Feng list (HWXNet only): {len(no_stem_not_in_feng):,}")
        if no_stem_words and len(no_stem_words) <= 50:
            print(f"  List: {''.join(no_stem_words)}")
        elif no_stem_words:
            print(f"  First 50: {''.join(no_stem_words[:50])} …")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
