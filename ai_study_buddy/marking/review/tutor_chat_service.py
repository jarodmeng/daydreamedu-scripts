from __future__ import annotations

import json
import os
import queue
import threading
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ai_study_buddy.marking.review.detail_service import AttemptNotFoundError, get_attempt_detail
from ai_study_buddy.marking.review.models import now_iso_utc
from ai_study_buddy.marking.review.repository import StudentReviewRepository
from ai_study_buddy.marking.review.tutor_chat_context_service import (
    TutorChatContextError,
    build_context_bundle,
    render_context_bundle_prompt,
)
from ai_study_buddy.marking.review.tutor_chat_repository import (
    TutorChatRepository,
    build_new_session,
    marking_artifact_stem_from_path,
)
from ai_study_buddy.marking.review.tutor_chat_stale import compute_stale_context
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

TUTOR_CHAT_MODEL = "auto"
TUTOR_CHAT_RUNTIME = "cursor-sdk-local"
TUTOR_CHAT_SSE_HEARTBEAT_SECONDS = float(os.environ.get("TUTOR_CHAT_SSE_HEARTBEAT_SECONDS", "15"))


class TutorChatServiceError(Exception):
    pass


class TutorChatNotFoundError(TutorChatServiceError):
    pass


class TutorChatBadRequestError(TutorChatServiceError):
    pass


class TutorChatUnavailableError(TutorChatServiceError):
    pass


class TutorChatInferenceError(TutorChatServiceError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class QuestionStorageKeys:
    student_id: str
    subject_context: str
    marking_artifact_stem: str
    result_id: str

    def as_dict(self) -> dict[str, str]:
        return {
            "student_id": self.student_id,
            "subject_context": self.subject_context,
            "marking_artifact_stem": self.marking_artifact_stem,
            "result_id": self.result_id,
        }


@dataclass(frozen=True)
class InferenceTurnResult:
    cursor_agent_id: str
    assistant_text: str
    run_id: str
    text_chunks: tuple[str, ...] = ()


class AgentRunner(Protocol):
    def run_turn(
        self,
        *,
        repo_root: Path,
        api_key: str,
        cursor_agent_id: str | None,
        prompt: str,
    ) -> InferenceTurnResult:
        ...


def tutor_chat_routes_enabled() -> bool:
    return os.environ.get("BUDDY_CONSOLE_DISABLE_TUTOR_CHAT", "").strip() != "1"


def tutor_chat_api_key() -> str | None:
    key = os.environ.get("CURSOR_API_KEY", "").strip()
    return key or None


def format_sse_event(event: str, data: dict[str, Any]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=True)}\n\n"


def storage_keys_from_bundle(bundle: dict[str, Any], result_id: str) -> QuestionStorageKeys:
    attempt_meta = bundle.get("attempt_meta")
    if not isinstance(attempt_meta, dict):
        raise TutorChatContextError("invalid attempt metadata")
    student_id = attempt_meta.get("student_id")
    subject_context = attempt_meta.get("subject_context")
    if not isinstance(student_id, str) or not student_id.strip():
        raise TutorChatContextError("student_id missing")
    if not isinstance(subject_context, str) or not subject_context.strip():
        raise TutorChatContextError("subject_context missing")

    snapshot = bundle.get("context_snapshot")
    if not isinstance(snapshot, dict):
        raise TutorChatContextError("context_snapshot missing")
    marking_result_path = snapshot.get("marking_result_path")
    if not isinstance(marking_result_path, str) or not marking_result_path.strip():
        raise TutorChatContextError("marking_result_path missing")

    return QuestionStorageKeys(
        student_id=student_id.strip(),
        subject_context=subject_context.strip(),
        marking_artifact_stem=marking_artifact_stem_from_path(marking_result_path),
        result_id=result_id,
    )


def stale_context_for_session(
    *,
    session: dict[str, Any],
    live_bundle: dict[str, Any],
) -> dict[str, bool]:
    live_snapshot = live_bundle.get("context_snapshot")
    if not isinstance(live_snapshot, dict):
        return {"marking": False, "review_notes": False}
    return compute_stale_context(
        snapshot=session.get("context_snapshot"),
        live_snapshot=live_snapshot,
    )


def build_inference_prompt(
    *,
    bundle: dict[str, Any],
    student_message: str,
    include_context_bundle: bool,
) -> str:
    if include_context_bundle:
        parts = [render_context_bundle_prompt(bundle)]
        parts.append(f"Student message:\n{student_message.strip()}")
        return "\n\n".join(parts)
    return student_message.strip()


def _load_bundle(
    *,
    attempt_id: str,
    result_id: str,
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
) -> dict[str, Any]:
    try:
        return build_context_bundle(
            attempt_id=attempt_id,
            result_id=result_id,
            context_root=context_root,
            manager=manager,
            review_repo=review_repo,
        )
    except AttemptNotFoundError as exc:
        raise TutorChatNotFoundError(str(exc)) from exc
    except TutorChatContextError as exc:
        raise TutorChatNotFoundError(str(exc)) from exc


def get_latest_tutor_chat(
    *,
    attempt_id: str,
    result_id: str,
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
    tutor_repo: TutorChatRepository,
) -> dict[str, Any]:
    bundle = _load_bundle(
        attempt_id=attempt_id,
        result_id=result_id,
        context_root=context_root,
        manager=manager,
        review_repo=review_repo,
    )
    keys = storage_keys_from_bundle(bundle, result_id)
    session = tutor_repo.load_latest_session(**keys.as_dict())
    if session is None:
        raise TutorChatNotFoundError("no tutor chat session")

    return {
        "session_id": session["session_id"],
        "messages": session.get("messages") or [],
        "stale_context": stale_context_for_session(session=session, live_bundle=bundle),
    }


def create_tutor_chat_session(
    *,
    attempt_id: str,
    result_id: str,
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
    tutor_repo: TutorChatRepository,
) -> dict[str, str]:
    bundle = _load_bundle(
        attempt_id=attempt_id,
        result_id=result_id,
        context_root=context_root,
        manager=manager,
        review_repo=review_repo,
    )
    keys = storage_keys_from_bundle(bundle, result_id)
    snapshot = bundle.get("context_snapshot")
    if not isinstance(snapshot, dict):
        raise TutorChatContextError("context_snapshot missing")

    session = build_new_session(
        attempt_id=attempt_id,
        result_id=result_id,
        student_id=keys.student_id,
        subject_context=keys.subject_context,
        marking_artifact_stem=keys.marking_artifact_stem,
        context_snapshot=snapshot,
    )
    tutor_repo.save_session(session)
    return {"session_id": session["session_id"]}


def _resolve_session_for_send(
    *,
    attempt_id: str,
    result_id: str,
    session_id: str | None,
    bundle: dict[str, Any],
    keys: QuestionStorageKeys,
    tutor_repo: TutorChatRepository,
) -> dict[str, Any]:
    if session_id:
        loaded = tutor_repo.load_session(session_id=session_id, **keys.as_dict())
        if loaded is None:
            raise TutorChatNotFoundError("session not found")
        return loaded

    latest = tutor_repo.load_latest_session(**keys.as_dict())
    if latest is not None:
        return latest

    snapshot = bundle.get("context_snapshot")
    if not isinstance(snapshot, dict):
        raise TutorChatContextError("context_snapshot missing")
    session = build_new_session(
        attempt_id=attempt_id,
        result_id=result_id,
        student_id=keys.student_id,
        subject_context=keys.subject_context,
        marking_artifact_stem=keys.marking_artifact_stem,
        context_snapshot=snapshot,
    )
    tutor_repo.save_session(session)
    return session


def _extract_assistant_text(run: Any, result: Any) -> str:
    text = ""
    if hasattr(run, "text"):
        try:
            text = run.text() or ""
        except Exception:
            text = ""
    if not text and isinstance(getattr(result, "result", None), str):
        text = result.result
    return text.strip()


class CursorSdkAgentRunner:
    def run_turn(
        self,
        *,
        repo_root: Path,
        api_key: str,
        cursor_agent_id: str | None,
        prompt: str,
    ) -> InferenceTurnResult:
        try:
            from cursor_sdk import Agent, CursorAgentError, LocalAgentOptions
            from cursor_sdk.types import AgentOptions
        except ImportError as exc:
            raise TutorChatUnavailableError("cursor-sdk is not installed") from exc

        local = LocalAgentOptions(cwd=repo_root)
        resume_options = AgentOptions(
            api_key=api_key,
            local=local,
            model=TUTOR_CHAT_MODEL,
        )
        try:
            if cursor_agent_id:
                agent = Agent.resume(cursor_agent_id, resume_options)
            else:
                agent = Agent.create(
                    model=TUTOR_CHAT_MODEL,
                    api_key=api_key,
                    local=local,
                )
        except CursorAgentError as err:
            raise TutorChatInferenceError("startup_failed", err.message) from err
        except Exception as err:
            raise TutorChatInferenceError("startup_failed", str(err)) from err

        chunks: list[str] = []
        with agent:
            try:
                run = agent.send(prompt, {"model": TUTOR_CHAT_MODEL})
                for chunk in run.iter_text():
                    chunks.append(chunk)
                result = run.wait()
                if result.status == "error":
                    raise TutorChatInferenceError("run_failed", f"run_id={run.id}")
            except CursorAgentError as err:
                raise TutorChatInferenceError("run_failed", err.message) from err

            assistant_text = "".join(chunks).strip()
            if not assistant_text:
                assistant_text = _extract_assistant_text(run, result)
            if not assistant_text:
                raise TutorChatInferenceError("run_failed", "inference returned empty text")

            return InferenceTurnResult(
                cursor_agent_id=agent.agent_id,
                assistant_text=assistant_text,
                run_id=run.id,
                text_chunks=tuple(chunks),
            )


_default_agent_runner: AgentRunner | None = None


def get_agent_runner() -> AgentRunner:
    global _default_agent_runner
    if _default_agent_runner is None:
        _default_agent_runner = CursorSdkAgentRunner()
    return _default_agent_runner


def set_agent_runner_for_tests(runner: AgentRunner | None) -> None:
    global _default_agent_runner
    _default_agent_runner = runner


def _run_turn_worker(
    *,
    runner: AgentRunner,
    result_queue: queue.Queue[tuple[str, Any]],
    repo_root: Path,
    api_key: str,
    cursor_agent_id: str | None,
    prompt: str,
) -> None:
    try:
        turn_result = runner.run_turn(
            repo_root=repo_root,
            api_key=api_key,
            cursor_agent_id=cursor_agent_id,
            prompt=prompt,
        )
        result_queue.put(("ok", turn_result))
    except TutorChatInferenceError as err:
        result_queue.put(("inference_error", err))
    except Exception as err:
        result_queue.put(("error", err))


def _iter_turn_result_with_status(
    *,
    runner: AgentRunner,
    repo_root: Path,
    api_key: str,
    cursor_agent_id: str | None,
    prompt: str,
) -> Iterator[str | InferenceTurnResult]:
    result_queue: queue.Queue[tuple[str, Any]] = queue.Queue(maxsize=1)
    thread = threading.Thread(
        target=_run_turn_worker,
        kwargs={
            "runner": runner,
            "result_queue": result_queue,
            "repo_root": repo_root,
            "api_key": api_key,
            "cursor_agent_id": cursor_agent_id,
            "prompt": prompt,
        },
        daemon=True,
    )
    yield format_sse_event("status", {"phase": "started"})
    yield format_sse_event("status", {"phase": "running"})
    thread.start()

    kind: str | None = None
    payload: Any = None
    while True:
        try:
            kind, payload = result_queue.get(timeout=TUTOR_CHAT_SSE_HEARTBEAT_SECONDS)
            break
        except queue.Empty:
            yield format_sse_event("status", {"phase": "running"})
            if not thread.is_alive():
                break

    thread.join()

    if kind is None:
        if not result_queue.empty():
            kind, payload = result_queue.get_nowait()
        else:
            yield format_sse_event(
                "error",
                {"code": "run_failed", "message": "Tutor inference ended without a result"},
            )
            return

    if kind == "inference_error":
        err = payload
        assert isinstance(err, TutorChatInferenceError)
        yield format_sse_event("error", {"code": err.code, "message": str(err)})
        return
    if kind == "error":
        yield format_sse_event("error", {"code": "run_failed", "message": str(payload)})
        return
    if kind != "ok":
        yield format_sse_event("error", {"code": "run_failed", "message": "Unexpected inference result"})
        return

    turn_result = payload
    assert isinstance(turn_result, InferenceTurnResult)
    yield turn_result


def preflight_tutor_chat_send(
    *,
    attempt_id: str,
    result_id: str,
    session_id: str | None,
    context_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
    tutor_repo: TutorChatRepository,
) -> None:
    bundle = _load_bundle(
        attempt_id=attempt_id,
        result_id=result_id,
        context_root=context_root,
        manager=manager,
        review_repo=review_repo,
    )
    if not session_id:
        return
    keys = storage_keys_from_bundle(bundle, result_id)
    if tutor_repo.load_session(session_id=session_id, **keys.as_dict()) is None:
        raise TutorChatNotFoundError("session not found")


def iter_tutor_chat_post_sse(
    *,
    attempt_id: str,
    result_id: str,
    message: str,
    session_id: str | None,
    refresh_context: bool,
    context_root: Path,
    repo_root: Path,
    manager: PdfFileManager,
    review_repo: StudentReviewRepository,
    tutor_repo: TutorChatRepository,
    api_key: str,
    agent_runner: AgentRunner | None = None,
) -> Iterator[str]:
    if not isinstance(message, str) or not message.strip():
        raise TutorChatBadRequestError("message is required")

    runner = agent_runner or get_agent_runner()
    bundle = _load_bundle(
        attempt_id=attempt_id,
        result_id=result_id,
        context_root=context_root,
        manager=manager,
        review_repo=review_repo,
    )
    keys = storage_keys_from_bundle(bundle, result_id)
    session = _resolve_session_for_send(
        attempt_id=attempt_id,
        result_id=result_id,
        session_id=session_id,
        bundle=bundle,
        keys=keys,
        tutor_repo=tutor_repo,
    )

    stale_before = stale_context_for_session(session=session, live_bundle=bundle)
    should_refresh_snapshot = refresh_context or any(stale_before.values())
    if should_refresh_snapshot:
        live_snapshot = bundle.get("context_snapshot")
        if isinstance(live_snapshot, dict):
            session = tutor_repo.update_context_snapshot(session, context_snapshot=live_snapshot)
            tutor_repo.save_session(session)

    session = tutor_repo.append_message(
        session,
        {"role": "student", "content": message.strip(), "at": now_iso_utc()},
    )

    include_context_bundle = session.get("cursor_agent_id") is None or should_refresh_snapshot
    prompt = build_inference_prompt(
        bundle=bundle,
        student_message=message.strip(),
        include_context_bundle=include_context_bundle,
    )

    turn_result: InferenceTurnResult | None = None
    for item in _iter_turn_result_with_status(
        runner=runner,
        repo_root=repo_root,
        api_key=api_key,
        cursor_agent_id=session.get("cursor_agent_id"),
        prompt=prompt,
    ):
        if isinstance(item, str):
            yield item
            continue
        turn_result = item

    if turn_result is None:
        return

    chunks_to_emit = turn_result.text_chunks
    if not chunks_to_emit and turn_result.assistant_text:
        chunks_to_emit = (turn_result.assistant_text,)
    for chunk in chunks_to_emit:
        yield format_sse_event("token", {"text": chunk})

    assistant_message = {
        "role": "assistant",
        "content": turn_result.assistant_text,
        "at": now_iso_utc(),
        "model": TUTOR_CHAT_MODEL,
        "runtime": TUTOR_CHAT_RUNTIME,
        "run_id": turn_result.run_id,
    }
    session["cursor_agent_id"] = turn_result.cursor_agent_id
    session = tutor_repo.append_message(session, assistant_message)

    stale_after = stale_context_for_session(session=session, live_bundle=bundle)
    yield format_sse_event(
        "done",
        {
            "session_id": session["session_id"],
            "stale_context": stale_after,
            "message": assistant_message,
        },
    )


def assert_tutor_chat_ready() -> None:
    if not tutor_chat_routes_enabled():
        raise TutorChatNotFoundError("tutor chat disabled")
    if not tutor_chat_api_key():
        raise TutorChatUnavailableError("CURSOR_API_KEY not configured")
