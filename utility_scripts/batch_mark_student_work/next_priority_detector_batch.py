#!/usr/bin/env python3
"""Print the next N detector tasks from a priority template queue."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from fqi_detector_marking_reference import (
    marking_reference_prompt_section,
    write_prior_marking_reference_sidecar,
)

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_DEFAULT_CONTEXT_ROOT = _REPO_ROOT / "ai_study_buddy" / "context"


def _load_queue(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Queue not found: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Queue payload must be a JSON object")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ValueError("Queue payload missing items list")
    return payload


def _pending_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in payload.get("items", []):
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "").strip().lower()
        if status in {"pending_detection", "pending", ""}:
            out.append(item)
    out.sort(key=lambda item: int(item.get("ord") or 0))
    return out


def _resolve_fqi_run_folder(template_file_id: str, *, context_root: Path) -> Path | None:
    from ai_study_buddy.marking.file_question_info import file_question_info_run_dir_for_pdf
    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

    manager = PdfFileManager()
    pdf_file = manager.get_file(template_file_id)
    if pdf_file is None:
        return None
    return file_question_info_run_dir_for_pdf(pdf_file, context_root=context_root)


def _task_prompt(item: dict[str, Any], *, prior_marking_sidecar_rel: str | None = None) -> str:
    template_path = str(item.get("template_path") or "")
    template_id = str(item.get("template_file_id") or "")
    detector = str(item.get("detector") or "")
    linked_count = int(item.get("linked_completion_count") or 0)
    linked_students = ", ".join(item.get("linked_student_names") or [])

    marking_ref = item.get("marking_reference")
    marking_section = ""
    if isinstance(marking_ref, dict):
        marking_section = marking_reference_prompt_section(marking_ref)

    sidecar_line = ""
    if prior_marking_sidecar_rel:
        sidecar_line = (
            f"- prior_marking_reference_sidecar: {prior_marking_sidecar_rel} "
            "(read if present; non-binding)\n"
        )

    return (
        "Detect question sections for this template and persist canonical question_sections snapshot.\n\n"
        f"- detector_subagent_type: {detector}\n"
        f"- template_file_id: {template_id}\n"
        f"- template_path: {template_path}\n"
        f"- linked_completion_count_in_priority_gap: {linked_count}\n"
        f"- linked_students: {linked_students or 'unknown'}\n"
        f"{sidecar_line}\n"
        f"{marking_section}"
        "Requirements:\n"
        "1) Use the detector for this subject and produce a schema-valid payload.\n"
        "2) Persist under ai_study_buddy/context/file_question_info/.../question_sections.json.\n"
        "3) If prior marking reference was supplied, summarize how it influenced detection in "
        "input_context.hints (non-binding) and note material discrepancies in debug.notes.\n"
        "4) Ensure the payload is finalized and ready for downstream marking use.\n"
        "5) Return concise result: detector used, output path, schema_version, and confidence."
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=5, help="How many detector tasks to emit")
    parser.add_argument("--offset", type=int, default=0, help="Skip first N pending items")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Emit machine-readable task specs instead of human text",
    )
    parser.add_argument(
        "--output-task-spec-json",
        type=Path,
        default=None,
        help="Optional path to save emitted task specs JSON",
    )
    parser.add_argument(
        "--context-root",
        type=Path,
        default=_DEFAULT_CONTEXT_ROOT,
        help="Context root for FQI run_folder sidecars",
    )
    parser.add_argument(
        "--write-marking-reference-sidecars",
        action="store_true",
        help=(
            "Write prior_marking_reference.json under each template file_question_info run_folder "
            "(requires marking_reference on queue items)"
        ),
    )
    args = parser.parse_args()

    context_root = args.context_root.expanduser().resolve()
    payload = _load_queue(args.queue.expanduser().resolve())
    pending = _pending_items(payload)
    start = max(args.offset, 0)
    size = max(args.batch_size, 1)
    selected = pending[start : start + size]

    task_specs: list[dict[str, Any]] = []
    for item in selected:
        detector = str(item.get("detector") or "").strip()
        ord_num = int(item.get("ord") or 0)
        template_id = str(item.get("template_file_id") or "")
        template_path = str(item.get("template_path") or "")

        sidecar_rel: str | None = None
        marking_ref = item.get("marking_reference")
        if args.write_marking_reference_sidecars and isinstance(marking_ref, dict):
            run_folder = _resolve_fqi_run_folder(template_id, context_root=context_root)
            if run_folder is not None:
                sidecar_path = write_prior_marking_reference_sidecar(marking_ref, run_folder=run_folder)
                try:
                    sidecar_rel = str(sidecar_path.resolve().relative_to(context_root))
                except ValueError:
                    sidecar_rel = str(sidecar_path)

        task_specs.append(
            {
                "ord": ord_num,
                "subagent_type": detector,
                "model": "inherit",
                "description": f"detector ord {ord_num}",
                "template_file_id": template_id,
                "template_path": template_path,
                "prior_marking_reference_sidecar": sidecar_rel,
                "prompt": _task_prompt(item, prior_marking_sidecar_rel=sidecar_rel),
            }
        )

    if args.output_task_spec_json is not None:
        out_path = args.output_task_spec_json.expanduser().resolve()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(task_specs, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.json:
        print(
            json.dumps(
                {
                    "queue": str(args.queue.expanduser().resolve()),
                    "pending_total": len(pending),
                    "offset": start,
                    "batch_size": size,
                    "selected_count": len(task_specs),
                    "tasks": task_specs,
                },
                indent=2,
                ensure_ascii=False,
            )
        )
        return 0

    print(f"Queue: {args.queue.expanduser().resolve()}")
    print(f"Pending detector items: {len(pending)}")
    print(f"Batch slice: offset={start}, size={size}, selected={len(task_specs)}")
    if not task_specs:
        return 0
    print("")
    for spec in task_specs:
        print(f"- ord={spec['ord']} detector={spec['subagent_type']}")
        print(f"  template_file_id={spec['template_file_id']}")
        print(f"  template_path={spec['template_path']}")
        if spec.get("prior_marking_reference_sidecar"):
            print(f"  prior_marking_reference_sidecar={spec['prior_marking_reference_sidecar']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
