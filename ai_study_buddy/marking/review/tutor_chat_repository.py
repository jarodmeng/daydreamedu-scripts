from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.review.models import now_iso_utc, parse_iso_timestamp

SCHEMA_VERSION = "tutor_chat.v1"
_ALLOWED_ROLES = frozenset({"student", "assistant"})


class TutorChatRepositoryError(ValueError):
    pass


def new_session_id() -> str:
    return str(uuid.uuid4())


def _normalize_message(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    role = raw.get("role")
    if role not in _ALLOWED_ROLES:
        return None
    content = raw.get("content")
    if not isinstance(content, str):
        return None
    at = raw.get("at")
    if not isinstance(at, str) or not at.strip():
        at = now_iso_utc()
    message: dict[str, Any] = {
        "role": role,
        "content": content,
        "at": at,
    }
    for optional in ("model", "runtime", "run_id"):
        value = raw.get(optional)
        if isinstance(value, str) and value.strip():
            message[optional] = value.strip()
    return message


def normalize_tutor_chat_session(raw: dict[str, Any] | None) -> dict[str, Any]:
    if not isinstance(raw, dict):
        raise TutorChatRepositoryError("session payload must be an object")

    required_strings = (
        "attempt_id",
        "result_id",
        "student_id",
        "subject_context",
        "marking_artifact_stem",
        "session_id",
    )
    for key in required_strings:
        value = raw.get(key)
        if not isinstance(value, str) or not value.strip():
            raise TutorChatRepositoryError(f"{key} is required")

    created_at = raw.get("created_at")
    if not isinstance(created_at, str) or not created_at.strip():
        created_at = now_iso_utc()
    updated_at = raw.get("updated_at")
    if not isinstance(updated_at, str) or not updated_at.strip():
        updated_at = created_at

    snapshot = raw.get("context_snapshot")
    if not isinstance(snapshot, dict):
        raise TutorChatRepositoryError("context_snapshot is required")
    marking_result_path = snapshot.get("marking_result_path")
    fingerprint = snapshot.get("resolved_question_fingerprint")
    if not isinstance(marking_result_path, str) or not marking_result_path.strip():
        raise TutorChatRepositoryError("context_snapshot.marking_result_path is required")
    if not isinstance(fingerprint, str) or not fingerprint.strip():
        raise TutorChatRepositoryError("context_snapshot.resolved_question_fingerprint is required")

    messages_raw = raw.get("messages")
    messages: list[dict[str, Any]] = []
    if isinstance(messages_raw, list):
        for row in messages_raw:
            normalized = _normalize_message(row)
            if normalized is not None:
                messages.append(normalized)

    cursor_agent_id = raw.get("cursor_agent_id")
    if cursor_agent_id is not None and not isinstance(cursor_agent_id, str):
        cursor_agent_id = None
    if isinstance(cursor_agent_id, str) and not cursor_agent_id.strip():
        cursor_agent_id = None

    return {
        "schema_version": SCHEMA_VERSION,
        "attempt_id": raw["attempt_id"].strip(),
        "result_id": raw["result_id"].strip(),
        "student_id": raw["student_id"].strip(),
        "subject_context": raw["subject_context"].strip(),
        "marking_artifact_stem": raw["marking_artifact_stem"].strip(),
        "session_id": raw["session_id"].strip(),
        "cursor_agent_id": cursor_agent_id,
        "created_at": created_at.strip(),
        "updated_at": updated_at.strip(),
        "messages": messages,
        "context_snapshot": {
            "marking_result_path": marking_result_path.strip(),
            "amendment_updated_at": snapshot.get("amendment_updated_at")
            if isinstance(snapshot.get("amendment_updated_at"), str)
            else None,
            "review_state_updated_at": snapshot.get("review_state_updated_at")
            if isinstance(snapshot.get("review_state_updated_at"), str)
            else None,
            "resolved_question_fingerprint": fingerprint.strip(),
        },
    }


def build_new_session(
    *,
    attempt_id: str,
    result_id: str,
    student_id: str,
    subject_context: str,
    marking_artifact_stem: str,
    context_snapshot: dict[str, Any],
    session_id: str | None = None,
    cursor_agent_id: str | None = None,
) -> dict[str, Any]:
    timestamp = now_iso_utc()
    payload = {
        "schema_version": SCHEMA_VERSION,
        "attempt_id": attempt_id,
        "result_id": result_id,
        "student_id": student_id,
        "subject_context": subject_context,
        "marking_artifact_stem": marking_artifact_stem,
        "session_id": session_id or new_session_id(),
        "cursor_agent_id": cursor_agent_id,
        "created_at": timestamp,
        "updated_at": timestamp,
        "messages": [],
        "context_snapshot": context_snapshot,
    }
    return normalize_tutor_chat_session(payload)


def marking_artifact_stem_from_path(marking_result_path: str) -> str:
    if not marking_result_path.strip():
        raise TutorChatRepositoryError("marking_result_path is required")
    return Path(marking_result_path).stem


class TutorChatRepository:
    def __init__(self, *, context_root: Path):
        self._context_root = context_root
        self._root = context_root / "tutor_chats"

    def session_path(
        self,
        *,
        student_id: str,
        subject_context: str,
        marking_artifact_stem: str,
        result_id: str,
        session_id: str,
    ) -> Path:
        return (
            self._root
            / student_id
            / subject_context
            / marking_artifact_stem
            / result_id
            / f"{session_id}.json"
        )

    def question_dir(
        self,
        *,
        student_id: str,
        subject_context: str,
        marking_artifact_stem: str,
        result_id: str,
    ) -> Path:
        return self._root / student_id / subject_context / marking_artifact_stem / result_id

    def save_session(self, payload: dict[str, Any]) -> Path:
        normalized = normalize_tutor_chat_session(payload)
        normalized["updated_at"] = now_iso_utc()
        path = self.session_path(
            student_id=normalized["student_id"],
            subject_context=normalized["subject_context"],
            marking_artifact_stem=normalized["marking_artifact_stem"],
            result_id=normalized["result_id"],
            session_id=normalized["session_id"],
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        canonical = json.dumps(normalized, indent=2, ensure_ascii=True) + "\n"
        path.write_text(canonical, encoding="utf-8")
        return path

    def load_session(
        self,
        *,
        student_id: str,
        subject_context: str,
        marking_artifact_stem: str,
        result_id: str,
        session_id: str,
    ) -> dict[str, Any] | None:
        path = self.session_path(
            student_id=student_id,
            subject_context=subject_context,
            marking_artifact_stem=marking_artifact_stem,
            result_id=result_id,
            session_id=session_id,
        )
        if not path.is_file():
            return None
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        if not isinstance(raw, dict):
            return None
        try:
            return normalize_tutor_chat_session(raw)
        except TutorChatRepositoryError:
            return None

    def list_sessions_for_question(
        self,
        *,
        student_id: str,
        subject_context: str,
        marking_artifact_stem: str,
        result_id: str,
    ) -> list[dict[str, Any]]:
        directory = self.question_dir(
            student_id=student_id,
            subject_context=subject_context,
            marking_artifact_stem=marking_artifact_stem,
            result_id=result_id,
        )
        if not directory.is_dir():
            return []

        sessions: list[dict[str, Any]] = []
        for path in sorted(directory.glob("*.json")):
            session_id = path.stem
            loaded = self.load_session(
                student_id=student_id,
                subject_context=subject_context,
                marking_artifact_stem=marking_artifact_stem,
                result_id=result_id,
                session_id=session_id,
            )
            if loaded is not None:
                sessions.append(loaded)

        sessions.sort(
            key=lambda row: parse_iso_timestamp(row.get("updated_at")),
            reverse=True,
        )
        return sessions

    def load_latest_session(
        self,
        *,
        student_id: str,
        subject_context: str,
        marking_artifact_stem: str,
        result_id: str,
    ) -> dict[str, Any] | None:
        sessions = self.list_sessions_for_question(
            student_id=student_id,
            subject_context=subject_context,
            marking_artifact_stem=marking_artifact_stem,
            result_id=result_id,
        )
        return sessions[0] if sessions else None

    def append_message(
        self,
        payload: dict[str, Any],
        message: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = normalize_tutor_chat_session(payload)
        row = _normalize_message(message)
        if row is None:
            raise TutorChatRepositoryError("invalid message")
        normalized["messages"] = [*normalized["messages"], row]
        self.save_session(normalized)
        return normalized

    def update_context_snapshot(
        self,
        payload: dict[str, Any],
        *,
        context_snapshot: dict[str, Any],
    ) -> dict[str, Any]:
        normalized = normalize_tutor_chat_session(payload)
        normalized["context_snapshot"] = {
            "marking_result_path": context_snapshot.get("marking_result_path"),
            "amendment_updated_at": context_snapshot.get("amendment_updated_at"),
            "review_state_updated_at": context_snapshot.get("review_state_updated_at"),
            "resolved_question_fingerprint": context_snapshot.get("resolved_question_fingerprint"),
        }
        return normalize_tutor_chat_session(normalized)
