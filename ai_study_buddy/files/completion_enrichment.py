"""Marking/review workflow flags for registered completion mains."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.marking.review.workflow_flags import completion_workflow_flags
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile, PdfFileManager


@dataclass(frozen=True)
class RegisteredCompletionEnrichment:
    has_marking: bool
    has_marking_amendment: bool
    review_status: str


def enrich_registered_completion(
    completion: PdfFile,
    *,
    context_root: Path,
    pfm: PdfFileManager,
    review_repo: StudentReviewRepository,
) -> RegisteredCompletionEnrichment:
    flags = completion_workflow_flags(
        completion,
        context_root=context_root,
        manager=pfm,
        review_repo=review_repo,
    )
    return RegisteredCompletionEnrichment(
        has_marking=flags.has_marking,
        has_marking_amendment=flags.has_marking_amendment,
        review_status=flags.review_status,
    )
