"""Completion workflow flags — shared by Review Workspace and ``files.completion_enrichment``."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.core.artifact_lookup import (
    MarkingArtifactIndex,
    MarkingArtifactRef,
    find_marking_artifacts_for_attempt,
)
from ai_study_buddy.marking.review.amendment_service import (
    build_amendment_context,
    normalize_amendment_state,
    resolve_marking_result,
)
from ai_study_buddy.marking.review.models import infer_subject_context
from ai_study_buddy.marking.review.payload_reader import read_marking_result_payload
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile, PdfFileManager


@dataclass(frozen=True)
class _CompletionWorkflowFlags:
    has_marking: bool
    has_marking_amendment: bool
    review_status: str


@dataclass(frozen=True)
class CompletionMarkingContext:
    """One load of marking + review + amendment state for a registered completion main."""

    has_marking: bool
    has_marking_amendment: bool
    review_status: str
    latest_ref: MarkingArtifactRef | None
    payload: dict[str, Any] | None
    resolved_summary: dict[str, Any] | None


def load_completion_marking_context(
    completion: PdfFile,
    *,
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
    artifact_index: MarkingArtifactIndex | None = None,
) -> CompletionMarkingContext:
    """Load marking artifact, review status, amendment presence, and resolved summary (if marked)."""
    refs = find_marking_artifacts_for_attempt(
        completion.id,
        manager=manager,
        context_root=context_root,
        artifact_index=artifact_index,
    )
    if not refs:
        return CompletionMarkingContext(
            has_marking=False,
            has_marking_amendment=False,
            review_status="not_started",
            latest_ref=None,
            payload=None,
            resolved_summary=None,
        )

    latest_ref = refs[0]
    payload = read_marking_result_payload(
        marking_result_json=latest_ref.marking_result_json,
        context_root=context_root,
    )
    subject_context = infer_subject_context(completion.subject)
    review_status = "not_started"
    has_amendment = False
    resolved_summary: dict[str, Any] | None = None

    if payload:
        ctx = payload.get("context") if isinstance(payload.get("context"), dict) else {}
        if isinstance(ctx.get("subject_context"), str):
            subject_context = ctx["subject_context"]
        student_id = (
            ctx.get("student_id") if isinstance(ctx.get("student_id"), str) else completion.student_id
        )
        if student_id and subject_context:
            artifact_stem = latest_ref.marking_result_json.stem
            state = review_repo.load_review_state(
                student_id=student_id,
                subject_context=subject_context,
                artifact_stem=artifact_stem,
            )
            review_status = state.get("review_status", "not_started")
            marking_result_path = latest_ref.marking_result_json.relative_to(context_root).as_posix()
            amendment_context = build_amendment_context(
                base_payload=payload,
                attempt_id=completion.id,
                marking_result_path=marking_result_path,
                fallback_student_id=completion.student_id,
            )
            raw_amendment = review_repo.load_raw_amendment(
                student_id=amendment_context["student_id"],
                subject_context=amendment_context["subject_context"],
                artifact_stem=artifact_stem,
            )
            has_amendment = bool(raw_amendment)
            amendment_state = normalize_amendment_state(
                raw_amendment,
                context=amendment_context,
            )
            resolved_payload = resolve_marking_result(
                base_payload=payload,
                amendment_state=amendment_state,
                valid_attempt_pages=None,
            )
            resolved_summary = (
                resolved_payload.get("summary")
                if isinstance(resolved_payload.get("summary"), dict)
                else None
            )

    return CompletionMarkingContext(
        has_marking=True,
        has_marking_amendment=has_amendment,
        review_status=review_status,
        latest_ref=latest_ref,
        payload=payload,
        resolved_summary=resolved_summary,
    )


def completion_workflow_flags(
    completion: PdfFile,
    *,
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
    artifact_index: MarkingArtifactIndex | None = None,
) -> _CompletionWorkflowFlags:
    """Marking / amendment / review_status for one registered completion main."""
    ctx = load_completion_marking_context(
        completion,
        context_root=context_root,
        manager=manager,
        review_repo=review_repo,
        artifact_index=artifact_index,
    )
    return _CompletionWorkflowFlags(
        has_marking=ctx.has_marking,
        has_marking_amendment=ctx.has_marking_amendment,
        review_status=ctx.review_status,
    )
