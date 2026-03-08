# Path-based inference (_infer_from_path and application during scan). See ARCHITECTURE.md.

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import pytest

_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))
from conftest import FIXTURE_ROOT, fixture_has_pdfs
from pdf_file_manager import PdfFileManager


def test_infer_from_path_science_exam_p5():
    """Path with Singapore Primary Science / ... / P5 / Exam infers subject=science, doc_type=exam, grade_or_scope=P5."""
    path = Path("/fake/DaydreamEdu/Singapore Primary Science/winston@mail.com/P5/Exam/paper.pdf")
    out = PdfFileManager._infer_from_path(path)
    assert out.get("subject") == "science"
    assert out.get("doc_type") == "exam"
    meta = out.get("metadata") or {}
    assert meta.get("content_folder") == "Exam"
    assert meta.get("grade_or_scope") == "P5"


def test_infer_from_path_english_exercise():
    """Path with English and Exercise infers subject=english, doc_type=worksheet."""
    path = Path("/fake/Singapore Primary English/P6/Exercise/sheet.pdf")
    out = PdfFileManager._infer_from_path(path)
    assert out.get("subject") == "english"
    assert out.get("doc_type") == "worksheet"
    meta = out.get("metadata") or {}
    assert meta.get("content_folder") == "Exercise"


def test_infer_from_path_math_activity():
    """Path with Math and Activity infers subject=math, doc_type=activity."""
    path = Path("/fake/Singapore Primary Math/PSLE/Activity/task.pdf")
    out = PdfFileManager._infer_from_path(path)
    assert out.get("subject") == "math"
    assert out.get("doc_type") == "activity"
    meta = out.get("metadata") or {}
    assert meta.get("grade_or_scope") == "PSLE"


def test_infer_from_path_chinese_note():
    """Path with Chinese and Note infers subject=chinese, doc_type=notes."""
    path = Path("/fake/Singapore Primary Chinese/P4/Note/notes.pdf")
    out = PdfFileManager._infer_from_path(path)
    assert out.get("subject") == "chinese"
    assert out.get("doc_type") == "notes"
    meta = out.get("metadata") or {}
    assert meta.get("grade_or_scope") == "P4"


def test_infer_from_path_no_matching_segments_returns_empty():
    """Path with no subject or content folder segments returns empty or minimal dict."""
    path = Path("/some/other/folder/file.pdf")
    out = PdfFileManager._infer_from_path(path)
    assert "subject" not in out or out.get("subject") is None
    assert "doc_type" not in out or out.get("doc_type") is None


def test_scan_applies_inference_to_new_files():
    """After scan (without dry_run), main files under DaydreamEdu/Science/.../Exam get subject and doc_type set."""
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        # Use fixture layout: .../Singapore Primary Science/.../P5/Exam/...
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        root = str(tmpdir)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_student("w", "W")
            mgr.add_scan_root(root, student_id="w")
            results = mgr.scan_for_new_files(dry_run=False, min_savings_pct=0)
            conn = sqlite3.connect(db_path)
            # At least one main file should have subject and doc_type from path inference
            rows = conn.execute(
                "SELECT id, path, subject, doc_type FROM pdf_files WHERE file_type = 'main'"
            ).fetchall()
            conn.close()
            assert len(rows) >= 1
            # Fixture is under Singapore Primary Science/.../P5/Exam so we expect inference
            with_inference = [r for r in rows if r[2] and r[3] and r[2] != "unknown" and r[3] != "unknown"]
            assert len(with_inference) >= 1, "Expected at least one main file with subject and doc_type inferred from path"
            for r in with_inference:
                assert r[2] == "science"
                assert r[3] == "exam"
        finally:
            Path(db_path).unlink(missing_ok=True)
