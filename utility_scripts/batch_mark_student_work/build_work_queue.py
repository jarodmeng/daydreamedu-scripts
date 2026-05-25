#!/usr/bin/env python3
"""Build or refresh a batch marking work_queue.json."""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
for p in (_REPO_ROOT, _SCRIPT_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from ai_study_buddy.marking.core.marking_time import now_marking_iso  # noqa: E402
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager  # noqa: E402
from policies import default_marking_mode_for_policy, resolve_policy  # noqa: E402
from queue_common import (  # noqa: E402
    COMPLETION_GLOBS,
    DEFAULT_SOURCE_FOLDER,
    DEFAULT_WORK_QUEUE_PATH,
    build_item_from_completion,
    detector_for_payload,
    infer_student_email,
    infer_subject_from_folder,
    save_work_queue,
    scan_completion_paths,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--folder",
        type=Path,
        default=DEFAULT_SOURCE_FOLDER,
        help="Folder containing completion PDFs (_c_*.pdf and/or c_*.pdf)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_WORK_QUEUE_PATH,
        help="Path to write work queue JSON",
    )
    parser.add_argument(
        "--policy",
        choices=("book", "exercise", "english_exercise", "science_exercise", "chinese_exercise"),
        default="book",
        help="Marking policy preset (book | exercise | english_exercise | science_exercise | chinese_exercise)",
    )
    parser.add_argument(
        "--marking-mode",
        choices=("standard", "teacher_annotated"),
        default=None,
        help="Override: standard requires book_answer_mapping; teacher_annotated for worksheets",
    )
    parser.add_argument(
        "--subject",
        choices=("math", "english", "chinese", "science"),
        default=None,
        help="Subject context (default: infer from folder path)",
    )
    args = parser.parse_args()

    marking_policy = resolve_policy(args.policy)
    policy_kind = marking_policy["policy_kind"]

    marking_mode = args.marking_mode
    if marking_mode is None:
        marking_mode = (
            "teacher_annotated"
            if default_marking_mode_for_policy(args.policy) == "teacher_annotated"
            else "standard"
        )
    allow_teacher_annotated = marking_mode == "teacher_annotated"
    queue_marking_mode = (
        "teacher_annotated" if allow_teacher_annotated else "standard_mapped_answer"
    )

    folder = args.folder.resolve()
    if not folder.is_dir():
        print(f"ERROR: folder does not exist: {folder}", file=sys.stderr)
        return 1

    completions = scan_completion_paths(folder)
    if not completions:
        print(
            f"ERROR: no completion PDFs matching {', '.join('_c_*.pdf / c_*.pdf')} in {folder}",
            file=sys.stderr,
        )
        return 1

    manager = PdfFileManager()
    items = [
        build_item_from_completion(
            manager=manager,
            ord_num=i,
            completion_path=path,
            allow_teacher_annotated=allow_teacher_annotated,
        )
        for i, path in enumerate(completions, start=1)
    ]

    subject = args.subject or infer_subject_from_folder(folder)
    student_email = infer_student_email(manager, folder, items)

    payload = {
        "generated_at": now_marking_iso(),
        "source_folder": str(folder),
        "student_email": student_email,
        "subject": subject,
        "policy": args.policy,
        "detector": marking_policy.get("detector"),
        "marking_mode": queue_marking_mode,
        "marking_policy": marking_policy,
        "completion_globs": list(COMPLETION_GLOBS),
        "items": items,
    }
    payload["detector"] = detector_for_payload(payload)

    save_work_queue(payload, args.output.resolve())

    counts = Counter(item["status"] for item in items)
    pending = [i for i in items if i["status"] == "pending"]
    needs_det = sum(1 for i in pending if i.get("needs_detection"))
    has_det = len(pending) - needs_det

    print(f"Wrote {args.output.resolve()}")
    print(f"  student:   {student_email}")
    print(f"  subject:   {subject}")
    print(f"  policy:    {args.policy}")
    print(f"  detector:  {payload['detector']}")
    print(f"  scanned:   {len(items)}")
    print(f"  skipped:   {counts.get('skipped', 0)} (already marked)")
    print(f"  pending:   {counts.get('pending', 0)} (need marking)")
    print(f"    need detector: {needs_det}")
    print(f"    have detector: {has_det}")
    print(f"  blocked:   {counts.get('blocked', 0)}")
    if counts.get("blocked"):
        for item in items:
            if item["status"] == "blocked":
                print(f"    ord={item['ord']}: {item['completion_normal_name']} — {item['error']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
