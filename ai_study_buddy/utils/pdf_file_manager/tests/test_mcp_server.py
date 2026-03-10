import builtins
import sys
from pathlib import Path

import anyio
import pytest
from fastmcp import FastMCP

_tests_dir = Path(__file__).resolve().parent
_util_dir = _tests_dir.parent
if str(_util_dir) not in sys.path:
    sys.path.insert(0, str(_util_dir))

from pdf_file_manager_mcp import (
    list_filesystem_mutation_tool_names,
    list_readonly_tool_names,
    list_safe_mutation_tool_names,
)
from pdf_file_manager_mcp_server import (
    DEFAULT_SERVER_NAME,
    TOOL_METADATA,
    _parse_args,
    create_fastmcp_server,
    main,
    register_filesystem_mutation_tools,
    register_readonly_tools,
    register_safe_mutation_tools,
)


class FakeFastMCP:
    def __init__(self, name: str) -> None:
        self.name = name
        self.registered: dict[str, object] = {}
        self.tool_options: dict[str, dict[str, object]] = {}
        self.run_calls: list[tuple[object, dict[str, object]]] = []

    def tool(self, *, name: str, description=None, tags=None):
        def _register(func):
            self.registered[name] = func
            self.tool_options[name] = {"description": description, "tags": tags}
            return func

        return _register

    def run(self, transport=None, **kwargs):
        self.run_calls.append((transport, kwargs))


def test_register_readonly_tools_registers_expected_names():
    server = FakeFastMCP("test-server")
    register_readonly_tools(server, db_path="/tmp/pdf-registry.db")
    assert sorted(server.registered.keys()) == sorted(list_readonly_tool_names())
    assert callable(server.registered["pdf_get_file"])


def test_register_safe_mutation_tools_registers_expected_names():
    server = FakeFastMCP("test-server")
    register_safe_mutation_tools(server, db_path="/tmp/pdf-registry.db")
    assert sorted(server.registered.keys()) == sorted(list_safe_mutation_tool_names())
    assert callable(server.registered["pdf_add_student"])


def test_register_filesystem_mutation_tools_registers_expected_names():
    server = FakeFastMCP("test-server")
    register_filesystem_mutation_tools(server, db_path="/tmp/pdf-registry.db")
    assert sorted(server.registered.keys()) == sorted(list_filesystem_mutation_tool_names())
    assert callable(server.registered["pdf_scan_for_new_files"])


def test_create_fastmcp_server_uses_injected_class():
    server = create_fastmcp_server(
        server_name="custom-server",
        db_path="/tmp/pdf-registry.db",
        fastmcp_cls=FakeFastMCP,
    )
    assert isinstance(server, FakeFastMCP)
    assert server.name == "custom-server"
    assert sorted(server.registered.keys()) == sorted(
        list_readonly_tool_names() + list_safe_mutation_tool_names() + list_filesystem_mutation_tool_names()
    )


def test_create_fastmcp_server_readonly_mode_uses_injected_class():
    server = create_fastmcp_server(
        server_name="readonly-server",
        db_path="/tmp/pdf-registry.db",
        tool_mode="readonly",
        fastmcp_cls=FakeFastMCP,
    )
    assert isinstance(server, FakeFastMCP)
    assert sorted(server.registered.keys()) == sorted(list_readonly_tool_names())


def test_create_fastmcp_server_uses_default_name():
    server = create_fastmcp_server(
        db_path="/tmp/pdf-registry.db",
        fastmcp_cls=FakeFastMCP,
    )
    assert server.name == DEFAULT_SERVER_NAME


def test_create_fastmcp_server_without_fastmcp_raises_clear_error(monkeypatch):
    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "fastmcp":
            raise ModuleNotFoundError("No module named 'fastmcp'")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ModuleNotFoundError) as exc:
        create_fastmcp_server()
    assert "fastmcp is required" in str(exc.value)


def test_parse_args_defaults_to_stdio():
    args = _parse_args([])
    assert args.transport == "stdio"
    assert args.db is None
    assert args.tool_mode == "default"
    assert args.no_banner is False


def test_main_runs_server_with_stdio_defaults(monkeypatch):
    fake_server = FakeFastMCP("test-server")

    def fake_create_fastmcp_server(*, server_name=DEFAULT_SERVER_NAME, db_path=None, manager_factory=None, tool_mode="default", fastmcp_cls=None):
        assert db_path == "/tmp/pdf-registry.db"
        assert server_name == DEFAULT_SERVER_NAME
        assert tool_mode == "default"
        return fake_server

    monkeypatch.setattr("pdf_file_manager_mcp_server.create_fastmcp_server", fake_create_fastmcp_server)
    exit_code = main(["--db", "/tmp/pdf-registry.db"])
    assert exit_code == 0
    assert fake_server.run_calls == [("stdio", {"show_banner": True})]


def test_main_passes_tool_mode(monkeypatch):
    fake_server = FakeFastMCP("test-server")

    def fake_create_fastmcp_server(*, server_name=DEFAULT_SERVER_NAME, db_path=None, manager_factory=None, tool_mode="default", fastmcp_cls=None):
        assert tool_mode == "readonly"
        return fake_server

    monkeypatch.setattr("pdf_file_manager_mcp_server.create_fastmcp_server", fake_create_fastmcp_server)
    exit_code = main(["--tool-mode", "readonly"])
    assert exit_code == 0
    assert fake_server.run_calls == [("stdio", {"show_banner": True})]


def test_main_runs_server_with_http_options(monkeypatch):
    fake_server = FakeFastMCP("test-server")

    def fake_create_fastmcp_server(*, server_name=DEFAULT_SERVER_NAME, db_path=None, manager_factory=None, tool_mode="default", fastmcp_cls=None):
        assert tool_mode == "default"
        return fake_server

    monkeypatch.setattr("pdf_file_manager_mcp_server.create_fastmcp_server", fake_create_fastmcp_server)
    exit_code = main(
        [
            "--transport",
            "http",
            "--host",
            "127.0.0.1",
            "--port",
            "9000",
            "--path",
            "/mcp",
            "--no-banner",
        ]
    )
    assert exit_code == 0
    assert fake_server.run_calls == [
        (
            "http",
            {
                "show_banner": False,
                "host": "127.0.0.1",
                "port": 9000,
                "path": "/mcp",
            },
        )
    ]


def test_registered_tools_include_metadata():
    server = FakeFastMCP("test-server")
    register_readonly_tools(server, db_path="/tmp/pdf-registry.db")
    assert "pdf_get_file" in server.registered
    assert "pdf_get_file" in TOOL_METADATA
    assert server.tool_options["pdf_get_file"]["description"] == TOOL_METADATA["pdf_get_file"]["description"]
    assert "readonly" in server.tool_options["pdf_get_file"]["tags"]


def test_create_fastmcp_server_registers_tools_on_real_fastmcp():
    server = create_fastmcp_server(
        server_name="real-fastmcp",
        db_path="/tmp/pdf-registry.db",
        tool_mode="readonly",
        fastmcp_cls=FastMCP,
    )

    async def _list_tools():
        return await server.list_tools()

    tools = anyio.run(_list_tools)
    names = sorted(tool.name for tool in tools)
    assert names == sorted(list_readonly_tool_names())
    sample = next(tool for tool in tools if tool.name == "pdf_get_file")
    assert sample.description == TOOL_METADATA["pdf_get_file"]["description"]
    assert sample.tags == TOOL_METADATA["pdf_get_file"]["tags"]
