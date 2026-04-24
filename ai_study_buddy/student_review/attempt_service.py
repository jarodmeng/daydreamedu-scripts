from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.core.artifact_lookup import find_marking_artifacts_for_attempt
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile, PdfFileManager
from ai_study_buddy.student_review.models import (
    attempt_title,
    infer_grade_bucket,
    infer_subject_context,
    parse_iso_timestamp,
)
from ai_study_buddy.student_review.repository import StudentReviewRepository


def _is_completion_candidate(file: PdfFile) -> bool:
    if file.is_template:
        return False
    if file.file_type == "raw":
        return False
    name_lower = file.name.lower()
    if name_lower.startswith("_raw_") or name_lower.startswith("raw_"):
        return False
    return True


def _read_json_payload(path: Path) -> dict[str, Any] | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _collection_kind_from_doc_type(doc_type: str | None) -> str:
    return "exam" if doc_type == "exam" else "book"


def _attempt_summary(
    *,
    completion: PdfFile,
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
) -> dict[str, Any]:
    refs = find_marking_artifacts_for_attempt(completion.id, manager=manager, context_root=context_root)
    latest_ref = refs[0] if refs else None

    context: dict[str, Any] = {}
    summary: dict[str, Any] = {}
    created_at: str | None = None
    subject_context: str | None = infer_subject_context(completion.subject)
    book_label: str | None = None
    title = Path(completion.path).stem
    attempt_sequence: int | None = None
    is_partial: bool | None = None
    review_status = "not_started"

    if latest_ref is not None:
        payload = _read_json_payload(latest_ref.marking_result_json)
        if payload:
            context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
            summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
            created_at = payload.get("created_at") if isinstance(payload.get("created_at"), str) else None
            subject_context = (
                context.get("subject_context")
                if isinstance(context.get("subject_context"), str)
                else subject_context
            )
            book_label = context.get("book_label") if isinstance(context.get("book_label"), str) else None
            title = attempt_title(context, attempt_path=completion.path)
            attempt_sequence = context.get("attempt_sequence") if isinstance(context.get("attempt_sequence"), int) else None
            is_partial = context.get("is_partial") if isinstance(context.get("is_partial"), bool) else None

            student_id = context.get("student_id") if isinstance(context.get("student_id"), str) else completion.student_id
            resolved_subject = subject_context or "unknown"
            if student_id:
                state = review_repo.load_review_state(
                    student_id=student_id,
                    subject_context=resolved_subject,
                    artifact_stem=latest_ref.marking_result_json.stem,
                )
                review_status = state.get("review_status", "not_started")

    grade_bucket = infer_grade_bucket(completion.path) or "unknown"
    latest_marked_at = created_at

    return {
        "attempt_id": completion.id,
        "title": title,
        "student_id": completion.student_id,
        "subject_context": subject_context,
        "grade_bucket": grade_bucket,
        "collection_kind": _collection_kind_from_doc_type(completion.doc_type),
        "book_label": book_label,
        "marking_status": "marked" if latest_ref else "not_marked",
        "review_status": review_status,
        "latest_marked_at": latest_marked_at,
        "attempt_sequence": attempt_sequence,
        "is_partial": is_partial,
        "score": {
            "earned_marks": summary.get("earned_marks"),
            "total_marks": summary.get("total_marks"),
            "percentage": summary.get("percentage"),
        }
        if latest_ref
        else None,
        "_sort_timestamp": latest_marked_at or completion.updated_at or completion.added_at,
    }


def list_students(*, manager: PdfFileManager) -> list[dict[str, str]]:
    students = manager.list_students()
    out: list[dict[str, str]] = []
    for student in students:
        out.append(
            {
                "student_id": student.id,
                "display_name": student.name,
                "grade_level": "PSLE",
            }
        )
    return out


def list_attempts_for_student(
    *,
    student_id: str,
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
) -> list[dict[str, Any]]:
    files = manager.find_files(student_id=student_id, is_template=False)
    attempts = [f for f in files if _is_completion_candidate(f)]

    items = [
        _attempt_summary(
            completion=completion,
            context_root=context_root,
            manager=manager,
            review_repo=review_repo,
        )
        for completion in attempts
    ]

    items.sort(
        key=lambda row: (
            0 if row["marking_status"] == "marked" else 1,
            -parse_iso_timestamp(row.get("_sort_timestamp")).timestamp(),
            row["title"].lower(),
        )
    )

    for row in items:
        row.pop("_sort_timestamp", None)
    return items
