#!/usr/bin/env python3
"""
Print full HWXNet DB entry for a character (basic_meanings, 拼音, etc.) for debugging.

Usage (run from backend/):
  python3 scripts/utils/show_hwxnet_entry.py 沈

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
        print("Usage: python3 scripts/utils/show_hwxnet_entry.py <character>")
        sys.exit(1)
    ch = sys.argv[1]

    backend_dir = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(backend_dir))
    import database as db

    hwx = db.get_hwxnet_lookup()
    if ch not in hwx:
        print(f"No HWXNet entry for {ch}")
        sys.exit(1)

    entry = hwx[ch]
    print("Character:", entry.get("character"))
    print("拼音 (pinyin, first = 'correct' in game):", entry.get("拼音"))
    print("部首:", entry.get("部首"))
    print("总笔画:", entry.get("总笔画"))
    print()
    print("基本字义解释 (raw):")
    print(json.dumps(entry.get("基本字义解释") or [], ensure_ascii=False, indent=2))
    print()
    print("英文翻译:", entry.get("英文翻译"))


if __name__ == "__main__":
    main()
