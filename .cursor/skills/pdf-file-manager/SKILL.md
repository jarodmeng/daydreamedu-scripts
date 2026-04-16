---
name: pdf-file-manager
description: Use the AI Study Buddy `pdf_file_manager` utility (SQLite registry + append-only operation log) for PDF registry work—students/scan roots, scan/register/compress, metadata and file_type repair, raw↔main and template↔completion links, GoodNotes template resolution, file groups (including exams and books), book unit→answer-page mappings, coverage and audit queries. Prefer `PdfFileManager` in [pdf_file_manager.py](../../../ai_study_buddy/pdf_file_manager/pdf_file_manager.py); use MCP `pdf_*` tools when appropriate. Do not query the registry SQLite DB directly for normal work.
---

# PDF File Manager

Use this skill for registry-backed PDF work under [`ai_study_buddy/pdf_file_manager/`](../../../ai_study_buddy/pdf_file_manager/).

**What it is:** A local library (`PdfFileManager`) plus an MCP server that keep **`pdf_files`**, relations, **`file_groups`**, and **`book_answer_mappings`** aligned with on-disk paths. Every mutation is recorded in **`operation_log`**. The package tracks exams, worksheets, books, book exercises, activities, practice, notes, and templates (with optional completions), including **first-class book unit → answer-page ranges** (not stored in `pdf_files.metadata`).

**Current package version** is stated in [README.md](../../../ai_study_buddy/pdf_file_manager/README.md) (header). Behaviour details: [SPEC.md](../../../ai_study_buddy/pdf_file_manager/SPEC.md), [DATA_MODEL.md](../../../ai_study_buddy/pdf_file_manager/DATA_MODEL.md), [ARCHITECTURE.md](../../../ai_study_buddy/pdf_file_manager/ARCHITECTURE.md).

## Core rule

Do **not** read or write the registry with raw SQLite when answering questions about registered files or performing registry operations.

Prefer, in order:

1. **`PdfFileManager`** in [pdf_file_manager.py](../../../ai_study_buddy/pdf_file_manager/pdf_file_manager.py).
2. **MCP `pdf_*` tools** from [pdf_file_manager_mcp.py](../../../ai_study_buddy/pdf_file_manager/pdf_file_manager_mcp.py) when the session exposes them.

The SQLite file and schema are implementation details. Touch them directly only when **developing or debugging `pdf_file_manager` itself**, not for normal lookups or mutations.

**Why Python first:** After repeated use, the direct API is easier to filter, script, and combine (loops, batch fixes, imports) than chaining many MCP calls—especially for nuanced registry work.

**Built-in CLI:** The old package CLI was **removed**; automation should use **`PdfFileManager`** or MCP. See [README.md § Implemented interfaces](../../../ai_study_buddy/pdf_file_manager/README.md#implemented-interfaces).

## Default paths and environment

| Concern | Resolution |
|--------|------------|
| **Registry DB** | Default `ai_study_buddy/db/pdf_registry.db` (repo-relative). Override with **`PDF_REGISTRY_PATH`** or MCP server **`--db`**. |
| **DaydreamEdu root on disk** | Not in Git. **`DAYDREAMEDU_ROOT`** (highest priority) or **`local_daydreamedu_root.txt`** under `ai_study_buddy/` (gitignored; copy from [`local_daydreamedu_root.example.txt`](../../../ai_study_buddy/local_daydreamedu_root.example.txt)). In code: **`resolve_daydreamedu_root()`** in [`ai_study_buddy/files/roots.py`](../../../ai_study_buddy/files/roots.py). See [ARCHITECTURE.md § Local DaydreamEdu root](../../../ai_study_buddy/pdf_file_manager/ARCHITECTURE.md#local-daydreamedu-root-not-in-git). |
| **GoodNotes root on disk** | **`GOODNOTES_ROOT`** or **`local_goodnotes_root.txt`** under `ai_study_buddy/` (gitignored; copy from [`local_goodnotes_root.example.txt`](../../../ai_study_buddy/local_goodnotes_root.example.txt)), else sibling **`…/GoodNotes`** next to the resolved DaydreamEdu root when that directory exists. In code: **`resolve_goodnotes_root()`** in [`ai_study_buddy/files/roots.py`](../../../ai_study_buddy/files/roots.py). See [ARCHITECTURE.md § Local GoodNotes root](../../../ai_study_buddy/pdf_file_manager/ARCHITECTURE.md#local-goodnotes-root-not-in-git). |

## Primary entry points

| Artifact | Role |
|----------|------|
| [pdf_file_manager.py](../../../ai_study_buddy/pdf_file_manager/pdf_file_manager.py) | **Source of truth** for behaviour: `PdfFileManager`, path inference, scan/compress, groups, book mappings. |
| [pdf_file_manager_mcp.py](../../../ai_study_buddy/pdf_file_manager/pdf_file_manager_mcp.py) | MCP tool implementations; maps to `PdfFileManager` (one manager instance per tool call). |
| [pdf_file_manager_mcp_server.py](../../../ai_study_buddy/pdf_file_manager/pdf_file_manager_mcp_server.py) | Runnable FastMCP entrypoint (`--db`, `--tool-mode`, `--transport`, etc.). |
| [MCP.md](../../../ai_study_buddy/pdf_file_manager/MCP.md) | Transports, **`readonly` vs `default`** tool modes, metadata/group/mapping notes. |
| [README.md](../../../ai_study_buddy/pdf_file_manager/README.md) | Overview, full **`pdf_*` tool list**, GoodNotes scan rules, backup pointers. |
| [SPEC.md](../../../ai_study_buddy/pdf_file_manager/SPEC.md) | Operation contract, scan/compress edge cases, rename/move semantics. |
| [DATA_MODEL.md](../../../ai_study_buddy/pdf_file_manager/DATA_MODEL.md) | Fields, dataclasses, **exam group completeness** (compulsory `metadata.unit`). |
| [TESTING.md](../../../ai_study_buddy/pdf_file_manager/TESTING.md) | How tests are organised; when to add tests for registry changes. |
| [scripts/validate_pdf_registry_integrity.py](../../../ai_study_buddy/pdf_file_manager/scripts/validate_pdf_registry_integrity.py) | Reproducible audits: `unknown` doc types, missing `student_id` in student-scoped paths, raw/main metadata drift. |
| [scripts/backup_pdf_registry.py](../../../ai_study_buddy/pdf_file_manager/scripts/backup_pdf_registry.py) | Optional cloud backup of the gitignored DB (see README). |

## MCP server

Run from repo root (paths as in [README.md](../../../ai_study_buddy/pdf_file_manager/README.md)):

```bash
python3 -m ai_study_buddy.pdf_file_manager.pdf_file_manager_mcp_server --db /path/to/pdf_registry.db
```

- **`--tool-mode readonly`:** read-only tools only—preferred when the agent should inspect but not mutate ([MCP.md](../../../ai_study_buddy/pdf_file_manager/MCP.md)).
- **`--tool-mode default` (default):** readonly + safe registry mutations + filesystem mutations (scan, register, compress, rename, move, delete, open).
- Responses are JSON-shaped: success **`{ "ok": true, "result": ... }`**, structured errors **`{ "ok": false, "error": { "type", "message" } }`**.

### Tool buckets (names only; parameters match Python APIs)

- **Readonly:** `pdf_get_file`, `pdf_find_files`, `pdf_get_file_by_path`, `pdf_list_students`, `pdf_list_scan_roots`, `pdf_get_related_files`, `pdf_get_template`, `pdf_get_completions`, `pdf_get_file_group`, `pdf_list_file_groups`, `pdf_get_book_answer_mapping`, `pdf_list_book_answer_mappings`, `pdf_get_file_group_membership`, `pdf_suggest_groups`, `pdf_get_operation_log`, `pdf_report_coverage`, **`pdf_resolve_goodnotes_template`**
- **Safe mutations (no path I/O beyond DB):** students/scan roots, `pdf_update_metadata`, groups (`pdf_create_file_group`, `pdf_add_to_file_group`, `pdf_remove_from_file_group`, `pdf_set_file_group_anchor`), book mappings (`pdf_set_book_answer_mapping`, `pdf_delete_book_answer_mapping`), template and raw/main links (`pdf_link_to_template`, `pdf_unlink_template`, `pdf_link_files`, `pdf_unlink_files`), GoodNotes template link helpers
- **Filesystem mutations:** `pdf_scan_for_new_files`, `pdf_register_file`, `pdf_compress_and_register`, `pdf_rename_file`, `pdf_move_file`, `pdf_delete_file`, `pdf_open_file`, `pdf_open_file_group`

Authoritative duplicate list: [README.md § MCP](../../../ai_study_buddy/pdf_file_manager/README.md#mcp).

## Python API surface (and gaps vs MCP)

Use **`PdfFileManager`** for everything MCP exposes, plus **Python-only** helpers when you need them:

- **`repair_main_raw_metadata_drift()`** — batch-fix document-level drift between linked raw/main rows ([CHANGELOG v0.2.6](../../../ai_study_buddy/pdf_file_manager/CHANGELOG.md)).
- **`import_book_answer_mappings_from_json(...)`** — bulk import validated mapping JSON (no MCP wrapper).
- **`ensure_book_group_from_path`**, **`delete_file_group`**, **`update_file_group_notes`** — group lifecycle/edits not exposed as MCP tools.
- **`link_template_by_paths`**, **`ensure_student`**, **`ensure_scan_root`** — convenience wrappers.
- **`PdfFileManager.find_leaf_dirs`** — static helper used with coverage analysis (MCP exposes **`pdf_report_coverage`** / `report_coverage` instead).

## Lookup workflow

- **By UUID:** `get_file(file_id)` → MCP `pdf_get_file`.
- **By absolute path:** `get_file_by_path(path)` → `pdf_get_file_by_path`.
- **Search:** `find_files(query=..., file_type=..., doc_type=..., student_id=..., subject=..., is_template=..., has_raw=...)` → `pdf_find_files`. Treat **`query`** as case-insensitive substring on **`name`** only ([SPEC.md](../../../ai_study_buddy/pdf_file_manager/SPEC.md)).
- **Relations:** `get_related_files`, `get_template`, `get_completions` (and MCP equivalents).
- **Group membership:** `get_file_group_membership` / `pdf_get_file_group_membership`.

Be explicit: **exact-path registration** vs **same-name match elsewhere** in the registry.

## Scan, register, and compress

- **`scan_for_new_files`** walks **configured scan roots** or an explicit **`roots=[...]`** override. It picks up only **direct `*.pdf` children** of each root—**no recursion**; pass nested folders explicitly if needed ([README.md](../../../ai_study_buddy/pdf_file_manager/README.md), [SPEC.md](../../../ai_study_buddy/pdf_file_manager/SPEC.md)).
- **`dry_run=True`:** no disk/DB writes; returned rows use **the same path inference** as a real run (not placeholder `unknown` everywhere) ([CHANGELOG v0.2.8](../../../ai_study_buddy/pdf_file_manager/CHANGELOG.md)).
- **Student assignment:** configured **`scan_root.student_id`** wins; else infer from a path segment matching **`students.email`** ([ARCHITECTURE.md](../../../ai_study_buddy/pdf_file_manager/ARCHITECTURE.md)).
- **Book folders:** Under `.../Book/<book name>/...`, scan sets `doc_type='book'`, infers **`metadata.unit`** where possible, and syncs a **`group_type='book'`** group labelled with the book name ([SPEC.md](../../../ai_study_buddy/pdf_file_manager/SPEC.md)).
- **GoodNotes:** Paths under a **`GoodNotes/`** segment use **`preserve_input=True`** for scan-driven compress and for **`compress_and_register`**—originals stay put; **`_c_`** mains are created alongside and linked raw↔main ([README.md](../../../ai_study_buddy/pdf_file_manager/README.md)).

## Metadata and `update_metadata`

- **`pdf_update_metadata` / `update_metadata`** merge **`metadata`** keys; they do **not** replace the entire JSON object ([MCP.md](../../../ai_study_buddy/pdf_file_manager/MCP.md)).
- Optional **`file_type`** (`main` / `raw` / `unknown`) supports promotion/repair without re-running compression ([CHANGELOG v0.2.6](../../../ai_study_buddy/pdf_file_manager/CHANGELOG.md)).
- Linked **raw/main** pairs: document-level fields are kept in **parity** on update; a single update on a linked main can propagate to the raw ([README.md § Raw/main parity](../../../ai_study_buddy/pdf_file_manager/README.md)).

## File groups, templates, and GoodNotes

- **Exam grouping:** create/list groups, add mains, set anchor—`create_file_group` / `add_to_file_group` / `set_file_group_anchor` (and MCP). **`suggest_groups` / `pdf_suggest_groups`** proposes exam groupings from metadata.
- **Template ↔ completion:** `link_to_template` / `unlink_template`; MCP `pdf_link_to_template`, `pdf_unlink_template`.
- **GoodNotes → DaydreamEdu:** **`resolve_goodnotes_template_path`** / **`pdf_resolve_goodnotes_template`** resolves a GoodNotes main path to the mirrored **`_c_`** template path. **`link_goodnotes_template_for_file`** and **`link_goodnotes_templates_for_root`** resolve and link; they **do not auto-register** templates that exist only on disk ([README.md](../../../ai_study_buddy/pdf_file_manager/README.md), [MCP.md](../../../ai_study_buddy/pdf_file_manager/MCP.md)).

**Sequencing:** Do **not** run **scan/register** and **`link_goodnotes_templates_for_root`** in parallel—the linker only sees files **already committed** to the registry. Order: **scan/register → link templates → verify**.

## Book answer-page mappings

Coverage for **`doc_type='book'`** units lives in **`book_answer_mappings`** (unit file, answer file, inclusive page range, optional split-page flags, provenance)—**not** in `pdf_files.metadata` ([DATA_MODEL.md](../../../ai_study_buddy/pdf_file_manager/DATA_MODEL.md), [MCP.md](../../../ai_study_buddy/pdf_file_manager/MCP.md)).

- Read: `get_book_answer_mapping`, `list_book_answer_mappings` / MCP `pdf_get_book_answer_mapping`, `pdf_list_book_answer_mappings`.
- Write: `set_book_answer_mapping`, `delete_book_answer_mapping` / MCP `pdf_set_book_answer_mapping`, `pdf_delete_book_answer_mapping`.
- Both files must be registered **`main`** rows with **`doc_type='book'`**. As of **v0.2.9**, mappings may span **different** `group_type='book'` groups ([CHANGELOG](../../../ai_study_buddy/pdf_file_manager/CHANGELOG.md)).
- Bulk import: Python **`import_book_answer_mappings_from_json`** only.

## Diagnostics and audit

- **`report_coverage` / `pdf_report_coverage`:** leaf directories vs scan roots vs registry ([README.md](../../../ai_study_buddy/pdf_file_manager/README.md)).
- **`get_operation_log` / `pdf_get_operation_log`:** filter by file, group, operation type, since, or single `log_id`.
- **`scripts/validate_pdf_registry_integrity.py`:** offline integrity pass ([README.md](../../../ai_study_buddy/pdf_file_manager/README.md)).

## Mutation workflow (quick map)

Prefer these over ad hoc `mv` + manual DB edits:

| Task | Python | MCP fallback |
|------|--------|----------------|
| Register one file | `register_file` | `pdf_register_file` |
| Scan folders | `scan_for_new_files` | `pdf_scan_for_new_files` |
| GoodNotes-safe compress | `compress_and_register(..., preserve_input=True)` | `pdf_compress_and_register` |
| Classify / metadata / `file_type` | `update_metadata` | `pdf_update_metadata` |
| Raw ↔ main | `link_files` / `unlink_files` | `pdf_link_files` / `pdf_unlink_files` |
| Completion ↔ template | `link_to_template` / `unlink_template` | `pdf_link_to_template` / `pdf_unlink_template` |
| GoodNotes template link | `link_goodnotes_template_for_file`, `link_goodnotes_templates_for_root` | MCP equivalents |
| Rename / move / delete (registry + disk rules) | `rename_file`, `move_file`, `delete_file` | `pdf_rename_file`, `pdf_move_file`, `pdf_delete_file` |
| Book answer range | `set_book_answer_mapping`, `delete_book_answer_mapping` | MCP equivalents |

**Rename nuance:** If the file was already renamed on disk, **`rename_file`** can sync **`path` / `name`** (and **`size_bytes`** when the target exists as a file) without moving again—see [SPEC.md](../../../ai_study_buddy/pdf_file_manager/SPEC.md) § `rename_file`. **`rename_file` does not automatically rename the paired `_raw_`**—handle separately if needed.

---

## Domain workflows (metadata `unit` and naming)

The following are **operational conventions** for agents; authoritative completeness rules remain in [DATA_MODEL.md — Exam group completeness](../../../ai_study_buddy/pdf_file_manager/DATA_MODEL.md#exam-group-completeness-compulsory-metadataunit).

### Exam `unit` inference fallback (`题目` / `答案` / `作文`)

`scan_for_new_files` auto-infers **`metadata.unit`** for `doc_type='book'`, not for all exam files. For Chinese exam folders when per-file **`unit`** is missing, post-scan on **`main`** files only:

1. Scope to the intended folder/batch.
2. Only rows with missing/empty **`metadata.unit`**.
3. Infer from filename keywords: `questions` (`题目`), `answers` (`答案`), `composition` (`作文`).
4. `update_metadata(..., metadata={"unit": <value>})` or `pdf_update_metadata`.
5. Report coverage and unmapped files.

Do **not** overwrite existing **`unit`** unless the user asks.

### Math exam-group `unit` (`Paper 1` / `Paper 2`)

For math exams in an **`exam`** group with missing **`unit`**: `(Paper 1)` → `Paper 1`, `(Paper 2)` → `Paper 2`. Restrict to **`file_type='main'`**, exam **`group_type`**, fill empty **`unit`** only unless asked.

### Science booklets (`(Booklet A)` / `(Booklet B)`)

Canonical **`metadata.unit`:** `Booklet A`, `Booklet B` (filename markers **`(Booklet A)`** / **`(Booklet B)`**). **`update_metadata` on a linked main copies metadata to the paired raw**—usually update mains only. Align markers on **`_c_` / `_raw_`** stems. On case-insensitive APFS, use a **short intermediate rename** when fixing casing-only changes.

### English exam naming and `unit` (`.p5.english.<ddd>`)

Prefer **`_c_<Title>.p5.english.<ddd>.pdf`** / **`_raw_<Title>.p5.english.<ddd>.pdf`** with a **single parenthetical tag** in `<Title>`; set **`metadata.unit`** to the **literal text inside the parentheses** (no `()`). Official vs practice = separate **`exam`** groups; keep filename prefix consistent with the group label.

### Exam group completeness (compulsory `unit`)

When checking if an **`exam`** group is complete, use **compulsory** `metadata.unit` values from non-template **`main`** members only. Summary:

- **chinese:** `questions`, `answers` — `composition` optional
- **math:** `Paper 1`, `Paper 2`
- **english:** `Paper 1`, `Paper 2 Booklet A`, `Paper 2 Booklet B` — `Oral`, `Listening Comprehension` optional
- **science:** `Booklet A`, `Booklet B`

Full table: [DATA_MODEL.md](../../../ai_study_buddy/pdf_file_manager/DATA_MODEL.md).

## GoodNotes vs DaydreamEdu

- A GoodNotes PDF may exist on disk but **not** be registered at that path.
- A DaydreamEdu **`_c_` / `_raw_`** file may already be registered under a mirrored path.
- For GoodNotes inputs, **do not** rename/move the original during compression—use the GoodNotes-safe flow above.

## Response discipline

- State whether you used **`PdfFileManager`** or **MCP `pdf_*`**.
- For “in the registry?”: answer **path-exact** registration first; list **same-name** matches separately.
- For deeper behaviour, cite the relevant section of [README.md](../../../ai_study_buddy/pdf_file_manager/README.md), [MCP.md](../../../ai_study_buddy/pdf_file_manager/MCP.md), or [SPEC.md](../../../ai_study_buddy/pdf_file_manager/SPEC.md) rather than guessing.
