from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_study_buddy.pdf_file_manager.pdf_file_manager import (
    PdfFile,
    PdfFileManager,
    has_raw_pdf_prefix,
)
from ai_study_buddy.marking.review.models import (
    attempt_title,
    infer_grade_bucket,
    infer_subject_context,
    parse_iso_timestamp,
)
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.marking.review.workflow_flags import load_completion_marking_context


def _is_completion_candidate(file: PdfFile) -> bool:
    if file.is_template:
        return False
    if file.file_type == "raw":
        return False
    if has_raw_pdf_prefix(file.name.lower()):
        return False
    return True


def _collection_kind_from_doc_type(doc_type: str | None) -> str:
    return "exam" if doc_type == "exam" else "book"


def _attempt_summary(
    *,
    completion: PdfFile,
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
) -> dict[str, Any]:
    marking_ctx = load_completion_marking_context(
        completion,
        context_root=context_root,
        manager=manager,
        review_repo=review_repo,
    )

    context: dict[str, Any] = {}
    summary: dict[str, Any] = {}
    created_at: str | None = None
    subject_context: str | None = infer_subject_context(completion.subject)
    book_label: str | None = None
    title = completion.normal_name
    attempt_sequence: int | None = None
    is_partial: bool | None = None

    if marking_ctx.latest_ref is not None and marking_ctx.payload:
        payload = marking_ctx.payload
        context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        summary = marking_ctx.resolved_summary or (
            payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
        )
        created_at = payload.get("created_at") if isinstance(payload.get("created_at"), str) else None
        subject_context = (
            context.get("subject_context")
            if isinstance(context.get("subject_context"), str)
            else subject_context
        )
        book_label = context.get("book_label") if isinstance(context.get("book_label"), str) else None
        title = attempt_title(context, attempt_path=completion.path)
        attempt_sequence = (
            context.get("attempt_sequence") if isinstance(context.get("attempt_sequence"), int) else None
        )
        is_partial = context.get("is_partial") if isinstance(context.get("is_partial"), bool) else None

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
        "marking_status": "marked" if marking_ctx.has_marking else "not_marked",
        "review_status": marking_ctx.review_status,
        "latest_marked_at": latest_marked_at,
        "attempt_sequence": attempt_sequence,
        "is_partial": is_partial,
        "score": {
            "earned_marks": summary.get("earned_marks"),
            "total_marks": summary.get("total_marks"),
            "percentage": summary.get("percentage"),
        }
        if marking_ctx.has_marking
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
