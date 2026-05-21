#!/usr/bin/env python3
"""Finalize one batch item from phase2_rows JSON and update work_queue."""

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

from ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3 import (
    V3InputRequest,
    cleanup_stale_partials_for_v3_run,
    finalize_phase_e_artifact,
    prepare_finalize_rows,
    resolve_attempt_input_to_pdf_file,
    resolve_question_sections_authority,
    resolve_v3_marking_context,
    write_run_state,
)
from ai_study_buddy.marking.workflows.report_renderer import render_learning_report_from_json
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
from policies import english_finalize_required
from queue_common import DEFAULT_WORK_QUEUE_PATH, load_work_queue, normalize_phase2_rows, save_work_queue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ord", type=int, required=True)
    parser.add_argument("--phase2-json", type=Path, required=True, help="JSON array of phase2 rows")
    parser.add_argument("--meta-json", type=Path, required=True, help="batch_item_meta.json from prep stdout or bundle/debug/")
    parser.add_argument("--queue", type=Path, default=DEFAULT_WORK_QUEUE_PATH)
    parser.add_argument("--context-root", type=Path, default=Path("ai_study_buddy/context"))
    args = parser.parse_args()

    phase2_rows = normalize_phase2_rows(json.loads(args.phase2_json.read_text(encoding="utf-8")))
    meta = json.loads(args.meta_json.read_text(encoding="utf-8"))

    context_root = args.context_root.resolve()
    bundle_root = Path(meta["bundle_root"])
    run_at = meta["run_at"]
    completion = Path(meta["completion_path"])

    mgr = PdfFileManager()
    req = V3InputRequest(attempt_file_id_or_path=str(completion))
    attempt = resolve_attempt_input_to_pdf_file(manager=mgr, request=req)
    payload_queue = load_work_queue(args.queue)
    queue_mode = payload_queue.get("marking_mode")
    mode_kwarg = "teacher_annotated" if queue_mode == "teacher_annotated" else None
    ctx = resolve_v3_marking_context(manager=mgr, request=req, marking_mode=mode_kwarg)
    template = mgr.get_template(attempt.id)
    authority = resolve_question_sections_authority(template_file=template)

    prep = prepare_finalize_rows(
        question_sections_payload=dict(authority.payload),
        phase2_rows=phase2_rows,
        phase3_rows=[],
        english_required=english_finalize_required(payload_queue),
    )
    result = finalize_phase_e_artifact(
        context=ctx,
        merged_rows=prep.merged_rows,
        mode=ctx.marking_mode,
        bundle_root=bundle_root,
        context_root=context_root,
        deep_dive_count=0,
        phase2_subagents=1,
        run_start_iso=run_at,
    )
    write_run_state(bundle_root=bundle_root, state="finalized")
    cleanup_stale_partials_for_v3_run(
        context_root=context_root,
        attempt_file_path=attempt.path,
        student_id=ctx.student_id,
        student_name=None,
        subject_context=ctx.subject_context,
        keep_bundle_root=bundle_root,
    )
    report = render_learning_report_from_json(result.artifact_path, context_root=context_root)

    payload = load_work_queue(args.queue)
    for item in payload["items"]:
        if item.get("ord") == args.ord:
            item["status"] = "done"
            item["marking_artifact_path"] = str(result.artifact_path.resolve())
            item["needs_marking"] = False
            item["needs_detection"] = False
            item["error"] = None
            break
    save_work_queue(payload, args.queue)

    print(json.dumps({"artifact_path": str(result.artifact_path), "report_path": str(report)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
