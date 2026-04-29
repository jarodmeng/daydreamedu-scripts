from __future__ import annotations

from pathlib import Path
from typing import Any

from ai_study_buddy.marking.core.artifact_lookup import find_marking_artifacts_for_attempt
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
from ai_study_buddy.marking.review.models import now_iso_utc, normalize_review_state
from ai_study_buddy.marking.review.repository import StudentReviewRepository

_ALLOWED_REVIEW_STATUS = {"not_started", "in_progress", "completed"}
_ALLOWED_AUTHOR_ROLES = {"student", "parent", "teacher"}
_ALLOWED_QUESTION_REVIEW_STATUS = {"not_reviewed", "in_progress", "reviewed"}


class ReviewStateWriteError(ValueError):
    pass


def _normalize_note_list(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    timestamp = now_iso_utc()
    for row in raw:
        if not isinstance(row, dict):
            continue
        note_text = row.get("note_text")
        if not isinstance(note_text, str):
            continue
        author_role = row.get("author_role")
        if not isinstance(author_role, str) or author_role not in _ALLOWED_AUTHOR_ROLES:
            author_role = "student"
        out.append(
            {
                "note_text": note_text,
                "author_role": author_role,
                "updated_at": timestamp,
            }
        )
    return out


def _normalize_question_reviews(raw: Any) -> list[dict[str, Any]]:
    if not isinstance(raw, list):
        return []

    out: list[dict[str, Any]] = []
    timestamp = now_iso_utc()
    for row in raw:
        if not isinstance(row, dict):
            continue
        result_id = row.get("result_id")
        if not isinstance(result_id, str) or not result_id.strip():
            continue

        review_status = row.get("review_status")
        if not isinstance(review_status, str) or review_status not in _ALLOWED_QUESTION_REVIEW_STATUS:
            review_status = "in_progress"

        note_text = row.get("note_text") if isinstance(row.get("note_text"), str) else ""
        author_role = row.get("author_role") if isinstance(row.get("author_role"), str) else "student"
        if author_role not in _ALLOWED_AUTHOR_ROLES:
            author_role = "student"

        out.append(
            {
                "result_id": result_id,
                "review_status": review_status,
                "note_text": note_text,
                "author_role": author_role,
                "updated_at": timestamp,
            }
        )
    return out


def put_review_state(
    *,
    attempt_id: str,
    body: dict[str, Any],
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
) -> dict[str, Any]:
    review_status = body.get("review_status")
    if review_status not in _ALLOWED_REVIEW_STATUS:
        raise ReviewStateWriteError("review_status must be not_started|in_progress|completed")

    refs = find_marking_artifacts_for_attempt(attempt_id, manager=manager, context_root=context_root)
    latest_ref = refs[0] if refs else None
    if latest_ref is None:
        raise ReviewStateWriteError("cannot persist review state: no marking artifact for attempt")

    completion = manager.get_file(attempt_id)
    if completion is None:
        raise ReviewStateWriteError("attempt not found")

    context = {}
    try:
        import json

        payload = json.loads(latest_ref.marking_result_json.read_text(encoding="utf-8"))
        if isinstance(payload, dict) and isinstance(payload.get("context"), dict):
            context = payload["context"]
    except Exception:
        context = {}

    student_id = context.get("student_id") if isinstance(context.get("student_id"), str) else (completion.student_id or "unknown")
    subject_context = (
        context.get("subject_context") if isinstance(context.get("subject_context"), str) else "unknown"
    )

    existing_raw = review_repo.load_raw_review_state(
        student_id=student_id,
        subject_context=subject_context,
        artifact_stem=latest_ref.marking_result_json.stem,
    )
    created_at = existing_raw.get("created_at") if isinstance(existing_raw, dict) else None
    if not isinstance(created_at, str) or not created_at.strip():
        created_at = now_iso_utc()
    updated_at = now_iso_utc()

    payload = {
        "schema_version": "student_review_state.v1",
        "created_at": created_at,
        "updated_at": updated_at,
        "context": {
            "student_id": student_id,
            "subject_context": subject_context,
            "attempt_file_id": context.get("attempt_file_id") or completion.id,
            "marking_result_path": latest_ref.marking_result_json.relative_to(context_root).as_posix(),
            "template_attempt_group_id": context.get("template_attempt_group_id"),
            "attempt_sequence": context.get("attempt_sequence"),
        },
        "summary": {"review_status": review_status},
        "review_status": review_status,
        "question_reviews": _normalize_question_reviews(body.get("question_reviews")),
        "attempt_notes": _normalize_note_list(body.get("attempt_notes")),
        "student_subject_notes": _normalize_note_list(body.get("student_subject_notes")),
        "review_meta": {
            "updated_by": body.get("updated_by") if isinstance(body.get("updated_by"), str) else "review_workspace",
        },
        "updated_by": body.get("updated_by") if isinstance(body.get("updated_by"), str) else "review_workspace",
    }

    path = review_repo.save_review_state(
        student_id=student_id,
        subject_context=subject_context,
        artifact_stem=latest_ref.marking_result_json.stem,
        payload=payload,
    )

    return {
        "ok": True,
        "saved_path": path.relative_to(context_root).as_posix(),
        "review_state": normalize_review_state(payload),
    }
