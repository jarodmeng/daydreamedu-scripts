# Marking Artifact v1.1: Multiple Attempts Per Template

Status: Implemented (`v0.2.3`)

Audience: Maintainers of `ai_study_buddy/marking`, `pdf_file_manager`, and the `mark-goodnote-completion` skill

## 1) Goal

Support cases where one student completes the same template unit multiple times (for example, assigned again later) while keeping:

- one canonical JSON + one derived markdown report per attempt
- deterministic grouping of attempts that belong to the same `(student, template)` pair
- backward-compatible evolution from `marking_result.v1`

This proposal intentionally keeps scope small: add only grouping and ordering metadata for attempts; no cross-artifact pointers and no computed progression fields yet.

## 2) Problem Statement

Current `marking_result.v1` models each marking run independently, which is correct for canonical storage. However, repeated attempts for the same template require inference from filenames, paths, and ad hoc queries.

We need first-class fields that answer:

1. Which artifacts are attempts of the same template for this student?
2. What is the attempt order (first, second, third)?
3. Optional human label for attempt intent (initial/retake/revision)?

## 3) Scope

### In scope

- Introduce schema version `marking_result.v1.1`
- Add three optional fields under `context`:
  - `template_attempt_group_id`
  - `attempt_sequence`
  - `attempt_label`
- Update validation and model parsing to accept/read/write these fields
- Define deterministic writer/backfill rules for these fields
- Keep report rendering and existing paths compatible

### Out of scope (for v1.1)

- `previous_*` context link fields
- `progress_vs_previous` or any computed deltas
- new persistent index tables or SQLite schema changes
- changing artifact storage paths or basename conventions

## 4) Proposed Schema Change (v1 -> v1.1)

Top-level:

- `schema_version` adds a new allowed value: `marking_result.v1.1`

`context` additions (all optional / nullable for compatibility):

- `template_attempt_group_id: string | null`
- `attempt_sequence: integer | null`
- `attempt_label: string | null`

No other fields are changed or removed.

### 4.1 Canonical semantics

`template_attempt_group_id`

- Stable identifier for all attempts by one student for one template.
- Recommended deterministic shape:
  - `"<student_slug>::<template_file_id>"`
- If `template_file_id` is unavailable (legacy edge case), leave `null` (do not invent unstable IDs).

`attempt_sequence`

- 1-based integer order of attempts inside one `template_attempt_group_id`.
- Determined by attempt chronology (see section 5).
- `null` if group cannot be established.

`attempt_label`

- Optional human-oriented tag such as:
  - `initial`
  - `retake`
  - `revision`
- Free text with conservative length (validation guidance below).

## 5) Write-Time Rules (normative)

> **Update (May 2026):** `attempt_sequence` and `template_attempt_group_id` are now sourced from **`PdfFileManager` completion series** (`next_attempt_sequence_for_completion`, `completion_series_id`) — distinct completion **`file_id`s** ordered by registry `pdf_files.added_at`, not by prior marking JSON count. Re-mark on the same `file_id` is idempotent. See [registry-derived completion series](../../../pdf_file_manager/docs/proposals/15-completion-series-derived.md) and [L4 completion framework](../../../docs/L4_COMPLETION_MARKING_FRAMEWORK.md#completion-series-registry-derived). Historical rules below describe the original v1.1 JSON-scan writer; use **`backfill_attempt_sequence_from_registry`** to align legacy artifacts.

When writing a new `v1.1` artifact:

1. Determine `student_slug` using existing slug logic (`artifact_paths.slugify_student` rules).
2. Read `context.template_file_id`.
3. If `template_file_id` exists:
   - set `template_attempt_group_id = f"{student_slug}::{template_file_id}"`
   - discover existing artifacts with same group id (or same `(student_slug, template_file_id)` for migrated `v1` data)
   - set `attempt_sequence = max(existing_sequence, inferred_sequence_from_time) + 1`
4. If `template_file_id` is missing:
   - set `template_attempt_group_id = null`
   - set `attempt_sequence = null`
5. Set `attempt_label` only if caller provides one; otherwise `null`.

Determinism requirement:

- For artifacts created in one batch process, tie-break attempt ordering using:
  1. `created_at` ascending
  2. canonical JSON path ascending (deterministic tie-breaker)

## 6) Validation Contract (v1.1)

Keep existing `v1` rules, plus:

1. `context.template_attempt_group_id`
   - type: string or null
   - when string: non-empty after trim
2. `context.attempt_sequence`
   - type: integer or null
   - when integer: `>= 1`
3. `context.attempt_label`
   - type: string or null
   - when string: non-empty after trim, recommended max length `<= 64`

Consistency recommendation (warning-level, not hard error in v1.1):

- if `attempt_sequence` is set while `template_attempt_group_id` is null, emit diagnostics/log warning and allow (legacy compatibility).

## 7) Backward Compatibility and Migration

### Reader compatibility

- `v1.1` readers must continue to read `v1` artifacts.
- `v1` readers that ignore unknown fields can still parse `v1.1` payloads, but official support should come from upgrading to `v1.1` validators/parsers.

### Backfill strategy (optional but recommended)

Backfill existing artifacts under `context/marking_results/**`:

1. Group by `(student_slug, context.template_file_id)` where template id exists.
2. Sort each group by:
   - `created_at` ascending
   - JSON path ascending
3. Write:
   - `template_attempt_group_id`
   - `attempt_sequence` (1..N)
   - `attempt_label = null` (unless explicitly provided externally)
4. Bump `schema_version` to `marking_result.v1.1` for rewritten files.

Safety:

- preserve all existing marks/diagnoses unchanged
- preserve basename/path conventions unchanged
- run schema validation before commit

## 8) API and Model Touchpoints

Expected update targets:

- `ai_study_buddy/schemas/marking/marking_result.v1.schema.json` -> add `v1.1` schema file (preferred) or evolve validator to accept both contracts
- `marking/core/models.py` (`MarkingArtifactContext`) -> add three new fields
- `marking/core/artifact_schema.py` -> accept `v1.1` + new validations
- writer/resolver pipeline -> populate fields during artifact creation
- docs (`SPEC.md`, `README.md`, `TESTING.md`) -> reflect v1.1 semantics

No changes required to:

- `question_results` row structure
- canonical output path builders (`artifact_paths`)
- markdown rendering format (unless adding optional display line for attempt metadata later)

## 9) Testing Plan

Minimum tests:

1. `v1.1` artifact with all new fields set validates.
2. `v1.1` artifact with null new fields validates.
3. invalid `attempt_sequence` (`0`, negative, non-int) fails validation.
4. invalid empty-string `template_attempt_group_id` fails validation.
5. backfill ordering creates contiguous `attempt_sequence` values for same group.
6. artifacts from different templates for same student are not cross-grouped.
7. artifacts from different students with same template are not cross-grouped.
8. existing `v1` fixtures continue to validate/read.

## 10) Acceptance Criteria

1. New artifacts can express repeated attempts for the same template with deterministic group and sequence metadata.
2. Existing `v1` artifacts remain readable.
3. No path or filename convention changes are required.
4. Queries such as "all attempts for Winston on template X" can be answered without filename heuristics.
5. Documentation clearly distinguishes v1.1 in-scope fields from deferred progression/link features.

## 11) Implementation Plan (phase-by-phase)

Ship in small phases with tests passing at each phase.

### Phase 0 - Contract lock and design decisions

Goal: freeze v1.1 behavior before code edits.

TODO checklist:

- [x] Confirm final field set for v1.1 is exactly:
  - [x] `context.template_attempt_group_id`
  - [x] `context.attempt_sequence`
  - [x] `context.attempt_label`
- [x] Confirm deferred items remain out of scope:
  - [x] `previous_*` links
  - [x] `progress_vs_previous`
- [x] Confirm deterministic group-id formula:
  - [x] `"<student_slug>::<template_file_id>"`
- [x] Confirm sequence ordering rules:
  - [x] primary: `created_at` ascending
  - [x] tie-breaker: canonical JSON path ascending
- [x] Confirm backward-compat policy (`v1` remains readable).
- [x] Confirm policy decisions from this proposal review:
  - [x] `attempt_label` remains free text in v1.1
  - [x] all marking-result/report writers must populate v1.1 attempt fields when context is available
  - [x] learning reports render `Attempt #<n>` immediately when `attempt_sequence` is present

Exit criteria:

- Team agrees on final v1.1 contract and migration boundaries in this proposal.

### Phase 1 - Schema and validator updates

Goal: make v1.1 parseable and enforceable.

TODO checklist:

- [x] Add/introduce schema contract for `marking_result.v1.1` (implemented by accepting both versions in current schema + validator).
- [x] Update validator to accept both `marking_result.v1` and `marking_result.v1.1`.
- [x] Add validations for new fields:
  - [x] non-empty string-or-null `template_attempt_group_id`
  - [x] int-or-null `attempt_sequence`, with `>= 1` when present
  - [x] non-empty string-or-null `attempt_label` (with length guard)
- [x] Keep all existing v1 checks unchanged.

Exit criteria:

- Validator accepts valid v1 and v1.1 payloads and rejects invalid new-field values.

### Phase 2 - Model and API surface updates

Goal: expose new fields through typed models and public APIs.

TODO checklist:

- [x] Update `MarkingArtifactContext` dataclass with the three v1.1 fields.
- [x] Update `MarkingArtifact.from_dict(...)` parsing for the new fields.
- [x] Ensure serialization (`to_dict`) emits new fields consistently.
- [x] Verify public API exports remain stable (`ai_study_buddy.marking`).

Exit criteria:

- New fields round-trip cleanly through model parse/serialize paths.

### Phase 3 - Writer flow (new artifacts)

Goal: populate v1.1 fields deterministically for newly created artifacts.

TODO checklist:

- [x] Add helper logic to compute `student_slug` and derive group ID from template id.
- [x] Add lookup of same-group existing artifacts to compute next `attempt_sequence`.
- [x] Apply stable ordering rule (`created_at`, then path) when deriving sequence.
- [x] Set `attempt_label` from caller input when provided; default `null`.
- [x] If `template_file_id` is missing, set all three fields to `null`.
- [x] Ensure all writer entrypoints that create marking JSON + learning reports populate v1.1 fields (no partial adoption across workflows).

Exit criteria:

- New artifacts created from normal marking workflows include correct group and sequence metadata.

### Phase 4 - Backfill/migration utility for existing artifacts

Goal: make existing historical data queryable with v1.1 grouping fields.

TODO checklist:

- [x] Add script/workflow to scan `context/marking_results/**`.
- [x] Group artifacts by `(student_slug, template_file_id)` where possible.
- [x] Assign contiguous `attempt_sequence` within each group (deterministic order).
- [x] Write:
  - [x] `template_attempt_group_id`
  - [x] `attempt_sequence`
  - [x] `attempt_label = null`
  - [x] `schema_version = marking_result.v1.1`
- [x] Validate every rewritten artifact before saving.
- [x] Provide dry-run mode and summary output (updated/skipped/error counts).

Exit criteria:

- Backfill can run repeatably and safely without changing marks/diagnoses content.

### Phase 5 - Tests (unit + regression)

Goal: lock behavior and prevent drift.

TODO checklist:

- [x] Add validator tests for new fields and edge cases.
- [x] Add model round-trip tests (`from_dict`/`to_dict`) for v1.1 fields.
- [x] Add writer tests for deterministic group-id and sequence assignment.
- [x] Add migration tests for:
  - [x] stable ordering
  - [x] contiguous sequence numbers
  - [x] cross-student isolation
  - [x] cross-template isolation
- [x] Keep/extend regression coverage so v1 fixtures still pass unchanged.

Exit criteria:

- Marking test suite passes with new v1.1 coverage and no v1 regressions.

### Phase 6 - Documentation updates (required)

Goal: publish final contract and usage guidance.

TODO checklist:

- [x] Update `ai_study_buddy/marking/SPEC.md` with normative v1.1 field semantics.
- [x] Update `ai_study_buddy/marking/README.md`:
  - [x] describe multi-attempt grouping behavior
  - [x] show one JSON example with group/sequence fields
- [x] Update learning report docs/examples to include rendering line `Attempt #<n>` when `attempt_sequence` exists.
- [x] Update `ai_study_buddy/marking/TESTING.md` with new test commands/coverage focus.
- [x] Keep `ai_study_buddy/marking/ARCHITECTURE.md` aligned at high level.
- [x] Mark this proposal status/notes to match implemented behavior when shipped.

Exit criteria:

- A maintainer can implement and operate v1.1 from docs without reading source internals.

### Phase 7 - Release housekeeping (small version bump)

Goal: ship as a small, explicit package increment.

Proposed version number: `v0.2.2 -> v0.2.3`

TODO checklist:

- [x] Add a new top entry in `ai_study_buddy/marking/CHANGELOG.md` for v1.1 support.
- [x] Bump marking package version from `v0.2.2` to `v0.2.3`.
- [x] Update `Current version` in `ai_study_buddy/marking/README.md` to exactly match changelog entry.
- [x] Confirm docs + schema/version references are internally consistent.
- [x] Run target tests before finalizing release notes.

Exit criteria:

- Version bump, changelog, docs, and tested behavior are consistent and merge-ready.

## 12) Decisions from Review

1. `attempt_label` remains free text in v1.1.
2. All writers that produce marking results and learning reports should populate v1.1 attempt metadata when context is available.
3. Learning reports should render `Attempt #<n>` immediately when `attempt_sequence` exists.

## 13) Implementation Status Snapshot

Implemented artifacts:

- `core/models.py` now includes v1.1 context fields (`template_attempt_group_id`, `attempt_sequence`, `attempt_label`).
- `core/artifact_schema.py` defaults to `marking_result.v1.1` and validates both `v1` and `v1.1`.
- `core/artifact_writer.py` now auto-populates attempt metadata and emits `schema_version = marking_result.v1.1`.
- `workflows/report_renderer.py` renders `Attempt #<n>` in `## Result` when sequence exists.
- `workflows/backfill_attempt_metadata_v1_1.py` adds dry-run/apply backfill for existing artifacts (legacy JSON grouping).
- `workflows/backfill_attempt_sequence_from_registry.py` (May 2026) rewrites `attempt_sequence` / `template_attempt_group_id` from registry completion series — preferred for production repair.
- Registry source of truth: [pdf_file_manager proposal 15](../../../pdf_file_manager/docs/proposals/15-completion-series-derived.md).
- `README.md`, `TESTING.md`, and `CHANGELOG.md` updated for `v0.2.3`.

Validation evidence:

- Test suite: `python3 -m pytest ai_study_buddy/marking/tests -q` -> passing (`37 passed`).
- Backfill dry-run on repository data completed with no validation errors:
  - scanned `95` JSON
  - candidate `95`
  - groups `95`
  - would update `95`
