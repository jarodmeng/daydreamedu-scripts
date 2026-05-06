# Learning DB architecture

This document describes **how** `ai_study_buddy/learning_db` is structured: layers, major components, and design rules. **Behavioral contracts** (flags, strict dual-write, ops expectations) live in [`SPEC.md`](./SPEC.md). **Table-level detail** is in [`SCHEMA.md`](./SCHEMA.md). The long-form proposal remains in [`../docs/L4_LOCAL_LEARNING_DB.md`](../docs/L4_LOCAL_LEARNING_DB.md).

---

## 1. Layers

| Layer | Role |
|-------|------|
| **`context/*.json`** | **Canonical artifacts** for supported families. Paths and file contents are the authoritative input for backfill and for hash-based identity. |
| **`study_buddy.db`** | **Projection / mirror**: normalized tables, indexes, raw JSON columns, import identity, quarantine, and operation log. |
| **`learning_db` package** | **Owner** of schema evolution, ingest rules, dual-write hooks, read façades, and operational CLI/scripts. |

---

## 2. Write pipelines (conceptual)

Two paths populate or refresh the projection:

1. **Batch import** — `ingest.import_context_json` walks `context/` (optionally filtered by artifact family), validates payloads, upserts rows, and sends failures to `import_quarantine`.
2. **Runtime dual-write** — After canonical JSON is written (or equivalent text is supplied when JSON export is off), `ingest.dual_write` runs the same upsert logic against the current snapshot so the DB stays aligned with disk or in-memory canonical form.

Both paths converge on shared upsert helpers and `operation_log` (see `SPEC.md` §Contracts).

---

## 3. Package layout (logical)

| Area | Responsibility |
|------|----------------|
| `core/migrate.py` | Apply pending `migrations/*.sql` in order. |
| `core/connection.py` | Resolve default DB and context paths; `get_connection()` enables foreign keys and `Row` factory. |
| `core/config.py` | Environment-driven toggles for reads, dual-write strictness, JSON export, filesystem fallback. |
| `core/repository.py` | `operation_log` writes, `import_identity_map` helpers, actor validation, shared ids/timestamps. |
| `ingest/import_context_json.py` | Scan `context/`, validate, upsert per family, quarantine failures, optional quarantine retry. |
| `ingest/dual_write.py` | `maybe_dual_write_snapshot` / `maybe_dual_write_from_canonical` after JSON-equivalent payloads are committed. |
| `read/` | DB queries returning raw JSON or artifact refs consistent with marking conventions. |
| `cli/` | Backup, tiering, validate, parity/coverage/audit commands for operators and CI. |
| `scripts/` | Optional host integrations (e.g. wake-triggered backup installer/runner). |
| `tests/` | Package tests for migrate, import, dual-write, reads, idempotency. |
| `migrations/` | Versioned SQL; see `SCHEMA.md` for what each file introduces. |

---

## 4. Design rules

- **Identifiers:** Application code must not treat SQLite `rowid` as a stable product identifier. Prefer explicit text IDs, stable paths, and content hashes as described in `SCHEMA.md` and migrations.
- **Portability:** Favor SQL and types that can move to Postgres later (see L4 proposal).
- **Access:** Prefer repository / `read_*` / `LearningDbReadRepository` over ad hoc SQL from unrelated packages.

---

## Related documentation

| Document | Contents |
|----------|----------|
| [`SPEC.md`](./SPEC.md) | Scope, contracts, env vars, operational expectations. |
| [`SCHEMA.md`](./SCHEMA.md) | Tables, indexes, idempotency notes. |
| [`README.md`](./README.md) | Quick commands and env summary. |

---

## Document control

- **When to update:** New modules under `core/`, `ingest/`, `read/`, or `cli/`; new write pipeline; meaningful change to how context and DB relate.
- **Owner:** `ai_study_buddy/learning_db` package maintainers.
