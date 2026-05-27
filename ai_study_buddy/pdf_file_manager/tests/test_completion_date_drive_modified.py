import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from ai_study_buddy.pdf_file_manager.completion_date.drive_modified import (
    completion_date_from_mtime,
    infer_completion_date_from_drive_modified,
)
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def test_completion_date_from_mtime_sgt():
    # 2025-10-22 12:00 UTC = 2025-10-22 20:00 SGT
    epoch = datetime(2025, 10, 22, 12, 0, tzinfo=timezone.utc).timestamp()
    day, utc = completion_date_from_mtime(epoch)
    assert day == "2025-10-22"
    assert utc.startswith("2025-10-22T12:00:00")


def test_infer_drive_modified_d_root_book():
    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        pdf_path = (
            root
            / "DaydreamEdu"
            / "completion"
            / "Singapore Primary English"
            / "student@x.com"
            / "P5"
            / "Book"
            / "My Book"
            / "_c_unit1.pdf"
        )
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"%PDF-1.0\n")
        epoch = datetime(2025, 6, 15, 4, 0, tzinfo=timezone.utc).timestamp()
        os.utime(pdf_path, (epoch, epoch))

        row = infer_completion_date_from_drive_modified(
            pdf_path, doc_type="book"
        )
        assert row is not None
        assert row.completion_date == "2025-06-15"
        assert row.source_detail["timezone"] == "Asia/Singapore"


def test_infer_rejects_non_book():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        path = Path(f.name)
    try:
        path.write_bytes(b"%PDF")
        assert (
            infer_completion_date_from_drive_modified(
                f"/DaydreamEdu/completion/x/P5/Exam/{path.name}",
                doc_type="exam",
            )
            is None
        )
    finally:
        path.unlink(missing_ok=True)


def test_set_drive_modified_on_book_completion():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            mgr.ensure_student("winston", "Winston")
            pdf_path = (
                root
                / "DaydreamEdu"
                / "completion"
                / "Singapore Primary English"
                / "winston@x.com"
                / "P5"
                / "Book"
                / "EPO_Grammar_01"
                / "_c_unit.pdf"
            )
            pdf_path.parent.mkdir(parents=True, exist_ok=True)
            pdf_path.write_bytes(b"%PDF-1.0\n")
            epoch = datetime(2025, 3, 10, 0, 0, tzinfo=timezone.utc).timestamp()
            os.utime(pdf_path, (epoch, epoch))

            reg = mgr.register_file(
                pdf_path,
                file_type="main",
                doc_type="book",
                student_id="winston",
                subject="english",
                is_template=False,
            )
            inferred = infer_completion_date_from_drive_modified(
                pdf_path, doc_type="book"
            )
            assert inferred is not None
            row = mgr.set_completion_date(
                reg.id,
                inferred.completion_date,
                source="drive_modified",
                confidence="medium",
                source_detail=inferred.source_detail,
            )
            assert row.source == "drive_modified"
            assert row.completion_date == "2025-03-10"
    finally:
        Path(db_path).unlink(missing_ok=True)
