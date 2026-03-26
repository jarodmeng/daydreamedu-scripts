#!/usr/bin/env python3
"""
Merge the HWXNet 常用词组按拼音 transition field into extracted_characters_hwxnet.json.

Creates a timestamped backup of the main JSON in data/backups/ before overwriting.
The legacy 常用词组 field is left unchanged; only 常用词组按拼音 is added/updated.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from build_common_phrases_by_pinyin_transition import (
    FIELD_NAME,
    MAIN_JSON,
    REVIEWED_JSON,
    BACKUP_DIR,
    build_transition_map,
)


def load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    if not MAIN_JSON.exists():
        print(f"Error: main file not found: {MAIN_JSON}", file=sys.stderr)
        return 1
    if not REVIEWED_JSON.exists():
        print(f"Error: reviewed file not found: {REVIEWED_JSON}", file=sys.stderr)
        return 1

    print(f"Loading {MAIN_JSON} ...")
    main_data = load_json(MAIN_JSON)
    print(f"Loading {REVIEWED_JSON} ...")
    reviewed_data = load_json(REVIEWED_JSON)

    transition_map, stats = build_transition_map(main_data, reviewed_data)

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"extracted_characters_hwxnet.{ts}.json"
    print(f"Backing up main JSON to {backup_path} ...")
    backup_path.write_bytes(MAIN_JSON.read_bytes())
    print("Backup written.")

    updated = 0
    for character, entry in main_data.items():
        if not isinstance(entry, dict):
            continue
        entry[FIELD_NAME] = transition_map.get(character, [])
        updated += 1

    print(f"Updated {FIELD_NAME} for {updated} characters.")
    if stats["polyphonic_characters_missing_review"]:
        missing = stats["polyphonic_characters_missing_review"]
        print(
            "Polyphonic characters with flat 常用词组 but no reviewed artifact; left as empty buckets: "
            + ", ".join(missing[:20])
            + (" ..." if len(missing) > 20 else "")
        )

    print(f"Writing {MAIN_JSON} ...")
    MAIN_JSON.write_text(json.dumps(main_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
