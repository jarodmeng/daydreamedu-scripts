from __future__ import annotations

import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from ai_study_buddy.buddy_console.backend.app import app
from ai_study_buddy.buddy_console.backend.inventory_api import (
    InventoryRuntime,
    build_buddy_console_source_detail,
)
from ai_study_buddy.buddy_console.tests.test_inventory_api import _card, _runtime
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def _make_pdf(path: Path) -> None:
    path.write_bytes(b"%PDF-1.0\n")


def _register_completion(mgr: PdfFileManager, path: Path, *, student_id: str = "emma") -> str:
    mgr.add_student(student_id, student_id.title())
    record = mgr.register_file(
        path,
        file_type="main",
        doc_type="exam",
        student_id=student_id,
        subject="math",
        is_template=False,
    )
    return record.id


def test_build_buddy_console_source_detail_includes_previous_on_overwrite() -> None:
    from ai_study_buddy.pdf_file_manager.completion_date import CompletionDateRecord

    existing = CompletionDateRecord(
        file_id="x",
        completion_date="2026-01-01",
        source="filename_term",
        confidence="medium",
        inference_model=None,
        source_detail=None,
        inferred_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
    )
    detail = build_buddy_console_source_detail(existing)
    assert detail["set_via"] == "buddy_console"
    assert detail["previous_completion_date"] == "2026-01-01"
    assert detail["previous_source"] == "filename_term"
    assert detail["previous_confidence"] == "medium"


def test_patch_completion_date_sets_manual_row(monkeypatch, tmp_path: Path) -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tdir:
            root = Path(tdir)
            pdf_path = root / "_c_exam.pdf"
            _make_pdf(pdf_path)
            mgr = PdfFileManager(db_path=db_path)
            file_id = _register_completion(mgr, pdf_path)

            monkeypatch.setenv("PDF_REGISTRY_PATH", db_path)
            runtime = _runtime(tmp_path)
            runtime.enriched_cache = [
                _card(tmp_path / "goodnotes" / "Math" / "emma" / "P4" / "registered.pdf")
            ]
            runtime.enriched_cache[0].registry_file_id = file_id
            app.state.inventory_runtime = runtime

            client = TestClient(app)
            response = client.patch(
                f"/api/inventory/items/{file_id}/completion-date",
                json={"completion_date": "2026-03-15"},
            )
            assert response.status_code == 200
            payload = response.json()
            assert payload == {
                "registry_file_id": file_id,
                "completion_date": "2026-03-15",
                "completion_date_source": "manual",
            }

            row = mgr.get_completion_date(file_id)
            assert row is not None
            assert row.completion_date == "2026-03-15"
            assert row.source == "manual"
            assert row.source_detail is not None
            assert row.source_detail.get("set_via") == "buddy_console"

            assert runtime.enriched_cache is None

            logs = mgr.get_operation_log(file_id=file_id, operation="set_completion_date")
            assert len(logs) == 1
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_patch_completion_date_overwrite_logs_before_state(monkeypatch, tmp_path: Path) -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tdir:
            root = Path(tdir)
            pdf_path = root / "_c_exam2.pdf"
            _make_pdf(pdf_path)
            mgr = PdfFileManager(db_path=db_path)
            file_id = _register_completion(mgr, pdf_path)
            mgr.set_completion_date(
                file_id,
                "2026-01-01",
                source="filename_term",
                confidence="medium",
            )

            monkeypatch.setenv("PDF_REGISTRY_PATH", db_path)
            app.state.inventory_runtime = _runtime(tmp_path)

            client = TestClient(app)
            response = client.patch(
                f"/api/inventory/items/{file_id}/completion-date",
                json={"completion_date": "2026-06-01"},
            )
            assert response.status_code == 200

            row = mgr.get_completion_date(file_id)
            assert row is not None
            assert row.source_detail is not None
            assert row.source_detail["previous_source"] == "filename_term"

            logs = mgr.get_operation_log(file_id=file_id, operation="set_completion_date")
            assert len(logs) == 2
            assert logs[-1].before_state is not None
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_patch_completion_date_404_and_400(monkeypatch, tmp_path: Path) -> None:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tdir:
            root = Path(tdir)
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_student("emma", "Emma")
            tpl_path = root / "tpl.pdf"
            _make_pdf(tpl_path)
            template_id = mgr.register_file(
                tpl_path,
                file_type="main",
                doc_type="exam",
                student_id="emma",
                is_template=True,
            ).id
            ok_path = root / "_c_ok.pdf"
            _make_pdf(ok_path)
            completion_id = mgr.register_file(
                ok_path,
                file_type="main",
                doc_type="exam",
                student_id="emma",
                subject="math",
                is_template=False,
            ).id

            monkeypatch.setenv("PDF_REGISTRY_PATH", db_path)
            app.state.inventory_runtime = _runtime(tmp_path)
            client = TestClient(app)

            missing = client.patch(
                "/api/inventory/items/does-not-exist/completion-date",
                json={"completion_date": "2026-03-15"},
            )
            assert missing.status_code == 404

            template = client.patch(
                f"/api/inventory/items/{template_id}/completion-date",
                json={"completion_date": "2026-03-15"},
            )
            assert template.status_code == 400

            bad_date = client.patch(
                f"/api/inventory/items/{completion_id}/completion-date",
                json={"completion_date": "not-a-date"},
            )
            assert bad_date.status_code == 400
    finally:
        Path(db_path).unlink(missing_ok=True)
