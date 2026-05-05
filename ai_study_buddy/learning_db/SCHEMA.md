# Schema Notes

This document summarizes key tables in `study_buddy.db` relevant to `learning_db` operations.

## Migration Files

- `001_initial_schema.sql`: base marking/review/import/quarantine schema
- `002_file_question_info.sql`: file-question-info projection tables + import family check expansion

## Core Operational Tables

- `schema_migrations`: applied migration versions
- `operation_log`: import/dual-write lifecycle audit events
- `import_identity_map`: stable identity mapping (`artifact_family`, `source_path`, `source_content_hash`)
- `import_quarantine`: failed import records and retry state

## Marking/Review Families (existing)

- `marking_artifacts`
- `marking_question_results`
- `marking_question_page_map`
- `marking_amendments`
- `marking_question_amendments`
- `marking_page_map_amendments`
- `student_review_states`
- `student_review_notes`

## file_question_info Projection

### `file_question_info_runs`

One row per imported `question_sections.json` identity.

Key columns:

- `run_id` (PK)
- `schema_version`
- `subject_scope`, `grade`, `slug`
- `primary_file_id`, `primary_file_path`
- `source_rel_path` (unique)
- `source_content_hash`
- `detector_model`, `detector_confidence`, `detector_notes`
- `raw_json`
- `created_at`, `updated_at`
- `row_version`, `is_deleted`

Indexes/uniques:

- unique `source_rel_path`
- unique `(primary_file_id, source_content_hash)`
- index `(primary_file_id, updated_at DESC)`
- index `(subject_scope, grade, slug)`

### `file_question_info_sections`

Section-level rows per run.

PK: `(run_id, ordinal)`

### `file_question_info_items`

Question-item rows per section.

PK: `(run_id, section_ordinal, question_index)`

## Identity and Idempotency

Importer uses `import_identity_map` to maintain stable ids across re-imports.

- same `source_path` + same `source_content_hash` => same identity
- path-level suggested id helps mutable JSON-at-stable-path workflows remain stable

