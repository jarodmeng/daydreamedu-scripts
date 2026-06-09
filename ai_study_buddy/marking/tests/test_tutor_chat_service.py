from __future__ import annotations

from pathlib import Path

import pytest

from ai_study_buddy.marking.review.tutor_chat_service import (
    CursorSdkAgentRunner,
    TutorChatInferenceError,
)


class _FakeRun:
    id = "run-test"

    def iter_text(self):
        yield "Hello"

    def wait(self):
        class _Result:
            status = "finished"
            result = ""

        return _Result()


class _FakeAgent:
    agent_id = "agent-test"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return None

    def send(self, _prompt: str, _options=None):
        return _FakeRun()


def test_cursor_sdk_runner_resume_passes_serializable_agent_options(monkeypatch):
    captured: dict[str, object] = {}

    def _fake_resume(agent_id: str, options):
        captured["agent_id"] = agent_id
        captured["options"] = options
        return _FakeAgent()

    monkeypatch.setattr("cursor_sdk.Agent.resume", _fake_resume)

    runner = CursorSdkAgentRunner()
    result = runner.run_turn(
        repo_root=Path("/tmp/repo"),
        api_key="test-key",
        cursor_agent_id="agent-existing",
        prompt="Follow-up",
    )

    assert captured["agent_id"] == "agent-existing"
    options = captured["options"]
    assert options is not None
    assert hasattr(options, "to_json")
    payload = options.to_json()
    assert payload.get("apiKey") == "test-key"
    assert payload.get("model", {}).get("id") == "auto"
    assert isinstance(payload.get("local"), dict)
    assert result.assistant_text == "Hello"
    assert result.cursor_agent_id == "agent-test"


def test_cursor_sdk_runner_wraps_resume_failures(monkeypatch):
    def _fake_resume(_agent_id: str, _options):
        raise TypeError("Object of type LocalAgentOptions is not JSON serializable")

    monkeypatch.setattr("cursor_sdk.Agent.resume", _fake_resume)

    runner = CursorSdkAgentRunner()
    with pytest.raises(TutorChatInferenceError) as exc_info:
        runner.run_turn(
            repo_root=Path("/tmp/repo"),
            api_key="test-key",
            cursor_agent_id="agent-existing",
            prompt="Follow-up",
        )

    assert exc_info.value.code == "startup_failed"
