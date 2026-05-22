# Learning: Phase 3 dual-write (SQLite projection after JSON-or-canonical payload)

## Context

After Phase 2 read-path parity sign-off, marking/review snapshots can optionally be mirrored into `study_buddy.db` alongside (or instead of, in early experiments) emitting JSON files under `ai_study_buddy/context/`.

Proposal index: [L4_LOCAL_LEARNING_DB.md](../../../docs/L4_LOCAL_LEARNING_DB.md).

## Runtime flags (`learning_db/core/config.py`)

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

## Rollback drill (`LEARNING_DB_ENABLE_DUAL_WRITE=0`)

Documented **2026-05-22** for L4 Phase 3 sign-off. Production keeps dual-write **on** by default; run this drill on a **copy** before Phase 4 cutover, or briefly in a controlled local session when validating rollback posture.

### Goal

Confirm that disabling DB projection restores **JSON-only** write behaviour without data loss: marking/review APIs still persist under `context/**`; no new `dual_write_snapshot` rows are required for operators to continue work.

### Steps (disposable copy recommended)

1. Copy `ai_study_buddy/context/` and `ai_study_buddy/db/study_buddy.db` to a scratch directory.
2. Point env at the copy (or export overrides for one shell session):

   ```bash
   export LEARNING_DB_ENABLE_DUAL_WRITE=0
   export LEARNING_DB_ENABLE_JSON_EXPORT=1   # default — JSON remains authoritative on disk
   export STUDY_BUDDY_DB_PATH=/path/to/copy/study_buddy.db   # if using a copy
   ```

3. Perform one representative write per family through normal APIs (not raw file edits):
   - `write_marking_artifact(...)` → `context/marking_results/...`
   - `StudentReviewRepository.save_review_state(...)` / `save_amendment(...)`
4. Verify JSON files exist and are readable; confirm **no** new `dual_write_snapshot` rows for those paths (optional):

   ```bash
   python3 -m ai_study_buddy.learning_db.cli.dual_write_stats --db-path /path/to/copy/study_buddy.db
   ```

5. Re-enable projection before returning to normal work:

   ```bash
   export LEARNING_DB_ENABLE_DUAL_WRITE=1
   ```

### Expected outcome

- Writes succeed with JSON on disk; DB projection is skipped when `LEARNING_DB_ENABLE_DUAL_WRITE=0` (see `maybe_dual_write_snapshot` / `maybe_dual_write_from_canonical` early return).
- Automated coverage: `learning_db/tests/test_dual_write_snapshots.py` (`test_dual_write_disabled_is_no_op`) and rollback posture noted in [L4_LOCAL_LEARNING_DB.md](../../../docs/L4_LOCAL_LEARNING_DB.md) Phase 3 checklist.

### Production posture after sign-off

- **Do not** leave `LEARNING_DB_ENABLE_DUAL_WRITE=0` in routine marking/review sessions while Phase 3 compatibility mode is active.
- Re-run `python3 -m ai_study_buddy.learning_db.cli.dual_write_stats --target-min-ops 1000` periodically until the final gate passes, then proceed to Phase 4 JSON demotion per L4.
