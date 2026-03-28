#!/usr/bin/env python3
"""
Show Phase 1 reading-unit payloads for one character from the live DB.

Usage (run from backend/):
  python3 scripts/utils/show_reading_units.py 行

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
        print("Usage: python3 scripts/utils/show_reading_units.py <character>")
        sys.exit(1)

    ch = sys.argv[1]

    backend_dir = Path(__file__).resolve().parent.parent.parent
    sys.path.insert(0, str(backend_dir))
    import database as db  # type: ignore
    from pinyin_recall import build_reading_units_for_character  # type: ignore

    hwxnet_lookup = db.get_hwxnet_lookup()
    hwxnet_entry = hwxnet_lookup.get(ch)
    if not hwxnet_entry:
        print(f"No HWXNet entry for {ch}")
        sys.exit(1)

    feng_entry = db.get_feng_character_by_character(ch)
    units = build_reading_units_for_character(ch, hwxnet_entry, feng_entry)
    print(json.dumps(units, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
