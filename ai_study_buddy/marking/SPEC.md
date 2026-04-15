# Marking Package Specification (`v0.1.0`)

## Purpose

`ai_study_buddy.marking` provides the canonical, file-first marking artifact
pipeline for AI Study Buddy.

The package guarantees:

1. a stable `marking_result.v1` JSON contract
2. deterministic artifact path/naming conventions
3. schema and scoring validation
4. markdown rendering as a non-canonical derived view

## Canonical Data Contract

- Schema identifier: `marking_result.v1`
- Schema source:
  `ai_study_buddy/marking/schemas/marking_result.v1.schema.json`
- Canonical storage path:
  `ai_study_buddy/context/marking_results/<student>/<subject_context>/<attempt_basename>.json`
- Derived markdown path:
  `ai_study_buddy/context/learning_reports/<student>/<subject_context>/<attempt_basename> - Marking Report.md`

## Core Functional Requirements

### 1) Artifact identity and naming

- `<attempt_basename>` is derived from attempt filename stem.
- Known prefixes are stripped repeatedly:
  - `c_`
  - `_c_`
  - `_raw_`
  - `raw_`
- Suffix uses marking timestamp: `__YYYYMMDD_HHMMSS`.

### 2) Validation and scoring rules

- Every artifact must validate against `marking_result.v1`.
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

### 6) Context resolver contract (MVP)

Primary function:

- `resolve_marking_context(...) -> MarkingContext`

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

## Public Entry Points

- `api.py`: compact public import surface for package consumers
- `workflows/migrate_learning_reports.py`: markdown to canonical JSON migration
- `workflows/report_renderer.py`: canonical JSON to markdown renderer
- `workflows/edit_human_notes.py`: safe note editing utility with schema validation
- `core/artifact_writer.py`: canonical JSON writer helper
- `core/artifact_schema.py`: schema loading/validation and scoring utilities
- `core/artifact_paths.py`: naming/path builder utilities

## Non-Goals for `v0.1.0`

- Bounding-box or crop-region evidence storage in artifact rows
- Database-first canonical storage
- Revision graph semantics (`revision`, `supersedes_marking_id`)

