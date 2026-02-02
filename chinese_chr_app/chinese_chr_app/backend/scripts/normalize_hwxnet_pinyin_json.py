#!/usr/bin/env python3
"""
Normalize pinyin in extracted_characters_hwxnet.json in-place.

- Converts breve vowels (ă ĕ ĭ ŏ ŭ) to standard 3rd‑tone caron vowels (ǎ ě ǐ ǒ ǔ)
- Lowercases all pinyin syllables
- Deduplicates within each entry while preserving order

Run from backend/:
  python scripts/normalize_hwxnet_pinyin_json.py --dry-run   # just show sample diffs
  python scripts/normalize_hwxnet_pinyin_json.py             # rewrite JSON with backup
"""

import json
from pathlib import Path
import shutil
import sys
from typing import List


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
DATA_DIR = OUTER_APP_DIR / "data"
HWXNET_JSON = DATA_DIR / "extracted_characters_hwxnet.json"


def _normalize_pinyin_syllable(p: str) -> str:
    if not p:
        return p
    mapping = str.maketrans({
        "ă": "ǎ",
        "ĕ": "ě",
        "ĭ": "ǐ",
        "ŏ": "ǒ",
        "ŭ": "ǔ",
    })
    return p.translate(mapping).lower()


def _normalize_pinyin_list(p_list: List[str]) -> List[str]:
    if not p_list:
        return []
    seen = set()
    out: List[str] = []
    for raw in p_list:
        if not isinstance(raw, str):
            continue
        norm = _normalize_pinyin_syllable(raw.strip())
        if not norm:
            continue
        if norm not in seen:
            seen.add(norm)
            out.append(norm)
    return out


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Normalize pinyin in extracted_characters_hwxnet.json (breve -> caron, lowercase, dedupe)."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write changes; just print a few sample before/after rows.",
    )
    args = parser.parse_args()

    if not HWXNET_JSON.exists():
        print(f"{HWXNET_JSON} not found")
        sys.exit(1)

    with open(HWXNET_JSON, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        print("Unexpected JSON shape: expected dict keyed by character.")
        sys.exit(1)

    samples = []
    changed_count = 0

    for ch, entry in data.items():
        p_old = entry.get("拼音") or []
        if not isinstance(p_old, list):
            continue
        p_new = _normalize_pinyin_list(p_old)
        if p_new != p_old:
            changed_count += 1
            if len(samples) < 10:
                samples.append((ch, p_old, p_new))
            entry["拼音"] = p_new

    print(f"Entries with changed 拼音: {changed_count}")
    if samples:
        print("\nSample changes:")
        for ch, old, new in samples:
            print(f"  {ch}: {old} -> {new}")

    if args.dry_run:
        print("\nDry run only; no files written.")
        return

    backup_path = HWXNET_JSON.with_suffix(".pinyin_backup.json")
    shutil.copy2(HWXNET_JSON, backup_path)
    print(f"\nBackup written to: {backup_path}")

    with open(HWXNET_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Updated file written to: {HWXNET_JSON}")


if __name__ == "__main__":
    main()

