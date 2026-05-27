import sqlite3
import tempfile
from pathlib import Path

import pytest

from ai_study_buddy.pdf_file_manager.completion_date import (
    normalize_completion_date,
    normalize_completion_date_source,
)
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def _make_pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.0\n")
    return path


def _register_completion(
    mgr: PdfFileManager, path: Path, *, student_id: str = "winston"
) -> str:
    mgr.add_student(student_id, student_id.title())
    record = mgr.register_file(
        _make_pdf(path),
        file_type="main",
        doc_type="exercise",
        student_id=student_id,
        subject="english",
        is_template=False,
    )
    return record.id


def test_manual_set_get_clear_round_trip():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            file_id = _register_completion(mgr, root / "_c_practice.pdf")

            assert mgr.get_completion_date(file_id) is None

            row = mgr.set_completion_date(
                file_id,
                "2025-10-22",
                confidence="high",
                source_detail={"note": "operator verified"},
            )
            assert row.completion_date == "2025-10-22"
            assert row.source == "manual"
            assert row.confidence == "high"
            assert row.source_detail == {"note": "operator verified"}

            fetched = mgr.get_completion_date(file_id)
            assert fetched == row

            batch = mgr.get_completion_dates_for_files([file_id, "missing-id"])
            assert file_id in batch
            assert batch[file_id] == row

            mgr.clear_completion_date(file_id)
            assert mgr.get_completion_date(file_id) is None

            logs = mgr.get_operation_log(file_id=file_id)
            operations = [entry.operation for entry in logs]
            assert "set_completion_date" in operations
            assert "clear_completion_date" in operations
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_set_completion_date_rejects_template_raw_and_missing_student():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_student("winston", "Winston")

            template_id = mgr.register_file(
                _make_pdf(root / "template.pdf"),
                file_type="main",
                doc_type="exercise",
                student_id="winston",
                is_template=True,
            ).id
            raw_id = mgr.register_file(
                _make_pdf(root / "_raw_scan.pdf"),
                file_type="raw",
                doc_type="exercise",
                student_id="winston",
            ).id
            no_student_id = mgr.register_file(
                _make_pdf(root / "orphan.pdf"),
                file_type="main",
                doc_type="exercise",
                student_id=None,
            ).id

            for file_id in (template_id, raw_id, no_student_id):
                with pytest.raises(ValueError):
                    mgr.set_completion_date(file_id, "2025-01-01")
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_completion_date_fk_cascade_on_pdf_files_delete():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            file_id = _register_completion(mgr, root / "_c_wa.pdf")
            mgr.set_completion_date(file_id, "2025-03-01")

            mgr.delete_file(file_id)

            conn = sqlite3.connect(db_path)
            row = conn.execute(
                "SELECT 1 FROM file_completion_dates WHERE file_id = ?",
                (file_id,),
            ).fetchone()
            conn.close()
            assert row is None
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_schema_check_rejects_invalid_completion_date_and_source():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        mgr = PdfFileManager(db_path=db_path)
        mgr._get_connection()
        conn = sqlite3.connect(db_path)
        conn.execute("PRAGMA foreign_keys = ON")

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO file_completion_dates (
                    file_id, completion_date, source, inferred_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                ("missing-file", "not-a-date", "manual", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            )

        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                """
                INSERT INTO file_completion_dates (
                    file_id, completion_date, source, inferred_at, updated_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                ("missing-file", "2025-01-01", "registry_added_at", "2026-01-01T00:00:00Z", "2026-01-01T00:00:00Z"),
            )
        conn.close()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_normalize_completion_date_rejects_invalid_values():
    with pytest.raises(ValueError):
        normalize_completion_date("25-10-22")
    with pytest.raises(ValueError):
        normalize_completion_date_source("added_at")


def test_infer_completion_dates_dry_run_and_force_flags():
    """Batch infer respects dry_run and force/force_manual semantics."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_student("winston", "Winston")
            dd = root / "DaydreamEdu" / "completion" / "Singapore Primary English"
            dd.mkdir(parents=True, exist_ok=True)
            p = dd / "winston.ry.meng@gmail.com" / "P5" / "Exercise"
            p.mkdir(parents=True, exist_ok=True)
            record = mgr.register_file(
                _make_pdf(p / "_c_stub.pdf"),
                file_type="main",
                doc_type="exercise",
                student_id="winston",
                is_template=False,
            )

            # Dry-run: no rows written, still_undated reflects current state.
            report = mgr.infer_completion_dates(
                root="d_root",
                dry_run=True,
            )
            assert report.processed >= 1
            assert report.written == 0
            assert report.still_undated >= 1
            assert mgr.get_completion_date(record.id) is None

            # Manual row is not overwritten without force_manual.
            mgr.set_completion_date(record.id, "2025-01-01")
            report2 = mgr.infer_completion_dates(root="d_root")
            assert report2.skipped_manual >= 1
    finally:
        Path(db_path).unlink(missing_ok=True)
