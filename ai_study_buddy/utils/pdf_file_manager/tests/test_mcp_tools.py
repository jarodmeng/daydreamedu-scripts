import sys
import tempfile
from pathlib import Path

import pytest

_tests_dir = Path(__file__).resolve().parent
_util_dir = _tests_dir.parent
if str(_tests_dir) not in sys.path:
    sys.path.insert(0, str(_tests_dir))
if str(_util_dir) not in sys.path:
    sys.path.insert(0, str(_util_dir))

from pdf_file_manager import ConfigError, PdfFileManager
from conftest import FIXTURE_ROOT, fixture_has_pdfs
from pdf_file_manager_mcp import (
    PdfFileManagerMcpTools,
    error_to_mcp_response,
    get_filesystem_mutation_tool_handlers,
    get_readonly_tool_handlers,
    get_safe_mutation_tool_handlers,
    list_filesystem_mutation_tool_names,
    list_readonly_tool_names,
    list_safe_mutation_tool_names,
    serialize_for_mcp,
)


def _make_pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.0\n")
    return path


def test_serialize_for_mcp_coverage_report_sorts_sets():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_scan_root(str(root / "b"))
            _make_pdf(root / "a.pdf")
            mgr.register_file(root / "a.pdf")
            report = mgr.report_coverage(from_registry=True)
            payload = serialize_for_mcp(report)
            assert payload["leaf_dirs"] == [str(root.resolve())]
            assert payload["leaf_not_in_roots"] == [str(root.resolve())]
            assert isinstance(payload["scan_roots"], list)
        Path(db_path).unlink(missing_ok=True)
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_error_to_mcp_response_maps_config_error():
    payload = error_to_mcp_response(ConfigError("missing config"))
    assert payload == {
        "ok": False,
        "error": {
            "type": "config_error",
            "message": "missing config",
        },
    }


def test_pdf_get_file_and_get_file_by_path_return_json_safe_payload():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = _make_pdf(Path(tmpdir) / "doc.pdf")
            mgr = PdfFileManager(db_path=db_path)
            file_record = mgr.register_file(pdf_path, doc_type="worksheet", metadata={"topic": "fractions"})
            tools = PdfFileManagerMcpTools(db_path=db_path)

            by_id = tools.pdf_get_file(file_record.id)
            by_path = tools.pdf_get_file_by_path(str(pdf_path))

            assert by_id["ok"] is True
            assert by_id["result"]["id"] == file_record.id
            assert by_id["result"]["metadata"] == {"topic": "fractions"}
            assert by_path["ok"] is True
            assert by_path["result"]["path"] == str(pdf_path.resolve())
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_pdf_find_files_and_list_helpers():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf_path = _make_pdf(root / "math.pdf")
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_student("winston", "Winston")
            mgr.add_scan_root(str(root), student_id="winston")
            mgr.register_file(pdf_path, doc_type="worksheet", student_id="winston", subject="math")

            tools = PdfFileManagerMcpTools(db_path=db_path)
            files = tools.pdf_find_files(subject="math")
            students = tools.pdf_list_students()
            scan_roots = tools.pdf_list_scan_roots()

            assert files["ok"] is True
            assert len(files["result"]) == 1
            assert files["result"][0]["subject"] == "math"
            assert students["result"][0]["id"] == "winston"
            assert scan_roots["result"][0]["student_id"] == "winston"
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_pdf_relations_template_groups_and_log_tools():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            template_path = _make_pdf(root / "_c_template.pdf")
            completed_path = _make_pdf(root / "_c_completed.pdf")
            raw_path = _make_pdf(root / "_raw_completed.pdf")

            mgr = PdfFileManager(db_path=db_path)
            template = mgr.register_file(template_path, file_type="main", is_template=True, doc_type="exam", subject="science")
            completed = mgr.register_file(completed_path, file_type="main", is_template=False, doc_type="unknown")
            raw = mgr.register_file(raw_path, file_type="raw")
            mgr.link_files(completed.id, raw.id, "raw_source")
            mgr.link_to_template(completed.id, template.id)
            group = mgr.create_file_group("Science exam", group_type="exam")
            mgr.add_to_file_group(group.id, completed.id, role="paper_1")
            mgr.set_file_group_anchor(group.id, completed.id)
            mgr.update_metadata(completed.id, student_id="winston", metadata={"exam_date": "2025-11-12"})

            tools = PdfFileManagerMcpTools(db_path=db_path)
            related = tools.pdf_get_related_files(completed.id)
            template_result = tools.pdf_get_template(completed.id)
            completions = tools.pdf_get_completions(template.id)
            file_group = tools.pdf_get_file_group(group.id)
            groups = tools.pdf_list_file_groups(group_type="exam")
            membership = tools.pdf_get_file_group_membership(completed.id)
            log = tools.pdf_get_operation_log(operation="link_template")

            assert related["ok"] is True
            assert {item["relation_type"] for item in related["result"]} == {"main_version", "raw_source"}
            assert all(item["file"]["id"] == raw.id for item in related["result"])
            assert template_result["result"]["id"] == template.id
            assert completions["result"][0]["id"] == completed.id
            assert file_group["result"]["anchor_id"] == completed.id
            assert file_group["result"]["members"][0]["file"]["id"] == completed.id
            assert groups["result"][0]["group_type"] == "exam"
            assert membership["result"][0]["id"] == group.id
            assert log["result"][0]["operation"] == "link_template"
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_pdf_suggest_groups_and_report_coverage():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            mgr.add_student("winston", "Winston")
            mgr.add_scan_root(str(root), student_id="winston")
            first = mgr.register_file(_make_pdf(root / "_c_first.pdf"), file_type="main", doc_type="exam", student_id="winston", subject="science", metadata={"exam_date": "2025-11-12"})
            second = mgr.register_file(_make_pdf(root / "_c_second.pdf"), file_type="main", doc_type="exam", student_id="winston", subject="science", metadata={"exam_date": "2025-11-12"})

            tools = PdfFileManagerMcpTools(db_path=db_path)
            suggestions = tools.pdf_suggest_groups()
            coverage = tools.pdf_report_coverage(from_registry=True)

            assert suggestions["ok"] is True
            assert len(suggestions["result"]) == 1
            candidate_ids = {item["id"] for item in suggestions["result"][0]["candidate_files"]}
            assert candidate_ids == {first.id, second.id}
            assert coverage["ok"] is True
            assert coverage["result"]["scan_roots"] == [str(root.resolve())]
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_pdf_get_file_group_missing_maps_not_found():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        tools = PdfFileManagerMcpTools(db_path=db_path)
        result = tools.pdf_get_file_group("missing-group")
        assert result["ok"] is False
        assert result["error"]["type"] == "not_found"
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_pdf_report_coverage_uses_fresh_manager_per_call():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    factory_calls: list[PdfFileManager] = []

    def manager_factory() -> PdfFileManager:
        manager = PdfFileManager(db_path=db_path)
        factory_calls.append(manager)
        return manager

    try:
        tools = PdfFileManagerMcpTools(manager_factory=manager_factory)
        first = tools.pdf_report_coverage(from_registry=True)
        second = tools.pdf_report_coverage(from_registry=True)
        assert first["ok"] is True
        assert second["ok"] is True
        assert len(factory_calls) == 2
        assert factory_calls[0] is not factory_calls[1]
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_readonly_tool_registry_matches_expected_surface():
    handlers = get_readonly_tool_handlers(db_path="/tmp/example.db")
    names = list_readonly_tool_names()
    assert sorted(handlers.keys()) == sorted(names)
    assert "pdf_get_file" in names
    assert "pdf_report_coverage" in names
    assert all(callable(handler) for handler in handlers.values())


def test_safe_mutation_tool_registry_matches_expected_surface():
    handlers = get_safe_mutation_tool_handlers(db_path="/tmp/example.db")
    names = list_safe_mutation_tool_names()
    assert sorted(handlers.keys()) == sorted(names)
    assert "pdf_add_student" in names
    assert "pdf_unlink_files" in names
    assert all(callable(handler) for handler in handlers.values())


def test_safe_mutation_tools_create_and_update_records():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf_path = _make_pdf(root / "doc.pdf")
            mgr = PdfFileManager(db_path=db_path)
            file_record = mgr.register_file(pdf_path)
            tools = PdfFileManagerMcpTools(db_path=db_path)

            student = tools.pdf_add_student(id="winston", name="Winston", email="w@example.com")
            scan_root = tools.pdf_add_scan_root(path=str(root), student_id="winston")
            updated = tools.pdf_update_metadata(
                file_id_or_path=file_record.id,
                doc_type="worksheet",
                student_id="winston",
                subject="math",
                metadata={"topic": "fractions"},
                notes="reviewed",
            )
            removed = tools.pdf_remove_scan_root(path=str(root))

            assert student["result"]["id"] == "winston"
            assert scan_root["result"]["path"] == str(root.resolve())
            assert updated["result"]["subject"] == "math"
            assert updated["result"]["metadata"] == {"topic": "fractions"}
            assert removed == {"ok": True, "result": None}
            assert mgr.list_scan_roots() == []
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_safe_mutation_group_and_relation_tools():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            template_path = _make_pdf(root / "_c_template.pdf")
            completed_path = _make_pdf(root / "_c_completed.pdf")
            raw_path = _make_pdf(root / "_raw_completed.pdf")
            mgr = PdfFileManager(db_path=db_path)
            template = mgr.register_file(template_path, file_type="main", is_template=True, doc_type="exam", subject="science")
            completed = mgr.register_file(completed_path, file_type="main", is_template=False, doc_type="unknown")
            raw = mgr.register_file(raw_path, file_type="raw")
            tools = PdfFileManagerMcpTools(db_path=db_path)

            link = tools.pdf_link_files(source_id=completed.id, target_id=raw.id, relation_type="raw_source")
            group = tools.pdf_create_file_group(label="Science", group_type="exam")
            member = tools.pdf_add_to_file_group(group_id=group["result"]["id"], file_id=completed.id, role="paper_1")
            anchor = tools.pdf_set_file_group_anchor(group_id=group["result"]["id"], file_id=completed.id)
            template_link = tools.pdf_link_to_template(completed_id=completed.id, template_id=template.id)
            unlink_template = tools.pdf_unlink_template(completed_id=completed.id)
            remove_member = tools.pdf_remove_from_file_group(group_id=group["result"]["id"], file_id=completed.id)
            unlink_files = tools.pdf_unlink_files(source_id=completed.id, target_id=raw.id)

            assert link["result"]["relation_type"] == "raw_source"
            assert group["result"]["group_type"] == "exam"
            assert member["result"]["role"] == "paper_1"
            assert anchor == {"ok": True, "result": None}
            assert template_link["result"]["relation_type"] == "template_for"
            assert unlink_template == {"ok": True, "result": None}
            assert remove_member == {"ok": True, "result": None}
            assert unlink_files == {"ok": True, "result": None}
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_safe_mutation_tools_map_validation_errors():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            pdf_path = _make_pdf(Path(tmpdir) / "doc.pdf")
            mgr = PdfFileManager(db_path=db_path)
            file_record = mgr.register_file(pdf_path)
            tools = PdfFileManagerMcpTools(db_path=db_path)
            invalid_update = tools.pdf_update_metadata(file_id_or_path=file_record.id, subject="history")
            invalid_group = tools.pdf_create_file_group(label="Bad", group_type="invalid")
            assert invalid_update["ok"] is False
            assert invalid_update["error"]["type"] == "invalid_argument"
            assert invalid_group["ok"] is False
            assert invalid_group["error"]["type"] == "invalid_argument"
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_filesystem_mutation_tool_registry_matches_expected_surface():
    handlers = get_filesystem_mutation_tool_handlers(db_path="/tmp/example.db")
    names = list_filesystem_mutation_tool_names()
    assert sorted(handlers.keys()) == sorted(names)
    assert "pdf_register_file" in names
    assert "pdf_open_file_group" in names
    assert all(callable(handler) for handler in handlers.values())


def test_filesystem_mutation_tools_register_scan_and_delete():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf_path = _make_pdf(root / "doc.pdf")
            tools = PdfFileManagerMcpTools(db_path=db_path)

            registered = tools.pdf_register_file(path=str(pdf_path), doc_type="worksheet")
            deleted = tools.pdf_delete_file(file_id_or_path=registered["result"]["id"], notes="cleanup")

            assert registered["ok"] is True
            assert registered["result"]["doc_type"] == "worksheet"
            assert deleted["ok"] is True
            assert deleted["result"]["operation"] == "delete"
            assert not pdf_path.exists()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_filesystem_mutation_tools_compress_rename_and_move():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf_path = _make_pdf(root / "doc.pdf")
            target_dir = root / "moved"
            tools = PdfFileManagerMcpTools(db_path=db_path)

            registered = tools.pdf_register_file(path=str(pdf_path))
            renamed = tools.pdf_rename_file(file_id_or_path=registered["result"]["id"], new_name="renamed.pdf")
            moved = tools.pdf_move_file(file_id_or_path=renamed["result"]["id"], new_dir=str(target_dir))

            assert registered["ok"] is True
            assert renamed["ok"] is True
            assert renamed["result"]["name"] == "renamed.pdf"
            assert moved["ok"] is True
            assert Path(moved["result"]["path"]).parent == target_dir.resolve()
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_filesystem_mutation_tools_compress_and_register():
    if not fixture_has_pdfs():
        pytest.skip("Fixture PDFs not present")
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            copied = root / "fixture"
            import shutil

            shutil.copytree(FIXTURE_ROOT, copied, dirs_exist_ok=True)
            pdf_path = next(copied.rglob("*.pdf"))
            tools = PdfFileManagerMcpTools(db_path=db_path)
            compressed = tools.pdf_compress_and_register(file_id_or_path=str(pdf_path), min_savings_pct=0, preserve_input=False)
            assert compressed["ok"] is True
            assert compressed["result"]["main_file_id"] is not None
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_filesystem_mutation_tools_open_file_and_open_group():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            pdf_path = _make_pdf(root / "_c_doc.pdf")
            mgr = PdfFileManager(db_path=db_path)
            file_record = mgr.register_file(pdf_path, file_type="main")
            group = mgr.create_file_group("Open group", group_type="exam")
            mgr.add_to_file_group(group.id, file_record.id)
            mgr.set_file_group_anchor(group.id, file_record.id)
            tools = PdfFileManagerMcpTools(db_path=db_path)

            with pytest.MonkeyPatch.context() as mp:
                calls = []

                def fake_run(args, check):
                    calls.append((args, check))

                mp.setattr("pdf_file_manager.subprocess.run", fake_run)
                opened_file = tools.pdf_open_file(file_id_or_path=file_record.id)
                opened_group = tools.pdf_open_file_group(group_id=group.id)

            assert opened_file == {"ok": True, "result": None}
            assert opened_group == {"ok": True, "result": None}
            assert len(calls) == 2
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_filesystem_mutation_tools_scan_and_error_mapping():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _make_pdf(root / "scan.pdf")
            tools = PdfFileManagerMcpTools(db_path=db_path)

            no_roots = tools.pdf_scan_for_new_files()
            dry_run = tools.pdf_scan_for_new_files(roots=[str(root)], dry_run=True)

            assert no_roots["ok"] is False
            assert no_roots["error"]["type"] == "config_error"
            assert dry_run["ok"] is True
            assert len(dry_run["result"]) == 1
    finally:
        Path(db_path).unlink(missing_ok=True)


@pytest.mark.parametrize("tool_name", list_readonly_tool_names())
def test_declared_readonly_tools_have_handlers(tool_name: str):
    tools = PdfFileManagerMcpTools(db_path="/tmp/example.db")
    assert callable(getattr(tools, tool_name))


@pytest.mark.parametrize("tool_name", list_safe_mutation_tool_names())
def test_declared_safe_mutation_tools_have_handlers(tool_name: str):
    tools = PdfFileManagerMcpTools(db_path="/tmp/example.db")
    assert callable(getattr(tools, tool_name))


@pytest.mark.parametrize("tool_name", list_filesystem_mutation_tool_names())
def test_declared_filesystem_mutation_tools_have_handlers(tool_name: str):
    tools = PdfFileManagerMcpTools(db_path="/tmp/example.db")
    assert callable(getattr(tools, tool_name))
