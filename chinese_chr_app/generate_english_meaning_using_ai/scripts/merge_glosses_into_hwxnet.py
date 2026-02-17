#!/usr/bin/env python3
"""
Merge AI-generated glosses into extracted_characters_hwxnet.json.

Updates 英文翻译 and 拼音 for characters that have AI gloss output.
Backs up the original file before overwriting.

Usage:
  python3 merge_glosses_into_hwxnet.py
  python3 merge_glosses_into_hwxnet.py --gloss-files ../batch_artifacts/batch1_glosses.json --data-json ../data/extracted_characters_hwxnet.json
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
BATCH_ARTIFACTS = ROOT / "batch_artifacts"
DEFAULT_GLOSS_FILES = [
    BATCH_ARTIFACTS / "batch1_glosses.json",
    BATCH_ARTIFACTS / "batch2_glosses.json",
    BATCH_ARTIFACTS / "batch3a_glosses.json",
    BATCH_ARTIFACTS / "batch3b_glosses.json",
    BATCH_ARTIFACTS / "batch4_glosses.json",
]
DEFAULT_DATA_JSON = ROOT.parent / "data" / "extracted_characters_hwxnet.json"


def load_all_glosses(gloss_paths: list[Path]) -> dict:
    """Load and merge all gloss JSON files. Later files override earlier for same hanzi."""
    merged = {}
    for p in gloss_paths:
        if not p.exists():
            print(f"Warning: {p} not found, skipping", file=sys.stderr)
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for hanzi, gloss in data.items():
            merged[hanzi] = gloss
    return merged


def build_new_english_gloss(gloss: dict) -> list[str]:
    """Build 英文翻译 list: [primary_sense, ...alternative_senses]."""
    primary = gloss.get("primary_sense")
    alts = gloss.get("alternative_senses") or []
    if not isinstance(alts, list):
        alts = [alts] if alts else []

    result = []
    if primary is not None and str(primary).strip():
        result.append(str(primary).strip())
    for a in alts:
        if a is not None and str(a).strip():
            result.append(str(a).strip())
    return result


def reorder_pinyin(pinyin_list: list, primary_pinyin: str | None) -> list:
    """Put primary_pinyin first if not already. If not in list, add it first."""
    if not primary_pinyin or not str(primary_pinyin).strip():
        return pinyin_list or []

    primary = str(primary_pinyin).strip()
    current = list(pinyin_list) if pinyin_list else []

    if not current:
        return [primary]

    if current[0] == primary:
        return current

    # Remove primary from elsewhere if present, then put first
    rest = [p for p in current if p != primary]
    return [primary] + rest


def main() -> None:
    parser = argparse.ArgumentParser(description="Merge AI glosses into hwxnet data")
    parser.add_argument(
        "--gloss-files",
        nargs="+",
        type=Path,
        default=DEFAULT_GLOSS_FILES,
        help="Gloss JSON files to merge (later override earlier)",
    )
    parser.add_argument(
        "--data-json",
        type=Path,
        default=DEFAULT_DATA_JSON,
        help="extracted_characters_hwxnet.json path",
    )
    parser.add_argument(
        "--backup-suffix",
        default=".backup",
        help="Suffix for backup file (default: .backup)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write files",
    )
    args = parser.parse_args()

    if not args.data_json.exists():
        print(f"Error: {args.data_json} not found", file=sys.stderr)
        sys.exit(1)

    glosses = load_all_glosses(args.gloss_files)
    print(f"Loaded {len(glosses)} glosses", file=sys.stderr)

    data = json.loads(args.data_json.read_text(encoding="utf-8"))
    updated_count = 0

    for hanzi, gloss in glosses.items():
        if hanzi not in data:
            continue

        entry = data[hanzi]

        # 1. Replace 英文翻译 with [primary_sense, ...alternative_senses]
        new_translations = build_new_english_gloss(gloss)
        if new_translations:
            entry["英文翻译"] = new_translations

        # 2. Put primary_pinyin first in 拼音
        primary_pinyin = gloss.get("primary_pinyin")
        current_pinyin = entry.get("拼音")
        if isinstance(current_pinyin, str):
            current_pinyin = [current_pinyin] if current_pinyin else []
        elif not isinstance(current_pinyin, list):
            current_pinyin = []

        if primary_pinyin:
            entry["拼音"] = reorder_pinyin(current_pinyin, primary_pinyin)

        updated_count += 1

    print(f"Updated {updated_count} entries", file=sys.stderr)

    if args.dry_run:
        print("Dry run: no files written", file=sys.stderr)
        return

    # Backup
    backup_path = args.data_json.with_suffix(
        args.data_json.suffix + args.backup_suffix
    )
    shutil.copy2(args.data_json, backup_path)
    print(f"Backed up to {backup_path}", file=sys.stderr)

    # Write
    args.data_json.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {args.data_json}", file=sys.stderr)


if __name__ == "__main__":
    main()
