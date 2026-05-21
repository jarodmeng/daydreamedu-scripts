#!/usr/bin/env python3
"""Print work queue summary and context for the next (or chosen) pending item."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
for p in (_REPO_ROOT, _SCRIPT_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from queue_common import (
    DEFAULT_WORK_QUEUE_PATH,
    detector_for_payload,
    load_work_queue,
    policy_prompt_for_payload,
)


def _find_item(items: list[dict], *, ord_num: int | None, next_pending: bool) -> dict | None:
    if ord_num is not None:
        for item in items:
            if item.get("ord") == ord_num:
                return item
        return None
    if next_pending:
        for item in items:
            if item.get("status") == "pending":
                return item
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_WORK_QUEUE_PATH)
    parser.add_argument("--ord", type=int, default=None, help="Show this ord (any status)")
    parser.add_argument("--next", action="store_true", help="Show first status=pending item")
    parser.add_argument("--json", action="store_true", help="Emit selected item as JSON only")
    parser.add_argument("--summary-only", action="store_true", help="Only print counts")
    args = parser.parse_args()

    path = args.queue.resolve()
    if not path.is_file():
        print(f"ERROR: queue not found: {path}", file=sys.stderr)
        print("Run build_work_queue.py first.", file=sys.stderr)
        return 1

    payload = load_work_queue(path)
    items = payload.get("items") or []
    counts = Counter(i.get("status") for i in items)

    if not args.json and not args.summary_only:
        print(f"Queue: {path}")
        print(f"  generated_at: {payload.get('generated_at')}")
        print(f"  student:   {payload.get('student_email')}")
        print(f"  subject:   {payload.get('subject')}")
        print(f"  policy:    {payload.get('policy')}")
        print(f"  detector:  {detector_for_payload(payload)}")
        print(f"  scanned:   {len(items)}")
        print(f"  pending:   {counts.get('pending', 0)}")
        print(f"  done:      {counts.get('done', 0)}")
        print(f"  failed:    {counts.get('failed', 0)}")
        print(f"  skipped:   {counts.get('skipped', 0)}")
        print(f"  blocked:   {counts.get('blocked', 0)}")

    if args.summary_only:
        return 0

    if not args.ord and not args.next:
        if counts.get("pending", 0) == 0:
            print("\nNo pending items.")
            return 0
        args.next = True

    item = _find_item(items, ord_num=args.ord, next_pending=args.next)
    if item is None:
        print("ERROR: no matching item", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(item, indent=2, ensure_ascii=True))
        return 0

    print()
    print(f"--- ord={item.get('ord')} status={item.get('status')} ---")
    print(f"completion_path:  {item.get('completion_path')}")
    print(f"completion_file_id: {item.get('completion_file_id')}")
    print(f"template_path:    {item.get('template_path')}")
    print(f"template_file_id: {item.get('template_file_id')}")
    print(f"marking_mode:     {item.get('marking_mode') or payload.get('marking_mode')}")
    print(f"book_answer_pages: {item.get('book_answer_pages')}")
    print(f"needs_detection:  {item.get('needs_detection')}")
    print(f"needs_marking:    {item.get('needs_marking')}")
    if item.get("marking_artifact_path"):
        print(f"marking_artifact_path: {item.get('marking_artifact_path')}")
    if item.get("error"):
        print(f"error: {item.get('error')}")
    print()
    print("--- marking_policy (paste into detector / marking prompts) ---")
    print(policy_prompt_for_payload(payload))
    policy = payload.get("marking_policy") or {}
    print(json.dumps(policy, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
