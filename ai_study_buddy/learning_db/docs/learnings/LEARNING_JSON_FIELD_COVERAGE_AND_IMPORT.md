# Learning: JSON field coverage and historical import into `study_buddy.db`

## Context

The `learning_db` package imports marking artifacts, amendments, and student review states from `ai_study_buddy/context/**` into SQLite (`study_buddy.db`). Each root row also stores a **`raw_json`** column intended as a redundant full-document snapshot (backup / round-trip aid).

We needed a way to answer:

1. **Full snapshot:** Does the DB’s `raw_json` match the on-disk JSON leaf-for-leaf?
2. **Without backups:** If we ignore every `raw_json` column, can we **reconstruct** the same logical document from **normalized columns** and **child tables** only?

See also the rollout proposal: [L4_LOCAL_LEARNING_DB.md](../../../docs/L4_LOCAL_LEARNING_DB.md).

## Tooling

Implementation: [`field_coverage.py`](../../field_coverage.py) (module: `ai_study_buddy.learning_db.cli.field_coverage`).

**Metrics (per file, then aggregated by leaf count):**

- Flatten each JSON to **leaf paths** (dot + bracket notation, e.g. `context.student_id`, `question_results[0].earned_marks`). Empty `{}` / `[]` count as one field at that path.
- **Coverage** = matched leaf paths in the DB-derived view ÷ leaf paths in the **source file** (denominator is always the filesystem JSON).

**Modes**

| Invocation | Compared view |
|------------|----------------|
| Default | Row `raw_json` on the primary table (`marking_artifacts`, `marking_amendments`, `student_review_states`) vs source file |
| `--exclude-raw-json` | Reconstructed object from typed columns + structured `*_json` fields + **child tables only** (never reads any `raw_json` column) |

Arrays that are logically unordered for identity (e.g. `question_results`, `question_page_map`, amendment lists, review-state note lists) are **sorted deterministically** before flattening so ordering differences do not inflate mismatch.

Commands:

```text
python3 -m ai_study_buddy.learning_db.cli.field_coverage
python3 -m ai_study_buddy.learning_db.cli.field_coverage --exclude-raw-json
```

Optional: `--db-path`, `--context-root` (same semantics as other `learning_db` CLIs).

## Observed outcome (representative corpus, 2026-04)

On a successfully imported corpus (**163** `marking_results`, **22** `marking_amendments`, **27** `student_review_states`), `python3 -m ai_study_buddy.learning_db.cli.field_coverage` printed **exact** weighted coverage (matched leaf paths ÷ leaf paths in source files):

| Mode | marking_result | marking_amendment | student_review_state | All families (weighted) |
|------|----------------|-------------------|----------------------|-------------------------|
| Default (`raw_json`) | **60,438 / 60,438 (100.00%)** | **832 / 832 (100.00%)** | **777 / 777 (100.00%)** | **62,047 / 62,047 (100.00%)** |
| `--exclude-raw-json` | **60,438 / 60,438 (100.00%)** | **832 / 832 (100.00%)** | **777 / 777 (100.00%)** | **62,047 / 62,047 (100.00%)** |

Per-file mean coverage was **100.00%** in every family for both modes (no divergent or missing paths on any file in that run).

Re-run the commands after imports change; file counts and leaf totals will move with the corpus.

**Interpretation:** For this snapshot, nothing important lived **only** in `raw_json`; the normalized projection plus child-row columns was sufficient to rebuild the same leaf values as counted by the script. If future payloads introduce keys stored solely in `raw_json` without mirroring elsewhere, the exclude mode would drop below 100% until the schema/import path projects those fields.

## Import / quarantine learnings

1. **`student_review_state` links via `context.marking_result_path`** — not derived from the review-state filename. If a marking run is superseded by a newer file (e.g. different `__YYYYMMDD_HHMMSS__` suffix) but the review-state JSON still points at the old path, resolution fails with **`BASE_ARTIFACT_NOT_FOUND`** until `marking_result_path` is updated to the current `marking_results/...` file.

2. **Schema gaps** — e.g. missing top-level `created_at` / `updated_at` where the importer requires them quarantines with transform errors. Repair the JSON (or align schema policy) before re-import; **`--retry-quarantine`** can reprocess after fixes.

3. **Full-corpus imports** — using `--limit` on the importer can strand companion files (amendments/review states) whose base artifact was not in the scanned subset; prefer a full run for a clean index.

## Operational checklist

After changing context JSON or the DB:

```text
python3 -m ai_study_buddy.learning_db.ingest.import_context_json
python3 -m ai_study_buddy.learning_db.cli.validate_study_buddy_db
python3 -m ai_study_buddy.learning_db.cli.field_coverage --exclude-raw-json
```

Optional backup:

```text
python3 -m ai_study_buddy.learning_db.cli.backup_study_buddy_db
```

## Takeaway

- **`raw_json` vs file:** Use default `field_coverage` when you care about backup blob fidelity.
- **“Do we really need `raw_json`?”** Use `--exclude-raw-json`. A **100.00%** weighted match on that mode (as in the table above) is strong evidence the **durable** representation is the normalized + child-table data, with `raw_json` as optional redundancy.
