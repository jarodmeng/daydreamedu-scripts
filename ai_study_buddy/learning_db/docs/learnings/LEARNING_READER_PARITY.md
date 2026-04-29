# Learning: Filesystem vs DB-backed marking lookup parity

## Context

`find_marking_artifacts_for_attempt(...)` (`ai_study_buddy.marking.core.artifact_lookup`) is the single public boundary for resolving **latest marking-result JSON (+ paired learning report path)** per registered completion attempt.

With env flags (`LEARNING_DB_ENABLE_READS`, `LEARNING_DB_READ_FALLBACK_FILESYSTEM`), behaviour switches:

| Mode | Intent |
|------|--------|
| Reads **off** (`LEARNING_DB_ENABLE_READS` unset / false) | **Historical** filesystem scan under `context/marking_results/<student_slug>/**/*.json`. |
| Reads **on** + fallback **off** (`LEARNING_DB_ENABLE_READS=1`, `LEARNING_DB_READ_FALLBACK_FILESYSTEM=0`) | **Strict DB-only** projection: no filesystem scan for hits; empty list if the DB misses. |

**Parity proof** means: for every qualification completion row you care about, the **ordered** list `(marking_result_json, learning_report_md)` tuples from the filesystem path equals that from the strict-DB path—after the same `context/**` tree has been **imported** into `study_buddy.db`.

See the rollout proposal and Phase 2 sign-off: [L4_LOCAL_LEARNING_DB.md](../../../docs/L4_LOCAL_LEARNING_DB.md).

## Tooling

| Piece | Role |
|-------|------|
| [`reader_parity.py`](../../reader_parity.py) | `run_reader_parity(...)`, `print_reader_parity_report(...)` — walks **non-template `main`** PDF rows with `student_id`, compares FS vs DB-strict keys per file. |
| [`validate_study_buddy_db.py`](../../validate_study_buddy_db.py) | Structural counts/FKs plus optional **`--reader-parity`** (calls `run_reader_parity`). Non-zero exit on mismatches or per-file errors. |

**Commands:**

```text
python3 -m ai_study_buddy.learning_db.validate_study_buddy_db \
  --db-path ai_study_buddy/db/study_buddy.db \
  --context-root ai_study_buddy/context
```

Structural only (cheap). Add reader parity:

```text
python3 -m ai_study_buddy.learning_db.validate_study_buddy_db \
  --db-path ai_study_buddy/db/study_buddy.db \
  --context-root ai_study_buddy/context \
  --pdf-registry ai_study_buddy/db/pdf_registry.db \
  --reader-parity
```

Speed up local iteration:

```text
python3 -m ai_study_buddy.learning_db.validate_study_buddy_db ... --reader-parity --parity-limit 50
```

**Environment during parity:** `reader_parity` temporarily sets `STUDY_BUDDY_DB_PATH` and `STUDY_BUDDY_CONTEXT_ROOT` for the run and restores the previous process env afterward so ad-hoc shells are not polluted.

## Preconditions

1. **`context/**` JSON has been imported** into the target `study_buddy.db` (otherwise DB-strict will often return `[]` while FS may still find files → false mismatch).
2. **`--pdf-registry`** points at the same **`pdf_registry.db`** the product uses (defaults follow `PDF_REGISTRY_PATH` / package default under `ai_study_buddy/db/`).
3. **Parity compares every scanned completion**, including attempts with **no** matching marking JSON (`[] == []` is still meaningful).

## Automated regression (small fixtures)

`learning_db/tests/test_phase2_reads.py` — single-attempt corpus: FS vs reads-on no-fallback, assert path lists match.

`learning_db/tests/test_reader_parity_module.py` — **`run_reader_parity`** smoke: **zero** mismatches after import into a temp DB.

## Observed outcome (full corpus parity proof, 2026-04-29)

Recorded when signing off Phase 2 in L4 (same repo layout):

- **Eligible** non-template `main` completions with `student_id`: **499**.
- **`--reader-parity`** run **three** times sequentially on unchanged data.
- Each run: **`parity_checked=499`**, **`mismatches=0`**, **`errors=0`** (latest-artifact path tuples match in API order).
- Runtime order of magnitude: **~40 s** per full run on that machine (I/O + double lookup per completion).

**Interpretation:** For that snapshot, the **DB projection + identity mapping** produced the same latest-artifact resolution as the historical filesystem scan for every registered completion checked. This does **not** by itself prove Review Workspace UI or amendment **overlay** math for every screen—that is a separate surface; the proof here is specifically **`find_marking_artifacts_for_attempt` parity**.

## Validation output and quarantine

- By default, **`validate_study_buddy_db`** does **not** print historic **`resolved`** quarantine counts (avoids looking like current failures). It prints **`import_quarantine_needing_attention`** only when **`open` or `ignored`** rows exist.
- **`--quarantine-history`** prints a full status breakdown (including **`resolved`** audit history).

See also: import/quarantine behaviours in [LEARNING_JSON_FIELD_COVERAGE_AND_IMPORT.md](./LEARNING_JSON_FIELD_COVERAGE_AND_IMPORT.md).

## Operational checklist (after changing context JSON or lookups)

```text
python3 -m ai_study_buddy.learning_db.import_context_json
python3 -m ai_study_buddy.learning_db.validate_study_buddy_db \
  --db-path ai_study_buddy/db/study_buddy.db \
  --context-root ai_study_buddy/context
python3 -m ai_study_buddy.learning_db.validate_study_buddy_db \
  --db-path ai_study_buddy/db/study_buddy.db \
  --context-root ai_study_buddy/context \
  --pdf-registry ai_study_buddy/db/pdf_registry.db \
  --reader-parity
python3 -m pytest ai_study_buddy/learning_db/tests/test_phase2_reads.py ai_study_buddy/learning_db/tests/test_reader_parity_module.py
```

Gate policy in L4: **three** consecutive green full parity runs **before treating read-path rollout as locked** for Phase 3 write work — re-run parity after importer or `artifact_lookup` changes.

## Takeaway

- **Parity** = same **`find_marking_artifacts_for_attempt`** API, filesystem mode vs **`LEARNING_DB_READ_FALLBACK_FILESYSTEM=0`** DB mode.
- **Proof at scale** = `validate_study_buddy_db --reader-parity` (plus optional **`--parity-limit`** for subsets).
- **Keep** **`learning_db`** tests green; **re-record** timings and corpus sizes in **this doc** when the registry or marking tree grows materially.
