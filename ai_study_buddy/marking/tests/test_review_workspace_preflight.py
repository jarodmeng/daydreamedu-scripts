from __future__ import annotations

from pathlib import Path

import pytest

from ai_study_buddy.review_workspace.backend import app as review_workspace_app


_ONE_BY_ONE_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00"
    b"\x1f\x15\xc4\x89"
    b"\x00\x00\x00\x0cIDATx\x9cc```\x00\x00\x00\x04\x00\x01"
    b"\x0d\n-\xb4"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def _write_png(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_ONE_BY_ONE_PNG)


def _artifact_payload(marking_asset: str, evidence_image: str = "attempt/page-01.png") -> dict:
    return {
        "schema_version": "marking_result.v1.4",
        "created_at": "2026-04-23T12:00:00+08:00",
        "updated_at": "2026-04-23T12:00:00+08:00",
        "context": {
            "student_id": "winston",
            "student_name": "Winston",
            "subject_context": "singapore_primary_english",
            "marking_asset": marking_asset,
            "question_page_map": [
                {
                    "result_id": "Q1",
                    "attempt_page_start": 1,
                    "confidence": "high",
                    "source": "manual_visual",
                    "evidence_image": evidence_image,
                    "note": None,
                }
            ],
        },
        "summary": {
            "total_marks": 1,
            "earned_marks": 1,
            "percentage": 100.0,
            "overall_assessment": "ok",
            "human_note": None,
        },
        "question_results": [],
        "review_meta": {"updated_by": None, "updated_at": None},
        "generation": {"produced_by": "test", "mode": "unit_test", "notes": None},
    }


def test_review_workspace_preflight_accepts_strict_valid_bundle(tmp_path, monkeypatch):
    marking_asset = "marking_assets/winston/singapore_primary_english/sample__20260423_120000"
    payload = _artifact_payload(marking_asset=marking_asset)
    bundle_root = tmp_path / marking_asset
    _write_png(bundle_root / "attempt" / "page-01.png")
    (bundle_root / "bundle.json").write_text(
        '{"bundle_layout_version":1,"attempt_page_count":1}',
        encoding="utf-8",
    )

    artifact = review_workspace_app.PilotArtifact(
        path=tmp_path / "artifact.json",
        payload=payload,
    )
    monkeypatch.setattr(review_workspace_app, "CONTEXT_ROOT", tmp_path)

    review_workspace_app._validate_pilot_artifact_bundle(artifact)


def test_review_workspace_preflight_rejects_invalid_bundle(tmp_path, monkeypatch):
    marking_asset = "marking_assets/winston/singapore_primary_english/sample__20260423_120000"
    payload = _artifact_payload(marking_asset=marking_asset, evidence_image="attempt/attempt-page-01.png")
    bundle_root = tmp_path / marking_asset
    _write_png(bundle_root / "attempt" / "attempt-page-01.png")
    (bundle_root / "bundle.json").write_text(
        '{"bundle_layout_version":1,"attempt_page_count":1}',
        encoding="utf-8",
    )

    artifact = review_workspace_app.PilotArtifact(
        path=tmp_path / "artifact.json",
        payload=payload,
    )
    monkeypatch.setattr(review_workspace_app, "CONTEXT_ROOT", tmp_path)

    with pytest.raises(RuntimeError, match="failed strict validation"):
        review_workspace_app._validate_pilot_artifact_bundle(artifact)
