#!/usr/bin/env python3
"""Finalize one batch item from phase2_rows JSON and update work_queue."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import replace
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
from batch_debug import write_debug_json
from policies import english_finalize_required_for_item, marking_mode_for_item
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
    queue_item = next((i for i in payload_queue.get("items") or [] if i.get("ord") == args.ord), None)
    if queue_item is None:
        print(f"ERROR: ord={args.ord} not found in queue", file=sys.stderr)
        return 1
    mode_kwarg = marking_mode_for_item(queue_item, payload_queue)
    bundled_answer_path = queue_item.get("answer_file_path")
    bundled_answer_pages = queue_item.get("book_answer_pages") or {}
    if bundled_answer_path and bundled_answer_pages:
        ctx = resolve_v3_marking_context(manager=mgr, request=req, marking_mode="teacher_annotated")
        bap = bundled_answer_pages
        answer_file = mgr.get_file_by_path(Path(str(bundled_answer_path)).resolve())
        ctx = replace(
            ctx,
            marking_mode=queue_item.get("marking_mode") or meta.get("marking_mode") or "standard_mapped_answer",
            answer_file_id=answer_file.id if answer_file else ctx.answer_file_id,
            answer_file_path=str(bundled_answer_path),
            answer_page_start=int(bap["start_page"]),
            answer_page_end=int(bap["end_page"]),
            starts_mid_page=bool(bap.get("starts_mid_page")),
            ends_mid_page=bool(bap.get("ends_mid_page")),
            answer_mapping_source="bundled_exercise_answer_key",
            answer_mapping_notes=str(queue_item.get("notes") or ""),
            needs_visual_answer_pages=True,
        )
    else:
        ctx = resolve_v3_marking_context(manager=mgr, request=req, marking_mode=mode_kwarg)
    template = mgr.get_template(attempt.id)
    authority = resolve_question_sections_authority(template_file=template)

    prep = prepare_finalize_rows(
        question_sections_payload=dict(authority.payload),
        phase2_rows=phase2_rows,
        phase3_rows=[],
        english_required=english_finalize_required_for_item(queue_item, payload_queue),
    )
    write_debug_json(
        bundle_root,
        "phasee_finalize_prep.json",
        {
            "phase3_row_count": 0,
            "phase3_skipped": True,
            "would_escalate_question_ids": list(prep.phase3_question_ids),
            "language_violations": list(prep.language_violations),
            "human_note_violations": list(prep.human_note_violations),
            "merged_row_count": len(prep.merged_rows),
        },
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
