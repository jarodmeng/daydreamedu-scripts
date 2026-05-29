from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from ai_study_buddy import files
from ai_study_buddy.buddy_console.backend.app import app
from ai_study_buddy.buddy_console.backend.inventory_api import InventoryRuntime
from ai_study_buddy.files.on_disk_inventory import OnDiskMainPdfCard


def _card(pdf_path: Path) -> OnDiskMainPdfCard:
    return OnDiskMainPdfCard(
        absolute_path=str(pdf_path),
        basename=pdf_path.name,
        root_id="goodnotes",
        scope="completion",
        subject="math",
        grade_or_scope="P4",
        doc_type="exam",
        book_group_name=None,
        student_email="emma@example.com",
        parse_status="ok",
        is_registered=True,
        student_id="emma",
        registry_file_id="attempt-123",
        normal_name="Worksheet",
        has_template=True,
        has_marking=True,
        review_status="not_started",
        marking_earned_marks=8,
        marking_total_marks=10,
        marking_percentage=80.0,
        registry_added_at="2026-05-26T10:00:00+08:00",
    )


def _runtime(tmp_path: Path) -> InventoryRuntime:
    root = tmp_path / "goodnotes"
    leaf = root / "Math" / "emma" / "P4"
    leaf.mkdir(parents=True)
    (leaf / "registered.pdf").write_bytes(b"%PDF-1.4 registered")
    (leaf / "_raw_registered.pdf").write_bytes(b"%PDF-1.4 raw")
    return InventoryRuntime(
        roots={"goodnotes": root},
        leaf_dirs_by_id={"goodnotes": frozenset({leaf.resolve()})},
        leaf_rels_by_id={"goodnotes": frozenset({"Math/emma/P4"})},
        index_rows=[],
        context_root=tmp_path,
        enriched_cache=[_card(leaf / "registered.pdf")],
    )


def test_inventory_health_reports_files_package_version(tmp_path: Path) -> None:
    app.state.inventory_runtime = _runtime(tmp_path)
    client = TestClient(app)
    health = client.get("/api/inventory/health")
    assert health.status_code == 200
    assert health.json()["files_version"] == files.__version__


def test_get_enriched_cards_reuses_cache_until_workflow_changes(
    monkeypatch, tmp_path: Path
) -> None:
    runtime = _runtime(tmp_path)
    app.state.inventory_runtime = runtime
    build_calls = {"n": 0}

    def fake_build(*_args, **_kwargs):
        build_calls["n"] += 1
        return [_card(tmp_path / "goodnotes" / "Math" / "emma" / "P4" / "registered.pdf")]

    monkeypatch.setattr(
        "ai_study_buddy.buddy_console.backend.inventory_api.build_enriched_inventory",
        fake_build,
    )
    monkeypatch.setattr(
        "ai_study_buddy.buddy_console.backend.inventory_api._workflow_context_stamp",
        lambda _root: 1.0,
    )

    from ai_study_buddy.buddy_console.backend.inventory_api import _get_enriched_cards

    first = _get_enriched_cards(runtime)
    second = _get_enriched_cards(runtime)
    assert build_calls["n"] == 1
    assert first is second

    runtime._enriched_workflow_stamp = 0.0
    monkeypatch.setattr(
        "ai_study_buddy.buddy_console.backend.inventory_api._workflow_context_stamp",
        lambda _root: 2.0,
    )
    third = _get_enriched_cards(runtime)
    assert build_calls["n"] == 2
    assert third is not first


def test_inventory_config_and_list(monkeypatch, tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    app.state.inventory_runtime = runtime

    class FakePfm:
        def list_students(self):
            return [SimpleNamespace(id="emma", name="Emma", email="emma@example.com")]

    monkeypatch.setattr(
        "ai_study_buddy.buddy_console.backend.inventory_api.PdfFileManager",
        FakePfm,
    )

    client = TestClient(app)

    config_response = client.get("/api/config")
    assert config_response.status_code == 200
    config_payload = config_response.json()
    assert config_payload["roots"] == [
        {
            "id": "goodnotes",
            "label": "GoodNotes",
            "path": str(runtime.roots["goodnotes"]),
        }
    ]
    assert config_payload["students"] == [
        {
            "student_id": "emma",
            "display_name": "Emma",
            "email": "emma@example.com",
        }
    ]

    inventory_response = client.get("/api/inventory?student=emma")
    assert inventory_response.status_code == 200
    inventory_payload = inventory_response.json()
    assert inventory_payload["meta"]["total_in_index"] == 1
    assert inventory_payload["meta"]["total_after_filter"] == 1
    assert inventory_payload["items"][0]["registry_file_id"] == "attempt-123"


def test_pdf_browser_list_and_stream(monkeypatch, tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    app.state.inventory_runtime = runtime

    class FakePfm:
        pass

    monkeypatch.setattr(
        "ai_study_buddy.buddy_console.backend.inventory_api.PdfFileManager",
        FakePfm,
    )
    monkeypatch.setattr(
        "ai_study_buddy.buddy_console.backend.inventory_api.RegistryPathIndex.from_pdf_file_manager",
        staticmethod(lambda pfm: object()),
    )
    monkeypatch.setattr(
        "ai_study_buddy.buddy_console.backend.inventory_api.is_pdf_registered",
        lambda path, idx: path.name == "registered.pdf",
    )

    client = TestClient(app)

    root_listing = client.get("/api/pdf-browser/list?id=goodnotes&rel=")
    assert root_listing.status_code == 200
    assert root_listing.json()["dirs"] == ["Math"]

    leaf_listing = client.get("/api/pdf-browser/list?id=goodnotes&rel=Math/emma/P4")
    assert leaf_listing.status_code == 200
    leaf_payload = leaf_listing.json()
    assert leaf_payload["pdfs"] == ["_raw_registered.pdf", "registered.pdf"]
    assert leaf_payload["pdfRegistration"]["registered.pdf"] is True
    assert leaf_payload["pdfRegistration"]["_raw_registered.pdf"] is False

    pdf_response = client.get("/api/pdf?id=goodnotes&rel=Math/emma/P4/registered.pdf")
    assert pdf_response.status_code == 200
    assert pdf_response.headers["content-type"] == "application/pdf"
    assert pdf_response.content.startswith(b"%PDF-1.4 registered")
