# AI Study Buddy - Local Learning DB

> Status: **Active rollout — Phase 3 final gate achieved (`v0.2`)**. Dual-write remains on in production; Phase 4 JSON demotion checklist is now the remaining blocker (final gate measured at **1201/1000**, 0 failures).
>
> Scope: create and maintain `ai_study_buddy/db/study_buddy.db` as the local durable learning-memory database, while preserving current JSON workflows during migration.
>
> Related docs: [DATA_STRATEGY](./L3_DATA_STRATEGY.md), [MARKING_RESULT_ARTIFACT](./L4_MARKING_RESULT_ARTIFACT.md), [STUDENT_MVP_EXPERIENCE](./L4_STUDENT_MVP_EXPERIENCE.md), [ARCHITECTURE](./L1_ARCHITECTURE.md)

---

## Why This Proposal Exists

AI Study Buddy currently has two kinds of persisted local data:

1. `ai_study_buddy/db/pdf_registry.db`, which is backed up and manages PDF file identity, grouping, template/completion relationships, and answer mappings.
2. JSON files under `ai_study_buddy/context/`, especially:
   - `marking_results/`
   - `marking_amendments/`
   - `student_review_states/`

The JSON files started as practical artifacts, but they now contain durable product memory:

- canonical marking facts
- human grading corrections
- student reflections
- review completion state
- question-level mistakes and diagnosis

These are inputs to future diagnostics, planner decisions, tutor memory, parent summaries, and gamification. They should not remain only as non-backed-up loose JSON files.

As of 2026-04-29, the local corpus is already structured enough to migrate:

| Data family | Count | Schema |
|-------------|-------|--------|
| `context/marking_results/**/*.json` | 163 | `marking_result.v1.6` |
| `context/marking_amendments/**/*.json` | 22 | `marking_amendment.v1` |
| `context/student_review_states/**/*.json` | 27 | `student_review_state.v1` |

The goal is not to deploy Postgres immediately. The goal is to build a local SQLite database that acts as a Postgres-shaped rehearsal: durable, queryable, backed up, and easy to migrate later.

Implementation update (2026-05-06):

- Wake-triggered auto backup shell for `study_buddy.db` lives under `ai_study_buddy/utils/backup/` (`run_learning_db_wake.sh`, `install_learning_db_wake.sh`, `uninstall_learning_db_wake.sh`). The pdf-registry `install_pdf_registry_wake.sh` uses `run_wake_all.sh`, which backs up **both** DBs on wake. After upgrades, migrate `~/.wakeup` with `utils/backup/migrate_wakeup_backup_paths.sh` if needed.
- backup retention tiering is implemented via:
  - `python3 -m ai_study_buddy.learning_db.cli.apply_backup_tiering`

Implementation update (2026-05-22) — **Phase 3 provisional gate (200 dual-writes)**:

- Production `operation_log` dual-write burn-in recorded below (**Phase 3 provisional sign-off**). Runtime posture unchanged: **`LEARNING_DB_ENABLE_DUAL_WRITE=1`**, **`LEARNING_DB_STRICT_DUAL_WRITE=0`**, **`LEARNING_DB_ENABLE_JSON_EXPORT=1`**, **`LEARNING_DB_ENABLE_READS=1`**.
- Re-measure before Phase 4: `python3 -m ai_study_buddy.learning_db.cli.dual_write_stats` and `python3 -m ai_study_buddy.learning_db.cli.dual_write_stats --target-min-ops 1000`.

Implementation update (2026-05-28) — **Phase 3 final gate (1,000 dual-writes) achieved**:

- Re-measured on production DB (`python3 -m ai_study_buddy.learning_db.cli.dual_write_stats --target-min-ops 1000`): **total=1201 succeeded=1201 failed=0 success_rate=100.0000%**.
- Final numeric gate status: **PASS** (`min_ops(1000)=PASS`, `success_rate(99.9000%)=PASS`).
- Runtime posture unchanged while completing Phase 4 checklist: **`LEARNING_DB_ENABLE_DUAL_WRITE=1`**, **`LEARNING_DB_STRICT_DUAL_WRITE=0`**, **`LEARNING_DB_ENABLE_JSON_EXPORT=1`**, **`LEARNING_DB_ENABLE_READS=1`**.

---

## Scope

### In Scope

1. Create `ai_study_buddy/db/study_buddy.db`.
2. Add migration files for the schema under a package-owned location.
3. Import existing marking results, amendments, and student review states into the DB.
4. Preserve source JSON path, schema version, content hash, and raw JSON for audit/export compatibility.
5. Add repository APIs that can read/write DB rows while preserving current JSON snapshot behavior during rollout.
6. Replace filesystem scans for latest marking artifact lookup with DB-backed queries once the index is trusted.
7. Add backup support for `study_buddy.db` mirroring the existing `pdf_registry.db` backup pattern.
8. Keep `pdf_registry.db` as the file registry rather than merging the two DBs.

### Out of Scope

1. Moving raw PDFs out of Google Drive.
2. Moving regenerated page renders/crops/marking assets into DB.
3. Hosting Postgres now.
4. Implementing pgvector embeddings.
5. Replacing `pdf_registry.db`.
6. Rewriting Review Workspace UI.
7. Changing marking-result schema semantics as part of this migration.

---

## Design

### Core Decision

Create a second local SQLite database:

`ai_study_buddy/db/study_buddy.db`

This DB is the local source of truth for durable learning/product memory. It should be designed so the same logical schema can later move to Postgres.

### Relationship to Existing Stores

| Store | Role |
|-------|------|
| `pdf_registry.db` | File/document registry: PDFs, templates, completions, groups, mappings |
| `study_buddy.db` | Learning/product memory: marking facts, amendments, review states, notes, future events/mastery |
| `context/marking_results/` | Transitional canonical JSON snapshots and export artifacts |
| `context/marking_amendments/` | Transitional amendment JSON snapshots |
| `context/student_review_states/` | Transitional review-state JSON snapshots |
| `context/marking_assets/` | Regenerable visual evidence cache |

### Postgres-Shaped SQLite Rules

To keep future migration easy:

1. Use stable text IDs for domain identity.
2. Do not rely on SQLite `rowid` as a product identifier.
3. Keep SQL portable where practical.
4. Use explicit schema migration files.
5. Store timestamps consistently as ISO-8601 text.
6. Store JSON payloads as text in SQLite, with a clear future mapping to Postgres `jsonb`.
7. Put all DB access behind repository APIs.
8. Keep foreign keys enabled.
9. Use generated stable IDs (UUID text) for primary identity, not path-derived IDs.

### Proposed Package Location

New package:

`ai_study_buddy/learning_db/`

Suggested files:

```text
ai_study_buddy/learning_db/
  __init__.py
  connection.py
  migrations/
    001_initial_schema.sql
  migrate.py
  repository.py
  import_context_json.py
  backup_study_buddy_db.py
  validate_study_buddy_db.py
```

### Initial Schema

The first schema should support the existing JSON families without forcing a full future student-model design.

Migration rule: the initial schema must be **lossless** for the current JSON contracts. Every top-level object should be preserved in `raw_json`, and every nested object/array that is not fully normalized should also be preserved in a `*_json` column. Normalized scalar columns are an index/query convenience, not a replacement for the original payload.

#### `schema_migrations`

Tracks applied DB migrations.

Key fields:

- `version`
- `applied_at`

#### `marking_artifacts`

One row per canonical marking result.

Key fields:

- `artifact_id` text primary key
- `schema_version`
- `artifact_path`
- `artifact_stem`
- `source_content_hash`
- `created_at`
- `updated_at`
- `student_id`
- `student_name`
- `subject_context`
- `attempt_file_id`
- `attempt_file_path`
- `template_file_id`
- `template_file_path`
- `book_group_id`
- `book_label`
- `unit_file_id`
- `unit_file_path`
- `unit_label`
- `answer_file_id`
- `answer_file_path`
- `answer_page_start`
- `answer_page_end`
- `starts_mid_page`
- `ends_mid_page`
- `answer_mapping_source`
- `answer_mapping_notes`
- `marking_asset`
- `is_partial`
- `template_attempt_group_id`
- `attempt_sequence`
- `attempt_label`
- `question_selection_json`
- `context_resolution_json`
- `summary_total_marks`
- `summary_earned_marks`
- `summary_percentage`
- `summary_overall_assessment`
- `summary_human_note`
- `review_meta_updated_at`
- `review_meta_updated_by`
- `generation_produced_by`
- `generation_mode`
- `generation_notes`
- `review_meta_json`
- `generation_json`
- `context_json`
- `summary_json`
- `row_version`
- `is_deleted`
- `deleted_at`
- `deleted_by`
- `delete_reason`
- `raw_json`

`artifact_id` should be a stable generated ID (UUID text). For imported historical artifacts, generate the ID once and preserve it on re-import through deterministic matching on immutable import keys (for example source path + content hash) to keep imports idempotent without path-derived primary identity.

`artifact_path` remains important for traceability and JSON compatibility, but it is not the primary identity because artifact filenames can change after a marking run.

#### `marking_question_results`

One row per `question_results[]` item.

Key fields:

- `artifact_id`
- `result_id`
- `scoring_status`
- `outcome`
- `max_marks`
- `earned_marks`
- `student_answer`
- `correct_answer`
- `diagnosis_mistake_type`
- `diagnosis_reasoning`
- `diagnosis_confidence`
- `human_note`
- `error_tags_json`
- `skill_tags_json`
- `diagnosis_json`
- `raw_json`

Primary key:

- `(artifact_id, result_id)`

#### `marking_question_page_map`

One row per `context.question_page_map[]` item.

Key fields:

- `artifact_id`
- `result_id`
- `attempt_page_start`
- `confidence`
- `source`
- `evidence_image`
- `note`
- `raw_json`

Primary key:

- `(artifact_id, result_id)`

#### `marking_amendments`

One row per amendment artifact.

Key fields:

- `amendment_id`
- `artifact_id`
- `schema_version`
- `amendment_path`
- `source_content_hash`
- `student_id`
- `subject_context`
- `attempt_file_id`
- `marking_result_path`
- `review_meta_updated_at`
- `review_meta_updated_by`
- `summary_overrides_json`
- `question_amendments_json`
- `question_page_map_amendments_json`
- `context_json`
- `review_meta_json`
- `row_version`
- `is_deleted`
- `deleted_at`
- `deleted_by`
- `delete_reason`
- `raw_json`

The `artifact_id` should resolve from `context.marking_result_path`. Keep `marking_result_path` exactly as stored in the JSON because existing companion artifacts use that relative path as their stable link to the base marking result.

#### `marking_question_amendments`

Optional normalized child table for queryable amendment rows.

Key fields:

- `amendment_id`
- `result_id`
- `fields_json`
- `reviewer_reason`
- `evidence_json`
- `updated_at`
- `updated_by`
- `raw_json`

Primary key:

- `(amendment_id, result_id)`

#### `marking_page_map_amendments`

Optional normalized child table for queryable page-map amendment rows.

Key fields:

- `amendment_id`
- `result_id`
- `attempt_page_start`
- `confidence`
- `updated_at`
- `updated_by`
- `raw_json`

Primary key:

- `(amendment_id, result_id)`

#### `student_review_states`

One row per review-state artifact.

Key fields:

- `review_state_id`
- `artifact_id`
- `schema_version`
- `review_state_path`
- `source_content_hash`
- `student_id`
- `subject_context`
- `attempt_file_id`
- `marking_result_path`
- `template_attempt_group_id`
- `attempt_sequence`
- `review_status`
- `created_at`
- `updated_at`
- `updated_by`
- `summary_json`
- `question_reviews_json`
- `attempt_notes_json`
- `student_subject_notes_json`
- `context_json`
- `review_meta_json`
- `row_version`
- `is_deleted`
- `deleted_at`
- `deleted_by`
- `delete_reason`
- `raw_json`

The current writer stores both `summary.review_status` and top-level `review_status`. Import both via `summary_json` and the scalar `review_status`; validation should flag disagreements if they ever appear.

#### `student_review_notes`

One row per student/parent/teacher note.

Key fields:

- `note_id`
- `review_state_id`
- `artifact_id`
- `scope` (`question`, `attempt`, `student_subject`)
- `result_id`
- `review_status`
- `author_role`
- `note_text`
- `updated_at`
- `raw_json`

For `question_reviews[]`, `scope = question` and `result_id` is populated. For `attempt_notes[]`, `scope = attempt` and `result_id` is null. For `student_subject_notes[]`, `scope = student_subject` and `result_id` is null.

#### `operation_log`

Append-only audit/diagnostic table for write operations, mirroring the intent of `pdf_registry.db` operation logging.

Key fields:

- `operation_id` text primary key
- `occurred_at`
- `actor`
- `operation_type` (for example `import_marking_result`, `write_marking_artifact`, `save_amendment`, `save_review_state`, `export_json_snapshot`, `backup_db`)
- `entity_type` (for example `marking_artifact`, `marking_amendment`, `student_review_state`)
- `entity_id`
- `status` (`started`, `succeeded`, `failed`)
- `error_code`
- `error_message`
- `metadata_json`

This log should support:

1. debugging migration and dual-write issues
2. identifying partial failures and retries
3. reconstructing operational history for maintenance tasks

#### `import_identity_map`

Stable ID reuse table for importer idempotency.

Key fields:

- `map_id` text primary key (UUID v7)
- `artifact_family` (`marking_result` | `marking_amendment` | `student_review_state`)
- `source_path` (normalized relative path)
- `source_content_hash` (SHA-256 hex)
- `artifact_id`
- `first_seen_at`
- `last_seen_at`

Unique key:

- `(artifact_family, source_path, source_content_hash)`

On re-import with matching unique key, importer must reuse the mapped `artifact_id` and update `last_seen_at`.

#### `import_quarantine`

Importer quarantine table for malformed/unresolvable artifacts.

Key fields:

- `quarantine_id` text primary key (UUID v7)
- `artifact_family` (`marking_result` | `marking_amendment` | `student_review_state`)
- `source_path`
- `source_content_hash`
- `schema_version_detected`
- `failure_stage` (`read_json` | `schema_validate` | `fk_resolve` | `transform` | `upsert` | `io`)
- `error_code`
- `error_message`
- `raw_payload_json` (nullable)
- `status` (`open` | `resolved` | `ignored`)
- `retry_count`
- `first_seen_at`
- `last_seen_at`
- `resolved_at` (nullable)
- `resolution_note` (nullable)

Behavior:

- Importer must quarantine per-file failures and continue processing other files.
- Retry runs should update `retry_count` and `last_seen_at`.
- Successful retry marks row as `resolved` and stamps `resolved_at`.

### Real Example Mapping

For this marking result:

`marking_results/abigail/singapore_primary_english/English Weekly Revision Primary 1 - 09 Practice 9 (Term 1 Week 9)__20260425_105325.json`

The DB would store:

- one `marking_artifacts` row with `attempt_file_id = e1cc0ae1-f9e5-4687-92c5-5bc260e503d7`
- eleven `marking_question_results` rows: `A1` through `C1`
- eleven `marking_question_page_map` rows mapping `A*` to page 1, `B*` to page 2, and `C1` to page 3

For the paired amendment:

`marking_amendments/abigail/singapore_primary_english/English Weekly Revision Primary 1 - 09 Practice 9 (Term 1 Week 9)__20260425_105325.json`

The DB would store a `C1` amendment:

```json
{
  "outcome": "correct",
  "earned_marks": 5
}
```

with reviewer reason:

```text
The student's writing is good enough.
```

For the paired review state:

`student_review_states/abigail/singapore_primary_english/English Weekly Revision Primary 1 - 09 Practice 9 (Term 1 Week 9)__20260425_105325.json`

The DB would store:

- `review_status = completed`
- one question note for `B3`: `The student didn't know what a "drawer" vs. "shelf" is.`

### Current Writers and Consumers

This project should migrate the current production seams, not invent a parallel data path. The DB layer should preserve the behavior of the existing writers and consumers before any cleanup or redesign.

#### Canonical marking results

Current JSON location:

`context/marking_results/<student>/<subject_context>/<artifact_stem>.json`

Current producer:

- `ai_study_buddy.marking.core.artifact_writer.write_marking_artifact(...)`

Producer responsibilities today:

1. Converts `MarkingArtifact` to a dict.
2. Sets explicit schema version (`marking_result.v1.6` by default).
3. Normalizes `created_at` and `updated_at` to marking time conventions.
4. Applies attempt metadata:
   - `template_attempt_group_id`
   - `attempt_sequence`
   - `attempt_label`
5. Infers `is_partial` when needed.
6. Sanitizes local/private paths into placeholder paths.
7. Enforces the context resolver contract.
8. Builds the deterministic artifact path when `output_path` is not supplied.
9. Applies `context.marking_asset`.
10. Validates the final payload against the schema.
11. Creates the marking asset directory skeleton.
12. Writes pretty JSON to `context/marking_results/**`.

Current direct consumers:

- `ai_study_buddy.marking.core.artifact_lookup.find_marking_artifacts_for_attempt(...)`
  - scans `context/marking_results/<student_slug>/**/*.json`
  - loads JSON payloads
  - matches by `context.attempt_file_id` first, with legacy path fallback
  - sorts by `created_at` descending
- `ai_study_buddy.marking.review.attempt_service`
  - builds the Review Workspace attempt index
  - reads latest marking summary, context, score, partial status, and attempt metadata
- `ai_study_buddy.marking.review.detail_service`
  - builds attempt detail payloads
  - loads base marking result
  - normalizes it for frontend display
  - applies amendment overlays to create resolved marking results
  - reads `context.marking_asset` to expose attempt/answer image URLs
- `ai_study_buddy.marking.review.note_service`
  - resolves the latest marking artifact before allowing review-state writes
  - reads context fields needed for companion review-state context
- `ai_study_buddy.marking.review.amendment_service`
  - resolves and loads the latest base marking result
  - validates amendment rows against base `question_results[]` and `question_page_map[]`
  - returns resolved marking results after applying overlays
- `ai_study_buddy.marking.workflows.report_renderer`
  - renders markdown learning reports from canonical JSON
- `ai_study_buddy.marking.core.artifact_cleanup`
  - removes one run's marking JSON, derived report, and marking asset bundle together
- Maintenance workflows under `ai_study_buddy.marking.workflows`
  - backfill/migration scripts scan and rewrite `context/marking_results/**`

DB migration implication:

- `write_marking_artifact(...)` remains the validation/normalization gate.
- The DB write should happen only after the payload has passed the same schema and context-contract checks.
- Latest-artifact lookup should eventually become an indexed query over `marking_artifacts.attempt_file_id`, with filesystem scan retained as a fallback during parity validation.
- Cleanup and report rendering need an artifact reference that can still resolve to the JSON snapshot path while JSON compatibility remains enabled.

#### Marking amendments

Current JSON location:

`context/marking_amendments/<student>/<subject_context>/<artifact_stem>.json`

Current producers:

- `ai_study_buddy.marking.review.amendment_service.put_amendments(...)`
- `ai_study_buddy.marking.review.repository.StudentReviewRepository.save_amendment(...)`

Producer responsibilities today:

1. Resolve latest base marking artifact with `find_marking_artifacts_for_attempt(...)`.
2. Load the base marking JSON.
3. Build amendment context from the base artifact and attempt ID.
4. Load existing amendment JSON if present.
5. Normalize incoming summary, question, and page-map amendments.
6. Upsert amendment rows by `result_id`.
7. Stamp `updated_at` and `updated_by`.
8. Validate amendments against base question IDs, marks, outcomes, and valid attempt pages.
9. Save pretty JSON to `context/marking_amendments/**`.
10. Return resolved marking result with the overlay applied.

Current direct consumers:

- `ai_study_buddy.marking.review.detail_service`
  - loads raw amendment JSON
  - normalizes amendment state
  - applies overlay to base marking result
- `ai_study_buddy.marking.review.amendment_service`
  - reads existing amendment JSON during subsequent amendment writes
  - validates and merges incoming changes
- Review Workspace frontend via backend detail response
  - receives `amendment_state`, `marking_result_base`, and `marking_result_resolved`

DB migration implication:

- `put_amendments(...)` should continue to own validation and merge behavior.
- DB rows should preserve both normalized queryable amendment rows and the exact amendment JSON payload.
- `marking_result_path` must remain stored exactly as written because it is the current stable companion link to the base artifact.

#### Student review states

Current JSON location:

`context/student_review_states/<student>/<subject_context>/<artifact_stem>.json`

Current producers:

- `ai_study_buddy.marking.review.note_service.put_review_state(...)`
- `ai_study_buddy.marking.review.repository.StudentReviewRepository.save_review_state(...)`

Producer responsibilities today:

1. Validate `review_status`.
2. Resolve latest base marking artifact with `find_marking_artifacts_for_attempt(...)`.
3. Load base marking context.
4. Preserve existing `created_at` when updating a review-state file.
5. Normalize question reviews, attempt notes, and student-subject notes.
6. Stamp updated note rows.
7. Persist both top-level `review_status` and `summary.review_status`.
8. Save pretty JSON to `context/student_review_states/**`.

Current direct consumers:

- `ai_study_buddy.marking.review.attempt_service`
  - loads review state to show `review_status` in the attempt index
- `ai_study_buddy.marking.review.detail_service`
  - loads review state for the attempt detail response
- `ai_study_buddy.marking.review.repository.StudentReviewRepository.load_review_state(...)`
  - normalizes missing or malformed review files to default empty state
- Review Workspace frontend via backend responses
  - displays and edits review status and notes

DB migration implication:

- `put_review_state(...)` should continue to own normalization and timestamp behavior.
- DB rows should preserve both the top-level status and the `summary` object to remain lossless.
- The normalized `student_review_notes` table should be treated as a query/index projection over `question_reviews[]`, `attempt_notes[]`, and `student_subject_notes[]`.

#### Derived and maintenance consumers

Several consumers are not product-facing but still matter for migration safety:

- `report_renderer` depends on canonical marking JSON as markdown input.
- `remove_run_artifacts` expects a JSON path under `context/marking_results/**`.
- Backfill workflows may scan and rewrite historical JSON artifacts.
- Tests construct temporary `marking_results/**`, `marking_amendments/**`, and `student_review_states/**` trees to verify behavior.

DB migration implication:

- Keep JSON snapshot export enabled during the migration.
- Do not remove path-based APIs until these maintenance workflows have DB-aware replacements or explicit JSON-export inputs.
- Validation should compare DB-backed behavior against these current filesystem consumers before flipping defaults.

### Repository Changes

Proposed migration path:

1. Add `LearningDbRepository`.
2. Add importer that populates the DB from current JSON.
3. Add dual-write mode:
   - write DB transaction
   - emit JSON snapshot for compatibility
4. Add DB-backed lookup:
   - query `marking_artifacts where attempt_file_id = ? order by created_at desc, artifact_path asc`
5. Keep filesystem fallback until validation shows parity.

Dual-write failure policy (explicit):

1. During compatibility phase, dual-write is **strict**: request-level success requires both DB write and JSON snapshot write to succeed.
2. If JSON snapshot write fails, rollback the DB transaction and return an error.
3. If DB commit fails after a JSON snapshot was emitted, delete the just-written snapshot best-effort and log a failed operation with cleanup result.
4. Every dual-write attempt must append `operation_log` rows (started/succeeded/failed) with enough metadata to replay or investigate.
5. After parity is proven and JSON is downgraded to debug/export artifacts, DB writes remain authoritative and JSON export can be async/best-effort.

### Operation Layer Contract (Explicit CRUD)

This proposal should define operations as explicitly as `pdf_file_manager/SPEC.md`: each write path has one owner, deterministic side effects, and operation-log semantics.

#### Design goals

1. Give Review Workspace and maintenance scripts a stable Python API surface.
2. Ensure every C/U/D operation has explicit invariants, failure behavior, and audit entries.
3. Keep read paths side-effect free (no operation-log write on reads).
4. Keep operation semantics stable even while storage shifts from JSON-first to DB-first.

#### Canonical API surface (proposed)

`LearningDbRepository` should expose operation-oriented methods:

- Create:
  - `create_marking_artifact(payload, *, write_json_snapshot=True, actor='system')`
  - `create_or_replace_amendment(payload, *, write_json_snapshot=True, actor='system')`
  - `create_or_replace_review_state(payload, *, write_json_snapshot=True, actor='system')`
- Read:
  - `get_latest_marking_artifact_for_attempt(attempt_file_id, *, prefer_db=True, fallback_filesystem=True)`
  - `get_marking_artifact_by_id(artifact_id)`
  - `get_amendment_by_artifact_id(artifact_id)`
  - `get_review_state_by_artifact_id(artifact_id)`
  - `list_operation_log(...)`
- Update:
  - `update_amendment(...)` (logical upsert on amendment rows by `result_id`)
  - `update_review_state(...)` (logical upsert on notes/status; preserve `created_at`)
  - `relink_artifact_paths(...)` (traceability metadata update only; must not change identity)
- Delete:
  - `delete_marking_artifact(...)` (normally maintenance-only; policy-gated)
  - `delete_amendment(...)` (policy-gated; generally replaced by update flows)
  - `delete_review_state(...)` (policy-gated; generally replaced by update flows)

Notes:

- During migration, "create" and "update" methods may still emit JSON snapshots for compatibility.
- Post-parity, JSON emission is optional debug/export behavior, not required runtime behavior.

#### Operation types and log requirements

Every C/U/D operation should append at least one `operation_log` row with:

- `operation_type` from a controlled enum (initial set):
  - `import_marking_result`
  - `import_marking_amendment`
  - `import_student_review_state`
  - `create_marking_artifact`
  - `upsert_marking_amendment`
  - `upsert_student_review_state`
  - `delete_marking_artifact`
  - `delete_marking_amendment`
  - `delete_student_review_state`
  - `export_json_snapshot`
  - `backup_db`
- `entity_type`, `entity_id`
- lifecycle status (`started`, `succeeded`, `failed`)
- structured metadata and error fields

Reads do not write `operation_log` entries.

#### CRUD invariants by entity family

`marking_artifacts`

- Create requires schema-valid payload (`marking_result.v1.x`) and context-contract validation before persistence.
- `artifact_id` is immutable after creation.
- Path fields (`artifact_path`, file-path context fields) are mutable metadata and must not be used as identity keys.
- Deleting an artifact is a maintenance operation and must define companion cleanup behavior for dependent amendment/review rows and optional JSON snapshots.

`marking_amendments`

- Upsert key is the logical companion of the base artifact (preserve `marking_result_path` as written + resolved `artifact_id`).
- Question/page-map amendment rows are validated against base artifact question/page constraints.
- Update preserves audit trail via `operation_log`; overwrite-in-place must still keep raw payload snapshots.

`student_review_states`

- Upsert key is the companion of the base artifact.
- `created_at` is stable after first creation; later writes only change `updated_at` and mutable review content.
- Top-level `review_status` and `summary.review_status` are both preserved; mismatches are validation warnings/errors.

#### Transaction and failure semantics

For each write operation, define one transaction boundary:

1. Validate input and resolve dependencies (base artifact existence, IDs, schema).
2. Write DB rows in one transaction.
3. If compatibility mode requires JSON snapshot, write snapshot according to strict dual-write policy.
4. Emit operation-log entries for start/success/failure with correlation metadata.

Required behavior:

- No silent partial success.
- All retryable failures must be identifiable from `operation_log`.
- Any compensating action (rollback/cleanup) must be logged with outcome.

#### Edge-case policy baseline

The operation layer should explicitly document behavior for:

- companion artifact missing (`amendment`/`review_state` references unknown base artifact)
- duplicate create requests (idempotent import keys vs non-idempotent runtime writes)
- stale writes (updating with older `updated_at` / conflicting edit windows)
- JSON snapshot write failure in compatibility mode
- path rename/move after artifact creation (identity must remain stable; only metadata updates)
- delete requests for non-existent rows (error vs no-op policy must be explicit per operation)

#### Operation matrix (initial)

| Operation | Preconditions | Main side effects | Operation log entries | Failure semantics |
|-----------|---------------|-------------------|-----------------------|-------------------|
| `import_marking_result` | Source JSON exists, schema-valid payload, import key resolvable | Upsert `marking_artifacts` + child rows; keep stable `artifact_id`; preserve `raw_json` + hashes + source path | `started` -> `succeeded`/`failed` | Idempotent by import key; malformed payload quarantined and logged as failed |
| `import_marking_amendment` | Base artifact resolvable by companion link/path, schema-valid amendment payload | Upsert `marking_amendments` + optional normalized child rows; preserve `marking_result_path` exactly | `started` -> `succeeded`/`failed` | If base artifact unresolved, fail import row and log diagnostic metadata |
| `import_student_review_state` | Base artifact resolvable, schema-valid review-state payload | Upsert `student_review_states` + `student_review_notes`; preserve `created_at` on re-import | `started` -> `succeeded`/`failed` | If base artifact unresolved or status invalid, fail and log details |
| `create_marking_artifact` | Payload passes current writer validation + context contract | Transactional DB write for artifact + child rows; optional JSON snapshot in compatibility mode | `create_marking_artifact` + optional `export_json_snapshot` | In strict compatibility mode, JSON write failure triggers DB rollback and operation failure |
| `upsert_marking_amendment` | Latest base artifact exists; amendment rows validate against base question/page constraints | Transactional upsert of amendment root + child projections; optional JSON snapshot | `upsert_marking_amendment` + optional `export_json_snapshot` | Validation error or write failure returns no partial success; cleanup/rollback outcome logged |
| `upsert_student_review_state` | Latest base artifact exists; `review_status` valid | Transactional upsert of review-state + notes; preserve first `created_at`; optional JSON snapshot | `upsert_student_review_state` + optional `export_json_snapshot` | Same strict dual-write behavior during compatibility phase |
| `relink_artifact_paths` | Target artifact exists; caller has maintenance/admin scope | Update mutable path fields only (`artifact_path`, related traceability fields) | operation with `status` lifecycle | Never changes `artifact_id`; attempts to mutate identity are rejected and logged failed |
| `delete_marking_artifact` | Maintenance policy allows delete; target exists (or explicit no-op policy) | Default path writes tombstone fields (`is_deleted`, `deleted_at`, `deleted_by`, `delete_reason`); hard-delete only in privileged path; optionally mark/remove JSON debug snapshots | `delete_marking_artifact` (+ cleanup metadata) | Missing-row behavior follows policy (default no-op + warning for maintenance reruns); hard-delete intent must be explicit and logged |
| `delete_marking_amendment` | Maintenance policy allows delete | Default path writes tombstone fields; hard-delete only in privileged path | `delete_marking_amendment` | Missing-row behavior follows policy (default no-op + warning for maintenance reruns) |
| `delete_student_review_state` | Maintenance policy allows delete | Default path writes tombstone fields; hard-delete only in privileged path | `delete_student_review_state` | Missing-row behavior follows policy (default no-op + warning for maintenance reruns) |
| `backup_db` | DB file exists and destination writable | Copy DB backup to retention/cold-storage strategy aligned with `pdf_registry.db` | `backup_db` | Backup failures return explicit error and include destination/context metadata |
| `list/read operations` | Query args valid | Read-only retrieval from DB (with optional filesystem fallback for parity phase); tombstoned rows excluded by default | none | Reads never create operation-log entries |

---

### Backup and Maintenance

Add a backup script mirroring the `pdf_registry.db` backup flow:

```text
python3 -m ai_study_buddy.learning_db.cli.backup_study_buddy_db
```

Default backup destination should be the same cloud-synced DB folder and retention model used by `pdf_registry.db` (including cold-storage workflow), with an env override:

`STUDY_BUDDY_DB_BACKUP_DIR`

Maintenance commands:

```text
python3 -m ai_study_buddy.learning_db.core.migrate
python3 -m ai_study_buddy.learning_db.ingest.import_context_json --dry-run
python3 -m ai_study_buddy.learning_db.ingest.import_context_json
python3 -m ai_study_buddy.learning_db.cli.validate_study_buddy_db
```

Validation should check:

- imported counts match source JSON counts
- every imported artifact has a content hash
- every amendment/review state resolves to a marking artifact
- latest-artifact lookup matches filesystem lookup during compatibility phase
- DB-derived resolved score matches existing amendment overlay behavior
- operation log coverage exists for import and dual-write operations

---

## Migration Plan

### Runtime flags (required before rollout)

Use explicit feature flags so each phase is reversible:

- `LEARNING_DB_ENABLE_READS` (default: `1`)
- `LEARNING_DB_ENABLE_DUAL_WRITE` (default: `1`)
- `LEARNING_DB_STRICT_DUAL_WRITE` (default: `0` — audit + keep JSON on projection failure; set `1` for strict rollback)
- `LEARNING_DB_ENABLE_JSON_EXPORT` (default: `1` during compatibility, can move to `0`/best-effort later)
- `LEARNING_DB_READ_FALLBACK_FILESYSTEM` (default: `1` until cutover)

### Phase 0 - Foundation and schema bootstrapping

Create DB plumbing, schema, migration runner, and operation logging with no product read/write changes.

Acceptance criteria:

- schema migration is idempotent on fresh/existing DB
- `operation_log` exists and supports lifecycle status entries
- repository methods can be instantiated in tests without changing runtime behavior

### Phase 1 - Historical import (read-only indexing)

Import existing JSON artifacts into DB as an index/projection while JSON remains authoritative.

Acceptance criteria:

- importer is idempotent across repeated runs
- counts/hash parity report passes for artifact/amendment/review-state families
- stable `artifact_id` values remain consistent across re-import
- unresolved/malformed artifacts are quarantined and reported (not silently dropped)

### Phase 2 - Read-path parity with fallback

Enable DB-backed read APIs for lookup/index use cases while keeping filesystem fallback.

Acceptance criteria:

- `get_latest_marking_artifact_for_attempt(...)` parity matches filesystem lookup
- Review Workspace attempt index parity matches current behavior
- detail payload parity matches current base+amendment resolved output
- fallback can be forced on and off via flags
- **Phase 2 -> Phase 3 numeric gate (required):**
  - critical parity fields must be `100%` (`0` critical mismatches): latest-artifact selection, artifact-attempt linkage, resolved score totals, review status
  - non-critical drift (ordering/format-only differences) must be `<= 0.1%` of validated attempts and explicitly documented
  - parity checks pass on full corpus and remain stable for `3` consecutive validation runs on unchanged data
  - no open critical quarantine items affecting active attempts

### Phase 3 - Controlled dual-write for create/update flows

Enable repository-owned writes for marking artifacts, amendments, and review states, with strict compatibility dual-write semantics.

Acceptance criteria:

- each create/update operation writes DB rows and JSON snapshot (when JSON export enabled)
- strict dual-write behavior is verified (JSON failure -> DB rollback; DB commit failure -> snapshot cleanup best-effort + failed log)
- C/U/D operations emit `operation_log` lifecycle entries with actor/entity/error metadata
- rollback path (`LEARNING_DB_ENABLE_DUAL_WRITE=0`) restores JSON-first behavior safely
- second-order write consumers (skills/scripts/orchestrators such as `mark-student-work-multi-agent-v2`) are updated to rely on marking/repository APIs, not direct filesystem scans or ad-hoc JSON writes
- **Phase 3 -> Phase 4 numeric gate (required):**
  - provisional gate: dual-write success rate `>= 99.9%` over a rolling validation window of at least `200` write operations (early rollout)
  - final gate before default DB-read cutover: dual-write success rate `>= 99.9%` over at least `1,000` write operations
  - strict dual-write invariant violations = `0` (no acknowledged DB success with missing required JSON snapshot while compatibility mode is enabled)
  - unresolved write failures older than `24h` = `0`
  - operation-log coverage for C/U/D writes = `100%` (no missing lifecycle entries)
  - rollback drill succeeds at least once during phase (`LEARNING_DB_ENABLE_DUAL_WRITE=0` restores JSON-first writes without data loss)

### Phase 4 - Operational DB source (JSON demoted)

Use DB as default operational source for app reads/writes. Keep JSON as debug/export artifact rather than required runtime state.

Acceptance criteria:

- default runtime no longer scans `context/marking_results/**` for normal reads
- JSON exports can be regenerated from DB for supported families
- maintenance workflows requiring JSON either consume export outputs or use DB-aware replacements
- operation log is sufficient to trace all production write operations
- second-order consumer docs/instructions no longer describe JSON files as primary runtime state (only debug/export artifacts)

### Phase 5 - Backup/retention hardening and cutover sign-off

Finalize backup, retention, and operational readiness using the same cold-storage/retention strategy as `pdf_registry.db`.

Acceptance criteria:

- scheduled/manual backup flows succeed and are logged
- retention behavior matches `pdf_registry.db` policy
- restore drill succeeds on a representative DB backup
- go-live checklist signed off (parity, rollback, backup, auditability)

### Future Postgres Migration

The eventual Postgres migration should be a direct ETL:

1. Create equivalent Postgres schema.
2. Export SQLite rows as JSONL/CSV or read directly via Python.
3. Insert rows preserving IDs, timestamps, raw JSON, and hashes.
4. Verify row counts, foreign keys, content hashes, and latest-artifact query parity.
5. Swap repository connection configuration.

---

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| DB and JSON drift during dual-write phase | Use strict dual-write semantics during compatibility phase, store content hashes, and log every write in `operation_log` |
| Premature schema overdesign | Start with current artifact families only; keep future mastery/events out until needed |
| SQLite-specific behavior blocks Postgres migration | Use portable SQL, text IDs, explicit migrations, repository layer |
| Existing tools rely on JSON paths | Preserve JSON snapshots and source paths during rollout |
| Corrupt import from malformed JSON | Validate schemas before import; quarantine invalid files in validation report |
| Assets mistaken for durable memory | Store only `marking_asset`; keep page renders/crops regenerable |
| Attempt sequence changes under DB writes | Compare DB-derived sequence with current filesystem-derived sequence before flipping writer behavior |
| Artifact path/file name changes break identity links | Use stable generated IDs as primary keys; keep paths as mutable traceability fields |

Rollback strategy:

1. Keep JSON snapshots during all early phases.
2. Gate DB reads behind `LEARNING_DB_ENABLE_READS`.
3. Gate dual-write behind `LEARNING_DB_ENABLE_DUAL_WRITE` (with strict mode via `LEARNING_DB_STRICT_DUAL_WRITE`).
4. Keep filesystem fallback available via `LEARNING_DB_READ_FALLBACK_FILESYSTEM` until cutover sign-off.
5. If DB behavior is wrong, disable DB reads/writes and continue with existing JSON flow.

---

## Implementation Decisions (Locked)

These decisions are now fixed for implementation unless explicitly revised.

1. **Stable ID generation policy**
   - **Decision:** use UUID `v7` for newly created rows (`artifact_id`, `amendment_id`, `review_state_id`, `note_id`, `operation_id`).
   - Rationale: v7 keeps IDs time-ordered while preserving high-entropy uniqueness, which better matches append-heavy write patterns and operational querying.
   - **Decision:** use a table-backed importer identity mapping to preserve stable IDs across repeated imports.
   - Mapping key: `(artifact_family, source_path, source_content_hash)` with `artifact_id` as mapped value and last-seen timestamps.
   - On re-import with matching key, reuse mapped `artifact_id`; do not mint a new ID.
   - Keep imported historical IDs stable; do not rewrite IDs after first successful import.
   - Treat all IDs as opaque strings at API boundaries (no business logic should parse UUID internals).

2. **Write concurrency and conflict policy**
   - **Decision:** use optimistic concurrency with compare-and-swap checks on mutable root rows.
   - Add `row_version` (integer) to mutable root tables and require updates with `WHERE id = ? AND row_version = ?`.
   - On successful update, increment `row_version`; on mismatch, return explicit conflict (do not silently overwrite).
   - Default conflict behavior is `reject-and-retry` after caller reloads latest state.
   - Do not use implicit last-write-wins for user-edited entities (`marking_amendments`, `student_review_states`).
   - Maintenance/admin delete operations may bypass version checks only through explicit privileged paths, and must log the bypass in `operation_log`.

3. **Delete semantics by operation**
   - **Decision:** use soft-delete defaults for core learning-memory entities; reserve hard delete for privileged maintenance paths only.
   - For normal delete operations on `marking_artifacts`, `marking_amendments`, and `student_review_states`, set tombstone fields (`is_deleted`, `deleted_at`, `deleted_by`, `delete_reason`) instead of physical row removal.
   - Default reads must exclude tombstoned rows unless an explicit include-deleted option is requested.
   - For maintenance batch operations, delete on missing row should be idempotent no-op with warning log (not hard error), to keep reruns safe.
   - Companion behavior should be logical-cascade at read layer (for example deleted artifact hides companion amendment/review-state by default view policy) without immediate physical purge.
   - Hard delete may be used only via explicit privileged/admin flows, must declare cascade behavior, and must emit an `operation_log` entry that marks hard-delete/bypass intent.

4. **Operation-log retention and querying**
   - **Decision:** keep `operation_log` without archive/prune for now.
   - No operational dashboard requirement for the initial rollout; ad-hoc query tooling is sufficient at current scale.

5. **Quarantine workflow for bad imports**
   - **Decision:** quarantine in DB via a dedicated `import_quarantine` table, with optional exported report for human review.
   - Quarantine rows should include source path, artifact family, source hash, detected schema version, failure stage, error code/message, raw payload (when parseable), first/last seen timestamps, retry count, and status (`open`, `resolved`, `ignored`).
   - Importer behavior: do not abort the full run on single-file failures; quarantine failed artifacts, emit operation-log failure linked to `quarantine_id`, continue run, and print end-of-run summary.
   - Add explicit retry path (`--retry-quarantine` with filters) that reprocesses open quarantine rows and marks them resolved on success.
   - Validation must report open quarantine rows and their failure classes as part of migration readiness checks.
   - CLI contract:
     - `python3 -m ai_study_buddy.learning_db.ingest.import_context_json --retry-quarantine`
     - optional filters: `--status open` (default), `--artifact-family <...>`, `--failure-stage <...>`, `--limit N`, `--dry-run`
     - end-of-run summary includes imported/updated/quarantined/resolved counts plus top failure codes
     - exit code `0` for completed run (even with remaining open quarantine), `1` for fatal runtime failure

6. **Phase-gate numeric thresholds**
   - **Decision:** use the following mandatory cutover gates:
     - **Phase 2 -> 3:** critical parity = `100%` with `0` critical mismatches; non-critical drift `<= 0.1%`; stable pass across `3` consecutive full-corpus runs; no open critical quarantine affecting active attempts.
     - **Phase 3 -> 4:** provisional dual-write gate `>= 99.9%` over at least `200` writes for early rollout confidence; final gate remains `>= 99.9%` over at least `1,000` writes before default DB-read cutover. Strict dual-write invariant violations = `0`; unresolved write failures older than `24h` = `0`; C/U/D operation-log coverage = `100%`; rollback drill pass required.

7. **Actor identity convention**
   - **Decision:** require a typed actor string on all operation-log-producing write paths.
   - Canonical format:
     - `user:<user_id>`
     - `script:<module_or_command>`
     - `agent:<skill_or_service>`
     - `system:<component>`
   - Optional suffixes:
     - `@<host>` (optional)
     - `#<run_id>` (optional)
   - Validation rules:
     - actor is required for C/U/D operation log entries
     - fallback `system:unknown` is allowed only as a warning path
     - ASCII-only, max length 128, no free-form PII-heavy text

8. **Post-cutover JSON export policy**
   - **Decision:** post-cutover JSON export is on-demand (not always-on).
   - During compatibility phases, JSON snapshot export remains enabled for dependent consumers.
   - After Phase 4 cutover, normal runtime writes do not require JSON emission; exports are generated only when explicitly requested by maintenance/debug workflows.
   - Maintenance tools that still need JSON should call a dedicated export command/path instead of assuming per-write filesystem snapshots.

---

## Detailed TODO Checklist (Implementation Monitoring)

### Phase 0 - Foundation and schema bootstrapping

- [x] Create `ai_study_buddy/learning_db/__init__.py`.
- [x] Create `ai_study_buddy/learning_db/core/connection.py` with default DB path `ai_study_buddy/db/study_buddy.db`.
- [x] Create `ai_study_buddy/learning_db/migrations/001_initial_schema.sql`.
- [x] Create `ai_study_buddy/learning_db/core/migrate.py` with idempotent migration application.
- [x] Enable SQLite foreign keys for every connection.
- [x] Add tests for fresh DB creation and migration idempotency.
- [x] Add `operation_log` table to initial schema and helper APIs for append-only operation logging.
- [x] Add `import_quarantine` table schema and status lifecycle (`open`, `resolved`, `ignored`).
- [x] Add importer identity mapping table (for stable ID reuse) with key `(artifact_family, source_path, source_content_hash)` and mapped `artifact_id`.
- [x] Add actor-format validation helper for operation-log writes (`user:...`, `script:...`, `agent:...`, `system:...`, optional `@host` and `#run_id`).
- [x] Add concurrency/versioning columns (`row_version`) and tombstone columns (`is_deleted`, `deleted_at`, `deleted_by`, `delete_reason`) for mutable root tables.

### Phase 1 - Historical import (read-only indexing)

- [x] Create `ai_study_buddy/learning_db/ingest/import_context_json.py`.
- [x] Import `context/marking_results/**/*.json` into `marking_artifacts`, `marking_question_results`, and `marking_question_page_map`.
- [x] Import `context/marking_amendments/**/*.json` into `marking_amendments` and `marking_question_amendments`.
- [x] Import `context/student_review_states/**/*.json` into `student_review_states` and `student_review_notes`.
- [x] Store relative source path, schema version, content hash, and raw JSON for every imported artifact.
- [x] Add `--dry-run`, `--limit`, and `--artifact-family` filters.
- [x] Ensure stable `artifact_id` reuse across repeated imports via identity mapping table lookups (no path-derived primary identity).
- [x] Log import start/success/failure in `operation_log` with import summary metadata.
- [x] Write malformed/unresolved artifacts to `import_quarantine` (with source path, failure stage, error code/message, and payload/hash when available).
- [x] Add importer summary output showing imported counts and quarantine counts by artifact family/failure class.
- [x] Add `--retry-quarantine` mode (with optional filters) to reprocess open quarantine rows.
- [x] Extend `import_context_json` with student/subject and/or path-prefix scoping for large-corpus imports and scoped parity runs (CLI: `--student-id`, `--subject-context`, `--path-prefix`; `limit` applies **after** scope filter; ignored for `--retry-quarantine`).
- [x] Add pytest that runs the historical importer twice on the same corpus and asserts stable row counts (formalizes importer idempotency).

### Phase 2 - Read-path parity with fallback

- [x] Centralize runtime defaults + env overrides for **read-path** flags: `LEARNING_DB_ENABLE_READS`, `LEARNING_DB_READ_FALLBACK_FILESYSTEM` (implemented in `ai_study_buddy/learning_db/core/config.py`; see **Runtime flags** above).
- [x] Add `LearningDbReadRepository` read façade + helpers (`learning_repository.py`, `read_marking.py`, `read_documents.py`) — latest artifact list per attempt mirrors `find_marking_artifacts_for_attempt`; review-state and amendment payloads by relative path under `context/`.
- [x] Add DB-backed lookup path behind `LEARNING_DB_ENABLE_READS` (`find_marking_artifacts_for_attempt` + `StudentReviewRepository` loaders).
- [x] Keep filesystem fallback controlled by `LEARNING_DB_READ_FALLBACK_FILESYSTEM`.
- [x] Add regression tests covering filesystem-only vs DB-backed vs DB+fallback-disabled for marking lookup (`learning_db/tests/test_phase2_reads.py`); broaden Review Workspace E2E when parity harness lands.
- [x] Operational checkpoint: filesystem read fallback stays **default-on** (`LEARNING_DB_READ_FALLBACK_FILESYSTEM`) until Phase 4 read cutover policy; parity on current corpus verified (Phase 2 sign-off below).
- [x] Create `ai_study_buddy/learning_db/cli/validate_study_buddy_db.py`.
- [x] Validate source JSON counts against DB row counts for the three artifact families.
- [x] Validate every amendment resolves to a known marking artifact.
- [x] Validate every review state resolves to a known marking artifact.
- [x] Validate latest-artifact DB query parity against `find_marking_artifacts_for_attempt(...)` (`learning_db/cli/reader_parity.py`, exposed via `python3 -m ai_study_buddy.learning_db.cli.validate_study_buddy_db --reader-parity`).
- [x] Validate the Abigail Practice 9 example: base marking has `C1` **`partial` / `4`/`5` earned**; amendment JSON sets `outcome` **`correct`** and **`earned_marks` `5`** (paths in the examples earlier in this doc).
- [x] Quarantine UX: default validation output mentions **`open`/`ignored`** only when attention is needed; optional **`--quarantine-history`** prints full status counts (includes resolved audit trail).
- [x] Full-corpus parity: three consecutive **`--reader-parity`** runs on unchanged corpus — **`0` mismatches**, **`0` errors**, **`499`** completion mains checked per run (critical **`0`**; non-critical drift **`0`**).
- [x] Phase 2→3 numeric gate thresholds for **this corpus** satisfied at sign-off; proceed to Phase 3 dual-write when implementation is ready (**process gate**, not automated CI).

##### Phase 2 sign-off (2026-04-29)

- **Reader parity:**  
  `python3 -m ai_study_buddy.learning_db.cli.validate_study_buddy_db --db-path ai_study_buddy/db/study_buddy.db --context-root ai_study_buddy/context --pdf-registry ai_study_buddy/db/pdf_registry.db --reader-parity`  
  run **three** times sequentially — each run: **`parity_checked=499`**, **`mismatches=0`**, **`errors=0`**.
- **Structural checks** at sign-off: source JSON row counts aligned with DB; **no `open`** import quarantine rows (`--quarantine-history` shows **`resolved`** history only).

**Captured learning (commands, tooling, gate policy):** [LEARNING_READER_PARITY.md](../learning_db/docs/learnings/LEARNING_READER_PARITY.md).

### Phase 3 - Controlled dual-write (create/update)

**Operational learning (flags, canonical vs snapshot paths):** [LEARNING_DUAL_WRITE_PHASE3.md](../learning_db/docs/learnings/LEARNING_DUAL_WRITE_PHASE3.md).

- [x] Centralize runtime defaults + env overrides for **write-path** flags (`learning_db/core/config.py`): `LEARNING_DB_ENABLE_DUAL_WRITE`, `LEARNING_DB_STRICT_DUAL_WRITE`, `LEARNING_DB_ENABLE_JSON_EXPORT`; dual-write callers consult these via helpers.
- [x] Add DB upsert after **`write_marking_artifact`** writes validated JSON (**`dual_write.maybe_dual_write_snapshot(..., family=\"marking_result\")`** reads the snapshot bytes; same upsert machinery as importer).
- [x] Add DB write mirror for `StudentReviewRepository.save_review_state(...)` (`family=\"student_review_state\"`).
- [x] Add DB write mirror for `StudentReviewRepository.save_amendment(...)` (`family=\"marking_amendment\"`).
- [x] Gate dual-write snapshot projection behind **`LEARNING_DB_ENABLE_DUAL_WRITE`** (default **`1`** / on; set `0` to disable).
- [x] Honour **`LEARNING_DB_ENABLE_JSON_EXPORT`** on write boundaries (**`write_marking_artifact`**, **`StudentReviewRepository.save_*`**): export **`1`** emits JSON then dual-write from snapshot bytes; **`0`** requires **`LEARNING_DB_ENABLE_DUAL_WRITE`** and persists via **`maybe_dual_write_from_canonical`** (no JSON file). Getter kept for tooling.
- [x] Enforce **`LEARNING_DB_STRICT_DUAL_WRITE`**: default **`0`** (**soft**) — audits failures via **`operation_log`** without unlinking snapshots; **`1`** (**strict**) — failure raises **and** JSON unlink best-effort for snapshot-based projections.
- [x] Add transaction tests proving interrupted upserts leave no orphan child projection rows beyond importer/dual-write invariants already enforced by DELETE-then-insert in upserts (see `test_partial_projection_failure_rolls_back_parent_and_child_rows` in `learning_db/tests/test_dual_write_semantics.py`).
- [x] Rollback operational posture: **`LEARNING_DB_ENABLE_DUAL_WRITE=0`** disables DB projection (**JSON-only**, existing behaviour unchanged).
- [x] Expand failure-semantics integration tests (**JSON-write failure**, **DB-commit failure**) beyond current dual-write audits (`test_commit_failure_leaves_no_committed_rows` + `test_write_marking_artifact_json_write_failure_logs_and_keeps_db_clean`).
- [x] **`operation_log`** entries for **`dual_write_snapshot`** success (in-transaction) and failure (separate connection audit).
- [x] Broaden typed **actor** + operation-log coverage across marking/repository write boundaries (implemented for `write_marking_artifact(...)`, `StudentReviewRepository.save_review_state(...)`, and `StudentReviewRepository.save_amendment(...)`; operation types: `marking_artifact_write`, `student_review_state_write`, `marking_amendment_write`).
- [x] Audit and update second-order write consumers (skills, scripts, orchestration prompts) to call marking/repository APIs as the write boundary, not direct JSON/file-path workflows (updated orchestrator skill policy; `edit_human_notes` and `retrack_marking_assets` now persist via `write_marking_artifact(...)`).
- [x] Specifically update `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md` to enforce API-first write semantics and prohibit filesystem scans as source-of-truth lookups.
- [x] Fix importer upsert identity reuse for edited JSON at the same path (`import_context_json`): when `source_content_hash` changes, reuse existing row IDs by unique path (`marking_artifacts.artifact_path`, `marking_amendments.amendment_path`, `student_review_states.review_state_path`) before identity-map insertion, preventing `UNIQUE constraint failed` quarantine loops on legitimate updates.
- [x] Measure and record dual-write success rate over at least **200** write operations (**provisional gate** — sign-off below).
- [x] Measure and record dual-write success rate over at least **1,000** write operations (**final gate** before Phase 4 JSON demotion). *(2026-05-28: 1201/1201 succeeded, 0 failed, 100.0000% success; gate PASS.)*
- [x] Verify strict dual-write invariant violations remain zero during compatibility mode (sign-off below).
- [x] Verify no unresolved **write-boundary** failures older than 24h before enabling Phase 4 (sign-off below; historical `import_*` failures are batch-import era only).
- [x] Run and document at least one rollback drill (`LEARNING_DB_ENABLE_DUAL_WRITE=0`) before Phase 4 cutover — [LEARNING_DUAL_WRITE_PHASE3.md](../learning_db/docs/learnings/LEARNING_DUAL_WRITE_PHASE3.md) § Rollback drill.

##### Phase 3 provisional sign-off (2026-05-22)

Measured on production `ai_study_buddy/db/study_buddy.db` (all-time `dual_write_snapshot` rows in `operation_log`):

```text
python3 -m ai_study_buddy.learning_db.cli.dual_write_stats
# overall: total=660 succeeded=660 failed=0 success_rate=100.0000%
# gate_check: min_ops(200)=PASS success_rate(99.9000%)=PASS

python3 -m ai_study_buddy.learning_db.cli.dual_write_stats --target-min-ops 1000
# gate_check: min_ops(1000)=FAIL (660/1000) success_rate(99.9000%)=PASS
```

| Check | Result |
|-------|--------|
| Provisional gate (≥200 ops, ≥99.9% success) | **PASS** (660 ops, 100% success) |
| Final gate (≥1,000 ops) | **Not met** — continue dual-write burn-in |
| `dual_write_snapshot` failures (all time) | **0** |
| Failed write-boundary ops (`dual_write_snapshot`, `marking_*_write`, `student_review_state_write`) | **0** |
| `import_quarantine` unresolved | **0** |
| Dual-write activity span | 2026-04-29 → 2026-05-21 (SGT) |
| Last 7 days | 244 dual-writes, 0 failures |

**By family (all-time):** `marking_result` 391 · `file_question_info` 114 · `marking_amendment` 108 · `student_review_state` 47 — all 100% success.

**Production experience (wrap-up notes):**

- Soft dual-write (`LEARNING_DB_STRICT_DUAL_WRITE=0`) has been sufficient: zero production projection failures logged; JSON snapshots remain the human-editable safety net while DB rows stay aligned.
- Reads are already DB-default (Phase 4 partial); **writes** still dual-path. Do not demote JSON or disable dual-write until the **1,000-op** gate and Phase 4 checklist complete.
- Historical `import_*` failures in `operation_log` (33 rows) predate runtime dual-write and do not affect write-boundary health; quarantine backlog is fully resolved.

**Captured learning:** [LEARNING_DUAL_WRITE_PHASE3.md](../learning_db/docs/learnings/LEARNING_DUAL_WRITE_PHASE3.md) (flags, entry points, rollback drill).

##### Phase 3 final gate update (2026-05-28)

Measured on production `ai_study_buddy/db/study_buddy.db`:

```text
python3 -m ai_study_buddy.learning_db.cli.dual_write_stats --target-min-ops 1000
# overall: total=1201 succeeded=1201 failed=0 success_rate=100.0000%
# gate_check: min_ops(1000)=PASS success_rate(99.9000%)=PASS
```

| Check | Result |
|-------|--------|
| Final gate (>=1,000 ops, >=99.9% success) | **PASS** (1201 ops, 100% success) |
| `dual_write_snapshot` failures (all time) | **0** |
| Failed write-boundary ops (`dual_write_snapshot`, `marking_*_write`, `student_review_state_write`) | **0** |

Next action is Phase 4 checklist execution (JSON demotion tasks), not additional dual-write burn-in for gating.

### Phase 4 - Operational DB source (JSON demoted)

- [x] Switch default runtime reads to DB (`LEARNING_DB_ENABLE_READS=1`) after parity sign-off.
- [ ] Keep JSON as debug/export artifact; remove runtime dependence on filesystem scans for normal product flows.
- [ ] Ensure maintenance workflows that still need JSON consume regenerated exports.
- [ ] Add explicit on-demand JSON export path/command for supported artifact families.
- [ ] Add minimal ad-hoc query helpers (CLI/SQL snippets) for `operation_log` inspection; no dashboard required in initial rollout.
- [ ] Update second-order consumer documentation to describe JSON as debug/export outputs only (not authoritative runtime state).

### Phase 5 - Backup/retention hardening and cutover

- [x] Create `ai_study_buddy/learning_db/cli/backup_study_buddy_db.py`.
- [x] Use the same default cloud-synced DB backup folder as `pdf_registry.db` when available.
- [ ] Reuse the same retention/cold-storage strategy as `pdf_registry.db` backup flow.
- [x] Support `STUDY_BUDDY_DB_BACKUP_DIR`.
- [x] Add `--timestamp` and `--force` options.
- [x] Add backup log file analogous to `pdf_registry_backup.log`.
- [ ] Execute and document a restore drill from backup.
- [ ] Document maintenance commands in module README or docs.

### Cross-phase documentation and rollout

- [ ] Update `ai_study_buddy/docs/L3_DATA_STRATEGY.md` after implementation status changes.
- [ ] Update `ai_study_buddy/docs/L1_ARCHITECTURE.md` after DB-backed reads become default.
- [ ] Update `ai_study_buddy/review_workspace/DATA_MODEL.md` if API behavior changes.
- [ ] Add `ai_study_buddy/marking/DATA_MODEL.md` to document canonical marking entities, companion artifacts, DB table mappings, and JSON export/debug contracts.
- [ ] Add `ai_study_buddy/marking/DECISIONS.md` and document the JSON->DB migration decision thoroughly (problem framing, alternatives considered, tradeoffs, phased cutover policy, rollback strategy, and downstream consumer implications).
- [ ] Update `ai_study_buddy/marking/SPEC.md` if `write_marking_artifact(...)` gains DB persistence responsibility.
- [ ] Record validation results and any skipped/quarantined artifacts.
- [ ] Mark this proposal implemented only after DB backup, import validation, and rollback path are verified.

---

## Decision

Adopt `study_buddy.db` as the local durable learning-memory database.

Keep `pdf_registry.db` as the file registry.

Treat `context/marking_results`, `context/marking_amendments`, and `context/student_review_states` as transitional JSON snapshots and export/debug artifacts once DB-backed persistence is verified.

Treat `context/marking_assets` as a regenerable evidence cache, not primary memory.

Design the SQLite schema and repository layer as a Postgres-shaped rehearsal so future hosted migration is straightforward.
