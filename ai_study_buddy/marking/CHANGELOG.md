# Changelog

All notable changes to `ai_study_buddy.marking` are documented in this file.

Committed changes under `ai_study_buddy/marking/` should add an entry here and bump **Current version** in `README.md` (semver: **patch** for docs or small renderer tweaks, **minor** for schema or public API changes). `SPEC.md` / `TESTING.md` titles do not carry the package version.

## [0.2.7] - 2026-04-22

Minor: bump canonical schema to `marking_result.v1.3` for partial-marking metadata.

### Changed

- `core/artifact_schema.py`:
  - `SCHEMA_VERSION` now defaults to `marking_result.v1.3`
  - validator now accepts `marking_result.v1`, `marking_result.v1.1`, `marking_result.v1.2`, and `marking_result.v1.3`
  - `marking_result.v1.3` requires `context.is_partial` as boolean
- `schemas/marking_result.v1.schema.json`:
  - schema `$id` / `title` bumped to v1.3
  - `schema_version` enum includes `marking_result.v1.3`
  - `context.is_partial` property added
- `core/models.py`:
  - `MarkingArtifactContext` includes `is_partial: bool = False`
- `core/artifact_writer.py`:
  - writer now emits `schema_version = marking_result.v1.3`
  - writer defaults/infers `context.is_partial` from `question_selection.raw_text` when missing
- `workflows/report_renderer.py`:
  - report context section now renders `Partial marking scope`
- `workflows/backfill_is_partial_v1_3.py`:
  - new migration workflow to backfill `context.is_partial`, default missing `marking_asset` to null, upgrade to v1.3, and re-render learning reports

### Documentation

- Updated `README.md`, `SPEC.md`, `ARCHITECTURE.md`, and `TESTING.md` for v1.3 semantics and migration command.

## [0.2.6] - 2026-04-22

Patch: bump canonical schema to `marking_result.v1.2` for `context.marking_asset`.

### Changed

- `core/artifact_schema.py`:
  - `SCHEMA_VERSION` now defaults to `marking_result.v1.2`
  - validator now accepts `marking_result.v1`, `marking_result.v1.1`, and `marking_result.v1.2`
- `schemas/marking_result.v1.schema.json`:
  - schema `$id` / `title` bumped to v1.2
  - `schema_version` enum includes `marking_result.v1.2`
- `core/artifact_writer.py`:
  - writer now emits `schema_version = marking_result.v1.2`
- `core/models.py`:
  - `MarkingArtifactContext` includes optional `marking_asset`

## [0.2.5] - 2026-04-21

Minor: fractional marks (e.g. 1.5 / 2) in `marking_result` rows and summary.

### Changed

- `core/models.py`: `max_marks` / `earned_marks` on `ArtifactQuestionResult` and `ArtifactSummary` use type `MarkingScore` (`int | float`).
- `core/artifact_schema.py`: validation accepts finite non-negative floats; `summary` totals compared with float tolerance; `compute_percentage` accepts float inputs.
- `workflows/report_renderer.py`: partial-credit bolding uses float-safe comparison.
- `workflows/migrate_learning_reports.py`: parses numeric marks with `float()` so legacy “32.5/40” scores migrate.

## [0.2.4] - 2026-04-20

Patch: renderer localization polish for diagnosis text in Chinese learning reports (schema/API unchanged).

### Changed

- `workflows/report_renderer.py`:
  - diagnosis cell formatting now supports subject-aware output:
    - Chinese / Higher Chinese contexts render Chinese mistake-type labels
    - other subjects keep existing `mistake_type: reasoning` style
  - reasoning-only rows continue to render without regression when mistake type is absent

## [0.2.3] - 2026-04-20

Patch: ship `marking_result.v1.1` attempt-group metadata support and immediate attempt-number rendering.

### Changed

- `core/artifact_schema.py`:
  - `SCHEMA_VERSION` now defaults to `marking_result.v1.1`
  - validator now accepts `marking_result.v1` and `marking_result.v1.1`
  - added validation for:
    - `context.template_attempt_group_id`
    - `context.attempt_sequence`
    - `context.attempt_label`
- `core/models.py`:
  - `MarkingArtifactContext` now includes:
    - `template_attempt_group_id`
    - `attempt_sequence`
    - `attempt_label`
  - parsing support added in `MarkingArtifact.from_dict(...)`
- `core/artifact_writer.py`:
  - writer now emits `schema_version = marking_result.v1.1`
  - auto-populates attempt grouping metadata when `template_file_id` is available
  - computes next `attempt_sequence` from existing same-student artifacts
- `workflows/backfill_attempt_metadata_v1_1.py`:
  - new dry-run/apply workflow to backfill `template_attempt_group_id`, `attempt_sequence`, and `attempt_label=null` on existing artifacts
  - upgrades backfilled artifacts to `schema_version = marking_result.v1.1`
- `workflows/report_renderer.py`:
  - result section now renders `Attempt #<n>` when `attempt_sequence` exists
- `schemas/marking_result.v1.schema.json`:
  - schema version field now accepts both `marking_result.v1` and `marking_result.v1.1`

## [0.2.2] - 2026-04-20

Patch: ink-color interpretation policy documentation for visual marking (schema/API unchanged).

### Documentation

- `SPEC.md`: added default color semantics and grading-scope rule:
  - blue/black = gradable student work
  - red/green/purple = non-gradable annotation by default
- `README.md`: added "Ink color interpretation policy" section and bumped package version.
- `TESTING.md`: added manual check to verify color-policy compliance in visual-marking runs.
- `.cursor/skills/mark-goodnote-completion/SKILL.md`: expanded color guidance beyond green-only correction handling and aligned scoring guardrails with blue/black-only grading.

## [0.2.1] - 2026-04-20

Patch: Singapore-time marking timestamps (schema `marking_result.v1` unchanged).

### Added

- `core/marking_time.py`: Singapore (`Asia/Singapore`) helpers — `now_marking_iso`, `to_marking_iso`, `format_basename_timestamp`, and `MARKING_TIMEZONE`.
- Public exports in `api.py` for the above (except `format_basename_timestamp`, which remains internal via `artifact_paths.format_artifact_timestamp`).

### Changed

- **Write path:** Canonical `created_at` / `updated_at` are normalized to **ISO-8601 with `+08:00`** on save (callers may still pass `Z`; `write_marking_artifact` converts to SGT).
- **Basename suffix:** `__YYYYMMDD_HHMMSS` uses **Singapore local wall time** for the marking instant.
- `workflows/edit_human_notes.py`: `review_meta.updated_at` and top-level `updated_at` use SGT.
- `workflows/migrate_learning_reports.py`: migrated artifact timestamps use SGT via `to_marking_iso`.

### Documentation

- `SPEC.md` §1.1 marking timestamps; `README.md`; `.cursor/skills/mark-goodnote-completion/SKILL.md` (SGT rule for agents).

## [0.2.0] - 2026-04-19

Small API addition release for completion-based artifact lookup.

### Added

- `core/artifact_lookup.py` with:
  - `find_marking_artifacts_for_attempt(...)`
  - `MarkingArtifactRef`
- Public API export in `api.py` for completion->artifact lookup.
- New tests in `tests/test_artifact_lookup.py` covering:
  - student-scoped lookup boundaries
  - id/path matching precedence
  - deterministic sorting
  - condition filtering (`json_only`, `json_and_report`)
  - malformed JSON skip behavior

### Documentation

- `README.md`: helper usage examples and version bump.
- `SPEC.md`: normative lookup contract section.
- `TESTING.md`: lookup test coverage and command entry.
- `ARCHITECTURE.md`: module-boundary and preflight lookup mention.

## [0.1.5] - 2026-04-19

### Changed

- `core/context_resolver.py`: student attempt files may resolve when under a `DaydreamEdu` path as well as `GoodNotes`; error messages updated accordingly.
- `tests/test_context_resolver.py`: regression test for a DaydreamEdu-scoped attempt main.

## [0.1.4] - 2026-04-17

### Documentation

- `SPEC.md` / `TESTING.md`: removed semver from titles; version is tracked in `README.md` and this changelog only.

## [0.1.3] - 2026-04-17

Small documentation and report-rendering polish.

### Changed

- `workflows/report_renderer.py`: marking table uses ✅ / ⚠️ / ❌ / 🚫 icons (and legend text updated) instead of `OK` / `PART` / `X` / `DQ`, aligned with the mark-goodnote-completion skill.

### Documentation

- `SPEC.md` and `README.md`: document ephemeral per-run renders, crops, and `_*.py` helpers under `ai_study_buddy/context/marking_assets/`; README clarifies they are not kept at the package root.

## [0.1.2] - 2026-04-16

Small privacy hardening release for canonical artifact paths.

### Added

- `core/path_privacy.py` with shared helpers to:
  - sanitize canonical artifact context paths at write time
  - resolve placeholder paths back to local paths at read/render time
- Artifact-core tests for write-time path sanitization and read-time placeholder expansion.

### Changed

- `write_marking_artifact(...)` now writes PII-safe context paths:
  - absolute GoodNotes prefixes are normalized to `GOODNOTES_ROOT`
  - absolute DaydreamEdu prefixes are normalized to `DAYDREAMEDU_ROOT`
  - email-shaped path segments are replaced with `<student_email>`
- `render_marking_report_markdown(...)` now resolves placeholders for display:
  - root placeholders from configured roots (`files/roots.py`)
  - `<student_email>` via student lookup from `PdfFileManager` using `context.student_id` when available

## [0.1.1] - 2026-04-15

Small MVP enhancement release for context resolution and skill alignment.

### Added

- `resolve_marking_context(...)` support for:
  - `auto_register_attempt=True` to register untracked GoodNotes completion paths as `main`
  - `self_answer_pages=(begin, end)` override mode for embedded-answer papers
- Focused resolver tests in `tests/test_context_resolver.py` covering new success/failure paths.
- Context resolver usage examples in `README.md` for mapped-answer, onboarding, and embedded-answer flows.

### Changed

- `resolve_marking_context(...)` now supports end-to-end first-touch onboarding in one call when `auto_register_attempt=True` and `auto_link_template=True`.
- Embedded-answer override mode now sets template as answer source with explicit `answer_mapping_source` note.
- `mark-goodnote-completion` skill contract now aligns with resolver flags and fallback rules.
- `MarkingContext.book_group_id` and `book_label` are nullable to support embedded-answer override runs without book-group dependency.

## [0.1.0] - 2026-04-15

Initial package documentation baseline for the marking system.

### Added

- Canonical package overview and usage guide in `README.md`.
- Package-level technical specification in `SPEC.md`.
- Package-level testing guide in `TESTING.md`.
- Release log initialized with version `0.1.0`.

### Current behavior at `0.1.0`

- Canonical artifact contract: `marking_result.v1`.
- JSON-first marking flow with markdown as derived output.
- Legacy markdown migration tooling and migration completion status documented.
