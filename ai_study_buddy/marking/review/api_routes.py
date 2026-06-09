from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
from ai_study_buddy.marking.core.artifact_lookup import find_marking_artifacts_for_attempt
from ai_study_buddy.marking.review.attempt_service import list_attempts_for_student, list_students
from ai_study_buddy.marking.review.amendment_service import (
    AmendmentValidationError,
    AmendmentWriteError,
    put_amendments,
)
from ai_study_buddy.marking.review.detail_service import (
    AttemptNotFoundError,
    ReviewEvidenceNotFoundError,
    get_attempt_detail,
    get_attempt_review_evidence,
    normalize_marking_result_for_frontend,
)
from ai_study_buddy.marking.review.note_service import ReviewStateWriteError, put_review_state
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.marking.review.tutor_chat_context_service import (
    TutorChatContextError,
    build_context_bundle,
    tutor_chat_debug_enabled,
)
from ai_study_buddy.marking.review.tutor_chat_repository import TutorChatRepository
from ai_study_buddy.marking.review.tutor_chat_service import (
    TutorChatNotFoundError,
    TutorChatUnavailableError,
    assert_tutor_chat_ready,
    create_tutor_chat_session,
    get_latest_tutor_chat,
    iter_tutor_chat_post_sse,
    preflight_tutor_chat_send,
    tutor_chat_api_key,
)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


REPO_ROOT = _repo_root()
CONTEXT_ROOT = REPO_ROOT / "ai_study_buddy" / "context"

router = APIRouter()


def _manager() -> PdfFileManager:
    return PdfFileManager()


def _repo() -> StudentReviewRepository:
    return StudentReviewRepository(context_root=CONTEXT_ROOT)


def _tutor_repo() -> TutorChatRepository:
    return TutorChatRepository(context_root=CONTEXT_ROOT)


def _tutor_chat_guard() -> None:
    try:
        assert_tutor_chat_ready()
    except TutorChatNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
    except TutorChatUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from None


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


@router.get("/api/student/attempts/{attempt_id}/review-evidence")
def attempt_review_evidence(attempt_id: str) -> dict[str, Any]:
    manager = _manager()
    try:
        return get_attempt_review_evidence(
            attempt_id=attempt_id,
            context_root=CONTEXT_ROOT,
            manager=manager,
        )
    except AttemptNotFoundError:
        raise HTTPException(status_code=404, detail="attempt not found") from None
    except ReviewEvidenceNotFoundError:
        raise HTTPException(status_code=404, detail="review evidence unavailable") from None


def _invalidate_buddy_console_inventory_cache(request: Request) -> None:
    try:
        from ai_study_buddy.buddy_console.backend.inventory_api import invalidate_enriched_cache

        invalidate_enriched_cache(request.app)
    except ImportError:
        pass


@router.put("/api/student/attempts/{attempt_id}/review-state")
def update_review_state(
    request: Request,
    attempt_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
    manager = _manager()
    repo = _repo()
    try:
        result = put_review_state(
            attempt_id=attempt_id,
            body=body,
            context_root=CONTEXT_ROOT,
            manager=manager,
            review_repo=repo,
        )
    except ReviewStateWriteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    _invalidate_buddy_console_inventory_cache(request)
    return result


@router.put("/api/student/attempts/{attempt_id}/amendments")
def update_amendments(
    request: Request,
    attempt_id: str,
    body: dict[str, Any],
) -> dict[str, Any]:
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
        refs = find_marking_artifacts_for_attempt(attempt_id, manager=manager, context_root=CONTEXT_ROOT)
        latest_ref = refs[0] if refs else None
        marking_result = detail.get("marking_result")
        if latest_ref is not None and isinstance(result.get("marking_result_resolved"), dict):
            marking_result = normalize_marking_result_for_frontend(
                payload=result["marking_result_resolved"],
                context_root=CONTEXT_ROOT,
                marking_result_json=latest_ref.marking_result_json,
            )
        return {
            **result,
            "marking_result": marking_result,
            "marking_result_base": detail.get("marking_result_base"),
            "marking_result_resolved": marking_result,
            "amendment_state": result.get("amendment_state") or detail.get("amendment_state"),
        }
    except AmendmentValidationError as exc:
        raise HTTPException(status_code=400, detail={"errors": exc.errors}) from None
    except AmendmentWriteError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None
    _invalidate_buddy_console_inventory_cache(request)


@router.get("/api/student/attempts/{attempt_id}/questions/{result_id}/tutor-chat")
def tutor_chat_get_latest(attempt_id: str, result_id: str) -> dict[str, Any]:
    _tutor_chat_guard()
    manager = _manager()
    repo = _repo()
    tutor_repo = _tutor_repo()
    try:
        return get_latest_tutor_chat(
            attempt_id=attempt_id,
            result_id=result_id,
            context_root=CONTEXT_ROOT,
            manager=manager,
            review_repo=repo,
            tutor_repo=tutor_repo,
        )
    except TutorChatNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.post("/api/student/attempts/{attempt_id}/questions/{result_id}/tutor-chat/sessions")
def tutor_chat_create_session(attempt_id: str, result_id: str) -> dict[str, str]:
    _tutor_chat_guard()
    manager = _manager()
    repo = _repo()
    tutor_repo = _tutor_repo()
    try:
        return create_tutor_chat_session(
            attempt_id=attempt_id,
            result_id=result_id,
            context_root=CONTEXT_ROOT,
            manager=manager,
            review_repo=repo,
            tutor_repo=tutor_repo,
        )
    except TutorChatNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None


@router.post("/api/student/attempts/{attempt_id}/questions/{result_id}/tutor-chat")
def tutor_chat_post_message(
    attempt_id: str,
    result_id: str,
    body: dict[str, Any],
) -> StreamingResponse:
    _tutor_chat_guard()
    message = body.get("message") if isinstance(body, dict) else None
    session_id = body.get("session_id") if isinstance(body, dict) else None
    refresh_context = bool(body.get("refresh_context")) if isinstance(body, dict) else False
    if session_id is not None and not isinstance(session_id, str):
        session_id = None

    if not isinstance(message, str) or not message.strip():
        raise HTTPException(status_code=400, detail="message is required") from None

    api_key = tutor_chat_api_key()
    if not api_key:
        raise HTTPException(status_code=503, detail="CURSOR_API_KEY not configured") from None

    manager = _manager()
    repo = _repo()
    tutor_repo = _tutor_repo()
    try:
        preflight_tutor_chat_send(
            attempt_id=attempt_id,
            result_id=result_id,
            session_id=session_id,
            context_root=CONTEXT_ROOT,
            manager=manager,
            review_repo=repo,
            tutor_repo=tutor_repo,
        )
    except TutorChatNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None

    return StreamingResponse(
        iter_tutor_chat_post_sse(
            attempt_id=attempt_id,
            result_id=result_id,
            message=message,
            session_id=session_id,
            refresh_context=refresh_context,
            context_root=CONTEXT_ROOT,
            repo_root=REPO_ROOT,
            manager=manager,
            review_repo=repo,
            tutor_repo=tutor_repo,
            api_key=api_key,
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/api/student/attempts/{attempt_id}/questions/{result_id}/tutor-chat/context-preview")
def tutor_chat_context_preview(attempt_id: str, result_id: str) -> dict[str, Any]:
    if not tutor_chat_debug_enabled():
        raise HTTPException(status_code=404, detail="not found") from None
    manager = _manager()
    repo = _repo()
    try:
        return build_context_bundle(
            attempt_id=attempt_id,
            result_id=result_id,
            context_root=CONTEXT_ROOT,
            manager=manager,
            review_repo=repo,
        )
    except AttemptNotFoundError:
        raise HTTPException(status_code=404, detail="attempt not found") from None
    except TutorChatContextError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from None
