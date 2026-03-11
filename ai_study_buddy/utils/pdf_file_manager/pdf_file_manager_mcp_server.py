from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

try:
    from .pdf_file_manager import PdfFileManager
    from .pdf_file_manager_mcp import (
        get_filesystem_mutation_tool_handlers,
        get_readonly_tool_handlers,
        get_safe_mutation_tool_handlers,
        list_filesystem_mutation_tool_names,
        list_readonly_tool_names,
        list_safe_mutation_tool_names,
    )
except ImportError:
    from pdf_file_manager import PdfFileManager
    from pdf_file_manager_mcp import (
        get_filesystem_mutation_tool_handlers,
        get_readonly_tool_handlers,
        get_safe_mutation_tool_handlers,
        list_filesystem_mutation_tool_names,
        list_readonly_tool_names,
        list_safe_mutation_tool_names,
    )

DEFAULT_SERVER_NAME = "pdf-file-manager"
ToolMode = Literal["readonly", "default"]

TOOL_METADATA: dict[str, dict[str, Any]] = {
    "pdf_get_file": {"description": "Get a single registered PDF file by id.", "tags": {"readonly", "files"}},
    "pdf_find_files": {"description": "Find registered PDF files using metadata and name filters.", "tags": {"readonly", "files", "search"}},
    "pdf_get_file_by_path": {"description": "Get a single registered PDF file by absolute path.", "tags": {"readonly", "files"}},
    "pdf_list_students": {"description": "List configured students in the registry.", "tags": {"readonly", "config"}},
    "pdf_list_scan_roots": {"description": "List configured scan roots.", "tags": {"readonly", "config"}},
    "pdf_get_related_files": {"description": "Get raw/main related files for a file id.", "tags": {"readonly", "relations"}},
    "pdf_get_template": {"description": "Get the template linked to a completed file.", "tags": {"readonly", "relations", "templates"}},
    "pdf_get_completions": {"description": "List completions linked to a template file.", "tags": {"readonly", "relations", "templates"}},
    "pdf_get_file_group": {"description": "Get a file group and its members.", "tags": {"readonly", "groups"}},
    "pdf_list_file_groups": {"description": "List file groups, optionally by group type.", "tags": {"readonly", "groups"}},
    "pdf_get_file_group_membership": {"description": "List file groups that include a given file.", "tags": {"readonly", "groups"}},
    "pdf_suggest_groups": {"description": "Suggest exam groups based on matching metadata.", "tags": {"readonly", "groups", "diagnostics"}},
    "pdf_get_operation_log": {"description": "Query the append-only operation log.", "tags": {"readonly", "audit"}},
    "pdf_report_coverage": {"description": "Report scan-root coverage against registry or filesystem leaf directories.", "tags": {"readonly", "diagnostics"}},
    "pdf_add_student": {"description": "Add a student record to the registry.", "tags": {"mutation", "config"}},
    "pdf_add_scan_root": {"description": "Add a scan root to the registry configuration.", "tags": {"mutation", "config"}},
    "pdf_remove_scan_root": {"description": "Remove a scan root from the registry configuration.", "tags": {"mutation", "config"}},
    "pdf_update_metadata": {"description": "Update file classification and metadata without changing files on disk.", "tags": {"mutation", "metadata"}},
    "pdf_create_file_group": {"description": "Create a new file group.", "tags": {"mutation", "groups"}},
    "pdf_add_to_file_group": {"description": "Add a main file to a file group.", "tags": {"mutation", "groups"}},
    "pdf_remove_from_file_group": {"description": "Remove a file from a file group.", "tags": {"mutation", "groups"}},
    "pdf_set_file_group_anchor": {"description": "Set the anchor file for a file group.", "tags": {"mutation", "groups"}},
    "pdf_link_to_template": {"description": "Link a completed file to a template file.", "tags": {"mutation", "relations", "templates"}},
    "pdf_unlink_template": {"description": "Remove the template link for a completed file.", "tags": {"mutation", "relations", "templates"}},
    "pdf_link_files": {"description": "Link files with a raw/main relation.", "tags": {"mutation", "relations"}},
    "pdf_unlink_files": {"description": "Remove a raw/main relation between files.", "tags": {"mutation", "relations"}},
    "pdf_scan_for_new_files": {"description": "Scan roots for new PDFs and optionally register/compress them.", "tags": {"mutation", "filesystem", "scan"}},
    "pdf_register_file": {"description": "Register a single file path in the registry.", "tags": {"mutation", "filesystem", "files"}},
    "pdf_compress_and_register": {"description": "Register a file if needed, then compress and archive the raw source.", "tags": {"mutation", "filesystem", "files"}},
    "pdf_rename_file": {"description": "Rename a registered file on disk and in the registry.", "tags": {"mutation", "filesystem", "files"}},
    "pdf_move_file": {"description": "Move a registered file on disk and update the registry path.", "tags": {"mutation", "filesystem", "files"}},
    "pdf_delete_file": {"description": "Delete a registered file from disk and the registry.", "tags": {"mutation", "filesystem", "files"}},
    "pdf_open_file": {"description": "Open a registered file with the local system PDF handler.", "tags": {"mutation", "filesystem", "local-ui"}},
    "pdf_open_file_group": {"description": "Open the anchor file for a file group.", "tags": {"mutation", "filesystem", "groups", "local-ui"}},
}


def _register_tools(
    server: Any,
    handlers: dict[str, Callable[..., dict[str, Any]]],
    tool_names: list[str],
) -> Any:
    for tool_name in tool_names:
        handler = handlers[tool_name]
        metadata = TOOL_METADATA.get(tool_name, {})
        server.tool(
            name=tool_name,
            description=metadata.get("description"),
            tags=metadata.get("tags"),
        )(handler)
    return server


def register_readonly_tools(
    server: Any,
    *,
    db_path: str | Path | None = None,
    manager_factory: Callable[[], PdfFileManager] | None = None,
) -> Any:
    handlers = get_readonly_tool_handlers(db_path=db_path, manager_factory=manager_factory)
    return _register_tools(server, handlers, list_readonly_tool_names())


def register_safe_mutation_tools(
    server: Any,
    *,
    db_path: str | Path | None = None,
    manager_factory: Callable[[], PdfFileManager] | None = None,
) -> Any:
    handlers = get_safe_mutation_tool_handlers(db_path=db_path, manager_factory=manager_factory)
    return _register_tools(server, handlers, list_safe_mutation_tool_names())


def register_filesystem_mutation_tools(
    server: Any,
    *,
    db_path: str | Path | None = None,
    manager_factory: Callable[[], PdfFileManager] | None = None,
) -> Any:
    handlers = get_filesystem_mutation_tool_handlers(db_path=db_path, manager_factory=manager_factory)
    return _register_tools(server, handlers, list_filesystem_mutation_tool_names())


def create_fastmcp_server(
    *,
    server_name: str = DEFAULT_SERVER_NAME,
    db_path: str | Path | None = None,
    manager_factory: Callable[[], PdfFileManager] | None = None,
    tool_mode: ToolMode = "default",
    fastmcp_cls: type[Any] | None = None,
) -> Any:
    if fastmcp_cls is None:
        try:
            from fastmcp import FastMCP as imported_fastmcp_cls
        except ModuleNotFoundError as exc:
            raise ModuleNotFoundError(
                "fastmcp is required to create the PDF File Manager MCP server"
            ) from exc
        fastmcp_cls = imported_fastmcp_cls

    server = fastmcp_cls(server_name)
    register_readonly_tools(server, db_path=db_path, manager_factory=manager_factory)
    if tool_mode == "default":
        register_safe_mutation_tools(server, db_path=db_path, manager_factory=manager_factory)
        register_filesystem_mutation_tools(server, db_path=db_path, manager_factory=manager_factory)
    return server


def _parse_args(argv: list[str] | None = None) -> Any:
    import argparse

    parser = argparse.ArgumentParser(
        prog="pdf_file_manager_mcp_server",
        description="Run the PDF File Manager MCP server.",
    )
    parser.add_argument("--db", help="Path to the SQLite registry DB")
    parser.add_argument(
        "--tool-mode",
        choices=["readonly", "default"],
        default="default",
        help="Tool exposure mode: readonly or default (all implemented tool groups)",
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "streamable-http", "sse"],
        default="stdio",
        help="Transport to use for the MCP server",
    )
    parser.add_argument("--host", help="Host for HTTP-based transports")
    parser.add_argument("--port", type=int, help="Port for HTTP-based transports")
    parser.add_argument("--path", help="Path for HTTP-based transports")
    parser.add_argument(
        "--no-banner",
        action="store_true",
        help="Disable the FastMCP startup banner",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    server = create_fastmcp_server(db_path=args.db, tool_mode=args.tool_mode)
    run_kwargs: dict[str, Any] = {"show_banner": not args.no_banner}
    if args.transport != "stdio":
        if args.host is not None:
            run_kwargs["host"] = args.host
        if args.port is not None:
            run_kwargs["port"] = args.port
        if args.path is not None:
            run_kwargs["path"] = args.path
    server.run(args.transport, **run_kwargs)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
