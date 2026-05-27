import tempfile
from pathlib import Path

import pytest

from ai_study_buddy.pdf_file_manager.completion_date import (
    normalize_inference_model,
    validate_inferred_completion_date_provenance,
)
from ai_study_buddy.pdf_file_manager.completion_date.page1 import (
    parse_page1_inspection_payload,
)
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def test_normalize_inference_model_rejects_inherit():
    with pytest.raises(ValueError, match="inherit"):
        normalize_inference_model("inherit")


def test_validate_inferred_provenance_requires_confidence_and_model():
    validate_inferred_completion_date_provenance(
        source="manual",
        confidence=None,
        inference_model=None,
    )
    with pytest.raises(ValueError, match="confidence"):
        validate_inferred_completion_date_provenance(
            source="handwritten_page1",
            confidence=None,
            inference_model="gpt-5.4-medium",
        )
    with pytest.raises(ValueError, match="inference_model"):
        validate_inferred_completion_date_provenance(
            source="handwritten_page1",
            confidence="high",
            inference_model=None,
        )


def test_parse_page1_requires_model_and_confidence_when_dated():
    with pytest.raises(ValueError, match="inference_model"):
        parse_page1_inspection_payload(
            {
                "file_id": "x",
                "completion_date": "2025-01-01",
                "confidence": "high",
            }
        )


def test_set_completion_date_persists_inference_model():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            mgr.ensure_student("winston", "Winston")
            dd = root / "DaydreamEdu" / "completion" / "Singapore Primary English"
            p = dd / "winston.ry.meng@gmail.com" / "P5" / "Exercise"
            p.mkdir(parents=True, exist_ok=True)
            pdf = p / "_c_x.pdf"
            pdf.write_bytes(b"%PDF-1.0\n")
            record = mgr.register_file(
                pdf,
                file_type="main",
                doc_type="exercise",
                student_id="winston",
                is_template=False,
            )
            row = mgr.set_completion_date(
                record.id,
                "2025-06-01",
                source="handwritten_page1",
                confidence="medium",
                inference_model="claude-4.6-sonnet-medium-thinking",
            )
            assert row.inference_model == "claude-4.6-sonnet-medium-thinking"
            assert mgr.get_completion_date(record.id).confidence == "medium"
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_migration_adds_inference_model_column():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        mgr = PdfFileManager(db_path=db_path)
        conn = mgr._get_connection()
        cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(file_completion_dates)").fetchall()
        }
        assert "inference_model" in cols
    finally:
        Path(db_path).unlink(missing_ok=True)
