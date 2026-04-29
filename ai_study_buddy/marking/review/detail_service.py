from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.core.artifact_lookup import find_marking_artifacts_for_attempt
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile, PdfFileManager
from ai_study_buddy.marking.review.amendment_service import (
    build_amendment_context,
    normalize_amendment_state,
    resolve_marking_result,
)
from ai_study_buddy.marking.review.models import (
    STATIC_ROUTE_PREFIX,
    attempt_title,
    default_review_state,
    infer_subject_context,
)
from ai_study_buddy.marking.review.payload_reader import read_marking_result_payload
from ai_study_buddy.marking.review.repository import StudentReviewRepository


class AttemptNotFoundError(Exception):
    pass


def _extract_page_num(path: Path) -> int:
    match = re.search(r"(\d+)(?!.*\d)", path.stem)
    if not match:
        return 10_000_000
    return int(match.group(1))


def _list_images(context_root: Path, asset_dir: Path, subdir: str) -> list[dict[str, Any]]:
    target = asset_dir / subdir
    if not target.is_dir():
        return []
    candidates = [
        p
        for p in target.iterdir()
        if p.is_file() and p.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
    ]
    out: list[dict[str, Any]] = []
    for path in sorted(candidates, key=lambda p: (_extract_page_num(p), p.name)):
        rel = path.relative_to(context_root).as_posix()
        out.append(
            {
                "name": path.name,
                "page_num": _extract_page_num(path),
                "url": f"{STATIC_ROUTE_PREFIX}/{rel}",
            }
        )
    return out


def _find_attempt_page_for_result(question_page_map: list[dict[str, Any]], result_id: str) -> int | None:
    for entry in question_page_map:
        if entry.get("result_id") == result_id and isinstance(entry.get("attempt_page_start"), int):
            return entry["attempt_page_start"]
    return None


def _is_completion_candidate(file: PdfFile) -> bool:
    if file.is_template:
        return False
    if file.file_type == "raw":
        return False
    name_lower = file.name.lower()
    if name_lower.startswith("_raw_") or name_lower.startswith("raw_"):
        return False
    return True


def normalize_marking_result_for_frontend(
    *,
    payload: dict[str, Any],
    context_root: Path,
    marking_result_json: Path,
) -> dict[str, Any]:
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    question_results = payload.get("question_results") if isinstance(payload.get("question_results"), list) else []
    question_page_map = context.get("question_page_map") if isinstance(context.get("question_page_map"), list) else []

    normalized_questions: list[dict[str, Any]] = []
    for row in question_results:
        if not isinstance(row, dict):
            continue
        result_id = str(row.get("result_id") or "")
        normalized_questions.append(
            {
                "result_id": result_id,
                "outcome": row.get("outcome"),
                "earned_marks": row.get("earned_marks"),
                "max_marks": row.get("max_marks"),
                "student_answer": row.get("student_answer"),
                "correct_answer": row.get("correct_answer"),
                "skill_tags": row.get("skill_tags") or [],
                "diagnosis": row.get("diagnosis") or {},
                "tutor_note": row.get("human_note"),
                "human_note": row.get("human_note"),
                "attempt_page_start": _find_attempt_page_for_result(question_page_map, result_id),
            }
        )

    return {
        "artifact_path": marking_result_json.relative_to(context_root).as_posix(),
        "schema_version": payload.get("schema_version"),
        "created_at": payload.get("created_at"),
        "context": {
            "unit_label": context.get("unit_label"),
            "attempt_sequence": context.get("attempt_sequence"),
            "template_attempt_group_id": context.get("template_attempt_group_id"),
            "answer_page_start": context.get("answer_page_start"),
            "answer_page_end": context.get("answer_page_end"),
            "is_partial": context.get("is_partial"),
            "question_page_map": question_page_map,
            "question_selection": context.get("question_selection") or {},
        },
        "summary": {
            "earned_marks": summary.get("earned_marks"),
            "total_marks": summary.get("total_marks"),
            "percentage": summary.get("percentage"),
            "overall_assessment": summary.get("overall_assessment"),
            "human_note": summary.get("human_note"),
        },
        "question_results": normalized_questions,
    }


def get_attempt_detail(
    *,
    attempt_id: str,
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
) -> dict[str, Any]:
    completion = manager.get_file(attempt_id)
    if completion is None or not _is_completion_candidate(completion):
        raise AttemptNotFoundError(f"Attempt not found: {attempt_id}")

    refs = find_marking_artifacts_for_attempt(completion.id, manager=manager, context_root=context_root)
    latest_ref = refs[0] if refs else None

    subject_context = infer_subject_context(completion.subject)
    attempt = {
        "attempt_id": completion.id,
        "title": Path(completion.path).stem,
        "student_id": completion.student_id,
        "subject_context": subject_context,
        "collection_kind": "exam" if completion.doc_type == "exam" else "book",
        "book_label": None,
    }

    if latest_ref is None:
        return {
            "attempt": attempt,
            "marking_status": "not_marked",
            "marking_result": None,
            "review_state": default_review_state(),
            "viewer": {
                "mode_default": "attempt",
                "attempt_images": [],
                "answer_images": [],
                "answer_page_start": None,
                "answer_page_end": None,
                "marking_asset": None,
            },
        }

    payload = read_marking_result_payload(
        marking_result_json=latest_ref.marking_result_json,
        context_root=context_root,
    )
    if payload is None:
        raise AttemptNotFoundError(f"Invalid marking artifact for attempt {attempt_id}")

    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    attempt["title"] = attempt_title(context, attempt_path=completion.path)
    attempt["subject_context"] = context.get("subject_context") if isinstance(context.get("subject_context"), str) else subject_context
    attempt["book_label"] = context.get("book_label") if isinstance(context.get("book_label"), str) else None

    marking_asset = context.get("marking_asset") if isinstance(context.get("marking_asset"), str) else None
    asset_dir = context_root / marking_asset if marking_asset else None
    attempt_images = _list_images(context_root, asset_dir, "attempt") if asset_dir else []
    answer_images = _list_images(context_root, asset_dir, "answers") if asset_dir else []

    student_id = context.get("student_id") if isinstance(context.get("student_id"), str) else (completion.student_id or "unknown")
    resolved_subject = (
        context.get("subject_context")
        if isinstance(context.get("subject_context"), str)
        else infer_subject_context(completion.subject) or "unknown"
    )

    review_state = review_repo.load_review_state(
        student_id=student_id,
        subject_context=resolved_subject,
        artifact_stem=latest_ref.marking_result_json.stem,
    )
    marking_result_path = latest_ref.marking_result_json.relative_to(context_root).as_posix()
    amendment_context = build_amendment_context(
        base_payload=payload,
        attempt_id=attempt_id,
        marking_result_path=marking_result_path,
        fallback_student_id=completion.student_id,
    )
    amendment_state = normalize_amendment_state(
        review_repo.load_raw_amendment(
            student_id=amendment_context["student_id"],
            subject_context=amendment_context["subject_context"],
            artifact_stem=latest_ref.marking_result_json.stem,
        ),
        context=amendment_context,
    )
    valid_attempt_pages = {img["page_num"] for img in attempt_images if isinstance(img.get("page_num"), int)}
    resolved_payload = resolve_marking_result(
        base_payload=payload,
        amendment_state=amendment_state,
        valid_attempt_pages=valid_attempt_pages,
    )
    marking_result_base = normalize_marking_result_for_frontend(
        payload=payload,
        context_root=context_root,
        marking_result_json=latest_ref.marking_result_json,
    )
    marking_result_resolved = normalize_marking_result_for_frontend(
        payload=resolved_payload,
        context_root=context_root,
        marking_result_json=latest_ref.marking_result_json,
    )

    return {
        "attempt": attempt,
        "marking_status": "marked",
        "marking_result": marking_result_resolved,
        "marking_result_base": marking_result_base,
        "marking_result_resolved": marking_result_resolved,
        "amendment_state": amendment_state,
        "review_state": review_state,
        "viewer": {
            "mode_default": "attempt",
            "attempt_images": attempt_images,
            "answer_images": answer_images,
            "answer_page_start": context.get("answer_page_start"),
            "answer_page_end": context.get("answer_page_end"),
            "marking_asset": marking_asset,
        },
    }
