from __future__ import annotations

import json
from pathlib import Path

import pytest

from ai_study_buddy.marking import remove_marking_run_artifacts
from ai_study_buddy.marking.core.artifact_cleanup import MarkingRunArtifactRemovalError


def _write_json(path: Path, payload: dict) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _artifact_payload(*, marking_asset: str | None) -> dict:
    return {
        "schema_version": "marking_result.v1.5",
        "created_at": "2026-04-23T10:00:00+08:00",
        "updated_at": "2026-04-23T10:00:00+08:00",
        "context": {
            "student_id": "winston",
            "student_name": "Winston",
            "subject_context": "singapore_primary_english",
            "attempt_file_path": "/tmp/attempt.pdf",
            "marking_asset": marking_asset,
            "question_page_map": [],
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


def _build_paths(context_root: Path) -> tuple[Path, Path, Path]:
    json_path = (
        context_root
        / "marking_results"
        / "winston"
        / "singapore_primary_english"
        / "EPO_Comprehension_Cloze_07__20260419_203539.json"
    )
    report_path = (
        context_root
        / "learning_reports"
        / "winston"
        / "singapore_primary_english"
        / "EPO_Comprehension_Cloze_07__20260419_203539 - Marking Report.md"
    )
    bundle_path = (
        context_root
        / "marking_assets"
        / "winston"
        / "singapore_primary_english"
        / "EPO_Comprehension_Cloze_07__20260419_203539"
    )
    return json_path, report_path, bundle_path


def test_remove_marking_run_artifacts_dry_run_returns_plan(tmp_path: Path) -> None:
    context_root = tmp_path / "context"
    json_path, report_path, bundle_path = _build_paths(context_root)
    payload = _artifact_payload(
        marking_asset="marking_assets/winston/singapore_primary_english/EPO_Comprehension_Cloze_07__20260419_203539"
    )
    _write_json(json_path, payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# report", encoding="utf-8")
    (bundle_path / "attempt").mkdir(parents=True, exist_ok=True)

    result = remove_marking_run_artifacts(
        json_path,
        context_root=context_root,
        dry_run=True,
        mode="strict",
    )

    assert result.requested.marking_result_json == json_path.resolve()
    assert result.requested.learning_report_md == report_path.resolve()
    assert result.requested.marking_asset_bundle == bundle_path.resolve()
    assert result.deleted_paths == ()
    assert result.skipped_missing_paths == ()


def test_remove_marking_run_artifacts_strict_deletes_json_report_and_bundle(tmp_path: Path) -> None:
    context_root = tmp_path / "context"
    json_path, report_path, bundle_path = _build_paths(context_root)
    payload = _artifact_payload(
        marking_asset="marking_assets/winston/singapore_primary_english/EPO_Comprehension_Cloze_07__20260419_203539"
    )
    _write_json(json_path, payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# report", encoding="utf-8")
    (bundle_path / "attempt").mkdir(parents=True, exist_ok=True)
    (bundle_path / "attempt" / "page-01.png").write_bytes(b"png")
    (bundle_path / "crops").mkdir(parents=True, exist_ok=True)
    (bundle_path / "crops" / "q1.png").write_bytes(b"png")

    result = remove_marking_run_artifacts(
        json_path,
        context_root=context_root,
        mode="strict",
    )

    assert result.deleted_paths == (
        report_path.resolve(),
        bundle_path.resolve(),
        json_path.resolve(),
    )
    assert not report_path.exists()
    assert not bundle_path.exists()
    assert not json_path.exists()


def test_remove_marking_run_artifacts_strict_fails_when_report_or_bundle_missing(tmp_path: Path) -> None:
    context_root = tmp_path / "context"
    json_path, report_path, _bundle_path = _build_paths(context_root)
    payload = _artifact_payload(
        marking_asset="marking_assets/winston/singapore_primary_english/EPO_Comprehension_Cloze_07__20260419_203539"
    )
    _write_json(json_path, payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# report", encoding="utf-8")

    with pytest.raises(FileNotFoundError) as exc:
        remove_marking_run_artifacts(
            json_path,
            context_root=context_root,
            mode="strict",
        )
    assert "Missing expected artifact(s)" in str(exc.value)
    assert json_path.exists()
    assert report_path.exists()


def test_remove_marking_run_artifacts_best_effort_skips_missing_report_and_bundle(tmp_path: Path) -> None:
    context_root = tmp_path / "context"
    json_path, report_path, bundle_path = _build_paths(context_root)
    payload = _artifact_payload(
        marking_asset="marking_assets/winston/singapore_primary_english/EPO_Comprehension_Cloze_07__20260419_203539"
    )
    _write_json(json_path, payload)

    result = remove_marking_run_artifacts(
        json_path,
        context_root=context_root,
        mode="best_effort",
    )

    assert result.deleted_paths == (json_path.resolve(),)
    assert set(result.skipped_missing_paths) == {report_path.resolve(), bundle_path.resolve()}
    assert not json_path.exists()


def test_remove_marking_run_artifacts_strict_errors_when_json_missing(tmp_path: Path) -> None:
    context_root = tmp_path / "context"
    json_path, _, _ = _build_paths(context_root)

    with pytest.raises(FileNotFoundError) as exc:
        remove_marking_run_artifacts(
            json_path,
            context_root=context_root,
            mode="strict",
        )
    assert "Canonical marking result JSON not found" in str(exc.value)


def test_remove_marking_run_artifacts_rejects_unsafe_marking_asset_and_deletes_nothing(tmp_path: Path) -> None:
    context_root = tmp_path / "context"
    json_path, report_path, _bundle_path = _build_paths(context_root)
    payload = _artifact_payload(marking_asset="/tmp/escape")
    _write_json(json_path, payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# report", encoding="utf-8")

    with pytest.raises(MarkingRunArtifactRemovalError) as exc:
        remove_marking_run_artifacts(
            json_path,
            context_root=context_root,
            mode="best_effort",
        )
    assert "context.marking_asset" in str(exc.value)
    assert json_path.exists()
    assert report_path.exists()


def test_remove_marking_run_artifacts_strict_deletes_bundle_with_nested_files(tmp_path: Path) -> None:
    context_root = tmp_path / "context"
    json_path, report_path, bundle_path = _build_paths(context_root)
    payload = _artifact_payload(
        marking_asset="marking_assets/winston/singapore_primary_english/EPO_Comprehension_Cloze_07__20260419_203539"
    )
    _write_json(json_path, payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# report", encoding="utf-8")
    (bundle_path / "attempt").mkdir(parents=True, exist_ok=True)
    (bundle_path / "attempt" / "page-01.png").write_bytes(b"png")
    (bundle_path / "scripts").mkdir(parents=True, exist_ok=True)
    (bundle_path / "scripts" / "_helper.py").write_text("print('x')", encoding="utf-8")
    (bundle_path / "nested" / "deeper").mkdir(parents=True, exist_ok=True)
    (bundle_path / "nested" / "deeper" / "artifact.txt").write_text("x", encoding="utf-8")

    remove_marking_run_artifacts(
        json_path,
        context_root=context_root,
        mode="strict",
    )

    assert not bundle_path.exists()


def test_remove_marking_run_artifacts_uses_json_stem_for_report_mapping(tmp_path: Path) -> None:
    context_root = tmp_path / "context"
    json_path = (
        context_root
        / "marking_results"
        / "winston"
        / "singapore_primary_english"
        / "custom_run__20260423_101010.json"
    )
    report_path = (
        context_root
        / "learning_reports"
        / "winston"
        / "singapore_primary_english"
        / "custom_run__20260423_101010 - Marking Report.md"
    )
    payload = _artifact_payload(marking_asset=None)
    _write_json(json_path, payload)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text("# report", encoding="utf-8")

    result = remove_marking_run_artifacts(
        json_path,
        context_root=context_root,
        dry_run=True,
        mode="strict",
    )

    assert result.requested.learning_report_md == report_path.resolve()
