# Changelog

All notable changes to the pdf_file_manager utility are documented here.

---

## [v0.2.1] — GoodNotes-safe compression and template resolution

- Added `preserve_input` flag to `compress_and_register` to support GoodNotes-safe compression: originals remain at their paths and `_c_` mains are created alongside and linked as raw↔main.
- Updated `scan_for_new_files` to detect `GoodNotes/` paths and automatically use `preserve_input=True` so GoodNotes backups are never renamed or moved.
- Implemented `resolve_goodnotes_template_path` and exposed it via the MCP tool `pdf_resolve_goodnotes_template` to resolve GoodNotes main paths to DaydreamEdu `_c_` templates based on folder mirroring and naming conventions.
- Extended MCP `pdf_compress_and_register` schema to accept `preserve_input`, and documented GoodNotes behaviour in `MCP.md`, `ARCHITECTURE.md`, `SPEC.md`, and `README.md`.

## [v0.2.0] — MCP interface, server hardening, and CLI removal

- Added the MCP machine interface: wrapper/tool contract in `pdf_file_manager_mcp.py` and FastMCP binding/entrypoint in `pdf_file_manager_mcp_server.py`.
- Added MCP-focused tests in `tests/test_mcp_tools.py` and `tests/test_mcp_server.py`.
- Added FastMCP tool metadata, readonly-only server mode, connection docs in `MCP.md`, and a real `FastMCP` registration test.
- Updated current-facing docs to prefer Python API + MCP as the supported interfaces.
- Removed the legacy built-in CLI layer from `pdf_file_manager.py` and deleted the CLI smoke tests to avoid maintaining a second, partial machine interface.

---

## [v0.1.1] — Inference improvements + proposals 1–4

Merges all prior **Unreleased** changes (inference) and implements the four API/CLI proposals from `docs/learnings/LEARNING_FROM_FIRST_RUN.md` and `docs/proposals/`.

- **Path-based is_template inference:** `_infer_from_path` sets `is_template` from the path (student folder vs grade/scope). Scan applies this via `update_metadata`. See ARCHITECTURE § Folder-based inference; tests in `test_inference.py`.
- **Chinese exam variant inference:** For `subject='chinese'` and `doc_type='exam'`, `_infer_from_path` infers `metadata.chinese_variant` from the filename (`higher` / `foundation`). Documented in ARCHITECTURE § Metadata schemas; tests in `test_inference.py`.
- **Proposal 1 — Ensure students and scan roots:** `ensure_student(student_id, name, email=None)` and `ensure_scan_root(path, student_id=None)`; idempotent helpers. Tests in `test_config.py`.
- **Proposal 2 — Scan CLI:** `pdf_file_manager scan [--root PATH ...] [--dry-run] [--min-savings-pct N] [--progress]`; uses configured scan roots when `--root` omitted; `ConfigError` when no roots. Tests in `test_cli.py`.
- **Proposal 3 — Coverage / read‑only registry paths:** `find_leaf_dirs(base)` (static), `report_coverage(base_path=None, from_registry=False)` returning `CoverageReport`; `coverage` CLI with `--base` and `--from-registry`. Tests in `test_coverage.py` and `test_cli.py`.
- **Proposal 4 — Template linking by path:** `link_template_by_paths(completed_path, template_path, inherit_metadata=True)`; `link-template` CLI with `--template`, `--completed`, `--no-inherit-metadata`. Tests in `test_relations.py` and `test_cli.py`.

---

## [v0.1.0] — 5-phase build and test plan

First working version: SQLite registry, manager, operation log, config and file lifecycle, read/update/delete, relations and groups, audit log query, and minimal CLI. Delivered via a 5-phase build and test plan; all phase tests pass.

### Phase 1 — Foundation

- **Schema:** Seven tables (`students`, `pdf_files`, `file_relations`, `file_groups`, `file_group_members`, `operation_log`, `scan_roots`) with constraints; schema in `schema.sql` in the utility folder.
- **PdfFileManager:** Init with default DB path (env `PDF_REGISTRY_PATH` or repo-relative `ai_study_buddy/db/pdf_registry.db`) or custom path; auto-create DB and schema on first use.
- **Operation log:** Every C/U/D writes to `operation_log` via `_log_operation` (operation, file_id, group_id, performed_at, performed_by, before_state, after_state, notes).

### Phase 2 — Config & file lifecycle

- **Students:** `add_student`, `get_student`, `list_students`.
- **Scan roots:** `add_scan_root`, `remove_scan_root`, `list_scan_roots`.
- **Register:** `register_file(path, ...)` — path must exist; infers `file_type` from `_raw_` prefix; optional doc_type, student_id, subject, metadata; raises `AlreadyRegisteredError` if path already registered.
- **Compress and register:** `compress_and_register(file_id_or_path, ...)` — register if missing, then move to `_raw_<name>`, call real `compress_pdf`, insert main + raw rows and relations when savings ≥ threshold; otherwise restore and mark main.
- **Scan:** `scan_for_new_files(roots=None, dry_run=False)` — walk roots (or configured), skip registered paths; for `_raw_` files register and link to main; for others run `compress_and_register`; populate `student_id` from root when set.

### Phase 3 — Read / update / delete

- **Read:** `get_file(file_id)`, `find_files(query=..., file_type=..., doc_type=..., student_id=..., subject=..., is_template=..., has_raw=...)`.
- **Update:** `update_metadata(file_id_or_path, ...)` — merge metadata; validate `subject` (english, math, science, chinese); log `update_metadata`. `rename_file`, `move_file` — disk + DB + log; raise `ValueError` if destination exists.
- **Delete:** `delete_file(file_id_or_path, keep_related=False, ...)` — snapshot relations and group members, log delete, remove from groups (clear anchor if needed), remove file from disk, delete row; cascade to raw when `keep_related=False`.
- **Open:** `open_file(file_id_or_path)` — resolve path; raise `FileNotFoundError` if missing; open via platform command (e.g. macOS `open`).

### Phase 4 — Relations & groups

- **Raw ↔ main:** `get_related_files(file_id)`, `link_files(source_id, target_id, relation_type)`, `unlink_files(source_id, target_id)`; `has_raw` kept in sync.
- **Template ↔ completion:** `link_to_template(completed_id, template_id, inherit_metadata=True)`, `unlink_template(completed_id)`, `get_template(file_id)`, `get_completions(template_id)`; validation (both main, template `is_template=True`, completed `is_template=False`, not already linked).
- **File groups:** `create_file_group`, `add_to_file_group` (main only), `remove_from_file_group`, `set_file_group_anchor`, `update_file_group_notes`, `get_file_group`, `list_file_groups`, `get_file_group_membership`, `delete_file_group`; `open_file_group(group_id)` opens anchor (raises `ConfigError` if no anchor).
- **Suggest groups:** `suggest_groups()` — main files with `doc_type='exam'`, `is_template=False`, and `metadata.exam_date`; group by (student_id, subject, exam_date); return `list[SuggestedGroup]` for groups of size ≥ 2.

### Phase 5 — Audit & CLI

- **Operation log query:** `get_operation_log(file_id=None, group_id=None, operation=None, since=None, log_id=None)` — optional filters; if `log_id` set return at most one entry (empty if not found); otherwise order by `performed_at ASC`; return `list[OperationRecord]` with parsed before_state/after_state.
- **CLI:** Entry point in `pdf_file_manager.py` (`if __name__ == "__main__"`). Global `--db`; subcommand `log` with `--file`, `--group`, `--operation`, `--since`, `--id`; `--help` on main and subcommands.

### Testing

- **Phase 1:** 6 tests (schema, custom/default DB path, operation log write).
- **Phase 2:** 14 tests (students, roots, register_file, compress_and_register, scan dry_run and full); uses DaydreamEdu fixture (copy to temp dir); real `compress_pdf`.
- **Phase 3:** 22 tests (get_file, find_files filters, update_metadata merge/validation, rename/move, delete with/without cascade, open_file); open_file subprocess mocked in test to avoid blocking dialog.
- **Phase 4:** 17 tests (get_related_files, link/unlink files, link_to_template/get_template/get_completions/unlink, validation, file group CRUD, suggest_groups, open_file_group).
- **Phase 5:** 8 tests (get_operation_log no filters + ordering, filters by file_id/operation/group_id/log_id/since; CLI --help and --db log --help).

All tests use a temporary DB and (where needed) temp dirs and the shared fixture; no real drive or production registry.
