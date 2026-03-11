# compress_and_register. See TESTING.md § Phase 2 (compress_and_register).

import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path

import numpy as np
import pymupdf
import pytest
from PIL import Image

_tests_dir = Path(__file__).resolve().parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))
from conftest import FIXTURE_ROOT, fixture_has_pdfs
from pdf_file_manager import PdfFileManager


def _make_image_plus_text_pdf(path: Path) -> Path:
    img_path = path.with_suffix(".png")
    Image.new("RGB", (1200, 1700), "white").save(img_path)
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    page.insert_image(page.rect, filename=str(img_path))
    page.insert_text((72, 120), "Overlay text should survive compression", fontsize=24)
    doc.save(str(path))
    doc.close()
    img_path.unlink(missing_ok=True)
    return path


def test_compress_and_register_with_unregistered_path():
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        path = pdfs[0]
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            result = mgr.compress_and_register(path, min_savings_pct=0)
            conn = sqlite3.connect(db_path)
            main_rows = conn.execute("SELECT file_type, has_raw FROM pdf_files WHERE file_type = 'main'").fetchall()
            assert len(main_rows) >= 1
            log_register = conn.execute("SELECT 1 FROM operation_log WHERE operation = 'register'").fetchall()
            log_compress = conn.execute("SELECT 1 FROM operation_log WHERE operation = 'compress'").fetchall()
            assert len(log_register) >= 1 and len(log_compress) >= 1
            conn.close()
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_compress_and_register_already_main_raises():
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        path = pdfs[0]
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            result = mgr.compress_and_register(path, min_savings_pct=0)
            main_file = mgr.get_file(result.main_file_id)
            with pytest.raises(ValueError):
                mgr.compress_and_register(main_file.path)
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_compress_and_register_preserve_input_creates_raw_and_main():
    """preserve_input=True should keep the original as raw and create a new _c_ main without renaming/moving the source file."""
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        shutil.copytree(FIXTURE_ROOT, tmpdir / "fixture", dirs_exist_ok=True)
        pdfs = list((tmpdir / "fixture").rglob("*.pdf"))
        path = pdfs[0]
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            # Register as unknown first (normal scanned state)
            reg = mgr.register_file(path)
            assert reg.file_type == "unknown"
            # Run GoodNotes-safe variant
            result = mgr.compress_and_register(path, min_savings_pct=0, preserve_input=True)
            main_file = mgr.get_file(result.main_file_id)
            raw_file = mgr.get_file(result.raw_archive_id) if result.raw_archive_id else None
            # Original path should still exist on disk and be the raw record
            assert path.exists()
            assert raw_file is not None
            assert Path(raw_file.path).resolve() == path.resolve()
            assert raw_file.file_type == "raw"
            # Main file should be the new _c_ copy
            assert main_file is not None
            assert main_file.file_type == "main"
            assert main_file.has_raw
            assert main_file.name.startswith("_c_")
            # Relations should link raw and main
            related = mgr.get_related_files(main_file.id)
            rel_types = {rel_type for _, rel_type in related}
            assert "raw_source" in rel_types or "main_version" in rel_types
        finally:
            Path(db_path).unlink(missing_ok=True)


def test_compress_and_register_preserves_non_image_page_content():
    """Compression should preserve page text/vector overlays, not just the first embedded image."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        path = _make_image_plus_text_pdf(tmpdir / "overlay.pdf")
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False, dir=tmpdir) as f:
            db_path = f.name
        try:
            mgr = PdfFileManager(db_path=db_path)
            result = mgr.compress_and_register(path, min_savings_pct=0, preserve_input=True)
            main_file = mgr.get_file(result.main_file_id)
            assert main_file is not None

            doc = pymupdf.open(main_file.path)
            pix = doc[0].get_pixmap(alpha=False)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
            doc.close()

            assert np.array(img).min() < 250
        finally:
            Path(db_path).unlink(missing_ok=True)
