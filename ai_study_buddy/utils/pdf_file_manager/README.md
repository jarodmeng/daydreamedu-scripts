# pdf_file_manager

**Version: v0.2.7**

A local utility that keeps a SQLite registry of PDF files in the study archive. It tracks exams, worksheets, books, book exercises, activities, notes, and templates (with optional completed variants), keeps on-disk paths and database records in sync, and now supports first-class book unit → answer-page mappings inside `group_type='book'` collections. You can scan one or more folders for new PDFs, optionally compress and archive originals, classify documents by type and metadata, group multi-file documents (e.g. exam booklets or book folders), link completions to templates, and query or import validated book-answer coverage. Every state-mutating operation is recorded in an append-only operation log.

**Typical workflow:** Add scan roots (e.g. Google Drive folders) and students → run **scan** on the exact folder you want to ingest → **classify** with `doc_type`, `subject`, and metadata → use **suggest-groups** for exams, or let scan infer/group `.../Book/<book name>/...` folders as books, then link templates as needed. Only main files are ingested by the pipeline; raw archives are kept for traceability.

**DaydreamEdu folder on disk:** Set `DAYDREAMEDU_ROOT` or create `local_daydreamedu_root.txt` (gitignored; copy from [`local_daydreamedu_root.example.txt`](./local_daydreamedu_root.example.txt)). Call **`resolve_daydreamedu_root()`** in [`pdf_file_manager.py`](./pdf_file_manager.py) to read it. See [ARCHITECTURE.md § Local DaydreamEdu root](./ARCHITECTURE.md#local-daydreamedu-root-not-in-git).

**Raw/main parity:** Linked raw and main records represent the same logical document in two file forms. Document-level metadata such as `subject`, `doc_type`, `student_id`, `is_template`, and core metadata fields is expected to stay in sync across the pair. The manager now enforces that parity during metadata updates and includes a repair helper for older drift.

**Student inference:** When `student_id` is not supplied explicitly by a configured scan root or direct API call, the manager can now fall back to matching registered `students.email` path segments so student-scoped scans do not silently leave `student_id` unset.

**Integrity validation:** Use [`scripts/validate_pdf_registry_integrity.py`](./scripts/validate_pdf_registry_integrity.py) to reproducibly audit the registry for lingering `doc_type='unknown'` files, missing `student_id` in student-scoped folders, and raw/main invariant metadata drift.

**Machine interface:** The preferred machine-facing contract is now the MCP wrapper in [`pdf_file_manager_mcp.py`](./pdf_file_manager_mcp.py) plus the runnable FastMCP entrypoint in [`pdf_file_manager_mcp_server.py`](./pdf_file_manager_mcp_server.py). The Python library in [`pdf_file_manager.py`](./pdf_file_manager.py) remains the source of truth for business logic. The old built-in CLI has been removed to avoid maintaining a second, partial interface.

---

## Type dimensions

Every file has two independent attributes: **file_type** (main vs raw vs unknown — which file is the primary one for ingestion) and **doc_type** (exam, worksheet, book, book_exercise, activity, practice, notes, unknown — what kind of content). The former drives processing and naming; the latter drives metadata shape and how the ingestion pipeline routes the file.

For a quick reference on file-level metadata vs group-level fields (including `metadata.unit`, `label`, `group_type`, and legacy `role`), see [`DATA_MODEL.md`](./DATA_MODEL.md).

---

## Docs

| Doc | Contents |
|-----|----------|
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Source folder layout, schema, file naming, metadata, integrations |
| [DATA_MODEL.md](./DATA_MODEL.md) | File metadata fields, group fields, unit-vs-group semantics, returned data classes |
| [MCP.md](./MCP.md) | MCP server transports, tool modes, and client connection examples |
| [SPEC.md](./SPEC.md) | API, MCP contract, operation contract, implementation status |
| [TESTING.md](./TESTING.md) | Test levels, test data strategy, when to add tests |
| [DECISIONS.md](./DECISIONS.md) | Decision log |
| [CHANGELOG.md](./CHANGELOG.md) | Version history |

Parent: [L4_INGESTION_PIPELINE](../../docs/L4_INGESTION_PIPELINE.md) — Utilities section.

---

## Implemented interfaces

### Python API

The full implemented surface lives in [`pdf_file_manager.py`](./pdf_file_manager.py) via `PdfFileManager`.

### MCP

The MCP layer currently exposes:

- Read-only tools: `pdf_get_file`, `pdf_find_files`, `pdf_get_file_by_path`, `pdf_list_students`, `pdf_list_scan_roots`, `pdf_get_related_files`, `pdf_get_template`, `pdf_get_completions`, `pdf_get_file_group`, `pdf_list_file_groups`, `pdf_get_book_answer_mapping`, `pdf_list_book_answer_mappings`, `pdf_get_file_group_membership`, `pdf_suggest_groups`, `pdf_get_operation_log`, `pdf_report_coverage`
- Safe mutations: `pdf_add_student`, `pdf_add_scan_root`, `pdf_remove_scan_root`, `pdf_update_metadata`, `pdf_create_file_group`, `pdf_add_to_file_group`, `pdf_remove_from_file_group`, `pdf_set_file_group_anchor`, `pdf_set_book_answer_mapping`, `pdf_delete_book_answer_mapping`, `pdf_link_to_template`, `pdf_link_goodnotes_template_for_file`, `pdf_link_goodnotes_templates_for_root`, `pdf_unlink_template`, `pdf_link_files`, `pdf_unlink_files`
- File-system mutations: `pdf_scan_for_new_files`, `pdf_register_file`, `pdf_compress_and_register`, `pdf_rename_file`, `pdf_move_file`, `pdf_delete_file`, `pdf_open_file`, `pdf_open_file_group`

GoodNotes-specific support:

- `compress_and_register(..., preserve_input=True)` allows GoodNotes-safe compression by keeping originals untouched and creating `_c_` mains alongside them, linked as raw↔main.
- `scan_for_new_files` automatically uses `preserve_input=True` for any path under a `GoodNotes/` segment.
- `scan_for_new_files` scans only direct `*.pdf` children of each supplied root. It does not recurse into nested subfolders; pass nested folders explicitly if you want them processed.
- `resolve_goodnotes_template_path` (and the MCP tool `pdf_resolve_goodnotes_template`) resolve GoodNotes main paths to the corresponding DaydreamEdu `_c_` template/source paths based on folder mirroring and naming conventions.
- `link_goodnotes_template_for_file` and `link_goodnotes_templates_for_root` resolve and link DaydreamEdu templates for registered GoodNotes mains. They do not auto-register missing resolved templates; they fail clearly instead.

Run the MCP server with:

```bash
python3 ai_study_buddy/utils/pdf_file_manager/pdf_file_manager_mcp_server.py --db /path/to/pdf_registry.db
```

## Database backup

The registry DB (`ai_study_buddy/db/pdf_registry.db`) is gitignored. To back it up to the cloud **without** committing it to GitHub, copy it into a folder that syncs to the cloud (e.g. Google Drive on your Mac):

1. **Default backup location:** `~/genrong.meng@gmail.com - Google Drive/My Drive/DaydreamEdu/db`. No setup needed unless you want a different destination (set `PDF_REGISTRY_BACKUP_DIR` or use `--dest`).

2. **Run the backup script** from the repo root or from `ai_study_buddy/`:
   ```bash
   python3 ai_study_buddy/utils/pdf_file_manager/scripts/backup_pdf_registry.py
   ```
   Use `--timestamp` to keep dated copies (e.g. `pdf_registry_2025-03-10_14-30-00+0800.db`) instead of overwriting. Backup log entries and timestamped filenames use Singapore time.

Once the file is inside your Google Drive folder, it will sync to the cloud automatically.

**Run backup on wake (optional)**  
To back up automatically when the Mac wakes from sleep (only if the DB changed), use [sleepwatcher](https://formulae.brew.sh/formula/sleepwatcher):

```bash
brew install sleepwatcher
./ai_study_buddy/utils/pdf_file_manager/scripts/install_run_on_wake.sh
```

This installs a user LaunchAgent that runs the backup after each wake. The backup script still skips when unchanged. To remove: `launchctl unload ~/Library/LaunchAgents/com.daydreamedu.pdf-registry-backup-on-wake.plist` and edit or remove `~/.wakeup`.
