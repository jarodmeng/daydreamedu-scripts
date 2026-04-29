# Learning: Phase 3 dual-write (SQLite projection after JSON-or-canonical payload)

## Context

After Phase 2 read-path parity sign-off, marking/review snapshots can optionally be mirrored into `study_buddy.db` alongside (or instead of, in early experiments) emitting JSON files under `ai_study_buddy/context/`.

Proposal index: [L4_LOCAL_LEARNING_DB.md](../../../docs/L4_LOCAL_LEARNING_DB.md).

## Runtime flags (`learning_db/config.py`)

| Env | Typical default | Role |
|-----|-----------------|------|
| `LEARNING_DB_ENABLE_DUAL_WRITE` | `1` | When `1`, **`maybe_dual_write_*`** persists rows matching importer upserts after a validated payload snapshot. Set `0` to disable DB projection. |
| `LEARNING_DB_STRICT_DUAL_WRITE` | `0` | When `1`, projection failure raises and (**snapshot path**) JSON may be rolled back (`unlink`). When `0` (“soft”), JSON/human snapshot is retained and **`operation_log`** records **failed**. |
| `LEARNING_DB_ENABLE_JSON_EXPORT` | `1` | When `1`, **`write_marking_artifact`** and **`StudentReviewRepository.save_*`** write JSON files as today, then optionally dual-write from disk bytes. When `0`, callers must **`LEARNING_DB_ENABLE_DUAL_WRITE=1`** and payloads are projected via **canonical UTF-8 string** (**no `.json`** file emitted). |

**Soft rollout:** keep **`LEARNING_DB_STRICT_DUAL_WRITE=0`** while exercising dual-write against a copied `context/` + `study_buddy.db` so importer-sized DB errors retain quality JSON snapshots on disk until behaviour is predictable.

## Code entry points

| Function | Behaviour |
|---------|-----------|
| [`dual_write.maybe_dual_write_snapshot(...)`](../../dual_write.py) | **`path.read_text`** → **`sha256`** → importer **`upsert_*`** (**hash matches on-disk importer imports**). |
| [`dual_write.maybe_dual_write_from_canonical(...)`](../../dual_write.py) | Canonical **`indent=2` + `\n`** string (same deterministic serialisation callers use); **hash** **`sha256(utf8(text))`** identity-key stable with importer if content matches byte-for-byte. |

**Call sites:**

- **`marking.core.artifact_writer.write_marking_artifact`**
- **`marking.review.repository.StudentReviewRepository.save_review_state`** / **`save_amendment`**

## Operational recipe (recommended)

1. Copy **`context/`** and **`study_buddy.db`** to a disposable directory.
2. Set **`export=1`** (default); enable **`LEARNING_DB_ENABLE_DUAL_WRITE=1`**; keep **`strict=0`**.
3. Run one representative write per family; validate row counts (`validate_study_buddy_db.py`) — same structural checks Phase 2 already uses.
4. Only then exercise **`LEARNING_DB_ENABLE_JSON_EXPORT=0`** for DB-only previews (dual-write mandatory).

See also parity learning: [LEARNING_READER_PARITY.md](./LEARNING_READER_PARITY.md).
