# Proposal 14: Persist `file_question_info` in `study_buddy.db`

## Status

Implemented (as of 2026-05-05), within Proposal 14 scope. Consumer/read/orchestration follow-up remains intentionally deferred to Proposal 15.

## Goal

Mirror validated `context/file_question_info/**/question_sections.json` into `study_buddy.db` so we can query by `file_id`/scope/recency without filesystem walks, while keeping the JSON file as canonical source.

## Dependency and current reality

This proposal depends on implemented helpers in `ai_study_buddy.marking.file_question_info`:

- `load_question_sections_json(path)`
- `validate_question_sections_dict(payload)`
- `file_question_info_run_dir_for_pdf(pdf_file, ...)`
- `render_file_question_info_pages_for_pdf(pdf_file, ...)`

Validation support currently includes:

- `chinese-v1.4`
- `high-chinese-v1.2`
- `english-v1.3`
- `math-v1.2`
- `science-v1.2`
- (legacy in map: `math-v1.0`, `science-v1.0`)

Importer/dual-write must use `validate_question_sections_dict` as the gate.

## Non-goals

- Replacing detector agents as canonical writers.
- Moving detector logic into DB import.
- Changing `marking_result` schema in this proposal.

## Data model

Create migration: `ai_study_buddy/learning_db/migrations/002_file_question_info.sql`.

### `file_question_info_runs`

Columns:

- `run_id TEXT PRIMARY KEY`
- `schema_version TEXT NOT NULL`
- `subject_scope TEXT NOT NULL`
- `grade TEXT NOT NULL`
- `slug TEXT NOT NULL`
- `primary_file_id TEXT NOT NULL`
- `primary_file_path TEXT`
- `source_rel_path TEXT NOT NULL`
- `source_content_hash TEXT NOT NULL`
- `detector_model TEXT`
- `detector_confidence TEXT`
- `detector_notes TEXT`
- `raw_json TEXT NOT NULL`
- `created_at TEXT NOT NULL`
- `updated_at TEXT NOT NULL`
- `row_version INTEGER NOT NULL DEFAULT 1`
- `is_deleted INTEGER NOT NULL DEFAULT 0`

Indexes:

- `idx_fqi_runs_primary_file_updated` on `(primary_file_id, updated_at DESC)`
- `idx_fqi_runs_scope` on `(subject_scope, grade, slug)`
- `ux_fqi_runs_source_rel_path` unique on `(source_rel_path)`
- `ux_fqi_runs_content_identity` unique on `(primary_file_id, source_content_hash)`

### `file_question_info_sections`

- `run_id TEXT NOT NULL`
- `ordinal INTEGER NOT NULL`
- `question_type TEXT NOT NULL`
- `printed_section_title TEXT`
- `section_total_marks REAL`
- `questions_page_range_json TEXT NOT NULL`
- `stem_page_range_json TEXT`
- `answers_page_range_json TEXT`
- `answers_in_separate_booklet INTEGER`
- `raw_json TEXT NOT NULL`
- PK: `(run_id, ordinal)`

Standardization rule:

- Use one canonical section column: `answers_page_range_json`.
- Upstream JSON Schemas must standardize on one canonical payload key: `answers_page_range`.
- Importers should not rely on alias mapping between `answers_page_range` and `answers_page_range`; payloads must already conform to the latest schema contract before DB import.

### `file_question_info_items`

- `run_id TEXT NOT NULL`
- `section_ordinal INTEGER NOT NULL`
- `question_index TEXT NOT NULL`
- `question_mark REAL`
- `start_page INTEGER`
- `extra_json TEXT`
- `raw_json TEXT NOT NULL`
- PK: `(run_id, section_ordinal, question_index)`

## Write path (learning_db)

Add to `ai_study_buddy/learning_db/ingest/import_context_json.py`:

1. `upsert_file_question_info_run(conn, *, payload, rel_path, source_hash) -> str`
2. Validate with `validate_question_sections_dict(payload)`.
3. Extract `primary_file_id = payload["input_context"]["files"][0]["file_id"]`.
4. Resolve stable `run_id` via `get_or_create_identity_map(..., artifact_family="file_question_info", source_path=rel_path, source_content_hash=source_hash, suggested_artifact_id=existing_run_id_by_rel_path)`.
5. Upsert `file_question_info_runs` row; replace section/item children for that run.
6. Write operation log event (`entity_type="file_question_info_run"`).

Error handling:

- Validation/schema/version failures: quarantine with `artifact_family="file_question_info"`.
- Missing/blank `primary_file_id`: quarantine (production invariant breach).

## Import scanner integration

Extend `import_context_json` scan logic to include:

- `context/file_question_info/**/question_sections.json`

For each file:

- Parse JSON
- Validate via `validate_question_sections_dict`
- Compute `source_hash` from raw text
- Upsert through `upsert_file_question_info_run`
- Resolve open quarantine entries on success

## Dual-write integration

Extend `ai_study_buddy/learning_db/ingest/dual_write.py`:

- Add family literal: `"file_question_info"`
- Route to `upsert_file_question_info_run` in `_commit_projection`

This keeps behavior aligned with current dual-write toggles (`LEARNING_DB_ENABLE_DUAL_WRITE`, strict mode, audit logging).

## Reader handoff

Read APIs and consumer-layer orchestration are owned by proposal 15:

- [15-file-question-info-consumer-layer-and-marking-orchestration.md](./15-file-question-info-consumer-layer-and-marking-orchestration.md)

Proposal 14 remains persistence-only: migration, importer, quarantine behavior, dual-write integration, and backfill.

## Implementation

### Phase 1: Migration + write model

Objective: Add durable schema for runs/sections/items and write-path upsert logic.

Todo checklist:

- [x] Add SQL migration `002_file_question_info.sql` with:
- [x] `file_question_info_runs`
- [x] `file_question_info_sections`
- [x] `file_question_info_items`
- [x] Required indexes and uniqueness constraints from this proposal
- [x] Standardize detector schema files to one canonical section key (`answers_page_range`) across all relevant `question_sections` schemas.
- [x] When any schema file is changed, bump its `schema_version` and update all schema references in code/docs/tests to the newest version.
- [x] After schema version bump, migrate all existing `context/file_question_info/**/question_sections.json` files on older versions to the new latest schema version before enabling import.
- [x] Add required run-level timestamp fields to schemas (ISO 8601), and ensure detector outputs carry a single run-specific timestamp set reused across all timestamp fields written by that run.
- [x] Implement `upsert_file_question_info_run(conn, *, payload, rel_path, source_hash) -> str`
- [x] Enforce `validate_question_sections_dict(payload)` before any write
- [x] Resolve `run_id` via `get_or_create_identity_map(... artifact_family="file_question_info" ...)`
- [x] Replace section/item child rows on run upsert
- [x] Write operation log event (`entity_type="file_question_info_run"`)

Testing plan:

- Add migration test in `ai_study_buddy/learning_db/tests/test_migrate.py` (or dedicated migration test) to assert new tables/indexes exist.
- Add schema-version contract tests ensuring only canonical `answers_page_range` is accepted for latest versions, and old-key payloads fail for latest versions.
- Add schema contract tests for required run-level timestamp fields (ISO 8601) in latest versions.
- Add corpus migration test/script validation: all `context/file_question_info/**/question_sections.json` files report the latest schema version(s) after migration.
- Add repository/importer-level upsert test that inserts valid payload and asserts run + section + item rows.
- Add idempotency test: same `rel_path` + same content hash does not duplicate rows.

Success criteria:

- Migration applies cleanly on empty DB and existing DB.
- Schema files and payload corpus are standardized on latest versions with canonical keys before import rollout.
- One valid payload produces one run row with matching section/item projections.
- Re-upsert of unchanged payload is stable and queryable.

### Phase 2: Import scanner + quarantine wiring

Objective: Make bulk import pick up `file_question_info` artifacts with robust failure handling, then execute and verify backfill on existing corpus.

Todo checklist:

- [x] Extend `import_context_json` scanner to include `context/file_question_info/**/question_sections.json`
- [x] Dispatch matched files to `upsert_file_question_info_run`
- [x] On parse/validation/schema failure, quarantine with `artifact_family="file_question_info"`
- [x] On success, mark matching open quarantine rows resolved
- [x] Run backfill import on existing `context/file_question_info` corpus
- [x] Validate row counts and quarantine counts after backfill
- [x] Document expected backfill operation steps/results for maintainers

Testing plan:

- Add import happy-path test using fixture `question_sections.json` under `context/file_question_info/...`.
- Add quarantine test for unknown `schema_version`.
- Add quarantine test for malformed JSON.
- Add quarantine test for missing/blank `primary_file_id`.
- Add import idempotency regression test across repeated runs.
- Add backfill smoke test against a small fixture corpus.

Success criteria:

- `import_context_json` reports imports for valid files and quarantines invalid files with explicit error codes.
- Re-running import does not duplicate canonical run identity.
- Backfill succeeds and produces expected row counts for fixture corpus.

Backfill status (completed 2026-05-05):

- Import command: `PYTHONPATH=. python3 -m ai_study_buddy.learning_db.ingest.import_context_json --artifact-family file_question_info`
- Import summary: `scanned=23 imported=23 updated=0 quarantined=0 resolved=0`
- DB counts after backfill:
- `file_question_info_runs=23`
- `file_question_info_sections=105`
- `file_question_info_items=760`
- Quarantine (`artifact_family='file_question_info'`): `open=0`, `total=0`

Maintainer runbook (backfill + verification):

1. Run importer for file-question-info family only:
- `PYTHONPATH=. python3 -m ai_study_buddy.learning_db.ingest.import_context_json --artifact-family file_question_info`

2. Expected import-summary shape:
- `file_question_info: scanned=<N> imported=<N|0> updated=<0|N> quarantined=<0|K> resolved=<...>`

3. Verify row counts in DB:
- `SELECT COUNT(*) FROM file_question_info_runs;`
- `SELECT COUNT(*) FROM file_question_info_sections;`
- `SELECT COUNT(*) FROM file_question_info_items;`

4. Verify quarantine status:
- `SELECT COUNT(*) FROM import_quarantine WHERE artifact_family='file_question_info' AND status='open';`
- `SELECT error_code, COUNT(*) FROM import_quarantine WHERE artifact_family='file_question_info' GROUP BY error_code;`

5. Idempotency check:
- Re-run step 1; expected behavior is no duplicate logical runs (existing rows become `updated` or remain unchanged, with stable identity).

### Phase 3: Dual-write integration

Objective: Keep runtime writes and DB mirror behavior consistent with existing dual-write controls.

Todo checklist:

- [x] Extend `Family` literal in `learning_db/ingest/dual_write.py` to include `"file_question_info"`
- [x] Route `"file_question_info"` to `upsert_file_question_info_run` in `_commit_projection`
- [x] Preserve strict/non-strict semantics and operation-log auditing behavior
- [x] Add a centralized post-write helper for detector workflows (shared function) that performs validation + dual-write for `question_sections.json`.
- [x] Update all 5 detector agent workflows to call the centralized post-write helper immediately after writing `question_sections.json`.
- [x] Inside centralized helper, call `maybe_dual_write_snapshot(family="file_question_info", snapshot_path=<written_json_path>, context_root=<ai_study_buddy/context>)`.
- [x] Ensure detector fail/continue behavior follows existing strict-mode semantics from `learning_db.dual_write`.
- [x] Update detector docs/prompts (where relevant) so runtime contract includes post-write dual-write invocation.

Testing plan:

- Add dual-write success test: `maybe_dual_write_snapshot(family="file_question_info", ...)` writes DB rows and operation log.
- Add dual-write failure test in strict and non-strict modes (invalid payload path).
- Add integration tests (or workflow smoke tests) proving detector-run output calls the centralized post-write helper and creates/updates DB rows.

Success criteria:

- Dual-write behavior for `file_question_info` matches existing marking families.
- Failure paths are auditable via operation log and respect strict mode.
- New detector outputs are mirrored to DB during normal runs without waiting for Phase 2 batch import.

Runtime verification status (completed 2026-05-05):

- Real detector run verified: `file_question_info/singapore_primary_math/P6/P6 Math WA1/question_sections.json`
- Real detector run verified: `file_question_info/singapore_primary_math/P6/P6 WA1 practice paper 1/question_sections.json`
- Both runs:
- validated successfully against latest schema (`math-v1.2`)
- carried required run-level timestamps (`created_at`, `updated_at`)
- were mirrored into `study_buddy.db` with expected projected `sections` and `items` rows

### Post-phase handoff

No additional implementation phases are defined in this proposal.

All consumer-layer work, including `resolve_marking_context` integration, `prefer_file_question_info` rollout/default behavior, and reader APIs, is explicitly deferred to proposal 15:

- [15-file-question-info-consumer-layer-and-marking-orchestration.md](./15-file-question-info-consumer-layer-and-marking-orchestration.md)

## Open questions

Resolved decisions:

1. Canonical schema key: standardize on `answers_page_range` (matching `questions_page_range`).
2. `run_id` identity policy: path-stable.
3. Uniqueness constraints: keep both unique `(source_rel_path)` and unique `(primary_file_id, source_content_hash)`.
4. Timestamp policy: detector workflows must populate required ISO 8601 run-level timestamps once per run and reuse them across all timestamp fields written by that run.
5. Section/item ordering: array-based section ordinal + `(run_id, section_ordinal, question_index)` is sufficient.
6. Detector integration point: use a centralized post-write helper for validation + dual-write, called by all 5 detector workflows.
7. Quarantine error code taxonomy: define now.

Quarantine error codes:

- `fqi_json_parse_error`
- `fqi_schema_version_unknown`
- `fqi_schema_validation_failed`
- `fqi_primary_file_id_missing`
- `fqi_primary_file_id_blank`
- `fqi_upsert_failed`
- `fqi_dual_write_failed`

## References

- [13-file-question-info-marking-python-apis.md](./13-file-question-info-marking-python-apis.md)
- `ai_study_buddy/learning_db/ingest/import_context_json.py`
- `ai_study_buddy/learning_db/ingest/dual_write.py`
- `ai_study_buddy/learning_db/core/repository.py`
