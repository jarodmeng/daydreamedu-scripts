#!/usr/bin/env python3
"""Phase A/B prep for one work-queue item: bundle, renders, section summary JSON."""

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

from ai_study_buddy.marking import render_attempt_pdf_to_bundle, render_answers_pdf_pages_to_bundle
from ai_study_buddy.marking.core.marking_time import now_marking_iso
from ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3 import (
    V3InputRequest,
    build_context_resolution_debug_record,
    build_phase2_section_inputs,
    resolve_attempt_input_to_pdf_file,
    resolve_or_create_bundle_for_v3_run,
    resolve_question_sections_authority,
    resolve_v3_marking_context,
    write_context_resolution_debug_artifact,
    write_run_state,
)
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
from queue_common import DEFAULT_WORK_QUEUE_PATH, load_work_queue


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ord", type=int, required=True)
    parser.add_argument("--queue", type=Path, default=DEFAULT_WORK_QUEUE_PATH)
    parser.add_argument("--context-root", type=Path, default=Path("ai_study_buddy/context"))
    args = parser.parse_args()

    payload = load_work_queue(args.queue)
    item = next((i for i in payload["items"] if i.get("ord") == args.ord), None)
    if item is None:
        print(f"ERROR: ord={args.ord} not found", file=sys.stderr)
        return 1
    if item.get("status") != "pending":
        print(f"ERROR: ord={args.ord} status={item.get('status')!r}, expected pending", file=sys.stderr)
        return 1

    run_at = now_marking_iso()
    context_root = args.context_root.resolve()
    completion = Path(item["completion_path"])
    mgr = PdfFileManager()
    req = V3InputRequest(attempt_file_id_or_path=str(completion))
    attempt = resolve_attempt_input_to_pdf_file(manager=mgr, request=req)
    queue_mode = payload.get("marking_mode")
    mode_kwarg = "teacher_annotated" if queue_mode == "teacher_annotated" else None
    ctx = resolve_v3_marking_context(manager=mgr, request=req, marking_mode=mode_kwarg)
    bundle = resolve_or_create_bundle_for_v3_run(
        context_root=context_root,
        attempt_file_path=attempt.path,
        student_id=ctx.student_id,
        student_name=None,
        subject_context=ctx.subject_context,
        run_marked_at=run_at,
    )
    write_context_resolution_debug_artifact(
        bundle_root=bundle.bundle_root,
        record=build_context_resolution_debug_record(request=req, context=ctx),
    )
    write_run_state(bundle_root=bundle.bundle_root, state="phase_ab_done")

    template = mgr.get_template(attempt.id)
    if template is None:
        print("ERROR: no template", file=sys.stderr)
        return 1
    authority = resolve_question_sections_authority(template_file=template)
    sections = build_phase2_section_inputs(authority)

    render_attempt_pdf_to_bundle(attempt.path, bundle.bundle_root)
    bap = item.get("book_answer_pages") or {}
    if ctx.marking_mode == "teacher_annotated" or not bap:
        pages: list[int] = []
    else:
        pages = list(range(int(bap["start_page"]), int(bap["end_page"]) + 1))
        render_answers_pdf_pages_to_bundle(
            ctx.answer_file_path, bundle.bundle_root, pages_1_based=pages
        )

    out = {
        "ord": args.ord,
        "run_at": run_at,
        "bundle_root": str(bundle.bundle_root.resolve()),
        "artifact_json_path": str(bundle.artifact_json_path.resolve()),
        "completion_path": item["completion_path"],
        "template_path": item["template_path"],
        "template_file_id": item["template_file_id"],
        "answer_file_path": ctx.answer_file_path,
        "marking_mode": ctx.marking_mode,
        "book_answer_pages": bap,
        "sections": [
            {
                "section_index": s.section_index,
                "section_label": s.section_label,
                "question_ids": list(s.question_ids),
                "page_numbers": list(s.page_numbers),
            }
            for s in sections
        ],
        "needs_detection": item.get("needs_detection", False),
        "detector": payload.get("detector"),
        "subject": payload.get("subject"),
        "policy": payload.get("policy"),
    }
    meta_path = bundle.bundle_root / "debug" / "batch_item_meta.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps(out, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(json.dumps(out, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
