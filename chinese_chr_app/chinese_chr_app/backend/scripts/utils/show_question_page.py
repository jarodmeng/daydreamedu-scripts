#!/usr/bin/env python3
"""
Show what the pinyin-recall question page displays for a character (stem + character).
Uses the same DB and get_stem_words logic as the app.

Usage (run from backend/):
  python3 scripts/utils/show_question_page.py 玄

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

url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
if not url:
    print("DATABASE_URL or SUPABASE_DB_URL is not set.")
    sys.exit(1)

def main():
    if len(sys.argv) != 2 or len(sys.argv[1]) != 1:
        print("Usage: python3 scripts/utils/show_question_page.py <character>")
        sys.exit(1)
    character = sys.argv[1]

    # Use app's database and pinyin_recall so we match exactly what the question page shows
    backend_dir = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(backend_dir))
    import database as db
    from pinyin_recall import get_stem_words

    feng = db.get_feng_character_by_character(character)
    hwxnet_full = db.get_hwxnet_lookup()
    hwxnet_one = {character: hwxnet_full[character]} if character in hwxnet_full else {}
    character_lookup = {character: feng} if feng else {}

    stem_words = get_stem_words(character, character_lookup, hwxnet_one, 3)

    print("Question page for:", character)
    print("  看这个字：", character)
    if stem_words:
        print("  常见词组：", " / ".join(stem_words))
    else:
        print("  常见词组： (none)")
    print()
    if feng:
        print("  Feng Words:", feng.get("Words") or [])
    else:
        print("  Feng: no row")
    if character in hwxnet_full:
        entry = hwxnet_full[character]
        words_from_hwx = []
        for sense in entry.get("基本字义解释") or []:
            for definition in sense.get("释义") or []:
                for ex in definition.get("例词") or []:
                    if ex and ex not in words_from_hwx:
                        words_from_hwx.append(ex)
        print("  HWXNet 例词:", words_from_hwx)
        print("  拼音:", entry.get("拼音"))
    else:
        print("  HWXNet: no row")


if __name__ == "__main__":
    main()
