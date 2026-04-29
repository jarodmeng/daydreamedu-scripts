from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
from ai_study_buddy.marking.review.attempt_service import list_attempts_for_student, list_students
from ai_study_buddy.marking.review.amendment_service import (
    AmendmentValidationError,
    AmendmentWriteError,
    put_amendments,
)
from ai_study_buddy.marking.review.detail_service import AttemptNotFoundError, get_attempt_detail
from ai_study_buddy.marking.review.note_service import ReviewStateWriteError, put_review_state
from ai_study_buddy.marking.review.repository import StudentReviewRepository


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


REPO_ROOT = _repo_root()
CONTEXT_ROOT = REPO_ROOT / "ai_study_buddy" / "context"

router = APIRouter()


def _manager() -> PdfFileManager:
    return PdfFileManager()


def _repo() -> StudentReviewRepository:
    return StudentReviewRepository(context_root=CONTEXT_ROOT)


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/students")
def students() -> dict[str, list[dict[str, str]]]:
    manager = _manager()
    return {"students": list_students(manager=manager)}


@router.get("/api/student/attempts")
def attempts(student_id: str = Query(...)) -> dict[str, list[dict[str, Any]]]:
    manager = _manager()
    repo = _repo()
    items = list_attempts_for_student(
        student_id=student_id,
        context_root=CONTEXT_ROOT,
        manager=manager,
        review_repo=repo,
    )
    return {"items": items}


@router.get("/api/student/attempts/{attempt_id}")
def attempt_detail(attempt_id: str) -> dict[str, Any]:
    manager = _manager()
    repo = _repo()
    try:
        return get_attempt_detail(
            attempt_id=attempt_id,
            context_root=CONTEXT_ROOT,
            manager=manager,
            review_repo=repo,
        )
    except AttemptNotFoundError:
        raise HTTPException(status_code=404, detail="attempt not found") from None


@router.put("/api/student/attempts/{attempt_id}/review-state")
def update_review_state(attempt_id: str, body: dict[str, Any]) -> dict[str, Any]:
    manager = _manager()
    repo = _repo()
    try:
        return put_review_state(
            attempt_id=attempt_id,
            body=body,
            context_root=CONTEXT_ROOT,
            manager=manager,
            review_repo=repo,
        )
    except ReviewStateWriteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.put("/api/student/attempts/{attempt_id}/amendments")
def update_amendments(attempt_id: str, body: dict[str, Any]) -> dict[str, Any]:
    manager = _manager()
    repo = _repo()
    try:
        result = put_amendments(
            attempt_id=attempt_id,
            body=body,
            context_root=CONTEXT_ROOT,
            manager=manager,
            review_repo=repo,
        )
        detail = get_attempt_detail(
            attempt_id=attempt_id,
            context_root=CONTEXT_ROOT,
            manager=manager,
            review_repo=repo,
        )
        return {
            **result,
            "marking_result": detail.get("marking_result"),
            "marking_result_base": detail.get("marking_result_base"),
            "marking_result_resolved": detail.get("marking_result_resolved"),
            "amendment_state": detail.get("amendment_state"),
        }
    except AmendmentValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from None
    except AmendmentWriteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
