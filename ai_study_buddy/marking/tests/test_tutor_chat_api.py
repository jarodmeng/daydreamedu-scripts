from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from ai_study_buddy.marking.review import api_routes
import ai_study_buddy.marking.review.tutor_chat_context_service as tutor_chat_context_service
from ai_study_buddy.marking.review.tutor_chat_repository import TutorChatRepository, build_new_session
from ai_study_buddy.marking.review import tutor_chat_service
from ai_study_buddy.marking.review.tutor_chat_service import (
    InferenceTurnResult,
    set_agent_runner_for_tests,
)
from ai_study_buddy.marking.review.tutor_chat_context_service import build_context_bundle_from_detail
from ai_study_buddy.marking.tests.test_tutor_chat_context_service import _detail_fixture
from ai_study_buddy.review_workspace.backend import app as review_workspace_backend


class _FakeAgentRunner:
    def __init__(
        self,
        *,
        reply: str = "Because the stem carries water.",
        chunks: tuple[str, ...] | None = None,
        delay_seconds: float = 0.0,
    ):
        self.reply = reply
        self.chunks = chunks if chunks is not None else ("Because ", "the stem carries water.")
        self.delay_seconds = delay_seconds
        self.calls: list[dict[str, object]] = []

    def run_turn(self, **kwargs) -> InferenceTurnResult:
        import time

        self.calls.append(kwargs)
        if self.delay_seconds > 0:
            time.sleep(self.delay_seconds)
        return InferenceTurnResult(
            cursor_agent_id="agent-test-1",
            assistant_text=self.reply,
            run_id="run-test-1",
            text_chunks=self.chunks,
        )


def _enable_tutor_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BUDDY_CONSOLE_DISABLE_TUTOR_CHAT", raising=False)
    monkeypatch.setenv("CURSOR_API_KEY", "test-key")


def _install_detail_fixture(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    detail = _detail_fixture()
    page_dir = tmp_path / "marking_assets/emma/singapore_primary_science/sample/attempt"
    page_dir.mkdir(parents=True, exist_ok=True)
    (page_dir / "page-02.png").write_bytes(b"png")

    class _FakeManager:
        def get_file(self, file_id: str):
            return object()

    def _fake_get_attempt_detail(**kwargs):
        return detail

    class _FakeRepo:
        def load_raw_review_state(self, **kwargs):
            return {"updated_at": "2026-06-02T10:00:00Z"}

    monkeypatch.setattr(tutor_chat_context_service, "get_attempt_detail", _fake_get_attempt_detail)
    monkeypatch.setattr(api_routes, "_manager", lambda: _FakeManager())
    monkeypatch.setattr(api_routes, "_repo", lambda: _FakeRepo())
    monkeypatch.setattr(api_routes, "CONTEXT_ROOT", tmp_path)
    monkeypatch.setattr(api_routes, "REPO_ROOT", tmp_path)


def _parse_sse(body: str) -> list[tuple[str, dict]]:
    events: list[tuple[str, dict]] = []
    event_name = "message"
    for line in body.splitlines():
        if line.startswith("event:"):
            event_name = line.split(":", 1)[1].strip()
        elif line.startswith("data:"):
            payload = json.loads(line.split(":", 1)[1].strip())
            events.append((event_name, payload))
    return events


@pytest.fixture(autouse=True)
def _reset_agent_runner():
    set_agent_runner_for_tests(None)
    yield
    set_agent_runner_for_tests(None)


def test_tutor_chat_routes_return_404_when_disabled(monkeypatch):
    monkeypatch.setenv("BUDDY_CONSOLE_DISABLE_TUTOR_CHAT", "1")
    client = TestClient(review_workspace_backend.app)
    response = client.get("/api/student/attempts/attempt-1/questions/Q2/tutor-chat")
    assert response.status_code == 404


def test_tutor_chat_routes_return_503_without_api_key(monkeypatch):
    monkeypatch.delenv("BUDDY_CONSOLE_DISABLE_TUTOR_CHAT", raising=False)
    monkeypatch.delenv("CURSOR_API_KEY", raising=False)
    client = TestClient(review_workspace_backend.app)
    response = client.get("/api/student/attempts/attempt-1/questions/Q2/tutor-chat")
    assert response.status_code == 503


def test_get_latest_session_returns_404_when_missing(monkeypatch, tmp_path: Path):
    _enable_tutor_env(monkeypatch)
    _install_detail_fixture(monkeypatch, tmp_path)

    client = TestClient(review_workspace_backend.app)
    response = client.get("/api/student/attempts/attempt-1/questions/Q2/tutor-chat")
    assert response.status_code == 404


def test_create_session_and_get_latest(monkeypatch, tmp_path: Path):
    _enable_tutor_env(monkeypatch)
    _install_detail_fixture(monkeypatch, tmp_path)

    client = TestClient(review_workspace_backend.app)
    created = client.post("/api/student/attempts/attempt-1/questions/Q2/tutor-chat/sessions")
    assert created.status_code == 200
    session_id = created.json()["session_id"]

    loaded = client.get("/api/student/attempts/attempt-1/questions/Q2/tutor-chat")
    assert loaded.status_code == 200
    payload = loaded.json()
    assert payload["session_id"] == session_id
    assert payload["messages"] == []
    assert payload["stale_context"] == {"marking": False, "review_notes": False}


def test_post_streams_tokens_and_persists_transcript(monkeypatch, tmp_path: Path):
    _enable_tutor_env(monkeypatch)
    _install_detail_fixture(monkeypatch, tmp_path)
    runner = _FakeAgentRunner()
    set_agent_runner_for_tests(runner)

    client = TestClient(review_workspace_backend.app)
    with client.stream(
        "POST",
        "/api/student/attempts/attempt-1/questions/Q2/tutor-chat",
        json={"message": "Why was I wrong?"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    events = _parse_sse(body)
    assert ("status", {"phase": "started"}) in events
    assert any(name == "status" and payload.get("phase") == "running" for name, payload in events)
    assert ("token", {"text": "Because "}) in events
    assert ("token", {"text": "the stem carries water."}) in events
    done_events = [payload for name, payload in events if name == "done"]
    assert len(done_events) == 1
    assert done_events[0]["message"]["content"] == "Because the stem carries water."
    assert done_events[0]["stale_context"] == {"marking": False, "review_notes": False}

    tutor_repo = TutorChatRepository(context_root=tmp_path)
    session = tutor_repo.load_latest_session(
        student_id="emma",
        subject_context="singapore_primary_science",
        marking_artifact_stem="sample",
        result_id="Q2",
    )
    assert session is not None
    assert session["cursor_agent_id"] == "agent-test-1"
    assert len(session["messages"]) == 2
    assert session["messages"][0]["role"] == "student"
    assert session["messages"][1]["role"] == "assistant"
    assert runner.calls[0]["cursor_agent_id"] is None
    assert "Why was I wrong?" in str(runner.calls[0]["prompt"])


def test_post_emits_running_heartbeats_while_inference_blocks(monkeypatch, tmp_path: Path):
    _enable_tutor_env(monkeypatch)
    _install_detail_fixture(monkeypatch, tmp_path)
    monkeypatch.setattr(tutor_chat_service, "TUTOR_CHAT_SSE_HEARTBEAT_SECONDS", 0.05)
    set_agent_runner_for_tests(_FakeAgentRunner(delay_seconds=0.12))

    client = TestClient(review_workspace_backend.app)
    with client.stream(
        "POST",
        "/api/student/attempts/attempt-1/questions/Q2/tutor-chat",
        json={"message": "Why was I wrong?"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    events = _parse_sse(body)
    running_status_events = [
        payload for name, payload in events if name == "status" and payload.get("phase") == "running"
    ]
    assert len(running_status_events) >= 2


def test_post_rejects_empty_message(monkeypatch, tmp_path: Path):
    _enable_tutor_env(monkeypatch)
    _install_detail_fixture(monkeypatch, tmp_path)

    client = TestClient(review_workspace_backend.app)
    response = client.post(
        "/api/student/attempts/attempt-1/questions/Q2/tutor-chat",
        json={"message": "   "},
    )
    assert response.status_code == 400


def test_post_with_unknown_session_id_returns_404(monkeypatch, tmp_path: Path):
    _enable_tutor_env(monkeypatch)
    _install_detail_fixture(monkeypatch, tmp_path)

    client = TestClient(review_workspace_backend.app)
    response = client.post(
        "/api/student/attempts/attempt-1/questions/Q2/tutor-chat",
        json={"message": "Hello", "session_id": "missing-session"},
    )
    assert response.status_code == 404


def test_post_follow_up_resumes_agent(monkeypatch, tmp_path: Path):
    _enable_tutor_env(monkeypatch)
    _install_detail_fixture(monkeypatch, tmp_path)
    runner = _FakeAgentRunner(reply="Follow-up answer.", chunks=("Follow-up ", "answer."))
    set_agent_runner_for_tests(runner)

    detail = _detail_fixture()
    bundle = build_context_bundle_from_detail(
        detail=detail,
        result_id="Q2",
        context_root=tmp_path,
        review_state_updated_at="2026-06-02T10:00:00Z",
    )
    tutor_repo = TutorChatRepository(context_root=tmp_path)
    session = build_new_session(
        attempt_id="attempt-1",
        result_id="Q2",
        student_id="emma",
        subject_context="singapore_primary_science",
        marking_artifact_stem="sample",
        context_snapshot=bundle["context_snapshot"],
        session_id="sess-existing",
        cursor_agent_id="agent-existing",
    )
    session["messages"] = [
        {"role": "student", "content": "First", "at": "2026-06-01T00:00:00Z"},
        {"role": "assistant", "content": "First reply", "at": "2026-06-01T00:00:01Z"},
    ]
    tutor_repo.save_session(session)

    client = TestClient(review_workspace_backend.app)
    with client.stream(
        "POST",
        "/api/student/attempts/attempt-1/questions/Q2/tutor-chat",
        json={"message": "Tell me more", "session_id": "sess-existing"},
    ) as response:
        assert response.status_code == 200
        body = "".join(response.iter_text())

    events = _parse_sse(body)
    assert any(name == "done" for name, _ in events)
    assert runner.calls[0]["cursor_agent_id"] == "agent-existing"
    assert runner.calls[0]["prompt"] == "Tell me more"


def test_get_reports_stale_context(monkeypatch, tmp_path: Path):
    _enable_tutor_env(monkeypatch)
    _install_detail_fixture(monkeypatch, tmp_path)

    tutor_repo = TutorChatRepository(context_root=tmp_path)
    session = build_new_session(
        attempt_id="attempt-1",
        result_id="Q2",
        student_id="emma",
        subject_context="singapore_primary_science",
        marking_artifact_stem="sample",
        context_snapshot={
            "marking_result_path": "marking_results/emma/singapore_primary_science/sample.json",
            "amendment_updated_at": "2026-05-01T00:00:00Z",
            "review_state_updated_at": "2026-05-01T00:00:00Z",
            "resolved_question_fingerprint": "stale-fingerprint",
        },
        session_id="sess-stale",
    )
    tutor_repo.save_session(session)

    client = TestClient(review_workspace_backend.app)
    response = client.get("/api/student/attempts/attempt-1/questions/Q2/tutor-chat")
    assert response.status_code == 200
    payload = response.json()
    assert payload["stale_context"]["marking"] is True
    assert payload["stale_context"]["review_notes"] is True
