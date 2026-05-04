# Marking Package Specification

Package release version: see **Current version** in `README.md` and entries in `CHANGELOG.md`.

## Purpose

`ai_study_buddy.marking` provides the canonical, file-first marking artifact
pipeline for AI Study Buddy.

The package guarantees:

1. a stable `marking_result.v1.6` JSON contract
2. a stable `marking_amendment.v1` JSON overlay schema contract for review-workspace amendment artifacts
3. deterministic artifact path/naming conventions
4. schema and scoring validation
5. markdown rendering as a non-canonical derived view
6. safe run-level artifact cleanup for canonical JSON, derived report, and marking-asset bundle
7. a review-domain backend contract under `ai_study_buddy.marking.review` for attempt review payload shaping and companion artifact writes

## Canonical Data Contract

- Schema identifier: `marking_result.v1.6` (legacy `v1` / `v1.1` / `v1.2` / `v1.3` / `v1.4` are rejected in normal runtime validation; `v1.5` remains readable for migration/backward compatibility)
- Schema source:
  `ai_study_buddy/schemas/marking/marking_result.v1.6.schema.json`
- Amendment schema source:
  `ai_study_buddy/schemas/marking/marking_amendment.v1.schema.json`
- Canonical storage path:
  `ai_study_buddy/context/marking_results/<student>/<subject_context>/<attempt_basename>.json`
- Derived markdown path:
  `ai_study_buddy/context/learning_reports/<student>/<subject_context>/<attempt_basename> - Marking Report.md`
- Ephemeral page renders, verification crops, and per-run `_*.py` helpers (not part of this package) live under the standardized bundle root:
  `ai_study_buddy/context/marking_assets/<student_slug>/<subject_context>/<artifact_stem>/` — see `.cursor/skills/mark-goodnote-completion/SKILL.md`.

## Core Functional Requirements

### 0) Review domain contract (`marking.review`)

`ai_study_buddy.marking.review` is a package-owned review-domain backend surface consumed by `review_workspace` backend wiring.

Ownership and boundaries:

1. `marking.review` may read canonical marking artifacts under `context/marking_results/**`.
2. `marking.review` may write only companion artifacts:
   - `context/student_review_states/**`
   - `context/marking_amendments/**`
3. `marking.review` must never mutate canonical `context/marking_results/**` artifacts.
4. Latest-artifact selection for attempts must reuse `find_marking_artifacts_for_attempt(...)`.

Route surface (via `api_routes.py`):

1. `GET /api/health`
2. `GET /api/students`
3. `GET /api/student/attempts`
4. `GET /api/student/attempts/{attempt_id}`
5. `PUT /api/student/attempts/{attempt_id}/review-state`
6. `PUT /api/student/attempts/{attempt_id}/amendments`

Implementation modules:

1. `attempt_service.py`: attempt index shaping over registry + latest artifact lookup
2. `detail_service.py`: marked/unmarked detail shaping and resolved/base projection
3. `note_service.py`: review-state validation and writes (`student_review_state.v1`)
4. `amendment_service.py`: amendment validation/merge and overlay writes (`marking_amendment.v1`)
5. `repository.py`: filesystem persistence helpers for review companion artifacts
6. `models.py`: shared normalization and timestamp helper behavior for review payloads

### 1) Artifact identity and naming

- `<attempt_basename>` is derived from attempt filename stem.
- Known prefixes are stripped repeatedly:
  - `c_`
  - `_c_`
  - `_raw_`
  - `raw_`
- Suffix uses marking timestamp: `__YYYYMMDD_HHMMSS`.

### 1.1) Marking timestamps (Singapore time)

- **Timezone:** `Asia/Singapore` (SGT, UTC+8, no DST).
- **Persisted fields:** `created_at` and `updated_at` on canonical JSON are **ISO-8601 strings with a `+08:00` offset** (not `Z` / UTC-by-default).
- **Basename suffix:** `__YYYYMMDD_HHMMSS` is the **Singapore local civil time** corresponding to the marking instant (same instant may be supplied as UTC in memory; the canonical writer normalizes before save).
- **API:** `ai_study_buddy.marking.core.marking_time` (`now_marking_iso`, `to_marking_iso`) and `write_marking_artifact` enforce this on write.
- **Human note edits:** `review_meta.updated_at` uses the same SGT rule (`workflows/edit_human_notes.py`).

### 1.2) Multiple attempts per template (`v1.1`)

When a student attempts the same template multiple times, canonical JSON context may carry:

- `template_attempt_group_id`: deterministic group id for `(student_slug, template_file_id)`:
  - `"<student_slug>::<template_file_id>"`
- `attempt_sequence`: 1-based sequence number inside that group
- `attempt_label`: optional free-text label (for example, `initial`, `retake`)

Writer contract:

- `write_marking_artifact(...)` emits `schema_version = marking_result.v1.6`.
- When `template_file_id` exists, writer auto-populates `template_attempt_group_id` and `attempt_sequence`.
- If `template_file_id` is missing, writer sets:
  - `template_attempt_group_id = null`
  - `attempt_sequence = null`
  - `attempt_label` remains caller-provided or `null`.

### 2) Validation and scoring rules

- `question_results[].max_marks` and `earned_marks`, and `summary.total_marks` / `summary.earned_marks`, may be **non-negative integers or finite floats** (e.g. **0.5** step for teacher-marked papers). **Booleans are rejected** (they subclass `int` in Python).
- Every artifact must validate against `marking_result.v1.6`.
- v1.1+ context field validation:
  - `template_attempt_group_id`: null or non-empty string
  - `attempt_sequence`: null or integer `>= 1`
  - `attempt_label`: null or non-empty string (max length 64)
- v1.2 context field validation:
  - `marking_asset`: null or non-empty string (relative path under `ai_study_buddy/context/marking_assets/`)
- v1.3 context field validation:
  - `is_partial`: boolean
- v1.5+ context field validation:
  - `question_page_map`: required array (may be empty)
  - each entry must include:
    - `result_id` (non-empty string, unique within map, must exist in `question_results[].result_id`)
    - `attempt_page_start` (integer `>= 1`)
    - `confidence` (`high|medium|low`)
    - `source` (`manual_visual|ai_visual_backfill|script_inferred`)
  - optional fields:
    - `evidence_image` (null or non-empty string)
    - `note` (null or string)
- v1.6 context field validation:
  - `context_resolution`: required object in canonical writes
  - required non-empty string fields:
    - `method` (must be `resolve_marking_context`)
    - `resolver_version`
    - `resolved_at`
    - `mode` (`standard_mapped_answer|embedded_answer_override|teacher_annotated`)
  - optional fields:
    - `invariants` (object)
- Ink interpretation baseline for visual marking:
  - blue/black ink: student's original answers/workings (gradable)
  - red ink: correctness/correction marks, deductions, tallying (non-gradable annotation)
  - green ink: student correction layer (non-gradable annotation by default)
  - purple ink: parent remarks/learning notes (non-gradable annotation)
- Default grading scope uses only student blue/black writing with printed question text.
- Red/green/purple annotations are excluded from scoring unless a future workflow explicitly requests annotation extraction as auxiliary metadata.
- Summary totals must match computed totals from question rows:
  - `summary.total_marks` equals sum of counted row `max_marks`
  - `summary.earned_marks` equals sum of counted row `earned_marks`
- Percentage is computed consistently via `compute_percentage`.
- Rows with `scoring_status=excluded_disqualified` remain traceable but do not
  contribute to summary scoring.

### 3) Rendering rules

- Markdown learning report is generated from canonical JSON.
- Rendering is idempotent for unchanged JSON input.
- Markdown is not treated as source-of-truth data.
- When `context.attempt_sequence` exists, report result section renders: `Attempt #<n>`.
- Diagnosis text in question tables is subject-aware:
  - Chinese / Higher Chinese contexts may render Chinese mistake-type labels.
  - non-Chinese contexts render diagnosis as `mistake_type: reasoning` when both exist.
  - reasoning-only diagnosis remains valid and should render directly.
- Renderer may resolve canonical placeholders to local runtime paths for display:
  - `GOODNOTES_ROOT` and `DAYDREAMEDU_ROOT` via configured roots
  - `<student_email>` via `student_id` lookup when available

### 3.1) Path privacy rules (`v0.1.2`)

- Canonical artifact context path fields (`attempt/template/unit/answer`) must be
  persisted in a privacy-safe normalized form.
- Write-time normalization rules:
  - GoodNotes absolute local prefix -> `GOODNOTES_ROOT`
  - DaydreamEdu absolute local prefix -> `DAYDREAMEDU_ROOT`
  - email-shaped segments -> `<student_email>`
- The placeholder form is canonical for persisted JSON artifacts.

### 4) Human review rules

- Human notes are co-located in canonical JSON:
  - `summary.human_note`
  - `question_results[].human_note`
- Review metadata updates on note changes:
  - `review_meta.updated_at`
  - `review_meta.updated_by`

### 5) Legacy migration rules

- Legacy markdown reports can be parsed into `marking_result.v1`.
- Migration supports dry-run and batch controls (`--limit`, student/subject
  filters).
- Existing destination artifacts are skipped unless `--overwrite` is set.
- Context lookup backfills (`*_file_id`, book group, unit label) are best
  effort and non-blocking.
- Attempt metadata backfill workflow:
  - `python3 -m ai_study_buddy.marking.workflows.backfill_attempt_metadata_v1_1 --dry-run`
  - groups by `(student_slug, template_file_id)` and assigns contiguous `attempt_sequence` by `(created_at, json path)`

### 5.1) Schema evolution checklist

Any new field or schema version must ship as one cohesive change:

1. approved proposal update in `docs/proposal/`
2. schema update (`ai_study_buddy/schemas/marking/marking_result.v1.6.schema.json` or new `vNext` schema file)
3. runtime validator update (`core/artifact_schema.py`)
4. producer/consumer update (`core/artifact_writer.py` and affected workflow/parser)
5. tests:
   - schema fixture/parity coverage
   - semantic invariant coverage
6. docs/versioning:
   - `README.md`, `SPEC.md`, `TESTING.md`
   - `CHANGELOG.md` with version bump

### 6) Context resolver contract (MVP)

Primary function:

- `resolve_marking_context(...) -> MarkingContext`

Resolver-only write contract:

1. Canonical producers must obtain `context` from resolver APIs in this package.
2. Manual context assembly is unsupported for canonical writes.
3. `write_marking_artifact(...)` enforces resolver provenance/invariant checks fail-closed.

MVP usage is path-first:

- Required:
  - `attempt_file_id_or_path: str | Path`
- Optional:
  - `self_answer_pages: tuple[int, int] | None`
  - `auto_register_attempt: bool = False`
  - `auto_link_template: bool = False`
  - `manager: PdfFileManager | None`

Other resolver hints (`student_*`, `unit_query`) are secondary and may evolve.

Input semantics:

1. `attempt_file_id_or_path` is authoritative.
2. Resolver accepts file ID or file path.
3. Resolver does not do fuzzy discovery; caller must pass a unique attempt.
4. If input is a file path and attempt is not registered:
   - fail when `auto_register_attempt=False`
   - register as completion `main` and continue when `auto_register_attempt=True`
5. If template link is missing:
   - fail when `auto_link_template=False`
   - attempt link and re-check when `auto_link_template=True`
6. `self_answer_pages`, when provided:
   - must be a two-int tuple `(begin_page, end_page)`
   - uses inclusive 1-based page numbers
   - requires `begin_page <= end_page`
   - switches answer-source mode to embedded/self-answer override

Output contract (`MarkingContext`):

1. Attempt/template/unit identity:
   - `attempt_file_id`, `attempt_file_path`
   - `template_file_id`, `template_file_path`
   - `unit_file_id`, `unit_file_path`, `unit_label`
2. Answer context:
   - `answer_file_id`, `answer_file_path`
   - `answer_page_start`, `answer_page_end`
   - `starts_mid_page`, `ends_mid_page`
   - `answer_mapping_source`, `answer_mapping_notes`
3. Book context (registry mapping mode):
   - `book_group_id`, `book_label`
4. Render hints:
   - `needs_visual_attempt_pages`
   - `needs_visual_answer_pages`

MVP scope rule:

- Context is always full-attempt scope.
- Question-level selection is out of scope for this contract.

Embedded-answer override guarantees (`self_answer_pages` provided):

1. `answer_file_id == template_file_id`
2. `answer_file_path == template_file_path`
3. `answer_page_start == self_answer_pages[0]`
4. `answer_page_end == self_answer_pages[1]`
5. `answer_mapping_source` includes explicit self-answer override note

Determinism and invariants:

1. No OCR, grading, or rendering side effects.
2. Deterministic output for identical inputs and registry state.
3. Exactly one selected attempt and one linked template.
4. Attempt must be registered `main`, non-template, and under `GoodNotes`.
5. Auto-registration is allowed only when `auto_register_attempt=True`.
6. Auto-registration must not register a template as attempt.
7. Answer-source mode is mutually exclusive:
   - registry mapping mode
   - self-answer override mode via `self_answer_pages`
8. Returned IDs/paths are registry-backed.

Errors:

- `NotFoundError` for missing dependencies (attempt/template/book group/answer mapping)
- `MarkingContextResolutionError` for invalid resolution states, including:
  - template in multiple book groups
  - invalid attempt type/location constraints
  - invalid secondary-hint combinations
  - invalid `self_answer_pages` shape/range
  - invalid auto-registration attempts

Normative algorithm (MVP, path-first):

1. Resolve attempt by ID/path.
2. If path is unregistered and auto-register enabled, register then re-resolve.
3. Resolve linked template (optionally auto-link).
4. Resolve answer source:
   - override mode when `self_answer_pages` is provided
   - else registry mapping mode via book group + answer mapping
5. Build and return immutable `MarkingContext`.

### 7) Completion -> artifact lookup contract

Primary function:

- `find_marking_artifacts_for_attempt(...) -> list[MarkingArtifactRef]`

Purpose:

- Given one completion attempt (`file_id` or path), return matching canonical JSON artifacts and paired report paths.

Input contract:

1. `attempt_file_id_or_path` accepts registry file id or path-like input.
2. `match_condition` supports:
   - `json_only` (default): include JSON matches even when report is missing
   - `json_and_report`: include only matches where report file exists
3. `manager` is required to enforce student-scoped lookup boundaries.

Matching rules:

1. Scan scope is limited to `context/marking_results/<student_slug>/` for the completion student.
2. Primary match key is `context.attempt_file_id` when present in artifact JSON.
3. Secondary match key is normalized `context.attempt_file_path` only when artifact `attempt_file_id` is absent.
4. If artifact has non-empty `attempt_file_id` and it mismatches the completion id, do not fallback-match by path.
5. Corrupt/malformed JSON files are skipped (non-fatal).

Output contract:

1. Return `MarkingArtifactRef(marking_result_json, learning_report_md)` rows.
2. Sort deterministically:
   - `created_at` descending
   - JSON path ascending tie-breaker
3. Empty list is valid when no matches are found.

### 8) Run artifact cleanup contract

Primary function:

- `remove_marking_run_artifacts(...) -> MarkingRunRemovalResult`

Purpose:

- Remove one marking run's filesystem artifacts as one operation:
  - canonical JSON under `context/marking_results/...`
  - derived markdown report under `context/learning_reports/...`
  - marking-asset bundle under `context/marking_assets/...` when `context.marking_asset` is set

Input contract:

1. `marking_result_json` identifies the run and may be absolute or relative to `context_root`.
2. v1 identity is JSON-path only (no delete-by-completion-id/path helper in this contract).
3. `mode` supports:
   - `strict` (default): any missing expected artifact is an error
   - `best_effort`: missing artifacts are skipped
4. Path-safety checks are mandatory in both modes.

Safety rules:

1. Canonical JSON path must resolve under `context_root/marking_results/`.
2. Derived report path must resolve under `context_root/learning_reports/`.
3. Bundle path (when present) must resolve under `context_root/marking_assets/`.
4. Invalid or unsafe `context.marking_asset` values are rejected.
5. Bundle-root symlink deletion is rejected.

Behavior:

1. Dry-run (`dry_run=True`) computes plan/output without deleting.
2. Delete ordering is:
   - learning report
   - marking-asset bundle
   - canonical JSON last
3. Result includes requested plan, deleted paths, and skipped-missing paths.

## Public Entry Points

- `api.py`: compact public import surface for package consumers
- `workflows/migrate_learning_reports.py`: markdown to canonical JSON migration
- `workflows/report_renderer.py`: canonical JSON to markdown renderer
- `workflows/edit_human_notes.py`: safe note editing utility with schema validation
- `workflows/remove_run_artifacts.py`: run-level cleanup workflow for one canonical artifact path
- `core/artifact_writer.py`: canonical JSON writer helper
- `core/artifact_schema.py`: schema loading/validation and scoring utilities
- `core/artifact_paths.py`: naming/path builder utilities
- `core/artifact_lookup.py`: completion-to-artifact lookup utility
- `core/artifact_cleanup.py`: safe run-level artifact cleanup utility

## Non-Goals

- Bounding-box or crop-region evidence storage in artifact rows
- Database-first canonical storage
- Revision graph semantics (`revision`, `supersedes_marking_id`)
- Soft-delete/archive/recovery log for deleted run artifacts
