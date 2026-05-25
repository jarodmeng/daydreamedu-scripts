# pdf_file_manager

**Version: v0.3.21**

A local utility that keeps a SQLite registry of PDF files in the study archive. It tracks exams, exercises, books, activities, notes, and templates (with optional completed variants), keeps on-disk paths and database records in sync, and supports first-class book unit → answer-page mappings inside `group_type='book'` collections. You can scan one or more folders for new PDFs, optionally compress and archive originals, classify documents by type and metadata, group multi-file documents (e.g. exam booklets or book folders), link completions to templates, and query or import validated book-answer coverage. Every state-mutating operation is recorded in an append-only operation log.

**Typical workflow:** Add scan roots (e.g. Google Drive folders) and students → run **scan** on the exact folder you want to ingest → **classify** with `doc_type`, `subject`, and metadata → use **suggest-groups** for exams, or let scan infer/group `.../Book/<book name>/...` folders as books, then link templates as needed. For books, grouped members are canonical general-scope templates; student mirror files are represented via template links, not duplicate group members. Only main files are ingested by the pipeline; raw archives are kept for traceability.

**DaydreamEdu folder on disk:** Set `DAYDREAMEDU_ROOT` or create `ai_study_buddy/local_daydreamedu_root.txt` (gitignored; copy from [`../local_daydreamedu_root.example.txt`](../local_daydreamedu_root.example.txt)). Call **`resolve_daydreamedu_root()`** in [`../files/roots.py`](../files/roots.py) to read it. See [ARCHITECTURE.md § Local DaydreamEdu root](./ARCHITECTURE.md#local-daydreamedu-root-not-in-git).

**GoodNotes folder on disk:** Set `GOODNOTES_ROOT` or create `ai_study_buddy/local_goodnotes_root.txt` (gitignored; copy from [`../local_goodnotes_root.example.txt`](../local_goodnotes_root.example.txt)), or rely on sibling discovery when `GoodNotes` sits next to the resolved DaydreamEdu root. Call **`resolve_goodnotes_root()`** in [`../files/roots.py`](../files/roots.py). See [ARCHITECTURE.md § Local GoodNotes root](./ARCHITECTURE.md#local-goodnotes-root-not-in-git).

**Raw/main parity:** Linked raw and main records represent the same logical document in two file forms. Document-level metadata such as `subject`, `doc_type`, `student_id`, `is_template`, and core metadata fields is expected to stay in sync across the pair. The manager now enforces that parity during metadata updates and includes a repair helper for older drift.

**Student inference:** When `student_id` is not supplied explicitly by a configured scan root or direct API call, the manager can now fall back to matching registered `students.email` path segments so student-scoped scans do not silently leave `student_id` unset. New scan roots created without `student_id` now also auto-infer and persist `student_id` from a unique matching email segment in the root path.

**Integrity validation:** Use [`scripts/validate_pdf_registry_integrity.py`](./scripts/validate_pdf_registry_integrity.py) to reproducibly audit the registry for missing `student_id` in student-scoped folders, raw/main invariant metadata drift, and other hygiene checks.

**Machine interface:** The supported machine-facing contract is the Python API in [`pdf_file_manager.py`](./pdf_file_manager.py) via `PdfFileManager`. The old built-in CLI has been removed to avoid maintaining a second, partial interface.

---

## Type dimensions

Every file has two independent attributes: **file_type** (main vs raw vs unknown — which file is the primary one for ingestion) and **doc_type** (`exam`, `exercise`, `book`, `activity`, `note` — what kind of content). The former drives processing and naming; the latter drives metadata shape and how the ingestion pipeline routes the file.
`metadata.unit` is enforced as a **book-only** metadata key (`doc_type='book'`).

For a quick reference on file-level metadata vs group-level fields (including `metadata.unit`, `label`, `group_type`, and legacy `role`), see [`DATA_MODEL.md`](./DATA_MODEL.md).

### Name fields (`name` vs `normal_name`)

- `PdfFile.name` is the exact on-disk basename (for example `_c_P5 Science WA2 (Booklet A).pdf`).
- `PdfFile.normal_name` is a computed display stem (for example `P5 Science WA2 (Booklet A)`), normalized by:
  - iterative prefix stripping: `_raw_`, `_c_`, `raw_`, `c_`
  - extension removal via `Path(...).stem`
- Shared helper: `normalize_pdf_display_name(name_or_path)` in `pdf_file_manager.py`.

---

## Docs

| Doc | Contents |
|-----|----------|
| [files package](../files/README.md) | Root resolution and leaf-folder traversal (`ai_study_buddy.files`): [SPEC](../files/SPEC.md), [TESTING](../files/TESTING.md), [CHANGELOG](../files/CHANGELOG.md) |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | Source folder layout, schema, file naming, metadata, integrations |
| [DATA_MODEL.md](./DATA_MODEL.md) | File metadata fields, group fields, unit-vs-group semantics, returned data classes |
| [SPEC.md](./SPEC.md) | API, operation contract, implementation status |
| [TESTING.md](./TESTING.md) | Test levels, test data strategy, when to add tests |
| [DECISIONS.md](./DECISIONS.md) | Decision log |
| [CHANGELOG.md](./CHANGELOG.md) | Version history |

Parent: [L4_INGESTION_PIPELINE](../../docs/L4_INGESTION_PIPELINE.md) — Utilities section.

---

## Implemented interfaces

### Python API

The full implemented surface lives in [`pdf_file_manager.py`](./pdf_file_manager.py) via `PdfFileManager`.

**Completion series (v0.3.19+):** derived ordering of distinct completion `file_id`s per `(student_id, template_file_id)` — no new SQLite tables. Module [`completion_series.py`](./completion_series.py); methods `get_completion_series`, `get_completion_series_for_file`, `get_completion_series_member`, `completion_series_id`, `next_attempt_sequence_for_completion`. Group id `"<student_slug>::<template_file_id>"` matches marking `template_attempt_group_id`. Order: `pdf_files.added_at` ASC, then resolved path. Used by marking writer, `files` inventory enrichment, and Student File Browser attempt chip. Design: [proposal 15](./docs/proposals/15-completion-series-derived.md), [L4 completion framework](../docs/L4_COMPLETION_MARKING_FRAMEWORK.md#completion-series-registry-derived).

**Goodnotes document timestamps (v0.3.21+):** read-only lookup from the local macOS Goodnotes metadata DBs for registered `GOODNOTES_ROOT` mains. Methods `get_goodnotes_document_timestamps_for_file(file_id)` and `get_goodnotes_document_timestamps_for_path(path)` return `GoodnotesDocumentMatch`, including match status, Goodnotes document id/name, Goodnotes app-folder path, and `created_at` / `updated_at` / `last_modified` timestamps. Matching supports exact backup stem, one leading underscore restored (`c_foo.pdf` -> `_c_foo`), and deterministic raw-source fallback for compressed `_c_` mains. Design: [proposal 16](./docs/proposals/16-goodnotes-document-timestamps.md), [L4 Goodnotes files](../docs/L4_FILE_FRAMEWORK.md#goodnotes-files).

### Import and invocation

Use package-style imports:

```python
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
```

or package re-exports:

```python
from ai_study_buddy.pdf_file_manager import PdfFileManager
```

The legacy bare import style (`from pdf_file_manager import ...`) is deprecated.

For scripts, prefer module invocation from the repo root (example):

```bash
python3 -m ai_study_buddy.pdf_file_manager.scripts.validate_pdf_registry_integrity
```

GoodNotes-specific support:

- `compress_and_register(..., preserve_input=True)` allows GoodNotes-safe compression by keeping originals untouched and creating `_c_` mains alongside them, linked as raw↔main.
- `scan_for_new_files` automatically uses `preserve_input=True` for any path under a `GoodNotes/` segment.
- `scan_for_new_files` scans only direct `*.pdf` children of each supplied root. It does not recurse into nested subfolders; pass nested folders explicitly if you want them processed.
- With `dry_run=True`, each returned `PdfFile` reflects path inference (subject, `doc_type`, metadata, etc.) as if the scan had run for real. When `roots=[...]` is passed, paths that match a configured scan root still receive that root’s `student_id`.
- `resolve_goodnotes_template_path` resolves GoodNotes main paths to DaydreamEdu `_c_` template/source paths in the mirrored **general-scope** folder only (templates are policy-constrained to general scope; student-scope folders are not searched).
- `link_goodnotes_template_for_file` and `link_goodnotes_templates_for_root` resolve and link DaydreamEdu templates for registered GoodNotes mains. They do not auto-register missing resolved templates; they fail clearly instead.
- `scan_for_new_files` (v0.3.20+) with `auto_link_goodnotes=True` (default) runs a **non-aborting** GoodNotes template link after each new `c_` / `_c_` main is registered under a `GoodNotes/` path; see `ScanResult.template_link`. Unresolved stems (e.g. GoodNotes `&` vs DaydreamEdu `-`) are recorded in `template_link.message` and do not stop the scan. Use `auto_link_goodnotes=False` or `link_goodnotes_templates_for_root` for a full-folder pass.

## Database backup

The registry DB (`ai_study_buddy/db/pdf_registry.db`) is gitignored. To back it up to the cloud **without** committing it to GitHub, copy it into a folder that syncs to the cloud (e.g. Google Drive on your Mac):

1. **Default backup location:** `<DaydreamEdu root>/db`, where the DaydreamEdu root comes from `DAYDREAMEDU_ROOT` or the first path line in `ai_study_buddy/local_daydreamedu_root.txt` (see `resolve_daydreamedu_root()`). Override with `PDF_REGISTRY_BACKUP_DIR` or `--dest` if needed.

2. **Run the backup script** from the repo root or from `ai_study_buddy/`:
   ```bash
   python3 -m ai_study_buddy.pdf_file_manager.scripts.backup_pdf_registry
   ```
   Use `--timestamp` to keep dated copies (e.g. `pdf_registry_2025-03-10_14-30-00+0800.db`) instead of overwriting. Backup log entries and timestamped filenames use Singapore time.

3. **Optional retention tiering (recommended):**
   ```bash
   python3 -m ai_study_buddy.pdf_file_manager.scripts.apply_backup_tiering --hot-days 7 --cold-days 60
   ```
   This keeps recent backups (`0-7` days) as raw `.db` files in the backup root, moves `7-60` day backups into `coldstorage/` as `.db.zst`, and removes backups older than 60 days.

Once the file is inside your Google Drive folder, it will sync to the cloud automatically.

**Run backup on wake (optional)**  
To back up automatically when the Mac wakes from sleep (only if DBs changed), use [sleepwatcher](https://formulae.brew.sh/formula/sleepwatcher):

```bash
brew install sleepwatcher
bash ai_study_buddy/utils/backup/install_pdf_registry_wake.sh
```

All wake helpers live under `ai_study_buddy/utils/backup/`: `install_pdf_registry_wake.sh`, `run_wake_all.sh`, `run_pdf_registry_wake.sh`, `run_learning_db_wake.sh`.

This installs `com.daydreamedu.pdf-registry-backup-on-wake` so `~/.wakeup` runs `run_wake_all.sh`:

1. PDF registry timestamped backup and tiering
2. `study_buddy.db` timestamped backup and tiering

**Upgrading:** if `~/.wakeup` still quotes removed paths under `pdf_file_manager/scripts/` or `learning_db/scripts/`, run:

```bash
bash ai_study_buddy/utils/backup/migrate_wakeup_backup_paths.sh --dry-run   # preview
bash ai_study_buddy/utils/backup/migrate_wakeup_backup_paths.sh             # rewrite ~/.wakeup
```

Each backup step skips when unchanged. To remove the agent: `launchctl unload ~/Library/LaunchAgents/com.daydreamedu.pdf-registry-backup-on-wake.plist` and edit `~/.wakeup` as needed.
