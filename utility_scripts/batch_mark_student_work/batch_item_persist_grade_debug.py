#!/usr/bin/env python3
"""After phase2 validate: copy phase2 + routing/section traces into bundle/debug/."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
for p in (_REPO_ROOT, _SCRIPT_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from batch_debug import persist_post_grade_debug
from ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3 import write_run_state


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meta-json", type=Path, required=True)
    parser.add_argument("--phase2-json", type=Path, required=True)
    parser.add_argument(
        "--grade-spec-json",
        type=Path,
        default=None,
        help="Optional batch_item_grade_context.py --json output",
    )
    parser.add_argument(
        "--validate-summary-json",
        type=Path,
        default=None,
        help="Optional JSON from batch_item_validate_phase2.py stdout",
    )
    parser.add_argument(
        "--phase3-enabled",
        action="store_true",
        help="Set when orchestrator ran Phase 3 (routing file reflects enabled)",
    )
    args = parser.parse_args()

    meta = json.loads(args.meta_json.read_text(encoding="utf-8"))
    rows = json.loads(args.phase2_json.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        print("ERROR: phase2 JSON must be an array", file=sys.stderr)
        return 1

    bundle_root = Path(meta["bundle_root"]).resolve()
    validate_summary = None
    if args.validate_summary_json and args.validate_summary_json.is_file():
        validate_summary = json.loads(args.validate_summary_json.read_text(encoding="utf-8"))

    grade_spec = None
    if args.grade_spec_json and args.grade_spec_json.is_file():
        grade_spec = json.loads(args.grade_spec_json.read_text(encoding="utf-8"))

    paths = persist_post_grade_debug(
        bundle_root=bundle_root,
        meta=meta,
        phase2_rows=rows,
        phase3_enabled=args.phase3_enabled,
        validate_summary=validate_summary,
        grade_spec=grade_spec,
    )
    write_run_state(bundle_root=bundle_root, state="phase2_persisted")

    print(json.dumps({"ok": True, **paths}, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
