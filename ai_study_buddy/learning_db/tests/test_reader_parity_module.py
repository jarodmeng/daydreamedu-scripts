"""Tests for reader_parity (FS vs DB-only find_marking_artifacts_for_attempt)."""

from __future__ import annotations

import json
from pathlib import Path

from ai_study_buddy.learning_db.ingest.import_context_json import run_import
from ai_study_buddy.learning_db.core.migrate import apply_migrations
from ai_study_buddy.learning_db.cli.reader_parity import run_reader_parity


def _touch(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"%PDF-1.4\n% mock pdf\n")
    return path


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _minimal_valid_payload(*, attempt_id: str, attempt_path: str) -> dict:
    root = Path(__file__).resolve().parents[2] / "marking" / "tests" / "fixtures" / "marking_result_v1_5" / "valid_minimal.json"
    data = json.loads(root.read_text(encoding="utf-8"))
    data["created_at"] = "2026-04-19T11:00:00+08:00"
    data["updated_at"] = "2026-04-19T11:00:00+08:00"
    ctx = data["context"]
    ctx["student_id"] = "emma"
    ctx["student_name"] = "Emma"
    ctx["subject_context"] = "singapore_primary_science"
    ctx["attempt_file_id"] = attempt_id
    ctx["attempt_file_path"] = attempt_path
    ctx["marking_asset"] = "marking_assets/emma/singapore_primary_science/example"
    ctx["template_attempt_group_id"] = "emma::template-1"
    return data


def test_run_reader_parity_fs_matches_db_strict(tmp_path: Path) -> None:
    study_db = tmp_path / "study_buddy.db"
    apply_migrations(db_path=study_db)

    from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

    registry_db = tmp_path / "pdf_registry.db"
    manager = PdfFileManager(db_path=registry_db)
    manager.add_student(id="emma", name="Emma", email="emma@example.com")
    attempt_path = _touch(tmp_path / "attempt.pdf")
    attempt = manager.register_file(
        attempt_path,
        file_type="main",
        doc_type="book",
        student_id="emma",
        is_template=False,
    )

    context_root = tmp_path / "context"
    _write_json(
        context_root / "marking_results" / "emma" / "singapore_primary_science" / "run_a.json",
        _minimal_valid_payload(attempt_id=str(attempt.id), attempt_path=str(attempt_path)),
    )

    run_import(
        db_path=study_db,
        context_root=context_root,
        dry_run=False,
        limit=None,
        artifact_family=None,
        retry_quarantine=False,
        retry_status="open",
        retry_failure_stage=None,
        student_id=None,
        subject_context=None,
        path_prefix=None,
    )

    report = run_reader_parity(
        study_buddy_db_path=study_db,
        context_root=context_root,
        pdf_registry_path=registry_db,
        limit=None,
    )
    assert report.eligible == 1
    assert report.skipped_no_student == 0
    assert report.mismatch_count == 0
    assert report.errors == []
    assert report.parity_checked == 1
