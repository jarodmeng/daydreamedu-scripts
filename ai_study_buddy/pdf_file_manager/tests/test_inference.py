# Path-based inference (_infer_from_path and application during scan). See ARCHITECTURE.md.

import json
import shutil
import sqlite3
import tempfile
from pathlib import Path

import pytest

from ai_study_buddy.pdf_file_manager.pdf_file_manager import InvalidMetadataError, PdfFileManager

from .conftest import FIXTURE_ROOT, fixture_has_pdfs
from .constants import STUDENT_DISPLAY_NAME, STUDENT_FOLDER_EMAIL


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


def test_infer_from_path_chinese_book_sets_book_doc_type_and_unit():
    path = Path(
        "/fake/DaydreamEdu/Singapore Primary Chinese/PSLE/Book/Power Pack Chinese PSLE/_c_PP Chinese 模拟考卷 3.pdf"
    )
    out = PdfFileManager._infer_from_path(path)
    assert out.get("subject") == "chinese"
    assert out.get("doc_type") == "book"
    assert out.get("is_template") is True
    meta = out.get("metadata") or {}
    assert meta.get("content_folder") == "Book"
    assert meta.get("grade_or_scope") == "PSLE"
    assert meta.get("unit") == "模拟考卷 3"


def test_infer_from_path_chinese_book_handles_non_numbered_unit():
    path = Path(
        "/fake/DaydreamEdu/Singapore Primary Chinese/PSLE/Book/Power Pack Chinese PSLE/PP Chinese 试卷蓝图与复习指南.pdf"
    )
    out = PdfFileManager._infer_from_path(path)
    assert out.get("doc_type") == "book"
    meta = out.get("metadata") or {}
    assert meta.get("unit") == "试卷蓝图与复习指南"


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
    path = Path(
        f"/Drive/DaydreamEdu/Singapore Primary Math/{STUDENT_FOLDER_EMAIL}/P6/Exam/paper.pdf"
    )
    out = PdfFileManager._infer_from_path(path)
    assert out.get("is_template") is False


def test_path_has_student_mirror_layout_matches_inference_rule():
    assert PdfFileManager._path_has_student_mirror_layout(
        Path("/fake/DaydreamEdu/Singapore Primary Math/P5/Book/Power Pack Math P5")
    ) is False
    assert PdfFileManager._path_has_student_mirror_layout(
        Path("/fake/DaydreamEdu/Singapore Primary Math/user@example.com/P5/Book/Power Pack Math P5")
    ) is True
    assert PdfFileManager._path_has_student_mirror_layout(
        Path("/Users/dev/GoogleDrive-owner@example.com/My Drive/DaydreamEdu/Singapore Primary Math/P6/Exam")
    ) is False


def test_register_file_infers_student_id_from_registered_student_email_folder():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        pdf_path = (
            tmpdir
            / "DaydreamEdu"
            / "Singapore Primary Science"
            / STUDENT_FOLDER_EMAIL
            / "P5"
            / "Exam"
            / "paper.pdf"
        )
        pdf_path.parent.mkdir(parents=True, exist_ok=True)
        pdf_path.write_bytes(b"pdf")
        db_path = tmpdir / "registry.db"
        mgr = PdfFileManager(db_path=str(db_path))
        mgr.add_student("winston", STUDENT_DISPLAY_NAME, STUDENT_FOLDER_EMAIL)

        registered = mgr.register_file(pdf_path)
        assert registered.student_id == "winston"


def test_infer_from_path_is_template_true_when_at_in_drive_segment_only():
    """Path with @ in a non-student segment (e.g. GoogleDrive-user@gmail.com) and P6 in path → is_template=True.
    Student folder = @ segment immediately followed by grade/scope (P3–P6, PSLE, Archive)."""
    path = Path(
        "/Users/dev/Library/CloudStorage/GoogleDrive-owner@example.com/My Drive/DaydreamEdu/Singapore Primary Math/P6/Exam/paper.pdf"
    )
    out = PdfFileManager._infer_from_path(path)
    assert out.get("is_template") is True
    assert out.get("metadata", {}).get("grade_or_scope") == "P6"


def test_infer_from_path_sets_chinese_variant_standard_for_chinese_exam():
    """Chinese exam filename with 华文/.chinese. sets metadata.chinese_variant='standard'."""
    path = Path(
        "/fake/DaydreamEdu/Singapore Primary Chinese/P6/Exam/华文 期末考试 (题目).p5.chinese.013.pdf"
    )
    out = PdfFileManager._infer_from_path(path)
    assert out.get("subject") == "chinese"
    assert out.get("doc_type") == "exam"
    meta = out.get("metadata") or {}
    assert meta.get("chinese_variant") == "standard"


def test_infer_from_path_sets_chinese_variant_higher_for_chinese_exam():
    """Chinese exam filename with 高华/.hc. sets metadata.chinese_variant='higher'."""
    path = Path(
        "/fake/DaydreamEdu/Singapore Primary Chinese/P6/Exam/高华 期末考试 (题目).p5.chinese.044.pdf"
    )
    out = PdfFileManager._infer_from_path(path)
    assert out.get("subject") == "chinese"
    assert out.get("doc_type") == "exam"
    meta = out.get("metadata") or {}
    assert meta.get("chinese_variant") == "higher"


def test_register_file_rejects_invalid_chinese_variant_foundation():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        pdf_path = tmpdir / "x.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")
        db_path = tmpdir / "registry.db"
        mgr = PdfFileManager(db_path=str(db_path))
        mgr.add_student("s", "S")
        with pytest.raises(InvalidMetadataError, match="foundation"):
            mgr.register_file(
                pdf_path,
                file_type="main",
                student_id="s",
                subject="chinese",
                doc_type="exam",
                metadata={"chinese_variant": "foundation"},
            )


def test_get_file_raises_when_stored_metadata_has_chinese_variant_foundation():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        pdf_path = tmpdir / "x.pdf"
        pdf_path.write_bytes(b"%PDF-1.4")
        db_path = tmpdir / "registry.db"
        mgr = PdfFileManager(db_path=str(db_path))
        mgr.add_student("s", "S")
        registered = mgr.register_file(
            pdf_path,
            file_type="main",
            student_id="s",
            subject="chinese",
            doc_type="exam",
            metadata={"chinese_variant": "standard"},
        )
        mgr._get_connection().execute(
            "UPDATE pdf_files SET metadata = ? WHERE id = ?",
            (json.dumps({"chinese_variant": "foundation"}), registered.id),
        )
        mgr._get_connection().commit()
        with pytest.raises(InvalidMetadataError, match="foundation"):
            mgr.get_file(registered.id)


def test_infer_from_path_does_not_set_chinese_variant_for_non_exam():
    """Chinese non-exam (e.g. Exercise) should not set chinese_variant even if name has 华文/高华."""
    path = Path(
        "/fake/DaydreamEdu/Singapore Primary Chinese/P6/Exercise/华文 补充练习一.p5.chinese.001.pdf"
    )
    out = PdfFileManager._infer_from_path(path)
    assert out.get("subject") == "chinese"
    assert out.get("doc_type") == "worksheet"
    meta = out.get("metadata") or {}
    assert "chinese_variant" not in meta


def test_scan_applies_inference_to_new_files():
    """After scan (without dry_run), main files under DaydreamEdu/Science/.../Exam get subject and doc_type set."""
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        # Use fixture layout: .../Singapore Primary Science/.../P5/Exam/...
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        science = tmpdir / "fixture" / "Singapore Primary Science"
        student_dirs = [p for p in science.iterdir() if p.is_dir() and "@" in p.name]
        assert student_dirs, (
            "Fixture needs Singapore Primary Science/<email-shaped folder>/P5/Exam "
            "(see tests/fixtures/daydreamedu_fixture/README.md)"
        )
        # scan_for_new_files only considers direct *.pdf children of the root
        root = str(student_dirs[0] / "P5" / "Exam")
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
            # Fixture is under .../Singapore Primary Science/<email-shaped>/P5/Exam → has @ so is_template=False
            with_inference = [r for r in rows if r[2] and r[3] and r[2] != "unknown" and r[3] != "unknown"]
            assert len(with_inference) >= 1, "Expected at least one main file with subject and doc_type inferred from path"
            for r in with_inference:
                assert r[2] == "science"
                assert r[3] == "exam"
                assert r[4] == 0, (
                    "Expected is_template=0 (path contains student-scoped email folder segment)"
                )
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
        root = str(exam_dir)
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


def test_scan_book_folder_applies_book_inference_and_grouping():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        book_dir = tmpdir / "Singapore Primary Chinese" / "PSLE" / "Book" / "Power Pack Chinese PSLE"
        book_dir.mkdir(parents=True)
        pdf_a = book_dir / "PP Chinese 模拟考卷 3.pdf"
        pdf_b = book_dir / "PP Chinese 试卷蓝图与复习指南.pdf"
        pdf_a.write_bytes(b"%PDF-1.4 fake")
        pdf_b.write_bytes(b"%PDF-1.4 fake")
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)

            def fake_compress_and_register(file_id_or_path, force=False, min_savings_pct=10, preserve_input=False, **compress_kwargs):
                registered = mgr.register_file(file_id_or_path, file_type="main", doc_type="unknown")
                return type("FakeCompressResult", (), {
                    "main_file_id": registered.id,
                    "compressed": False,
                    "raw_archive_id": None,
                })()

            mgr.compress_and_register = fake_compress_and_register  # type: ignore[method-assign]
            mgr.scan_for_new_files(roots=[book_dir], dry_run=False, min_savings_pct=101)
            main_files = mgr.find_files(doc_type="book", file_type="main")
            assert len(main_files) == 2
            units = sorted((file.metadata or {}).get("unit") for file in main_files)
            assert units == ["模拟考卷 3", "试卷蓝图与复习指南"]
            groups = mgr.list_file_groups(group_type="book")
            assert len(groups) == 1
            assert groups[0].label == "Power Pack Chinese PSLE"
            assert len(groups[0].members) == 2
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_ensure_book_group_from_student_folder_returns_none_and_does_not_create_group():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        student_book_dir = (
            tmpdir
            / "Singapore Primary Chinese"
            / "student@example.com"
            / "PSLE"
            / "Book"
            / "Power Pack Chinese PSLE"
        )
        student_book_dir.mkdir(parents=True)
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            group = mgr.ensure_book_group_from_path(student_book_dir)
            assert group is None
            assert mgr.list_file_groups(group_type="book") == []
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_scan_general_and_student_book_same_label_only_keeps_general_templates():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        general_book_dir = tmpdir / "Singapore Primary Chinese" / "PSLE" / "Book" / "Power Pack Chinese PSLE"
        student_book_dir = (
            tmpdir
            / "Singapore Primary Chinese"
            / "student@example.com"
            / "PSLE"
            / "Book"
            / "Power Pack Chinese PSLE"
        )
        general_book_dir.mkdir(parents=True)
        student_book_dir.mkdir(parents=True)
        (general_book_dir / "PP Chinese 模拟考卷 3.pdf").write_bytes(b"%PDF-1.4 fake")
        (student_book_dir / "PP Chinese 模拟考卷 3.pdf").write_bytes(b"%PDF-1.4 fake")
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)

            def fake_compress_and_register(file_id_or_path, force=False, min_savings_pct=10, preserve_input=False, **compress_kwargs):
                registered = mgr.register_file(file_id_or_path, file_type="main", doc_type="unknown")
                return type("FakeCompressResult", (), {
                    "main_file_id": registered.id,
                    "compressed": False,
                    "raw_archive_id": None,
                })()

            mgr.compress_and_register = fake_compress_and_register  # type: ignore[method-assign]
            mgr.scan_for_new_files(roots=[general_book_dir, student_book_dir], dry_run=False, min_savings_pct=101)
            groups = mgr.list_file_groups(group_type="book")
            assert len(groups) == 1
            group = groups[0]
            assert group.label == "Power Pack Chinese PSLE"
            assert len(group.members) == 1
            member = group.members[0].file
            assert member.is_template is True
            assert Path(member.path).resolve().parent == general_book_dir.resolve()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_ensure_book_group_reconciles_membership_to_desired_template_set():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        general_book_dir = tmpdir / "Singapore Primary Chinese" / "PSLE" / "Book" / "Power Pack Chinese PSLE"
        student_book_dir = (
            tmpdir
            / "Singapore Primary Chinese"
            / "student@example.com"
            / "PSLE"
            / "Book"
            / "Power Pack Chinese PSLE"
        )
        other_dir = tmpdir / "Singapore Primary Chinese" / "PSLE" / "Book" / "Other Book"
        general_book_dir.mkdir(parents=True)
        student_book_dir.mkdir(parents=True)
        other_dir.mkdir(parents=True)
        general_template_pdf = general_book_dir / "_c_PP Chinese 模拟考卷 3.pdf"
        student_completion_pdf = student_book_dir / "_c_PP Chinese 模拟考卷 3.pdf"
        wrong_parent_pdf = other_dir / "_c_PP Chinese 模拟考卷 3.pdf"
        for p in (general_template_pdf, student_completion_pdf, wrong_parent_pdf):
            p.write_bytes(b"%PDF-1.4 fake")
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            template_file = mgr.register_file(
                general_template_pdf,
                file_type="main",
                doc_type="book",
                is_template=True,
            )
            student_file = mgr.register_file(
                student_completion_pdf,
                file_type="main",
                doc_type="book",
                is_template=False,
            )
            wrong_parent_file = mgr.register_file(
                wrong_parent_pdf,
                file_type="main",
                doc_type="book",
                is_template=True,
            )
            group = mgr.create_file_group("Power Pack Chinese PSLE", group_type="book")
            mgr.add_to_file_group(group.id, template_file.id)
            mgr.add_to_file_group(group.id, student_file.id)
            mgr.add_to_file_group(group.id, wrong_parent_file.id)

            refreshed = mgr.ensure_book_group_from_path(general_book_dir)
            assert refreshed is not None
            assert {m.file_id for m in refreshed.members} == {template_file.id}
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_scan_registered_unknown_book_file_processes_it_on_rescan():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        book_dir = tmpdir / "Singapore Primary Chinese" / "PSLE" / "Book" / "Power Pack Chinese PSLE"
        book_dir.mkdir(parents=True)
        pdf_path = book_dir / "PP Chinese 作文 范文.pdf"
        pdf_path.write_bytes(b"%PDF-1.4 fake")
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            existing = mgr.register_file(pdf_path, file_type="unknown", doc_type="unknown")

            def fake_compress_and_register(file_id_or_path, force=False, min_savings_pct=10, preserve_input=False, **compress_kwargs):
                mgr._get_connection().execute(
                    "UPDATE pdf_files SET file_type = 'main' WHERE id = ?",
                    (existing.id,),
                )
                mgr._get_connection().commit()
                return type("FakeCompressResult", (), {
                    "main_file_id": existing.id,
                    "compressed": False,
                    "raw_archive_id": None,
                })()

            mgr.compress_and_register = fake_compress_and_register  # type: ignore[method-assign]
            mgr.scan_for_new_files(roots=[book_dir], dry_run=False, min_savings_pct=101)
            refreshed = mgr.get_file(existing.id)
            assert refreshed is not None
            assert refreshed.file_type == "main"
            assert refreshed.doc_type == "book"
            assert (refreshed.metadata or {}).get("unit") == "作文 范文"
        finally:
            Path(db_path).unlink(missing_ok=True)
