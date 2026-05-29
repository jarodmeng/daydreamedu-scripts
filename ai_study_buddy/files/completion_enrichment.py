"""Marking/review workflow flags for registered completion mains."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from ai_study_buddy.marking.review.repository import StudentReviewRepository

if TYPE_CHECKING:
    from ai_study_buddy.marking.core.artifact_lookup import MarkingArtifactIndex
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile, PdfFileManager


@dataclass(frozen=True)
class RegisteredCompletionEnrichment:
    has_marking: bool
    has_marking_amendment: bool
    review_status: str
    marking_earned_marks: float | int | None = None
    marking_total_marks: float | int | None = None
    marking_percentage: float | None = None


def _scalar_mark(value: Any) -> float | int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    return None


def _marking_score_from_summary(
    resolved_summary: dict[str, Any] | None,
) -> tuple[float | int | None, float | int | None, float | None]:
    if not isinstance(resolved_summary, dict):
        return None, None, None
    earned = _scalar_mark(resolved_summary.get("earned_marks"))
    total = _scalar_mark(resolved_summary.get("total_marks"))
    if earned is None or total is None:
        return None, None, None
    pct_raw = resolved_summary.get("percentage")
    if isinstance(pct_raw, (int, float)) and not isinstance(pct_raw, bool):
        return earned, total, float(pct_raw)
    from ai_study_buddy.marking.core.artifact_schema import compute_percentage

    return earned, total, compute_percentage(earned, total)


def enrich_registered_completion(
    completion: PdfFile,
    *,
    context_root: Path,
    pfm: PdfFileManager,
    review_repo: StudentReviewRepository,
    artifact_index: MarkingArtifactIndex | None = None,
) -> RegisteredCompletionEnrichment:
    # Lazy import avoids ``files`` ↔ ``marking`` cycle when ``marking`` loads via ``files.roots``.
    from ai_study_buddy.marking.review.workflow_flags import load_completion_marking_context

    ctx = load_completion_marking_context(
        completion,
        context_root=context_root,
        manager=pfm,
        review_repo=review_repo,
        artifact_index=artifact_index,
    )
    earned, total, pct = (
        _marking_score_from_summary(ctx.resolved_summary) if ctx.has_marking else (None, None, None)
    )
    return RegisteredCompletionEnrichment(
        has_marking=ctx.has_marking,
        has_marking_amendment=ctx.has_marking_amendment,
        review_status=ctx.review_status,
        marking_earned_marks=earned,
        marking_total_marks=total,
        marking_percentage=pct,
    )
