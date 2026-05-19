# Testing Guide

This guide defines the testing workflow for `ai_study_buddy.marking`. Package release version: see `README.md` / `CHANGELOG.md`.

## Test Scope

Primary automated coverage lives in:

- `ai_study_buddy/marking/tests/test_artifact_core.py`
- `ai_study_buddy/marking/tests/test_artifact_lookup.py`
- `ai_study_buddy/marking/tests/test_artifact_cleanup.py`
- `ai_study_buddy/marking/tests/test_marking_asset_bundle.py`
- `ai_study_buddy/marking/tests/test_marking_asset_render.py`
- `ai_study_buddy/marking/tests/test_file_question_info.py`
- `ai_study_buddy/marking/tests/test_v3_workflow_helpers.py`
- `ai_study_buddy/marking/tests/test_marking_time.py`
- `ai_study_buddy/marking/tests/test_migration.py`
- `ai_study_buddy/marking/tests/test_review_workspace_amendments.py`
- `ai_study_buddy/marking/tests/test_workflow_flags.py` (`v0.3.8`)

These tests cover:

- schema loading and validation
- companion amendment schema loading and JSON-schema validation
- artifact naming/path normalization
- completion->artifact lookup matching and condition filtering
- run-level artifact removal planning and deletion safety behavior
- summary/row score consistency
- strict `marking_result.v1.6` schema validation and closed-contract (`additionalProperties: false`) behavior
- v1.5+ `context.question_page_map` validation (membership, uniqueness, page/confidence/source constraints)
- v1.6 resolver-context contract checks at canonical write time
- disqualified scoring semantics
- JSON write and markdown re-render behavior
- path sanitization at write time and placeholder expansion at read/render time
- marking asset bundle path derivation and filesystem bundle validation checks
- package-owned PDF-to-bundle render helpers (`attempt/` and `answers/` full-page naming)
- human note update flow
- legacy markdown migration parsing and batching options
- attempt-metadata backfill workflow (`backfill_attempt_metadata_v1_1.py`)
- partial-marking metadata backfill workflow (`backfill_is_partial_v1_3.py`)
- dispatch/version handling errors (unsupported or missing `schema_version`)
- review-domain amendment validation, merge behavior, and API persistence responses
- `file_question_info` consumer/read contracts (`v0.3.2`):
  - ordered section/question iterators
  - duplicate-ID hard-fail behavior
  - DB/FS lookup and divergence behavior under READ flags
  - `question_page_map` compatibility with `marking_result.v1.6`
- completion workflow flags shared loader (`v0.3.8`): `load_completion_marking_context`, `completion_workflow_flags`, amendment/review/artifact presence
- v3 workflow helper/runtime contracts (`v0.3.3`):
  - Phase A input normalization + registration-first resolution
  - Phase B mode precedence/ambiguity and redo-practice golden reference resolution
  - Phase C authoritative template question-section resolution + detector-fallback validation
  - Phase D section-scoped execution planning/aggregation/retry-target routing + runtime trace
  - Phase E question-scoped deep-dive planning/execution/retry + finalization write path and debug traces

## Run Tests

From repository root:

```bash
# Package-only tests
python3 -m pytest ai_study_buddy/marking/tests -q

# Core tests only
python3 -m pytest ai_study_buddy/marking/tests/test_artifact_core.py -q

# Artifact lookup tests only
python3 -m pytest ai_study_buddy/marking/tests/test_artifact_lookup.py -q

# Artifact cleanup tests only
python3 -m pytest ai_study_buddy/marking/tests/test_artifact_cleanup.py -q

# Marking asset bundle tests only
python3 -m pytest ai_study_buddy/marking/tests/test_marking_asset_bundle.py -q

# MAB render helper tests only
python3 -m pytest ai_study_buddy/marking/tests/test_marking_asset_render.py -q

# Migration tests only
python3 -m pytest ai_study_buddy/marking/tests/test_migration.py -q

# Review-domain amendment tests only
python3 -m pytest ai_study_buddy/marking/tests/test_review_workspace_amendments.py -q

# Completion workflow flags (v0.3.8)
python3 -m pytest ai_study_buddy/marking/tests/test_workflow_flags.py -q

# file_question_info consumer/read tests (v0.3.2)
python3 -m pytest ai_study_buddy/marking/tests/test_file_question_info.py -q

# v3 workflow helper/runtime tests (v0.3.3)
python3 -m pytest ai_study_buddy/marking/tests/test_v3_workflow_helpers.py -q

# Recommended focused gate for v3 + file_question_info work
python3 -m pytest ai_study_buddy/marking/tests/test_v3_workflow_helpers.py ai_study_buddy/marking/tests/test_file_question_info.py -q
```

## Suggested Quality Gate

Before merging marking-related changes:

1. Run all package tests.
2. Ensure no schema validation regressions.
3. For migration/parser changes, run migration tests specifically.
4. For renderer or note-edit changes, verify artifact-core tests pass.
5. For backfill changes, verify migration tests pass (includes backfill dry-run/apply coverage).
6. For schema changes, verify fixture-based schema tests and parity checks pass.
7. For producer-flow changes, verify resolver-only context contract tests pass.
8. For `v0.3.2`/`v0.3.3` surfaces, run:
   - `test_file_question_info.py`
   - `test_v3_workflow_helpers.py`

## Schema Fixture And Parity Conventions

Schema fixture folder:

- `ai_study_buddy/marking/tests/fixtures/marking_result_v1_5/` (legacy folder name retained)

Fixture types:

- `valid_*.json`: expected to pass JSON Schema and runtime validator.
- `invalid_*.json`: expected to fail JSON Schema and runtime validator.
- `valid_schema_but_*.json`: expected to pass JSON Schema but fail runtime semantic invariants.

Parity rule:

- For structural constraints, JSON Schema and runtime validator should agree.
- For semantic invariants (for example computed totals), runtime validator is authoritative and may reject schema-valid payloads.

## Manual Verification Checklist

Use this checklist when changing behavior that affects outputs:

1. Generate or edit one canonical artifact JSON under
   `context/marking_results/...`.
2. Re-render markdown from that JSON and verify expected sections are present.
3. Update a summary note and one question note via `edit_human_notes.py`.
4. Confirm `review_meta.updated_at` and `review_meta.updated_by` were updated.
5. Verify path placeholders are persisted in JSON (`GOODNOTES_ROOT` / `DAYDREAMEDU_ROOT` / `<student_email>`).
6. Verify render output expands placeholders when roots/student email can be resolved.
7. Re-run schema validation (implicitly covered by write/update flows).
8. Verify a write with missing `context.context_resolution` fails deterministically.
9. For visual-marking workflow checks, confirm scoring used only blue/black student writing and ignored red/green/purple annotations unless explicitly requested as metadata extraction.
10. For renderer localization changes, verify diagnosis text formatting on:
   - one Chinese / Higher Chinese artifact (Chinese mistake-type labels)
   - one non-Chinese artifact (`mistake_type: reasoning` formatting).

## Regression Focus Areas

Changes in these areas should receive extra scrutiny:

- Prefix normalization and timestamp basename rules
- Artifact lookup id/path precedence and student-scoped scan boundaries
- `scoring_status` and disqualified row exclusion logic
- Path privacy normalization and placeholder expansion fallback behavior
- Markdown parsing tolerance for legacy report variants
- Context file-id/group backfill behavior when registry lookups fail
