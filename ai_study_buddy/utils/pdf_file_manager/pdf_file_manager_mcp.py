from __future__ import annotations

from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

try:
    from .pdf_file_manager import (
        AlreadyRegisteredError,
        ConfigError,
        CoverageReport,
        FileGroup,
        FileGroupMember,
        NotFoundError,
        PdfFile,
        PdfFileManager,
    )
except ImportError:
    from pdf_file_manager import (
        AlreadyRegisteredError,
        ConfigError,
        CoverageReport,
        FileGroup,
        FileGroupMember,
        NotFoundError,
        PdfFile,
        PdfFileManager,
    )

ErrorType = (
    AlreadyRegisteredError
    | ConfigError
    | FileNotFoundError
    | NotFoundError
    | ValueError
)


def serialize_for_mcp(value: Any) -> Any:
    if is_dataclass(value):
        if isinstance(value, CoverageReport):
            return {
                "leaf_dirs": sorted(value.leaf_dirs),
                "scan_roots": sorted(value.scan_roots),
                "leaf_not_in_roots": sorted(value.leaf_not_in_roots),
                "roots_without_leaf_pdfs": sorted(value.roots_without_leaf_pdfs),
            }
        if isinstance(value, FileGroup):
            data = asdict(value)
            data["members"] = [serialize_for_mcp(member) for member in value.members]
            return data
        if isinstance(value, FileGroupMember):
            data = asdict(value)
            data["file"] = serialize_for_mcp(value.file)
            return data
        return asdict(value)
    if isinstance(value, tuple) and len(value) == 2 and isinstance(value[0], PdfFile):
        return {
            "file": serialize_for_mcp(value[0]),
            "relation_type": value[1],
        }
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return sorted(serialize_for_mcp(item) for item in value)
    if isinstance(value, list):
        return [serialize_for_mcp(item) for item in value]
    if isinstance(value, tuple):
        return [serialize_for_mcp(item) for item in value]
    if isinstance(value, dict):
        return {str(key): serialize_for_mcp(item) for key, item in value.items()}
    return value


def error_to_mcp_response(error: ErrorType) -> dict[str, Any]:
    error_type = "internal_error"
    if isinstance(error, AlreadyRegisteredError):
        error_type = "already_registered"
    elif isinstance(error, NotFoundError):
        error_type = "not_found"
    elif isinstance(error, ConfigError):
        error_type = "config_error"
    elif isinstance(error, ValueError):
        error_type = "invalid_argument"
    elif isinstance(error, FileNotFoundError):
        error_type = "file_not_found"
    return {
        "ok": False,
        "error": {
            "type": error_type,
            "message": str(error),
        },
    }


class PdfFileManagerMcpTools:
    def __init__(
        self,
        *,
        db_path: str | Path | None = None,
        manager_factory: Callable[[], PdfFileManager] | None = None,
    ) -> None:
        if manager_factory is None:
            resolved_db_path = Path(db_path).resolve() if db_path is not None else None

            def _default_factory() -> PdfFileManager:
                return PdfFileManager(db_path=resolved_db_path)

            self._manager_factory = _default_factory
        else:
            self._manager_factory = manager_factory

    def _manager(self) -> PdfFileManager:
        return self._manager_factory()

    def _call(self, fn: Callable[..., Any], /, *args: Any, **kwargs: Any) -> dict[str, Any]:
        try:
            result = fn(*args, **kwargs)
        except (AlreadyRegisteredError, ConfigError, FileNotFoundError, NotFoundError, ValueError) as error:
            return error_to_mcp_response(error)
        return {
            "ok": True,
            "result": serialize_for_mcp(result),
        }

    def pdf_get_file(self, file_id: str) -> dict[str, Any]:
        return self._call(self._manager().get_file, file_id)

    def pdf_find_files(
        self,
        *,
        query: str | None = None,
        file_type: str | None = None,
        doc_type: str | None = None,
        student_id: str | None = None,
        subject: str | None = None,
        is_template: bool | None = None,
        has_raw: bool | None = None,
    ) -> dict[str, Any]:
        return self._call(
            self._manager().find_files,
            query=query,
            file_type=file_type,
            doc_type=doc_type,
            student_id=student_id,
            subject=subject,
            is_template=is_template,
            has_raw=has_raw,
        )

    def pdf_get_file_by_path(self, path: str) -> dict[str, Any]:
        return self._call(self._manager().get_file_by_path, path)

    def pdf_list_students(self) -> dict[str, Any]:
        return self._call(self._manager().list_students)

    def pdf_list_scan_roots(self) -> dict[str, Any]:
        return self._call(self._manager().list_scan_roots)

    def pdf_get_related_files(self, file_id: str) -> dict[str, Any]:
        return self._call(self._manager().get_related_files, file_id)

    def pdf_get_template(self, file_id: str) -> dict[str, Any]:
        return self._call(self._manager().get_template, file_id)

    def pdf_get_completions(self, template_id: str) -> dict[str, Any]:
        return self._call(self._manager().get_completions, template_id)

    def pdf_get_file_group(self, group_id: str) -> dict[str, Any]:
        return self._call(self._manager().get_file_group, group_id)

    def pdf_list_file_groups(self, group_type: str | None = None) -> dict[str, Any]:
        return self._call(self._manager().list_file_groups, group_type=group_type)

    def pdf_get_file_group_membership(self, file_id: str) -> dict[str, Any]:
        return self._call(self._manager().get_file_group_membership, file_id)

    def pdf_suggest_groups(self) -> dict[str, Any]:
        return self._call(self._manager().suggest_groups)

    def pdf_get_operation_log(
        self,
        *,
        file_id: str | None = None,
        group_id: str | None = None,
        operation: str | None = None,
        since: str | None = None,
        log_id: str | None = None,
    ) -> dict[str, Any]:
        return self._call(
            self._manager().get_operation_log,
            file_id=file_id,
            group_id=group_id,
            operation=operation,
            since=since,
            log_id=log_id,
        )

    def pdf_report_coverage(
        self,
        *,
        base_path: str | None = None,
        from_registry: bool = False,
    ) -> dict[str, Any]:
        return self._call(
            self._manager().report_coverage,
            base_path=Path(base_path) if base_path is not None else None,
            from_registry=from_registry,
        )

    def pdf_add_student(self, *, id: str, name: str, email: str | None = None) -> dict[str, Any]:
        return self._call(self._manager().add_student, id=id, name=name, email=email)

    def pdf_add_scan_root(self, *, path: str, student_id: str | None = None) -> dict[str, Any]:
        return self._call(self._manager().add_scan_root, path=path, student_id=student_id)

    def pdf_remove_scan_root(self, *, path: str) -> dict[str, Any]:
        return self._call(self._manager().remove_scan_root, path=path)

    def pdf_update_metadata(
        self,
        *,
        file_id_or_path: str,
        doc_type: str | None = None,
        student_id: str | None = None,
        subject: str | None = None,
        is_template: bool | None = None,
        metadata: dict | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        return self._call(
            self._manager().update_metadata,
            file_id_or_path,
            doc_type=doc_type,
            student_id=student_id,
            subject=subject,
            is_template=is_template,
            metadata=metadata,
            notes=notes,
        )

    def pdf_create_file_group(
        self,
        *,
        label: str,
        group_type: str = "collection",
        anchor_id: str | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        return self._call(
            self._manager().create_file_group,
            label=label,
            group_type=group_type,
            anchor_id=anchor_id,
            notes=notes,
        )

    def pdf_add_to_file_group(self, *, group_id: str, file_id: str, role: str | None = None) -> dict[str, Any]:
        return self._call(self._manager().add_to_file_group, group_id=group_id, file_id=file_id, role=role)

    def pdf_remove_from_file_group(self, *, group_id: str, file_id: str) -> dict[str, Any]:
        return self._call(self._manager().remove_from_file_group, group_id=group_id, file_id=file_id)

    def pdf_set_file_group_anchor(self, *, group_id: str, file_id: str) -> dict[str, Any]:
        return self._call(self._manager().set_file_group_anchor, group_id=group_id, file_id=file_id)

    def pdf_link_to_template(
        self,
        *,
        completed_id: str,
        template_id: str,
        inherit_metadata: bool = True,
    ) -> dict[str, Any]:
        return self._call(
            self._manager().link_to_template,
            completed_id=completed_id,
            template_id=template_id,
            inherit_metadata=inherit_metadata,
        )

    def pdf_unlink_template(self, *, completed_id: str) -> dict[str, Any]:
        return self._call(self._manager().unlink_template, completed_id=completed_id)

    def pdf_link_files(self, *, source_id: str, target_id: str, relation_type: str) -> dict[str, Any]:
        return self._call(
            self._manager().link_files,
            source_id=source_id,
            target_id=target_id,
            relation_type=relation_type,
        )

    def pdf_unlink_files(self, *, source_id: str, target_id: str) -> dict[str, Any]:
        return self._call(self._manager().unlink_files, source_id=source_id, target_id=target_id)

    def pdf_scan_for_new_files(
        self,
        *,
        roots: list[str] | None = None,
        min_savings_pct: float = 10,
        dry_run: bool = False,
    ) -> dict[str, Any]:
        return self._call(
            self._manager().scan_for_new_files,
            roots=roots,
            min_savings_pct=min_savings_pct,
            dry_run=dry_run,
        )

    def pdf_register_file(
        self,
        *,
        path: str,
        file_type: str | None = None,
        doc_type: str = "unknown",
        student_id: str | None = None,
        subject: str | None = None,
        is_template: bool = False,
        metadata: dict | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        return self._call(
            self._manager().register_file,
            path=path,
            file_type=file_type,
            doc_type=doc_type,
            student_id=student_id,
            subject=subject,
            is_template=is_template,
            metadata=metadata,
            notes=notes,
        )

    def pdf_compress_and_register(
        self,
        *,
        file_id_or_path: str,
        force: bool = False,
        min_savings_pct: float = 10,
        preserve_input: bool = False,
    ) -> dict[str, Any]:
        return self._call(
            self._manager().compress_and_register,
            file_id_or_path,
            force=force,
            min_savings_pct=min_savings_pct,
            preserve_input=preserve_input,
        )

    def pdf_resolve_goodnotes_template(self, *, main_path: str) -> dict[str, Any]:
        """Resolve a GoodNotes main file path to its DaydreamEdu _c_ template/source path."""
        return self._call(self._manager().resolve_goodnotes_template_path, main_path)

    def pdf_link_goodnotes_template_for_file(
        self,
        *,
        main_path: str,
        auto_fix_template: bool = True,
        inherit_metadata: bool = True,
    ) -> dict[str, Any]:
        return self._call(
            self._manager().link_goodnotes_template_for_file,
            main_path,
            auto_fix_template=auto_fix_template,
            inherit_metadata=inherit_metadata,
        )

    def pdf_link_goodnotes_templates_for_root(
        self,
        *,
        root: str,
        dry_run: bool = False,
        auto_fix_template: bool = True,
        inherit_metadata: bool = True,
    ) -> dict[str, Any]:
        return self._call(
            self._manager().link_goodnotes_templates_for_root,
            root,
            dry_run=dry_run,
            auto_fix_template=auto_fix_template,
            inherit_metadata=inherit_metadata,
        )

    def pdf_rename_file(self, *, file_id_or_path: str, new_name: str) -> dict[str, Any]:
        return self._call(self._manager().rename_file, file_id_or_path, new_name=new_name)

    def pdf_move_file(self, *, file_id_or_path: str, new_dir: str) -> dict[str, Any]:
        return self._call(self._manager().move_file, file_id_or_path, new_dir=new_dir)

    def pdf_delete_file(
        self,
        *,
        file_id_or_path: str,
        keep_related: bool = False,
        notes: str | None = None,
        deleted_by: str = "api",
    ) -> dict[str, Any]:
        return self._call(
            self._manager().delete_file,
            file_id_or_path,
            keep_related=keep_related,
            notes=notes,
            deleted_by=deleted_by,
        )

    def pdf_open_file(self, *, file_id_or_path: str) -> dict[str, Any]:
        return self._call(self._manager().open_file, file_id_or_path)

    def pdf_open_file_group(self, *, group_id: str) -> dict[str, Any]:
        return self._call(self._manager().open_file_group, group_id)


READONLY_TOOL_NAMES = [
    "pdf_get_file",
    "pdf_find_files",
    "pdf_get_file_by_path",
    "pdf_list_students",
    "pdf_list_scan_roots",
    "pdf_get_related_files",
    "pdf_get_template",
    "pdf_get_completions",
    "pdf_get_file_group",
    "pdf_list_file_groups",
    "pdf_get_file_group_membership",
    "pdf_suggest_groups",
    "pdf_get_operation_log",
    "pdf_report_coverage",
    "pdf_resolve_goodnotes_template",
]

SAFE_MUTATION_TOOL_NAMES = [
    "pdf_add_student",
    "pdf_add_scan_root",
    "pdf_remove_scan_root",
    "pdf_update_metadata",
    "pdf_create_file_group",
    "pdf_add_to_file_group",
    "pdf_remove_from_file_group",
    "pdf_set_file_group_anchor",
    "pdf_link_to_template",
    "pdf_link_goodnotes_template_for_file",
    "pdf_link_goodnotes_templates_for_root",
    "pdf_unlink_template",
    "pdf_link_files",
    "pdf_unlink_files",
]

FILESYSTEM_MUTATION_TOOL_NAMES = [
    "pdf_scan_for_new_files",
    "pdf_register_file",
    "pdf_compress_and_register",
    "pdf_rename_file",
    "pdf_move_file",
    "pdf_delete_file",
    "pdf_open_file",
    "pdf_open_file_group",
]


def list_readonly_tool_names() -> list[str]:
    return READONLY_TOOL_NAMES.copy()


def list_safe_mutation_tool_names() -> list[str]:
    return SAFE_MUTATION_TOOL_NAMES.copy()


def list_filesystem_mutation_tool_names() -> list[str]:
    return FILESYSTEM_MUTATION_TOOL_NAMES.copy()


def get_readonly_tool_handlers(
    *,
    db_path: str | Path | None = None,
    manager_factory: Callable[[], PdfFileManager] | None = None,
) -> dict[str, Callable[..., dict[str, Any]]]:
    tools = PdfFileManagerMcpTools(db_path=db_path, manager_factory=manager_factory)
    return {name: getattr(tools, name) for name in READONLY_TOOL_NAMES}


def get_safe_mutation_tool_handlers(
    *,
    db_path: str | Path | None = None,
    manager_factory: Callable[[], PdfFileManager] | None = None,
) -> dict[str, Callable[..., dict[str, Any]]]:
    tools = PdfFileManagerMcpTools(db_path=db_path, manager_factory=manager_factory)
    return {name: getattr(tools, name) for name in SAFE_MUTATION_TOOL_NAMES}


def get_filesystem_mutation_tool_handlers(
    *,
    db_path: str | Path | None = None,
    manager_factory: Callable[[], PdfFileManager] | None = None,
) -> dict[str, Callable[..., dict[str, Any]]]:
    tools = PdfFileManagerMcpTools(db_path=db_path, manager_factory=manager_factory)
    return {name: getattr(tools, name) for name in FILESYSTEM_MUTATION_TOOL_NAMES}
