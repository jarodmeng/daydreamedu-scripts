#!/usr/bin/env python3
"""Update one work_queue.json item after detector or marking completes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
for p in (_REPO_ROOT, _SCRIPT_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ai_study_buddy.marking.core.marking_time import now_marking_iso
from queue_common import DEFAULT_WORK_QUEUE_PATH, load_work_queue, save_work_queue

VALID_STATUSES = frozenset({"pending", "done", "failed", "skipped", "blocked"})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, default=DEFAULT_WORK_QUEUE_PATH)
    parser.add_argument("--ord", type=int, required=True)
    parser.add_argument("--status", required=True, choices=sorted(VALID_STATUSES))
    parser.add_argument("--artifact", type=str, default=None, help="marking_result JSON path when status=done")
    parser.add_argument("--error", type=str, default=None)
    parser.add_argument("--detector-done", action="store_true", help="Set detector_completed_at timestamp")
    args = parser.parse_args()

    path = args.queue.resolve()
    payload = load_work_queue(path)
    items = payload.get("items") or []
    target = None
    for item in items:
        if item.get("ord") == args.ord:
            target = item
            break
    if target is None:
        print(f"ERROR: ord={args.ord} not found", file=sys.stderr)
        return 1

    target["status"] = args.status
    if args.artifact:
        target["marking_artifact_path"] = str(Path(args.artifact).resolve())
    if args.error:
        target["error"] = args.error
    elif args.status == "done":
        target["error"] = None
    if args.detector_done:
        target["detector_completed_at"] = now_marking_iso()
        target["needs_detection"] = False
        if args.status == "pending":
            target["needs_marking"] = True

    save_work_queue(payload, path)
    print(f"Updated ord={args.ord} -> status={args.status}")
    if target.get("marking_artifact_path"):
        print(f"  artifact: {target['marking_artifact_path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
