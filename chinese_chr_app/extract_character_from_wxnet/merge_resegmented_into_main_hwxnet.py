#!/usr/bin/env python3
"""
One-off script: merge 基本字义解释 from extracted_characters_hwxnet.resegmented_affected.json
into extracted_characters_hwxnet.json for the 417 affected characters.

Creates a timestamped backup of the main JSON in data/backups/ before overwriting.
Only 基本字义解释 is merged; 常用词组 and all other fields are left unchanged.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"
BACKUP_DIR = DATA_DIR / "backups"
MAIN_JSON = DATA_DIR / "extracted_characters_hwxnet.json"
RESEG_JSON = DATA_DIR / "extracted_characters_hwxnet.resegmented_affected.json"


def main() -> int:
    if not MAIN_JSON.exists():
        print(f"Error: main file not found: {MAIN_JSON}", file=sys.stderr)
        return 1
    if not RESEG_JSON.exists():
        print(f"Error: resegmented file not found: {RESEG_JSON}", file=sys.stderr)
        return 1

    print(f"Loading {MAIN_JSON} ...")
    with open(MAIN_JSON, "r", encoding="utf-8") as f:
        main = json.load(f)
    print(f"Loading {RESEG_JSON} ...")
    with open(RESEG_JSON, "r", encoding="utf-8") as f:
        reseg = json.load(f)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"extracted_characters_hwxnet.{ts}.json"
    print(f"Backing up main JSON to {backup_path} ...")
    try:
        backup_path.write_bytes(MAIN_JSON.read_bytes())
    except Exception as e:
        print(f"Error: failed to write backup: {e}", file=sys.stderr)
        return 1
    print("Backup written.")

    merged = 0
    skipped = 0
    for char, entry in reseg.items():
        if char not in main:
            skipped += 1
            continue
        if not isinstance(entry, dict) or "基本字义解释" not in entry:
            skipped += 1
            continue
        main[char]["基本字义解释"] = entry["基本字义解释"]
        merged += 1

    print(f"Merged 基本字义解释 for {merged} characters (skipped {skipped}).")
    print(f"Writing {MAIN_JSON} ...")
    with open(MAIN_JSON, "w", encoding="utf-8") as f:
        json.dump(main, f, ensure_ascii=False, indent=2)
    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
