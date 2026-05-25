#!/usr/bin/env python3
"""Emit the single allowed grading Task spec for one batch queue item (post-prep)."""

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

from batch_debug import bundle_debug_paths, write_v3_batch_grade_spec
from ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3 import write_run_state
from queue_common import load_work_queue, policy_prompt_for_payload

V3_SKILL_REL = ".cursor/skills/mark-student-work-multi-agent-v3/SKILL.md"
ORCHESTRATOR_AGENT = "mark-student-work-v3-batch-orchestrator"
DEFAULT_PHASE2_OUT = "/tmp/phase2_ord{ord}.json"


def _build_prompt(
    *,
    ord_num: int,
    meta: dict,
    marking_policy: str,
    output_phase2_path: Path,
    debug_paths: dict[str, str],
) -> str:
    sections = meta.get("sections") or []
    if not sections:
        raise ValueError("meta has no sections[] — run batch_item_prep.py first")

    expected_rows = sum(len(s.get("question_ids") or []) for s in sections)
    lines = [
        "Batch queue item — v3 Phase 2 orchestration (one completion).",
        "",
        f"ord: {ord_num}",
        f"v3_skill (read first): {_REPO_ROOT / V3_SKILL_REL}",
        f"bundle_root: {meta['bundle_root']}",
        f"marking_mode: {meta.get('marking_mode')}",
        f"completion_path: {meta.get('completion_path')}",
        f"output_phase2_path: {output_phase2_path}",
        f"expected_phase2_row_count: {expected_rows}",
        f"required_section_task_count: {len(sections)}",
        "",
        "marking_policy:",
        marking_policy.strip(),
        "",
    ]
    marks = meta.get("authoritative_marks_by_question")
    if meta.get("policy") == "exercise" and isinstance(marks, dict) and marks:
        lines.extend(
            [
                "authoritative_max_marks_by_question (pass to each section grader; full credit = this max):",
                json.dumps(marks, indent=2, ensure_ascii=True),
                "",
            ]
        )
    lines.extend(
        [
            "sections (spawn exactly one marking-phase2-fast-pass-grader-v3 Task per entry):",
            json.dumps(sections, indent=2, ensure_ascii=True),
            "",
        ]
    )
    batches = meta.get("phase2_batches")
    if batches:
        lines.extend(
            [
                "phase2_batches (parallel launch waves only — NOT combined grader scope):",
                json.dumps(batches, indent=2, ensure_ascii=True),
                "",
            ]
        )
    lines.extend(
        [
            "Deliverables:",
            f"1. Write merged phase2 JSON array to: {output_phase2_path}",
            "2. section_tasks_launched must equal required_section_task_count",
            f"3. phase2_row_count must equal {expected_rows}",
            "",
            "Debug tracing (mandatory — write under bundle debug/ as you go):",
            f"  debug_dir: {debug_paths['debug_dir']}",
            "  At start: v3_batch_orchestration_trace.json — ord, sections, phase2_batches, task plan.",
            "  After each section grader returns: phase2_section_{section_index}.json — "
            "{section_index, section_label, question_ids, row_count, rows} for that section only.",
            f"  At end (before returning): phase2_orchestrator_summary.json — section_tasks_launched, "
            f"phase2_row_count, output_phase2_path, per-section status.",
            "  Parent scripts also persist phase2_fast_pass + routing after validate; "
            "your per-section files are the live audit trail.",
            "",
            "Phase 3 (optional): only when parent requests --with-phase3 in this prompt.",
            f"  Then also write: {debug_paths['phase3_deep_dive']}, "
            f"{debug_paths['phase3_question_execution_trace']}",
            "",
            "Forbidden: one grader Task covering multiple sections; grading inline in parent chat.",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ord", type=int, required=True)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--meta-json", type=Path, required=True, help="batch_item_prep stdout JSON")
    parser.add_argument(
        "--output-phase2",
        type=Path,
        default=None,
        help=f"Where orchestrator must write phase2 (default: {DEFAULT_PHASE2_OUT})",
    )
    parser.add_argument("--json", action="store_true", help="Emit Task spec as JSON")
    args = parser.parse_args()

    meta_path = args.meta_json.resolve()
    if not meta_path.is_file():
        print(f"ERROR: meta not found: {meta_path}", file=sys.stderr)
        return 1

    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    payload = load_work_queue(args.queue)
    marking_policy = policy_prompt_for_payload(payload)
    out_path = args.output_phase2 or Path(DEFAULT_PHASE2_OUT.format(ord=args.ord))
    bundle_root = Path(meta["bundle_root"]).resolve()
    debug_paths = bundle_debug_paths(bundle_root)

    try:
        prompt = _build_prompt(
            ord_num=args.ord,
            meta=meta,
            marking_policy=marking_policy,
            output_phase2_path=out_path.resolve(),
            debug_paths=debug_paths,
        )
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    spec = {
        "subagent_type": ORCHESTRATOR_AGENT,
        "description": f"v3 grade ord {args.ord}",
        "prompt": prompt,
        "bundle_root": str(bundle_root),
        "debug_paths": debug_paths,
        "output_phase2_path": str(out_path.resolve()),
        "expected_section_task_count": len(meta.get("sections") or []),
        "expected_phase2_row_count": sum(
            len(s.get("question_ids") or []) for s in (meta.get("sections") or [])
        ),
        "v3_skill_path": str((_REPO_ROOT / V3_SKILL_REL).resolve()),
        "forbidden_subagent_types_from_parent": ["marking-phase2-fast-pass-grader-v3"],
        "debug_artifacts_orchestrator_must_write": [
            "v3_batch_orchestration_trace.json",
            "phase2_section_{section_index}.json (one per section)",
            "phase2_orchestrator_summary.json",
        ],
        "debug_artifacts_parent_persists_after_validate": [
            "phase2_fast_pass.json",
            "phase2_section_execution_trace.json",
            "phase2_phase3_routing.json",
            "phase2_validate_gate.json",
            "v3_batch_grade_spec.json",
        ],
    }
    write_v3_batch_grade_spec(bundle_root=bundle_root, spec=spec)
    write_run_state(bundle_root=bundle_root, state="phase2_ready")

    if args.json:
        print(json.dumps(spec, indent=2, ensure_ascii=True))
    else:
        print(prompt)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
