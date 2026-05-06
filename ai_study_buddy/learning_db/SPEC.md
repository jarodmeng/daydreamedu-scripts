# Learning DB module specification

This document defines **scope**, **contracts**, and **operational expectations** for `ai_study_buddy/learning_db` and `study_buddy.db`. **Structure and components** are described in [`ARCHITECTURE.md`](./ARCHITECTURE.md). The long-form proposal and roadmap live in [`../docs/L4_LOCAL_LEARNING_DB.md`](../docs/L4_LOCAL_LEARNING_DB.md).

---

## 1. Purpose

`learning_db` is the Python package that owns **migrations**, **import/backfill**, **runtime projection (dual-write)**, **auditing**, **read helpers**, and **backup/retention tooling** for the local SQLite database `ai_study_buddy/db/study_buddy.db`.

It exists so marking, review, and detector workflows can keep using familiar JSON files while gaining a **queryable, backup-friendly projection** suitable for analytics and future server-side storage.

---

## 2. Scope

### In scope

- Apply versioned SQL migrations under `migrations/` and record them in `schema_migrations`.
- Import canonical JSON from `ai_study_buddy/context/` into normalized tables (`ingest.import_context_json`).
- Mirror new/updated snapshots into SQLite at write time (`ingest.dual_write`) for supported artifact families.
- Log import and dual-write lifecycle events in `operation_log`; record failed imports in `import_quarantine` with retry support.
- Expose read helpers and a small façade (`read.learning_repository.LearningDbReadRepository`) for DB-backed lookups.
- Provide CLI utilities: migrate, import, backup, retention tiering, validation/audit helpers under `cli/`.
- Document day-to-day operations in `OPERATIONS.md` and schema notes in `SCHEMA.md`.

### Out of scope

- Replacing or merging `pdf_file_manager` / `pdf_registry.db` (registry remains separate).
- Hosting or syncing to Postgres (local SQLite only; schema choices favor portability).
- Storing PDF binaries, page renders, or large binary blobs (those stay on disk / other stores unless explicitly added by a future proposal).

---

## 3. Supported artifact families

The following **families** are integrated end-to-end for import and dual-write (see `ingest.dual_write.Family`):

- `marking_result`
- `marking_amendment`
- `student_review_state`
- `file_question_info` (e.g. `context/file_question_info/**/question_sections.json`)

Adding a new family requires: migration(s), upsert logic in `import_context_json`, dual-write branch, validation/schema alignment, and tests (see [`ARCHITECTURE.md`](./ARCHITECTURE.md) §3 for where that code lives).

---

## 4. Contracts

### 4.1 Canonical JSON vs database

- **Canonical:** UTF-8 JSON files under `ai_study_buddy/context/` (layout per family).
- **Mirror:** Rows in `study_buddy.db` must be reproducible from context JSON + migrations; `raw_json` (where present) supports audit and export parity.
- **Dual-write:** When enabled, successful writes to canonical snapshots should be reflected in SQLite for supported families, subject to toggles in §5.

### 4.2 Write paths

1. **Batch import / backfill:** `python3 -m ai_study_buddy.learning_db.ingest.import_context_json` scans the tree (optionally per `--artifact-family`), validates, upserts, and records quarantine on failure.
2. **Runtime dual-write:** After a caller persists JSON (or provides equivalent canonical text), `maybe_dual_write_snapshot` (reads bytes from disk) or `maybe_dual_write_from_canonical` (string path for JSON-export-off mode) runs upsert + `operation_log` success/failure.

### 4.3 Read path and feature flags

Reads from `study_buddy.db` in product code are gated by **`LEARNING_DB_ENABLE_READS`** and optional **`LEARNING_DB_READ_FALLBACK_FILESYSTEM`** (see `core/config.py`). When the DB is authoritative for a lookup, callers should use `LearningDbReadRepository` or the underlying `read_*` helpers rather than ad hoc SQL.

### 4.4 Identity and idempotency

- **`import_identity_map`** maps `(artifact_family, source_path, source_content_hash)` to a stable artifact id; re-imports with the same path and hash update idempotently.
- Path-level identity is authoritative when JSON at a stable path changes (see `get_or_create_identity_map` behavior in `core/repository.py`).

### 4.5 Quarantine

Failed imports are stored in **`import_quarantine`** with status and error metadata. Operators retry with `import_context_json --retry-quarantine` (optional filters). Resolution is part of normal operations (see `OPERATIONS.md`).

### 4.6 Audit trail

**`operation_log`** records import and dual-write events with `actor` strings validated against allowed prefixes (`user:`, `script:`, `agent:`, `system:`). Dual-write failures may be logged without crashing the workflow unless strict mode is on.

### 4.7 Strict dual-write

When **`LEARNING_DB_STRICT_DUAL_WRITE`** is true, a failed DB projection surfaces to the caller; entrypoints may attempt to reconcile filesystem state depending on family (see `ingest/dual_write.py`). Default is non-strict so JSON workflows remain resilient.

---

## 5. Environment variables

| Variable | Default (conceptual) | Meaning |
|----------|----------------------|---------|
| `STUDY_BUDDY_DB_PATH` | `<repo>/ai_study_buddy/db/study_buddy.db` | SQLite file location. |
| `STUDY_BUDDY_CONTEXT_ROOT` | `<repo>/ai_study_buddy/context` | Root for import scans and path resolution. |
| `LEARNING_DB_ENABLE_DUAL_WRITE` | on | Mirror writes to SQLite when snapshots are produced. |
| `LEARNING_DB_STRICT_DUAL_WRITE` | off | Fail closed on projection errors. |
| `LEARNING_DB_ENABLE_JSON_EXPORT` | on | Keep writing JSON under `context/` alongside DB (compatibility). |
| `LEARNING_DB_ENABLE_READS` | on | Allow code paths to read from DB. |
| `LEARNING_DB_READ_FALLBACK_FILESYSTEM` | off | If DB miss, fall back to scanning JSON files. |
| `STUDY_BUDDY_DB_BACKUP_DIR` | DaydreamEdu-root-relative `db` (see `cli/backup_study_buddy_db`) | Backup destination for one-shot and scripted backups. |

Exact default resolution for paths is implemented in `core/connection.py` and backup CLI.

---

## 6. Operational expectations

1. **Migrations:** Run `python3 -m ai_study_buddy.learning_db.core.migrate` before relying on new columns/tables (deployments, local pull).
2. **Backfill:** After large JSON changes or new families, run `import_context_json` (full or per family).
3. **Health:** Check `import_quarantine` counts and `operation_log` for failures; retry quarantine as needed.
4. **Backup:** Use `cli.backup_study_buddy_db` and `cli.apply_backup_tiering`; optional wake scripts under `scripts/` for automated copies. See `OPERATIONS.md` and `README.md`.
5. **Tests:** Run package tests under `ai_study_buddy/learning_db/tests/` when changing ingest, dual-write, or schema.

---

## 7. Related documentation

| Document | Contents |
|----------|----------|
| [`ARCHITECTURE.md`](./ARCHITECTURE.md) | Layers, pipelines, package layout, design rules. |
| `README.md` | Overview, quick commands, env vars summary. |
| `SCHEMA.md` | Tables, indexes, idempotency notes. |
| `OPERATIONS.md` | Step-by-step runbook. |
| `CHANGELOG.md` | Package change history. |
| `../docs/L4_LOCAL_LEARNING_DB.md` | Proposal, phased rollout, and product context. |

---

## Document control

- **Owner:** `ai_study_buddy/learning_db` package maintainers.
- **When to update:** New artifact family, new env toggles, changed canonical-vs-DB contract, or materially new operational procedures. Update [`ARCHITECTURE.md`](./ARCHITECTURE.md) when structure or write pipelines change materially.
