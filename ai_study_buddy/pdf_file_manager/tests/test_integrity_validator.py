import json
import subprocess
import sys
import tempfile
from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

from .constants import STUDENT_DISPLAY_NAME, STUDENT_FOLDER_EMAIL


def test_integrity_validator_reports_known_issue_types():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        db_path = tmpdir / "registry.db"
        mgr = PdfFileManager(db_path=str(db_path))
        mgr.add_student("winston", STUDENT_DISPLAY_NAME, STUDENT_FOLDER_EMAIL)

        student_pdf = (
            tmpdir
            / "DaydreamEdu"
            / "Singapore Primary English"
            / STUDENT_FOLDER_EMAIL
            / "P6"
            / "Exam"
            / "student.pdf"
        )
        student_pdf.parent.mkdir(parents=True, exist_ok=True)
        student_pdf.write_bytes(b"%PDF-1.0\n")
        student_file = mgr.register_file(student_pdf, doc_type="exam", subject="english", is_template=False)
        mgr._get_connection().execute("UPDATE pdf_files SET student_id = NULL WHERE id = ?", (student_file.id,))
        mgr._get_connection().commit()

        missing_disk_pdf = tmpdir / "missing_on_disk.pdf"
        missing_disk_pdf.write_bytes(b"%PDF-1.0\n")
        missing_disk_reg = mgr.register_file(missing_disk_pdf, file_type="main", doc_type="note")
        Path(missing_disk_reg.path).unlink(missing_ok=True)

        general_non_template_pdf = (
            tmpdir
            / "DaydreamEdu"
            / "Singapore Primary Science"
            / "P6"
            / "Exam"
            / "general_non_template.pdf"
        )
        general_non_template_pdf.parent.mkdir(parents=True, exist_ok=True)
        general_non_template_pdf.write_bytes(b"%PDF-1.0\n")
        mgr.register_file(
            general_non_template_pdf,
            file_type="main",
            doc_type="exam",
            subject="science",
            is_template=False,
        )

        student_template_pdf = (
            tmpdir
            / "DaydreamEdu"
            / "Singapore Primary Math"
            / STUDENT_FOLDER_EMAIL
            / "P6"
            / "Book"
            / "Template Mirrors"
            / "student_template.pdf"
        )
        student_template_pdf.parent.mkdir(parents=True, exist_ok=True)
        student_template_pdf.write_bytes(b"%PDF-1.0\n")
        mgr.register_file(
            student_template_pdf,
            file_type="main",
            doc_type="book",
            subject="math",
            is_template=True,
            metadata={"unit": "student-template-unit"},
        )

        general_book_folder = (
            tmpdir
            / "DaydreamEdu"
            / "Singapore Primary English"
            / "P6"
            / "Book"
            / "Health Book"
        )
        general_book_folder.mkdir(parents=True, exist_ok=True)
        book_file_ok = general_book_folder / "health_book_unit_01.pdf"
        book_file_ok.write_bytes(b"%PDF-1.0\n")
        book_file_missing_unit = general_book_folder / "health_book_unit_02.pdf"
        book_file_missing_unit.write_bytes(b"%PDF-1.0\n")
        book_reg_ok = mgr.register_file(
            book_file_ok,
            file_type="main",
            doc_type="book",
            subject="english",
            is_template=True,
            metadata={"unit": "health_book_unit_01"},
        )
        mgr.register_file(
            book_file_missing_unit,
            file_type="main",
            doc_type="book",
            subject="english",
            is_template=True,
            metadata={},
        )
        book_group = mgr.create_file_group("Health Book", group_type="book")
        mgr.add_to_file_group(book_group.id, book_reg_ok.id)

        pair_pdf = tmpdir / "pair.pdf"
        pair_pdf.write_bytes(b"%PDF-1.0\n")
        reg = mgr.register_file(pair_pdf)
        conn = mgr._get_connection()
        raw_id = "raw-1"
        main_id = "main-1"
        now = "2026-01-01T00:00:00Z"
        (tmpdir / "_raw_pair.pdf").write_bytes(b"%PDF-1.0\n")
        (tmpdir / "_c_pair.pdf").write_bytes(b"%PDF-1.0\n")
        conn.execute("DELETE FROM pdf_files WHERE id = ?", (reg.id,))
        conn.execute(
            """INSERT INTO pdf_files (
                id, name, path, file_type, doc_type, student_id, subject, is_template,
                size_bytes, page_count, has_raw, metadata, added_at, updated_at, notes
            ) VALUES (?, ?, ?, 'raw', 'exam', NULL, 'math', 0, 1, 1, 0, ?, ?, ?, NULL)""",
            (raw_id, "_raw_pair.pdf", str((tmpdir / "_raw_pair.pdf").resolve()), json.dumps({"grade_or_scope": "P6"}), now, now),
        )
        conn.execute(
            """INSERT INTO pdf_files (
                id, name, path, file_type, doc_type, student_id, subject, is_template,
                size_bytes, page_count, has_raw, metadata, added_at, updated_at, notes
            ) VALUES (?, ?, ?, 'main', 'exam', NULL, 'math', 1, 1, 1, 1, ?, ?, ?, NULL)""",
            (main_id, "_c_pair.pdf", str((tmpdir / "_c_pair.pdf").resolve()), json.dumps({"grade_or_scope": "P6"}), now, now),
        )
        conn.execute(
            "INSERT INTO file_relations (id, source_id, target_id, relation_type, created_at) VALUES (?, ?, ?, 'main_version', ?)",
            ("rel-1", raw_id, main_id, now),
        )
        conn.execute(
            "INSERT INTO file_relations (id, source_id, target_id, relation_type, created_at) VALUES (?, ?, ?, 'raw_source', ?)",
            ("rel-2", main_id, raw_id, now),
        )
        conn.commit()

        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity",
                "--db",
                str(db_path),
                "--json",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert proc.returncode == 1
        payload = json.loads(proc.stdout)
        assert payload["summary"]["missing_on_disk_files"] == 1
        assert payload["summary"]["book_folder_group_unit_issues"] == 1
        assert payload["summary"]["student_scope_missing_student_id"] == 1
        assert payload["summary"]["general_scope_non_template"] == 1
        assert payload["summary"]["student_scope_template_true"] == 1
        assert payload["summary"]["missing_student_id"] == 1
        assert payload["summary"]["main_raw_metadata_drift"] == 1
