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

        unknown_pdf = tmpdir / "unknown.pdf"
        unknown_pdf.write_bytes(b"%PDF-1.0\n")
        unknown = mgr.register_file(unknown_pdf)

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

        pair_pdf = tmpdir / "pair.pdf"
        pair_pdf.write_bytes(b"%PDF-1.0\n")
        reg = mgr.register_file(pair_pdf)
        conn = mgr._get_connection()
        raw_id = "raw-1"
        main_id = "main-1"
        now = "2026-01-01T00:00:00Z"
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
        assert payload["summary"]["unknown_doc_type"] == 1
        assert payload["summary"]["missing_student_id"] == 1
        assert payload["summary"]["main_raw_metadata_drift"] == 1
