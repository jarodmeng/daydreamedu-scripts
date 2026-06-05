from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from ai_study_buddy.buddy_console.backend.app import app
from ai_study_buddy.buddy_console.tests.test_inventory_api import _card, _runtime


def test_patch_review_status_marks_completed(monkeypatch, tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.enriched_cache = [_card(tmp_path / "goodnotes" / "Math" / "emma" / "P4" / "registered.pdf")]
    runtime.enriched_cache[0].registry_file_id = "attempt-123"
    app.state.inventory_runtime = runtime

    fake_ref = SimpleNamespace(marking_result_json=tmp_path / "marking_results" / "emma" / "ctx" / "run.json")
    fake_ref.marking_result_json.parent.mkdir(parents=True, exist_ok=True)
    fake_ref.marking_result_json.write_text('{"context": {"student_id": "emma", "subject_context": "math"}}')

    with (
        patch(
            "ai_study_buddy.buddy_console.backend.inventory_api.PdfFileManager",
        ) as mock_mgr_cls,
        patch(
            "ai_study_buddy.buddy_console.backend.inventory_api.find_marking_artifacts_for_attempt",
            return_value=[fake_ref],
        ),
        patch(
            "ai_study_buddy.buddy_console.backend.inventory_api.read_marking_result_payload",
            return_value={"context": {"student_id": "emma", "subject_context": "math"}},
        ),
        patch(
            "ai_study_buddy.buddy_console.backend.inventory_api.StudentReviewRepository.load_review_state",
            return_value={
                "review_status": "not_started",
                "question_reviews": [],
                "attempt_notes": [],
                "student_subject_notes": [],
            },
        ),
        patch(
            "ai_study_buddy.buddy_console.backend.inventory_api.put_review_state",
            return_value={"review_state": {"review_status": "completed"}},
        ) as mock_put,
    ):
        mock_mgr = mock_mgr_cls.return_value
        mock_mgr.get_file.return_value = SimpleNamespace(student_id="emma")

        client = TestClient(app)
        response = client.patch(
            "/api/inventory/items/attempt-123/review-status",
            json={"review_status": "completed"},
        )

    assert response.status_code == 200
    assert response.json() == {
        "registry_file_id": "attempt-123",
        "review_status": "completed",
    }
    mock_put.assert_called_once()
    assert mock_put.call_args.kwargs["body"]["review_status"] == "completed"
    assert mock_put.call_args.kwargs["body"]["updated_by"] == "buddy_console_inventory"


def test_patch_review_status_requires_marking_artifact(monkeypatch, tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    app.state.inventory_runtime = runtime

    with (
        patch(
            "ai_study_buddy.buddy_console.backend.inventory_api.PdfFileManager",
        ) as mock_mgr_cls,
        patch(
            "ai_study_buddy.buddy_console.backend.inventory_api.find_marking_artifacts_for_attempt",
            return_value=[],
        ),
    ):
        mock_mgr = mock_mgr_cls.return_value
        mock_mgr.get_file.return_value = SimpleNamespace(student_id="emma")

        client = TestClient(app)
        response = client.patch(
            "/api/inventory/items/attempt-123/review-status",
            json={"review_status": "completed"},
        )

    assert response.status_code == 400
    assert response.json()["detail"] == "No marking artifact for this completion"
