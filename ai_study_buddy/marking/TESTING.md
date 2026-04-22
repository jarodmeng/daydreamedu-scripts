# Testing Guide

This guide defines the testing workflow for `ai_study_buddy.marking`. Package release version: see `README.md` / `CHANGELOG.md`.

## Test Scope

Primary automated coverage lives in:

- `ai_study_buddy/marking/tests/test_artifact_core.py`
- `ai_study_buddy/marking/tests/test_artifact_lookup.py`
- `ai_study_buddy/marking/tests/test_marking_time.py`
- `ai_study_buddy/marking/tests/test_migration.py`

These tests cover:

- schema loading and validation
- artifact naming/path normalization
- completion->artifact lookup matching and condition filtering
- summary/row score consistency
- disqualified scoring semantics
- JSON write and markdown re-render behavior
- path sanitization at write time and placeholder expansion at read/render time
- human note update flow
- legacy markdown migration parsing and batching options
- attempt-metadata backfill workflow (`backfill_attempt_metadata_v1_1.py`)
- partial-marking metadata backfill workflow (`backfill_is_partial_v1_3.py`)

## Run Tests

From repository root:

```bash
# Package-only tests
python3 -m pytest ai_study_buddy/marking/tests -q

# Core tests only
python3 -m pytest ai_study_buddy/marking/tests/test_artifact_core.py -q

# Artifact lookup tests only
python3 -m pytest ai_study_buddy/marking/tests/test_artifact_lookup.py -q

# Migration tests only
python3 -m pytest ai_study_buddy/marking/tests/test_migration.py -q
```

## Suggested Quality Gate

Before merging marking-related changes:

1. Run all package tests.
2. Ensure no schema validation regressions.
3. For migration/parser changes, run migration tests specifically.
4. For renderer or note-edit changes, verify artifact-core tests pass.
5. For backfill changes, verify migration tests pass (includes backfill dry-run/apply coverage).

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
8. For visual-marking workflow checks, confirm scoring used only blue/black student writing and ignored red/green/purple annotations unless explicitly requested as metadata extraction.
9. For renderer localization changes, verify diagnosis text formatting on:
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
