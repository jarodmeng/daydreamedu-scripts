import json
import tempfile
from pathlib import Path

import pytest

from ai_study_buddy.pdf_file_manager.completion_date.page1 import (
    REASON_NO_DATE_PAGES_1_AND_2,
    apply_page1_inspection_result,
    inventory_root_from_path,
    list_d_root_page1_cohort,
    merge_page_inspection_payloads,
    parse_page1_inspection_payload,
    prepare_page1_batch,
    read_batch_manifest,
    render_page1_png,
    save_page1_inspection_result,
)
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def _make_pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.0\n")
    return path


def _register_d_root_completion(
    mgr: PdfFileManager, root: Path, name: str, doc_type: str = "exercise"
) -> str:
    mgr.ensure_student("winston", "Winston")
    daydream = root / "DaydreamEdu" / "completion" / "Singapore Primary English"
    daydream.mkdir(parents=True, exist_ok=True)
    pdf_path = daydream / "winston.ry.meng@gmail.com" / "P5" / "Exercise"
    pdf_path.mkdir(parents=True, exist_ok=True)
    record = mgr.register_file(
        _make_pdf(pdf_path / name),
        file_type="main",
        doc_type=doc_type,
        student_id="winston",
        subject="english",
        is_template=False,
    )
    return record.id


def test_inventory_root_from_path():
    assert inventory_root_from_path("/x/DaydreamEdu/completion/a.pdf") == "d_root"
    assert inventory_root_from_path("/x/GoodNotes/student/a.pdf") == "g_root"
    assert inventory_root_from_path("/tmp/other.pdf") == "unknown"


def test_parse_and_apply_page1_result():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            file_id = _register_d_root_completion(mgr, root, "_c_practice.pdf")

            parsed = parse_page1_inspection_payload(
                {
                    "file_id": file_id,
                    "completion_date": "2025-10-22",
                    "confidence": "high",
                    "inference_model": "gpt-5.4-medium",
                    "source_detail": {
                        "page_index": 0,
                        "timezone": "Asia/Singapore",
                        "evidence": "Date: 22nd Oct 2025",
                    },
                }
            )
            row = apply_page1_inspection_result(mgr, parsed)
            assert row is not None
            assert row.completion_date == "2025-10-22"
            assert row.source == "handwritten_page1"
            assert row.confidence == "high"
            assert row.inference_model == "gpt-5.4-medium"

            null_parsed = parse_page1_inspection_payload(
                {
                    "file_id": file_id,
                    "completion_date": None,
                    "confidence": None,
                    "source_detail": {"reason": "no_date_on_page_1"},
                }
            )
            assert apply_page1_inspection_result(mgr, null_parsed) is None

            bad_year = parse_page1_inspection_payload(
                {
                    "file_id": file_id,
                    "completion_date": "2022-02-14",
                    "confidence": "medium",
                    "inference_model": "gpt-5.4-medium",
                    "source_detail": {"page_index": 1},
                }
            )
            assert apply_page1_inspection_result(mgr, bad_year) is None
            assert mgr.get_completion_date(file_id).completion_date == "2025-10-22"
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_cohort_orders_book_last_and_skips_g_root():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            exercise_id = _register_d_root_completion(mgr, root, "_c_ex.pdf", "exercise")
            book_id = _register_d_root_completion(mgr, root, "_c_unit.pdf", "book")

            gn = root / "GoodNotes" / "winston" / "P5" / "Exam"
            gn.mkdir(parents=True, exist_ok=True)
            mgr.register_file(
                _make_pdf(gn / "_c_gn.pdf"),
                file_type="main",
                doc_type="exam",
                student_id="winston",
                is_template=False,
            )

            cohort = list_d_root_page1_cohort(mgr, skip_doc_types=frozenset())
            ids = [f.id for f in cohort]
            assert ids == [exercise_id, book_id]
            assert cohort[0].doc_type == "exercise"
            assert cohort[1].doc_type == "book"
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_prepare_batch_manifest_and_render(monkeypatch):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            work_dir = root / "work"
            mgr = PdfFileManager(db_path=db_path)
            file_id = _register_d_root_completion(mgr, root, "_c_one.pdf")

            fake_png = work_dir / "images" / file_id / "page-01.png"

            def _fake_render(pdf_path, out_path, *, page_index=0, dpi_scale=2.0):
                Path(out_path).parent.mkdir(parents=True, exist_ok=True)
                Path(out_path).write_bytes(b"\x89PNG\r\n\x1a\n")
                return Path(out_path)

            monkeypatch.setattr(
                "ai_study_buddy.pdf_file_manager.completion_date.page1.render_page_png",
                _fake_render,
            )
            monkeypatch.setattr(
                "ai_study_buddy.pdf_file_manager.completion_date.page1.pdf_page_count",
                lambda _path: 1,
            )

            manifest = prepare_page1_batch(mgr, work_dir, limit=1)
            assert manifest.counts["total"] == 1
            assert manifest.items[0].slice == "priority"
            assert fake_png.is_file()

            roundtrip = read_batch_manifest(work_dir)
            assert roundtrip.counts == manifest.counts
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_merge_page_inspection_prefers_page1_then_page2():
    fid = "3966d6d8-1e61-420b-ac5f-97f9ab740c2f"
    page1_null = {
        "file_id": fid,
        "completion_date": None,
        "confidence": None,
        "inference_model": None,
        "source_detail": {"reason": "no_date_on_page_1"},
    }
    page2_dated = {
        "file_id": fid,
        "completion_date": "2026-02-15",
        "confidence": "high",
        "inference_model": "gpt-5.4-medium",
        "source_detail": {"evidence": "Date: 15 Feb 2026"},
    }
    merged = merge_page_inspection_payloads(fid, page1_null, page2_dated)
    assert merged["completion_date"] == "2026-02-15"
    assert merged["source_detail"]["page_index"] == 1

    page1_dated = {
        "file_id": fid,
        "completion_date": "2025-10-22",
        "confidence": "high",
        "inference_model": "gpt-5.4-medium",
        "source_detail": {"page_index": 0, "evidence": "Date: 22 Oct 2025"},
    }
    assert merge_page_inspection_payloads(fid, page1_dated, page2_dated)["completion_date"] == "2025-10-22"

    page2_null = {
        "file_id": fid,
        "completion_date": None,
        "confidence": None,
        "inference_model": None,
        "source_detail": {"reason": "no_date_on_page_1"},
    }
    both_null = merge_page_inspection_payloads(fid, page1_null, page2_null)
    assert both_null["completion_date"] is None
    assert both_null["source_detail"]["reason"] == REASON_NO_DATE_PAGES_1_AND_2


def test_save_page1_inspection_result_roundtrip():
    with tempfile.TemporaryDirectory() as tmpdir:
        work_dir = Path(tmpdir)
        payload = {
            "file_id": "abc-123",
            "completion_date": "2025-01-15",
            "confidence": "medium",
            "inference_model": "composer-2.5-fast",
            "source_detail": {"timezone": "Asia/Singapore"},
        }
        out = save_page1_inspection_result(work_dir, payload)
        assert out.is_file()
        loaded = json.loads(out.read_text(encoding="utf-8"))
        assert loaded["completion_date"] == "2025-01-15"


def test_render_page1_png_requires_pymupdf():
    with tempfile.TemporaryDirectory() as tmpdir:
        pdf = Path(tmpdir) / "doc.pdf"
        out = Path(tmpdir) / "page-01.png"
        _make_pdf(pdf)
        try:
            render_page1_png(pdf, out)
        except RuntimeError as exc:
            pytest.skip(f"PyMuPDF not available: {exc}")
        assert out.is_file()
        assert out.stat().st_size > 0


def test_infer_without_cached_result_returns_none():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = PdfFileManager(db_path=db_path)
            file_id = _register_d_root_completion(mgr, Path(tmpdir), "_c_x.pdf")
            assert mgr.infer_completion_date_for_file(file_id) is None
    finally:
        Path(db_path).unlink(missing_ok=True)
