import subprocess
import sys
import tempfile
from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def test_infer_completion_dates_cli_dry_run(tmp_path: Path) -> None:
    """Smoke-test the infer_completion_dates CLI in dry-run mode."""
    # Prepare a tiny registry with one completion.
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)
    try:
        mgr = PdfFileManager(db_path=db_path)
        mgr.add_student("winston", "Winston")
        dd = tmp_path / "DaydreamEdu" / "completion" / "Singapore Primary English"
        dd.mkdir(parents=True, exist_ok=True)
        p = dd / "winston.ry.meng@gmail.com" / "P5" / "Exercise"
        p.mkdir(parents=True, exist_ok=True)
        pdf = p / "_c_stub.pdf"
        pdf.write_bytes(b"%PDF-1.0\n")
        mgr.register_file(
            pdf,
            file_type="main",
            doc_type="exercise",
            student_id="winston",
            is_template=False,
        )

        # Run the CLI in dry-run mode; it should succeed and print a summary.
        cmd = [
            sys.executable,
            "-m",
            "ai_study_buddy.pdf_file_manager.scripts.infer_completion_dates",
            "--db",
            str(db_path),
            "--root",
            "d_root",
            "--dry-run",
        ]
        proc = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
        )
        assert proc.returncode == 0
        assert "completion_date inference report" in proc.stdout
    finally:
        db_path.unlink(missing_ok=True)

