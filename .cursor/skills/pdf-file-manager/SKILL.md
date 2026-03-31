---
name: pdf-file-manager
description: Use the AI Study Buddy `pdf_file_manager` utility for PDF registry and file-management work. Use this when the user asks whether PDFs are in the registry, wants files registered, scanned, linked, moved, renamed, grouped, or matched between GoodNotes and DaydreamEdu. Prefer the `PdfFileManager` Python API first, use MCP `pdf_*` tools second, and do not query the SQLite database directly.
---

# PDF File Manager

Use this skill for PDF registry work in `ai_study_buddy/utils/pdf_file_manager`.

## Core Rule

Do not read or write the registry through raw SQLite queries when answering user requests about registered files or performing registry operations.

Prefer, in order:

1. The Python utility in [pdf_file_manager.py](../../../ai_study_buddy/utils/pdf_file_manager/pdf_file_manager.py).
2. The MCP `pdf_*` tools when they are available in the session.

The SQLite file is an implementation detail. Use it only for low-level utility development on `pdf_file_manager` itself, not for normal registry lookups or mutations.

This preference is intentional: after repeated use, the direct Python utility has proven easier to inspect, less awkward to filter, and more reliable for nuanced registry work than going through MCP.

## Primary Entry Points

- Source of truth: [pdf_file_manager.py](../../../ai_study_buddy/utils/pdf_file_manager/pdf_file_manager.py)
- MCP wrapper: [pdf_file_manager_mcp.py](../../../ai_study_buddy/utils/pdf_file_manager/pdf_file_manager_mcp.py)
- MCP server docs: [MCP.md](../../../ai_study_buddy/utils/pdf_file_manager/MCP.md)
- Overview and conventions: [README.md](../../../ai_study_buddy/utils/pdf_file_manager/README.md)
- Full operation contract: [SPEC.md](../../../ai_study_buddy/utils/pdf_file_manager/SPEC.md)

## Lookup Workflow

For exact-path questions:

1. Call `PdfFileManager().get_file_by_path(path)`.
2. If direct Python access is unavailable, use MCP `pdf_get_file_by_path`.

For filename or metadata questions:

1. Call `PdfFileManager().find_files(...)`.
2. If direct Python access is unavailable, use MCP `pdf_find_files`.
3. Be explicit about whether a result is an exact-path match or only a same-name match elsewhere in the registry.

For scan-root or student context:

- Prefer the matching Python methods.
- Use `pdf_list_scan_roots` and `pdf_list_students` as fallback.

## Mutation Workflow

Prefer these supported operations instead of ad hoc filesystem or DB changes:

- Register one file: `PdfFileManager.register_file(...)`, fallback `pdf_register_file`
- Scan folders for new PDFs: `PdfFileManager.scan_for_new_files(...)`, fallback `pdf_scan_for_new_files`
- GoodNotes-safe compression and registration: `PdfFileManager.compress_and_register(... preserve_input=True)` when working under a `GoodNotes/` path, fallback `pdf_compress_and_register`
- Update classification or metadata: prefer `PdfFileManager.update_metadata(...)`, fallback `pdf_update_metadata`
- Link raw/main files: prefer `PdfFileManager.link_files(...)`, fallback `pdf_link_files`
- Link completed files to templates: prefer `PdfFileManager.link_to_template(...)`, fallback `pdf_link_to_template`
- Resolve and link GoodNotes templates: prefer `PdfFileManager.link_goodnotes_template_for_file(...)` or `PdfFileManager.link_goodnotes_templates_for_root(...)`, fallback MCP equivalents
- Rename, move, or delete registered files: use the corresponding Python API method first, or the matching `pdf_*` tool as fallback, so the registry stays in sync

Important sequencing rule:

- Do not run registration/scan and GoodNotes template-linking in parallel.
- `link_goodnotes_templates_for_root(...)` queries the registry for already-registered `main` files under the root. If a scan is still in progress, the linker may only see a partial subset and skip files that have not been committed to the registry yet.
- For GoodNotes capture flows, run in this order: scan/register first, then link templates, then verify the resulting registrations and links.

### Exam `unit` inference fallback (`题目` / `答案` / `作文`)

`scan_for_new_files(...)` currently auto-infers `metadata.unit` for `doc_type='book'`, but not for exam files. For Chinese exam folders, when a user expects per-file unit labels and they are missing, run a post-scan metadata pass on `main` files:

1. Filter to the intended scope (for example one exam folder, one student, or one batch).
2. Only update files where `metadata.unit` is missing/empty.
3. Infer from filename keywords:
   - `questions` (`题目`)
   - `answers` (`答案`)
   - `composition` (`作文`)
4. Write using `PdfFileManager.update_metadata(..., metadata={"unit": <value>})` (or MCP `pdf_update_metadata`).
5. Report coverage (updated count, already-set count, unmapped count) and list any unmapped files for manual review.

Use this fallback only when it matches user intent. Do not overwrite existing non-empty `metadata.unit` unless the user explicitly asks.

## GoodNotes vs DaydreamEdu

Keep this distinction clear in responses:

- A GoodNotes file may exist on disk but not be registered by that exact path.
- A matching DaydreamEdu `_c_` or `_raw_` file may already exist in the registry under a mirrored or book-organized folder.
- For GoodNotes paths, do not rename or move the original input during compression. Use the utility's GoodNotes-safe flow so the original remains in place and `_c_` mains are created alongside it.

## Response Discipline

- Say which supported interface you used: `PdfFileManager` or MCP tool.
- If the user asks whether files "exist in the registry," answer path-exact registration first.
- If you also find same-name matches elsewhere, call that out separately instead of conflating it with exact-path registration.
- If you need deeper behavior details, read only the relevant sections of [README.md](../../../ai_study_buddy/utils/pdf_file_manager/README.md), [MCP.md](../../../ai_study_buddy/utils/pdf_file_manager/MCP.md), or [SPEC.md](../../../ai_study_buddy/utils/pdf_file_manager/SPEC.md).
