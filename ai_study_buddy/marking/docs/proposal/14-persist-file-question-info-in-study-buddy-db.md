# Proposal 14: Persist `file_question_info` in `study_buddy.db`

## Goal

Mirror validated `context/file_question_info/**/question_sections.json` into `study_buddy.db` so we can query by `file_id`/scope/recency without filesystem walks, while keeping the JSON file as canonical source.

## Dependency and current reality

This proposal depends on implemented helpers in `ai_study_buddy.marking.file_question_info`:

- `load_question_sections_json(path)`
- `validate_question_sections_dict(payload)`
- `file_question_info_run_dir_for_pdf(pdf_file, ...)`
- `render_file_question_info_pages_for_pdf(pdf_file, ...)`

Validation support currently includes:

- `chinese-v1.3`
- `high-chinese-v1.1`
- `english-v1.2`
- `math-v1.1`
- `science-v1.1`
- (legacy in map: `math-v1.0`, `science-v1.0`)

Importer/dual-write must use `validate_question_sections_dict` as the gate.

## Non-goals

- Replacing detector agents as canonical writers.
- Moving detector logic into DB import.
- Changing `marking_result` schema in this proposal.

## Data model

Create migration: `ai_study_buddy/learning_db/migrations/00N_file_question_info.sql`.

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
- `answer_pages_range_json TEXT`
- `answers_in_separate_booklet INTEGER`
- `raw_json TEXT NOT NULL`
- PK: `(run_id, ordinal)`

Standardization rule:

- Use one canonical section column: `answer_pages_range_json`.
- Upstream JSON Schemas must standardize on one canonical payload key: `answer_pages_range`.
- Importers should not rely on alias mapping between `answer_page_range` and `answers_page_range`; payloads must already conform to the latest schema contract before DB import.

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

Add to `ai_study_buddy/learning_db/import_context_json.py`:

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

Extend `ai_study_buddy/learning_db/dual_write.py`:

- Add family literal: `"file_question_info"`
- Route to `upsert_file_question_info_run` in `_commit_projection`

This keeps behavior aligned with current dual-write toggles (`LEARNING_DB_ENABLE_DUAL_WRITE`, strict mode, audit logging).

## Read APIs

Add read helpers (location can be `read_marking.py` or a dedicated `read_file_question_info.py`):

- `get_latest_question_sections_for_file_id(conn, file_id: str) -> dict[str, Any] | None`
- `get_file_question_info_run_by_source_rel_path(conn, rel_path: str) -> dict[str, Any] | None`

Behavior:

- Read from `file_question_info_runs`
- Filter `is_deleted = 0`
- For latest-by-file: order by `updated_at DESC`
- Return parsed `raw_json`

## Implementation

### Phase 1: Migration + write model

Objective: Add durable schema for runs/sections/items and write-path upsert logic.

Todo checklist:

- [ ] Add SQL migration `00N_file_question_info.sql` with:
- [ ] `file_question_info_runs`
- [ ] `file_question_info_sections`
- [ ] `file_question_info_items`
- [ ] Required indexes and uniqueness constraints from this proposal
- [ ] Standardize detector schema files to one canonical section key (`answer_pages_range`) across all relevant `question_sections` schemas.
- [ ] When any schema file is changed, bump its `schema_version` and update all schema references in code/docs/tests to the newest version.
- [ ] After schema version bump, migrate all existing `context/file_question_info/**/question_sections.json` files on older versions to the new latest schema version before enabling import.
- [ ] Implement `upsert_file_question_info_run(conn, *, payload, rel_path, source_hash) -> str`
- [ ] Enforce `validate_question_sections_dict(payload)` before any write
- [ ] Resolve `run_id` via `get_or_create_identity_map(... artifact_family="file_question_info" ...)`
- [ ] Replace section/item child rows on run upsert
- [ ] Write operation log event (`entity_type="file_question_info_run"`)

Testing plan:

- Add migration test in `ai_study_buddy/learning_db/tests/test_migrate.py` (or dedicated migration test) to assert new tables/indexes exist.
- Add schema-version contract tests ensuring only canonical `answer_pages_range` is accepted for latest versions, and old-key payloads fail for latest versions.
- Add corpus migration test/script validation: all `context/file_question_info/**/question_sections.json` files report the latest schema version(s) after migration.
- Add repository/importer-level upsert test that inserts valid payload and asserts run + section + item rows.
- Add idempotency test: same `rel_path` + same content hash does not duplicate rows.

Success criteria:

- Migration applies cleanly on empty DB and existing DB.
- Schema files and payload corpus are standardized on latest versions with canonical keys before import rollout.
- One valid payload produces one run row with matching section/item projections.
- Re-upsert of unchanged payload is stable and queryable.

### Phase 2: Import scanner + quarantine wiring

Objective: Make bulk import pick up `file_question_info` artifacts with robust failure handling.

Todo checklist:

- [ ] Extend `import_context_json` scanner to include `context/file_question_info/**/question_sections.json`
- [ ] Dispatch matched files to `upsert_file_question_info_run`
- [ ] On parse/validation/schema failure, quarantine with `artifact_family="file_question_info"`
- [ ] On success, mark matching open quarantine rows resolved

Testing plan:

- Add import happy-path test using fixture `question_sections.json` under `context/file_question_info/...`.
- Add quarantine tests for:
- unknown `schema_version`
- malformed JSON
- missing/blank `primary_file_id`
- Add import idempotency regression test across repeated runs.

Success criteria:

- `import_context_json` reports imports for valid files and quarantines invalid files with explicit error codes.
- Re-running import does not duplicate canonical run identity.

### Phase 3: Dual-write integration

Objective: Keep runtime writes and DB mirror behavior consistent with existing dual-write controls.

Todo checklist:

- [ ] Extend `Family` literal in `learning_db/dual_write.py` to include `"file_question_info"`
- [ ] Route `"file_question_info"` to `upsert_file_question_info_run` in `_commit_projection`
- [ ] Preserve strict/non-strict semantics and operation-log auditing behavior

Testing plan:

- Add dual-write success test: `maybe_dual_write_snapshot(family="file_question_info", ...)` writes DB rows and operation log.
- Add dual-write failure test in strict and non-strict modes (invalid payload path).

Success criteria:

- Dual-write behavior for `file_question_info` matches existing marking families.
- Failure paths are auditable via operation log and respect strict mode.

### Phase 4: Read APIs + backfill

Objective: Provide query entry points and backfill existing corpus.

Todo checklist:

- [ ] Add `get_latest_question_sections_for_file_id(conn, file_id) -> dict | None`
- [ ] Add `get_file_question_info_run_by_source_rel_path(conn, rel_path) -> dict | None`
- [ ] Parse and return `raw_json` payloads
- [ ] Backfill local DB from existing `context/file_question_info` via importer
- [ ] Document basic usage for downstream callers

Testing plan:

- Add read API test covering multiple runs for same `primary_file_id`; assert latest `updated_at` wins.
- Add read-by-path test for exact `source_rel_path`.
- Add backfill smoke test against a small fixture corpus.

Success criteria:

- Callers can retrieve latest validated payload by `file_id` without filesystem walking.
- Backfill succeeds and produces expected row counts for fixture corpus.

### Phase 5: Optional integration follow-up

Objective: Prepare consumer-side adoption after DB mirror is stable.

Todo checklist:

- [ ] Evaluate `resolve_marking_context` integration via `prefer_file_question_info` flag (off by default)
- [ ] Defer default-on switch to follow-up proposal after consumer validation

Testing plan:

- Add gated integration tests only when resolver wiring starts.

Success criteria:

- No behavior change to existing marking context resolution until explicit opt-in.

## References

- [13-file-question-info-marking-python-apis.md](./13-file-question-info-marking-python-apis.md)
- `ai_study_buddy/learning_db/import_context_json.py`
- `ai_study_buddy/learning_db/dual_write.py`
- `ai_study_buddy/learning_db/repository.py`
