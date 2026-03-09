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
    """Path with Singapore Primary Science / ... / P5 / Exam infers subject=science, doc_type=exam, grade_or_scope=P5.
    Path contains email (winston@mail.com) so is_template=False (student-specific).
    """
    path = Path("/fake/DaydreamEdu/Singapore Primary Science/winston@mail.com/P5/Exam/paper.pdf")
    out = PdfFileManager._infer_from_path(path)
    assert out.get("subject") == "science"
    assert out.get("doc_type") == "exam"
    assert out.get("is_template") is False
    meta = out.get("metadata") or {}
    assert meta.get("content_folder") == "Exam"
    assert meta.get("grade_or_scope") == "P5"


def test_infer_from_path_english_exercise():
    """Path with English and Exercise infers subject=english, doc_type=worksheet.
    No email in path, has P6 → general scope → is_template=True."""
    path = Path("/fake/Singapore Primary English/P6/Exercise/sheet.pdf")
    out = PdfFileManager._infer_from_path(path)
    assert out.get("subject") == "english"
    assert out.get("doc_type") == "worksheet"
    assert out.get("is_template") is True
    meta = out.get("metadata") or {}
    assert meta.get("content_folder") == "Exercise"


def test_infer_from_path_math_activity():
    """Path with Math and Activity infers subject=math, doc_type=activity.
    No email, has PSLE → general scope → is_template=True."""
    path = Path("/fake/Singapore Primary Math/PSLE/Activity/task.pdf")
    out = PdfFileManager._infer_from_path(path)
    assert out.get("subject") == "math"
    assert out.get("doc_type") == "activity"
    assert out.get("is_template") is True
    meta = out.get("metadata") or {}
    assert meta.get("grade_or_scope") == "PSLE"


def test_infer_from_path_chinese_note():
    """Path with Chinese and Note infers subject=chinese, doc_type=notes.
    No email, has P4 → general scope → is_template=True."""
    path = Path("/fake/Singapore Primary Chinese/P4/Note/notes.pdf")
    out = PdfFileManager._infer_from_path(path)
    assert out.get("subject") == "chinese"
    assert out.get("doc_type") == "notes"
    assert out.get("is_template") is True
    meta = out.get("metadata") or {}
    assert meta.get("grade_or_scope") == "P4"


def test_infer_from_path_no_matching_segments_returns_empty():
    """Path with no subject or content folder segments returns empty or minimal dict.
    No grade scope → is_template not set."""
    path = Path("/some/other/folder/file.pdf")
    out = PdfFileManager._infer_from_path(path)
    assert "subject" not in out or out.get("subject") is None
    assert "doc_type" not in out or out.get("doc_type") is None
    assert "is_template" not in out


def test_infer_from_path_is_template_true_when_general_scope():
    """Path with P6 (or P5/PSLE etc.) and no email → is_template=True (general scope)."""
    path = Path("/Drive/DaydreamEdu/Singapore Primary Math/P6/Exam/paper.pdf")
    out = PdfFileManager._infer_from_path(path)
    assert out.get("is_template") is True
    assert out.get("metadata", {}).get("grade_or_scope") == "P6"


def test_infer_from_path_is_template_false_when_student_email_in_path():
    """Path containing @ (student email folder) → is_template=False (student-specific)."""
    path = Path("/Drive/DaydreamEdu/Singapore Primary Math/winston.ry.meng@gmail.com/P6/Exam/paper.pdf")
    out = PdfFileManager._infer_from_path(path)
    assert out.get("is_template") is False


def test_infer_from_path_is_template_true_when_at_in_drive_segment_only():
    """Path with @ in a non-student segment (e.g. GoogleDrive-user@gmail.com) and P6 in path → is_template=True.
    Student folder = @ segment immediately followed by grade/scope (P3–P6, PSLE, Archive)."""
    path = Path(
        "/Users/jarodm/Library/CloudStorage/GoogleDrive-genrong.meng@gmail.com/My Drive/DaydreamEdu/Singapore Primary Math/P6/Exam/paper.pdf"
    )
    out = PdfFileManager._infer_from_path(path)
    assert out.get("is_template") is True
    assert out.get("metadata", {}).get("grade_or_scope") == "P6"


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
            # At least one main file should have subject, doc_type, and is_template from path inference
            rows = conn.execute(
                "SELECT id, path, subject, doc_type, is_template FROM pdf_files WHERE file_type = 'main'"
            ).fetchall()
            conn.close()
            assert len(rows) >= 1
            # Fixture is under .../Singapore Primary Science/winston.ry.meng@gmail.com/P5/Exam → has @ so is_template=False
            with_inference = [r for r in rows if r[2] and r[3] and r[2] != "unknown" and r[3] != "unknown"]
            assert len(with_inference) >= 1, "Expected at least one main file with subject and doc_type inferred from path"
            for r in with_inference:
                assert r[2] == "science"
                assert r[3] == "exam"
                assert r[4] == 0, "Expected is_template=0 (path contains student email winston.ry.meng@gmail.com)"
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_scan_applies_is_template_true_when_path_has_no_email():
    """When scan root layout is .../Math/P6/Exam (no email in path), inferred is_template=True is applied."""
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        # Layout without email: Singapore Primary Math / P6 / Exam (general scope)
        exam_dir = tmpdir / "Singapore Primary Math" / "P6" / "Exam"
        exam_dir.mkdir(parents=True)
        pdfs = list(FIXTURE_ROOT.rglob("*.pdf"))
        shutil.copy2(pdfs[0], exam_dir / "sample.pdf")
        root = str(tmpdir)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_scan_root(root, student_id=None)
            mgr.scan_for_new_files(dry_run=False, min_savings_pct=0)
            conn = sqlite3.connect(db_path)
            rows = conn.execute(
                "SELECT path, is_template FROM pdf_files WHERE file_type = 'main'"
            ).fetchall()
            conn.close()
            assert len(rows) >= 1
            for path, is_tmpl in rows:
                if "P6" in path and "Exam" in path and "@" not in path:
                    assert is_tmpl == 1, f"Expected is_template=1 for general-scope path (no @): {path}"
                    break
            else:
                pytest.fail("No main file under P6/Exam without @ in path")
        finally:
            Path(db_path).unlink(missing_ok=True)
