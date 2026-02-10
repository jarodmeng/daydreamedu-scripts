#!/usr/bin/env python3
"""
Reorder 拼音 in extracted_characters_hwxnet.json based on 基本字义解释.

- Uses the order of 读音 entries in 基本字义解释 (or textual 基本解释/basic_explanation fallback)
  as the canonical ordering for each character's 拼音 list.
- Any extra pinyin that appear in 拼音 but not in 基本字义解释 are kept and appended at the end.

Usage (run from backend/ directory):

  python scripts/reorder_hwxnet_pinyin_from_basic.py --dry-run   # show sample diffs only
  python scripts/reorder_hwxnet_pinyin_from_basic.py             # rewrite JSON with backup
"""

import json
from pathlib import Path
import shutil
import sys
from typing import Dict, Any, List


SCRIPT_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SCRIPT_DIR.parent
OUTER_APP_DIR = BACKEND_DIR.parent.parent
DATA_DIR = OUTER_APP_DIR / "data"
HWXNET_JSON = DATA_DIR / "extracted_characters_hwxnet.json"


def _split_pinyins(s: str) -> List[str]:
    """Split a pinyin string on common separators."""
    if not isinstance(s, str):
        return []
    seps = " 、，,;"
    cur = ""
    out: List[str] = []
    for c in s:
        if c in seps:
            if cur.strip():
                out.append(cur.strip())
            cur = ""
        else:
            cur += c
    if cur.strip():
        out.append(cur.strip())
    return out


def _normalize_pinyin_sequence(value: Any) -> List[str]:
    """Normalize the 拼音 field into a flat list of non-empty strings."""
    if isinstance(value, list):
        out: List[str] = []
        for item in value:
            if not isinstance(item, str):
                continue
            s = item.strip()
            if s:
                out.append(s)
        return out
    if isinstance(value, str):
        return [s for s in _split_pinyins(value) if s]
    return []


def _extract_basic_order(entry: Dict[str, Any]) -> List[str]:
    """
    Extract the ordered list of pinyin from 基本字义解释 if present, otherwise from
    textual 基本解释/basic_explanation.
    """
    basic_list = (
        entry.get("基本字义解释")
        or entry.get("基本解释")
        or entry.get("basic_explanation")
    )

    if not basic_list:
        return []

    # Preferred structured form: list of dicts with 读音
    if (
        isinstance(basic_list, list)
        and basic_list
        and isinstance(basic_list[0], dict)
        and basic_list[0].get("读音")
    ):
        out: List[str] = []
        for d in basic_list:
            if not isinstance(d, dict):
                continue
            py = str(d.get("读音", "")).strip()
            if py:
                out.append(py)
        return out

    # Fallback: textual form like "pǔ：..." possibly across lines
    if isinstance(basic_list, str):
        lines = basic_list.splitlines()
    else:
        # join other shapes (e.g. list of strings) into a multi-line string
        lines = str(basic_list).splitlines()

    order: List[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        head = line
        for colon in ("：", ":"):
            if colon in head:
                head = head.split(colon, 1)[0].strip()
                break
        if head:
            order.extend(_split_pinyins(head))
    return [s for s in order if s]


def _reorder_pinyin_for_entry(entry: Dict[str, Any]) -> List[str]:
    """
    Compute the reordered 拼音 list for a single character entry.
    Returns the new list; caller is responsible for assigning it back.
    """
    p_list = _normalize_pinyin_sequence(entry.get("拼音") or entry.get("pinyin"))
    if not p_list:
        return []

    basic_order = _extract_basic_order(entry)
    if not basic_order:
        # Nothing better to do; preserve original order
        return p_list

    seen = set()
    new_order: List[str] = []

    # First: pinyin that appear in 基本字义解释, in that order
    for py in basic_order:
        if py in p_list and py not in seen:
            new_order.append(py)
            seen.add(py)

    # Then: any remaining pinyin from original 拼音 field
    for py in p_list:
        if py not in seen:
            new_order.append(py)
            seen.add(py)

    return new_order


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Reorder 拼音 in extracted_characters_hwxnet.json based on 基本字义解释.",
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
        p_old = _normalize_pinyin_sequence(entry.get("拼音") or entry.get("pinyin"))
        if not p_old:
            continue

        p_new = _reorder_pinyin_for_entry(entry)
        if not p_new or p_new == p_old:
            continue

        changed_count += 1
        if len(samples) < 15:
            samples.append((ch, p_old, p_new))
        entry["拼音"] = p_new

    print(f"Entries with reordered 拼音: {changed_count}")
    if samples:
        print("\nSample changes:")
        for ch, old, new in samples:
            print(f"  {ch}: {old} -> {new}")

    if args.dry_run:
        print("\nDry run only; no files written.")
        return

    backup_path = HWXNET_JSON.with_suffix(".pinyin_reorder_backup.json")
    shutil.copy2(HWXNET_JSON, backup_path)
    print(f"\nBackup written to: {backup_path}")

    with open(HWXNET_JSON, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"Updated file written to: {HWXNET_JSON}")


if __name__ == "__main__":
    main()

