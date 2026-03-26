#!/usr/bin/env python3
"""
Show phrase-source inputs for one character from the live DB.

Usage (run from backend/):
  python3 scripts/utils/show_character_phrase_sources.py 行

Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.
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

if not (os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")):
    print("DATABASE_URL or SUPABASE_DB_URL is not set.")
    sys.exit(1)


def main():
    if len(sys.argv) != 2 or len(sys.argv[1]) != 1:
        print("Usage: python3 scripts/utils/show_character_phrase_sources.py <character>")
        sys.exit(1)

    ch = sys.argv[1]

    backend_dir = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(backend_dir))
    import database as db  # type: ignore

    hwx = db.get_hwxnet_lookup()
    feng = db.get_feng_character_by_character(ch)

    entry = hwx.get(ch)
    if not entry:
        print(f"No HWXNet entry for {ch}")
        sys.exit(1)

    payload = {
        "character": ch,
        "source_url": entry.get("source_url"),
        "hwxnet_pinyin": entry.get("拼音") or [],
        "feng_words": (feng or {}).get("Words") or [],
        "hwxnet_common_phrases": entry.get("常用词组") or [],
        "hwxnet_common_phrases_by_pinyin": entry.get("常用词组按拼音") or [],
        "basic_meanings": entry.get("基本字义解释") or [],
    }

    print(json.dumps(payload, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
