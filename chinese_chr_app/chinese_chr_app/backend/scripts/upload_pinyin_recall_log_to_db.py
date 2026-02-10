#!/usr/bin/env python3
"""
One-off: upload local pinyin_recall.log lines into the two log tables.

Reads backend/logs/pinyin_recall.log (one JSON object per line), inserts
item_presented into pinyin_recall_item_presented and item_answered into
pinyin_recall_item_answered. Requires DATABASE_URL/SUPABASE_DB_URL.
Run scripts/create_pinyin_recall_log_tables.py first.

Run from backend/:
  python scripts/upload_pinyin_recall_log_to_db.py
  python scripts/upload_pinyin_recall_log_to_db.py --dry-run   # parse only, no insert
"""

import json
import os
import sys
from pathlib import Path

# Ensure backend/ is on path so "import database" works when run from backend/
_backend_dir = Path(__file__).resolve().parent.parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass


def main():
    log_file = _backend_dir / "logs" / "pinyin_recall.log"
    if not log_file.exists():
        print(f"Log file not found: {log_file}")
        sys.exit(1)

    dry_run = "--dry-run" in sys.argv
    if dry_run:
        print("Dry run: no inserts, only parse and count.")

    lines = []
    with open(log_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as e:
                print(f"Skip invalid JSON: {e}")
                continue
            ev = data.get("event")
            if ev not in ("item_presented", "item_answered"):
                print(f"Skip unknown event: {ev}")
                continue
            lines.append((ev, data))

    print(f"Parsed {len(lines)} events from {log_file}")

    if dry_run:
        print("Dry run done.")
        return

    try:
        import database as db
    except ImportError:
        print("database module not found. Run from backend/ with PYTHONPATH or from backend dir.")
        sys.exit(1)

    # Split into item_presented and item_answered payloads (drop "event" key)
    presented = [{k: v for k, v in p.items() if k != "event"} for ev, p in lines if ev == "item_presented"]
    answered = [{k: v for k, v in p.items() if k != "event"} for ev, p in lines if ev == "item_answered"]
    try:
        n_p = db.bulk_insert_pinyin_recall_item_presented(presented)
        n_a = db.bulk_insert_pinyin_recall_item_answered(answered)
        print(f"Inserted: {n_p} item_presented, {n_a} item_answered")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
