from __future__ import annotations

import json
from pathlib import Path

from ai_study_buddy.marking.assets.paths import (
    bundle_root_from_context,
    marking_asset_rel_path_from_artifact_path,
)
from ai_study_buddy.marking.assets.manifest import write_bundle_manifest_for_artifact
from ai_study_buddy.marking.assets.validate import validate_marking_asset_bundle


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


def _sample_artifact_dict() -> dict:
    return {
        "schema_version": "marking_result.v1.4",
        "created_at": "2026-04-21T12:00:00+08:00",
        "updated_at": "2026-04-21T12:00:00+08:00",
        "context": {
            "student_id": "winston",
            "student_name": "Winston",
            "subject_context": "singapore_primary_science",
            "marking_asset": "marking_assets/winston/singapore_primary_science/sample__20260421_120000",
            "question_page_map": [
                {
                    "result_id": "Q1",
                    "attempt_page_start": 1,
                    "confidence": "high",
                    "source": "manual_visual",
                    "evidence_image": "attempt/page-01.png",
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
        "question_results": [
            {
                "result_id": "Q1",
                "max_marks": 1,
                "earned_marks": 1,
                "outcome": "correct",
                "student_answer": "A",
                "correct_answer": "A",
                "feedback": None,
                "error_tags": [],
                "skill_tags": [],
                "diagnosis": {
                    "mistake_type": None,
                    "reasoning": None,
                    "confidence": "medium",
                },
                "human_note": None,
            }
        ],
        "review_meta": {"updated_by": None, "updated_at": None},
        "generation": {"produced_by": "test", "mode": "unit_test", "notes": None},
    }


def test_marking_asset_rel_path_from_artifact_path_extracts_writer_shape(tmp_path):
    artifact_path = (
        tmp_path
        / "marking_results"
        / "winston"
        / "singapore_primary_science"
        / "sample__20260421_120000.json"
    )
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text("{}", encoding="utf-8")
    rel = marking_asset_rel_path_from_artifact_path(
        artifact_json_path=artifact_path,
        context_root=tmp_path,
    )
    assert rel == "marking_assets/winston/singapore_primary_science/sample__20260421_120000"


def test_bundle_root_from_context_rejects_parent_escape(tmp_path):
    context = {"marking_asset": "marking_assets/winston/../escape"}
    assert bundle_root_from_context(context, context_root=tmp_path) is None


def test_validate_marking_asset_bundle_accepts_good_bundle(tmp_path):
    artifact = _sample_artifact_dict()
    bundle_root = tmp_path / artifact["context"]["marking_asset"]
    _write_png(bundle_root / "attempt" / "page-01.png")
    (bundle_root / "crops").mkdir(parents=True, exist_ok=True)
    (bundle_root / "bundle.json").write_text(
        json.dumps(
            {
                "bundle_layout_version": 1,
                "attempt_page_count": 1,
            }
        ),
        encoding="utf-8",
    )

    report = validate_marking_asset_bundle(
        bundle_root=bundle_root,
        artifact_dict=artifact,
        strict=True,
    )
    assert report.ok


def test_validate_marking_asset_bundle_rejects_missing_attempt_dir(tmp_path):
    artifact = _sample_artifact_dict()
    bundle_root = tmp_path / artifact["context"]["marking_asset"]
    bundle_root.mkdir(parents=True, exist_ok=True)
    report = validate_marking_asset_bundle(
        bundle_root=bundle_root,
        artifact_dict=artifact,
        strict=True,
    )
    assert not report.ok
    assert any(issue.code == "missing_attempt_dir" for issue in report.errors)


def test_validate_marking_asset_bundle_rejects_bad_evidence_image_path(tmp_path):
    artifact = _sample_artifact_dict()
    artifact["context"]["question_page_map"][0]["evidence_image"] = "../outside.png"
    bundle_root = tmp_path / artifact["context"]["marking_asset"]
    _write_png(bundle_root / "attempt" / "page-01.png")
    report = validate_marking_asset_bundle(
        bundle_root=bundle_root,
        artifact_dict=artifact,
        strict=False,
    )
    assert not report.ok
    assert any(issue.code == "invalid_evidence_image_path" for issue in report.errors)


def test_validate_marking_asset_bundle_rejects_manifest_page_count_mismatch(tmp_path):
    artifact = _sample_artifact_dict()
    bundle_root = tmp_path / artifact["context"]["marking_asset"]
    _write_png(bundle_root / "attempt" / "page-01.png")
    (bundle_root / "bundle.json").write_text(
        json.dumps(
            {
                "bundle_layout_version": 1,
                "attempt_page_count": 2,
            }
        ),
        encoding="utf-8",
    )
    report = validate_marking_asset_bundle(
        bundle_root=bundle_root,
        artifact_dict=artifact,
        strict=False,
    )
    assert not report.ok
    assert any(issue.code == "manifest_attempt_page_count_mismatch" for issue in report.errors)


def test_validate_marking_asset_bundle_warns_for_legacy_filename_in_non_strict_mode(tmp_path):
    artifact = _sample_artifact_dict()
    artifact["context"]["question_page_map"][0]["evidence_image"] = "attempt/attempt-page-01.png"
    bundle_root = tmp_path / artifact["context"]["marking_asset"]
    _write_png(bundle_root / "attempt" / "attempt-page-01.png")
    report = validate_marking_asset_bundle(
        bundle_root=bundle_root,
        artifact_dict=artifact,
        strict=False,
    )
    assert report.ok
    assert any(issue.code == "invalid_full_page_filename" for issue in report.warnings)


def test_write_bundle_manifest_for_artifact_writes_after_attempt_images_exist(tmp_path):
    artifact = _sample_artifact_dict()
    bundle_root = tmp_path / artifact["context"]["marking_asset"]
    _write_png(bundle_root / "attempt" / "page-01.png")
    _write_png(bundle_root / "answers" / "page-01.png")

    manifest_path = write_bundle_manifest_for_artifact(
        artifact_dict=artifact,
        context_root=tmp_path,
        require_attempt_images=True,
    )
    assert manifest_path is not None
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert payload["bundle_layout_version"] == 1
    assert payload["attempt_page_count"] == 1
    assert payload["answers_page_count"] == 1
    assert payload["marking_result_schema_version"] == "marking_result.v1.4"


def test_write_bundle_manifest_for_artifact_skips_when_attempt_images_missing(tmp_path):
    artifact = _sample_artifact_dict()
    bundle_root = tmp_path / artifact["context"]["marking_asset"]
    (bundle_root / "attempt").mkdir(parents=True, exist_ok=True)

    manifest_path = write_bundle_manifest_for_artifact(
        artifact_dict=artifact,
        context_root=tmp_path,
        require_attempt_images=True,
    )
    assert manifest_path is None
    assert not (bundle_root / "bundle.json").exists()
