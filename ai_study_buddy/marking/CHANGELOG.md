# Changelog

All notable changes to `ai_study_buddy.marking` are documented in this file.

Committed changes under `ai_study_buddy/marking/` should add an entry here and bump **Current version** in `README.md` (semver: **patch** for docs or small renderer tweaks, **minor** for schema or public API changes). `SPEC.md` / `TESTING.md` titles do not carry the package version.

## [0.3.1] - 2026-05-05

Patch: complete Proposal 14 persistence rollout for `file_question_info`, including DB migration/import/dual-write wiring, schema-version standardization updates, and run-level timestamp enforcement.

### Added

- `ai_study_buddy/learning_db/migrations/002_file_question_info.sql`:
  - adds `file_question_info_runs`, `file_question_info_sections`, `file_question_info_items`
  - expands import-family checks to include `file_question_info` in `import_identity_map` / `import_quarantine`
- `ai_study_buddy/marking/file_question_info/post_write.py`:
  - adds `finalize_question_sections_snapshot(...)` shared post-write helper for detector workflows (validate + dual-write mirror)

### Changed

- `learning_db/import_context_json.py`:
  - adds `upsert_file_question_info_run(...)`
  - extends scanner/import family support for `context/file_question_info/**/question_sections.json`
  - adds `file_question_info` quarantine routing/error-code mapping
  - enforces required run-level timestamps (`created_at`, `updated_at`) for `file_question_info` imports
- `learning_db/dual_write.py`:
  - adds `family=\"file_question_info\"` projection routing
- `marking/file_question_info/api.py`:
  - validator schema map now targets latest detector schema versions:
    - `english-v1.3`
    - `chinese-v1.4`
    - `high-chinese-v1.2`
    - `math-v1.2`
    - `science-v1.2`
- detector agent docs:
  - updated version/schema references
  - updated runtime contract to include shared post-write finalizer invocation

### Data and Schema Migration

- Added latest question-section schema files with timestamp-required top-level fields:
  - `english_paper2_questions_section.v1.3.schema.json`
  - `chinese_paper2_questions_section.v1.4.schema.json`
  - `higher_chinese_paper2_questions_section.v1.2.schema.json`
  - `math_questions_section.v1.2.schema.json`
  - `science_questions_section.v1.2.schema.json`
- Migrated existing `context/file_question_info/**/question_sections.json` corpus:
  - bumped `schema_version` to latest family versions
  - standardized section key usage to `answers_page_range`
  - backfilled `created_at` / `updated_at` from snapshot file mtime (same run-level timestamp per artifact)
- Backfilled `file_question_info` into `study_buddy.db`:
  - scanned/imported: `23/23`
  - runs: `23`
  - sections: `105`
  - items: `760`
  - quarantine (`file_question_info`): `0` open / `0` total

### Documentation

- `README.md`:
  - bump current version to `v0.3.1`
  - document shared post-write finalizer usage in `file_question_info` workflows
- `docs/proposal/14-persist-file-question-info-in-study-buddy-db.md`:
  - marked implemented and recorded rollout/backfill/runtime verification status

## [0.3.0] - 2026-05-05

Minor: add `marking.file_question_info` helpers for deterministic `context/file_question_info/...` detector artifacts and strict validation of `question_sections.json`.

### Added

- `ai_study_buddy/marking/file_question_info/`:
  - `file_question_info_run_dir_for_pdf(...)`: deterministic run-folder resolution.
  - `render_file_question_info_pages_for_pdf(...)`: page rasterization to `rendered_pages/page_%03d.png`.
  - `load_question_sections_json(...)` / `validate_question_sections_dict(...)`: schema-dispatched validation for `question_sections.json`.
  - CLI validator entrypoint: `python3 -m ai_study_buddy.marking.file_question_info.validate <path>`.
- Runtime validation invariant for stem-bearing sections:
  - `questions_page_range.start_page == min(question_info[*].start_page)` when `stem_page_range` exists.

### Documentation

- `README.md`:
  - bump current version to `v0.3.0`
  - document `file_question_info` layout and canonical validator command.

## [0.2.19] - 2026-05-04

Patch: migrate marking JSON schemas into the shared `ai_study_buddy/schemas/` tree and update runtime/documentation references.

### Changed

- schemas moved: `ai_study_buddy/marking/schemas/*.schema.json` -> `ai_study_buddy/schemas/marking/*.schema.json`
- `core/artifact_schema.py` now loads schemas from `ai_study_buddy/schemas/marking/`

### Documentation

- updated schema path references across `README.md`, `SPEC.md`, `CHANGELOG.md`, and marking docs/proposals

## [0.2.18] - 2026-04-29

Patch: consolidate review-domain backend services into `marking/review` and remove the old top-level `student_review` module (Option B direct move).

### Changed

- added `review/` package under `ai_study_buddy/marking` by moving review-domain backend services:
  - `amendment_service.py`
  - `api_routes.py`
  - `attempt_service.py`
  - `detail_service.py`
  - `models.py`
  - `note_service.py`
  - `repository.py`
- `review_workspace/backend/app.py` now imports routes/models from `ai_study_buddy.marking.review.*`
- updated marking tests to import review-domain services from `ai_study_buddy.marking.review.*`

### Documentation

- `README.md`:
  - bump current version to `v0.2.18`
  - include `review/` in package scope and directory layout
- `ARCHITECTURE.md`:
  - add `review/` layer and durable review-domain decisions
- `TESTING.md`:
  - include `tests/test_review_workspace_amendments.py` in primary automated coverage

## [0.2.17] - 2026-04-28

Patch: align `marking_result.v1.6` generation telemetry schema with optional model semantics.

### Changed

- `ai_study_buddy/schemas/marking/marking_result.v1.6.schema.json`:
  - keep `generation.telemetry` optional
  - allow `generation.telemetry` to be either `object` or `null`
  - relax telemetry key-shape constraints so producer/diagnostic metadata can be recorded without schema rejection

### Documentation

- `README.md`:
  - bump current version to `v0.2.17`

## [0.2.16] - 2026-04-28

Patch: complete resolver-only context hardening rollout (proposal phase 5-7), enforce fail-closed writer checks, and align producer/package docs with `marking_result.v1.6`.

### Changed

- `core/artifact_writer.py`:
  - removed `MARKING_ENFORCE_RESOLVER_CONTEXT` feature-flag gate
  - always enforces resolver-only context contract at canonical write time
- `tests/test_artifact_core.py`:
  - updated fixtures/tests for unconditional context-contract enforcement
  - added explicit rejection test for manual context writes missing `context_resolution` provenance
- `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md`:
  - strengthened producer guidance to forbid manual context assembly for persisted artifacts
  - added resolver-provenance preservation requirements

### Documentation

- `README.md`:
  - bump current version to `v0.2.16`
  - update canonical write contract references to `marking_result.v1.6`
  - add resolver-only context contract section and backward-compatibility note for `v1.5` reads
- `SPEC.md`:
  - update canonical contract references to `v1.6`
  - document `context.context_resolution` provenance requirements and fail-closed write boundary
- `ARCHITECTURE.md`:
  - add explicit writer enforcement boundary for resolver-only context production
  - update active writer schema-version contract to `v1.6`
- `TESTING.md`:
  - document resolver-context contract checks in test scope
  - add manual-verification expectation for deterministic write rejection when provenance is missing

## [0.2.15] - 2026-04-28

Minor: introduce `marking_result.v1.5`, migrate away from `question_results[].feedback`, and enforce `human_note` as the single per-question note field.

### Added

- `ai_study_buddy/schemas/marking/marking_result.v1.5.schema.json`:
  - standalone strict schema for `marking_result.v1.5`
  - removes `question_results[].feedback`
- `workflows/_migrate_feedback_to_human_note.py`:
  - one-off migration helper for `v1.4 -> v1.5`
  - conservative auto-merge for rows where both `feedback` and `human_note` exist
  - uses marker block: `[Migrated feedback]`

### Changed

- `core/artifact_schema.py`:
  - `SCHEMA_VERSION` and default writer/validator target now `marking_result.v1.5`
  - runtime strict validation now supports only `marking_result.v1.5`
- `core/models.py`:
  - `ArtifactQuestionResult` no longer includes `feedback`
- `workflows/migrate_learning_reports.py`:
  - migrated row construction no longer emits `feedback`
- `workflows/backfill_attempt_metadata_v1_1.py` and `workflows/backfill_is_partial_v1_3.py`:
  - when upgrading artifacts to current schema, migrate legacy `feedback` into `human_note` with conservative auto-merge and prune `feedback`
- `ai_study_buddy/schemas/marking/marking_amendment.v1.schema.json`:
  - remove `feedback` from allowed `question_amendments[].fields`
- `student_review/amendment_service.py` and `student_review/detail_service.py`:
  - remove amendment/detail-service dependency on `feedback`

### Data Migration

- Migrated corpus under `ai_study_buddy/context/marking_results/**/*.json`:
  - files migrated: `154`
  - question rows processed: `2655`
  - non-empty feedback rows: `149`
  - Case A (`feedback` -> empty `human_note` copy): `109`
  - Case B (append with marker to existing `human_note`): `40`
  - Case C (empty/null `feedback` pruned): `2506`
- All migrated artifacts now use `schema_version = marking_result.v1.5`.

### Documentation

- `README.md`, `SPEC.md`, `TESTING.md`:
  - update canonical schema contract references from `v1.4` to `v1.5`
  - update fixture path references to `tests/fixtures/marking_result_v1_5/`
- Marking producer contract alignment:
  - `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md`
  - remove references to `feedback` and require strict `v1.5` output alignment.

## [0.2.14] - 2026-04-28

Minor: make `marking_result.v1.4` an explicit strict schema contract and enforce strict runtime version handling.

### Added

- `ai_study_buddy/schemas/marking/marking_result.v1.4.schema.json`:
  - standalone, self-contained `v1.4` schema
  - explicit `question_results.items` structure
  - closed-contract policy via `additionalProperties: false` on top-level and key nested objects

### Changed

- `core/artifact_schema.py`:
  - `SCHEMA_PATH` now points to `ai_study_buddy/schemas/marking/marking_result.v1.4.schema.json`
  - `load_marking_result_schema(version)` now requires an explicit version argument
  - normal runtime validation now supports only `marking_result.v1.4`
  - unsupported versions raise `UnsupportedSchemaVersionError`
  - JSON Schema validation is executed before semantic Python invariants
- `workflows/migrate_learning_reports.py`:
  - migrated artifacts now construct with `SCHEMA_VERSION` (`marking_result.v1.4`)
- `tests/test_artifact_core.py`:
  - updated schema loader usage to explicit version constant
  - added coverage for unsupported-version rejection
  - added coverage for closed-contract rejection of unexpected top-level fields

### Documentation

- `README.md`:
  - bump current version to `v0.2.14`
  - update canonical schema path to `ai_study_buddy/schemas/marking/marking_result.v1.4.schema.json`
- `SPEC.md`:
  - update canonical schema path to `ai_study_buddy/schemas/marking/marking_result.v1.4.schema.json`
  - document strict `v1.4` runtime validation contract
- Consumer instruction alignment (skills/agents used by marking producers):
  - `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md`
  - `.cursor/agents/marking-phase1-mapper.md`
  - `.cursor/agents/marking-phase2-fast-pass-grader.md`
  - `.cursor/agents/marking-phase3-deep-dive.md`
  - `.cursor/agents/marking-phase4-taxonomy-tagger.md`
  - updated to enforce strict `marking_result.v1.4` output expectations (closed contract, enum-safe outcomes, schema-compatible row/object shapes, and final runtime validation before artifact write)

## [0.2.13] - 2026-04-26

Minor: add a first-class `marking_amendment.v1` JSON schema file and public loader so amendment overlay contracts are versioned alongside marking schemas.

### Added

- `ai_study_buddy/schemas/marking/marking_amendment.v1.schema.json`:
  - canonical JSON Schema contract for review-workspace amendment overlays
  - top-level contract for `schema_version`, `context`, `summary_overrides`, `question_amendments`, `question_page_map_amendments`, and `review_meta`
  - editable field allowlist for `question_amendments[].fields`
- `core/artifact_schema.py`:
  - `AMENDMENT_SCHEMA_PATH`
  - `load_marking_amendment_schema()`
- `tests/test_artifact_core.py`:
  - amendment schema load test
  - amendment schema accepts valid payload test
  - amendment schema rejects unsupported question field test

### Changed

- `api.py`:
  - exports `AMENDMENT_SCHEMA_PATH` and `load_marking_amendment_schema` in the public API

### Documentation

- `README.md`:
  - bump current version to `v0.2.13`
  - document `ai_study_buddy/schemas/marking/marking_amendment.v1.schema.json`
- `SPEC.md`:
  - include amendment schema as companion canonical contract
- `TESTING.md`:
  - include amendment schema validation coverage in test scope

## [0.2.12] - 2026-04-26

Minor: establish the multi-agent marking orchestration skill stack (active v2 orchestrator + dedicated phase agents), and archive superseded monolithic/v1 skill flows.

### Added

- Multi-agent phase subagents under `.cursor/agents/`:
  - `marking-phase1-mapper.md`
  - `marking-phase2-fast-pass-grader.md`
  - `marking-phase3-deep-dive.md`
  - `marking-phase4-taxonomy-tagger.md`
- Active orchestrator skill:
  - `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md`

### Changed

- Multi-agent proposal implementation plan and status tracking:
  - `docs/proposal/8-multi-agent-marking-architecture.md`
  - updated implementation checklist format
  - clarified why separate `.cursor/agents` files are required (`model: inherit` to align with orchestrator Auto mode)
  - updated Phase 2 cross-proposal link to the moved file path under `review_workspace/docs/proposal/`

### Archived

- Superseded monolithic/v1 skills moved to `.cursor/skills_archive/`:
  - `mark-goodnote-completion/`
  - `diagnose-student-school-work/`
  - `mark-student-work-multi-agent/`

## [0.2.11] - 2026-04-23

Minor: complete MAB Phase E with package-owned PDF-to-bundle render helpers and standardized full-page naming output.

### Added

- `assets/render.py`:
  - `render_attempt_pdf_to_bundle(...)` to render full attempt PDF pages to `attempt/page-{nn}.{ext}`
  - `render_answers_pdf_pages_to_bundle(...)` to render selected answer PDF pages in mapping order to `answers/page-{nn}.{ext}`
  - guardrails for page-range validation, optional cleanup of stale full-page renders, and explicit PyMuPDF dependency erroring
- `tests/test_marking_asset_render.py`:
  - covers standardized naming output
  - verifies cleanup behavior for stale `page-*` full-page files
  - verifies answer-page mapping order output and out-of-range page validation
- `core/artifact_cleanup.py`:
  - `remove_marking_run_artifacts(...)` to remove one run's canonical JSON, learning report, and marking asset bundle as a single operation
  - strict vs best-effort mode, dry-run planning, and path-safety guardrails under `context_root`
- `workflows/remove_run_artifacts.py`:
  - CLI wrapper for run-level artifact removal (`--dry-run`, strict default, optional `--best-effort`)
- `tests/test_artifact_cleanup.py`:
  - covers strict missing-artifact errors, best-effort skipping, unsafe bundle-path rejection, recursive bundle deletion, and report-path derivation

### Changed

- `api.py` / `assets/__init__.py`:
  - export new render helpers in the public package API
- `api.py`:
  - exports run-artifact cleanup surface (`remove_marking_run_artifacts`, `MarkingRunRemovalPlan`, `MarkingRunRemovalResult`, `MarkingRunArtifactRemovalError`)

### Documentation

- `README.md`:
  - bump current version to `v0.2.11`
  - align example `evidence_image` to standardized `attempt/page-01.png`
  - add quick-start snippet for `render_attempt_pdf_to_bundle(...)`
  - add `remove_run_artifacts` workflow usage in quick-start
- `TESTING.md`:
  - add artifact-cleanup test scope and command
- `SPEC.md`:
  - add normative run-artifact cleanup contract section (`remove_marking_run_artifacts`)
  - add cleanup workflow/core modules to public entry points
- `ARCHITECTURE.md`:
  - include run-artifact cleanup in responsibilities, module boundaries, and remediation flow notes
- `docs/proposal/`:
  - mark completion-lookup proposal (`2-...`) as implemented (`v0.2.0`)
  - mark run-artifact-removal proposal (`6-...`) as implemented (`v0.2.11`)
- Skill alignment (consumer side):
  - `.cursor/skills/mark-goodnote-completion/SKILL.md`
  - `.cursor/skills/diagnose-student-school-work/SKILL.md`
  - both now instruct using package render helpers instead of ad hoc PyMuPDF snippets where possible.

## [0.2.10] - 2026-04-23

Patch: establish Marking Asset Bundle (MAB) package support and validation, then align operator workflows to the same contract.

### Added

- `assets/` package:
  - `layout.py` with bundle dir constants and full-page filename regex helpers
  - `paths.py` with shared bundle path derivation (`marking_asset_rel_path_from_artifact_path`) and safe bundle resolution (`bundle_root_from_context`)
  - `validate.py` with `ValidationReport`, strict/lenient checks, evidence-image safety checks, and review-readiness assertion
- `workflows/validate_bundle.py` CLI for validating one artifact's bundle against the MAB contract.
- `tests/test_marking_asset_bundle.py` for bundle path + validation coverage.

### Changed

- `core/artifact_writer.py`:
  - uses shared path builder for `context.marking_asset` derivation
  - creates required `attempt/` and `crops/` subdirectories whenever `context.marking_asset` is present
- `api.py`:
  - exports bundle helpers and validators (`ValidationIssue`, `ValidationReport`, `validate_marking_asset_bundle`, `assert_marking_asset_bundle_ready_for_review`, path helpers)
- `tests/test_artifact_core.py`:
  - verifies writer-created bundle subdirectories (`attempt/`, `crops/`)

### Documentation

- Proposal update: `docs/proposal/5-marking-asset-bundle-standardization.md` now captures:
  - explicit path-safety rules for `context.marking_asset` and `question_page_map[].evidence_image`
  - `bundle.json` lifecycle rule: write only after render finalization
  - removal of speculative `workflow_mode` manifest field
- `README.md`:
  - bump current version to `v0.2.10`
  - add bundle-validation CLI usage
- `TESTING.md`:
  - add MAB validation test coverage and test command
- Skill alignment (consumer side, small part of this release):
  - `.cursor/skills/mark-goodnote-completion/SKILL.md` and `.cursor/skills/diagnose-student-school-work/SKILL.md` now follow the standardized MAB root and `page-{nn}` full-page naming.

## [0.2.9] - 2026-04-22

Minor: bump canonical schema to `marking_result.v1.4` with per-question attempt-page anchors for forward runs.

### Changed

- `core/artifact_schema.py`:
  - `SCHEMA_VERSION` now defaults to `marking_result.v1.4`
  - validator now accepts `marking_result.v1`, `marking_result.v1.1`, `marking_result.v1.2`, `marking_result.v1.3`, and `marking_result.v1.4`
  - `marking_result.v1.4` requires `context.question_page_map` as an array (may be empty)
  - validates `question_page_map` entry membership/uniqueness and field constraints (`attempt_page_start`, `confidence`, `source`)
- `core/models.py`:
  - added `QuestionPageMapEntry`
  - `MarkingArtifactContext` now includes `question_page_map`
  - parsing support added in `MarkingArtifact.from_dict(...)`
- `core/artifact_writer.py`:
  - writer now emits `schema_version = marking_result.v1.4`
  - writer defaults missing `context.question_page_map` to empty list
- `ai_study_buddy/schemas/marking/marking_result.v1.schema.json`:
  - schema `$id` / `title` bumped to v1.4
  - `schema_version` enum includes `marking_result.v1.4`
  - `context.question_page_map` property added
- `api.py`:
  - exports `QuestionPageMapEntry` in public API
- `tests/test_artifact_core.py` and `tests/test_migration.py`:
  - updated writer/schema expectations to v1.4
  - added v1.4 validation tests for `question_page_map` duplicate/unknown/invalid constraints

### Documentation

- Updated `README.md`, `SPEC.md`, `ARCHITECTURE.md`, and `TESTING.md` for v1.4 and `question_page_map`.
- Updated `.cursor/skills/mark-goodnote-completion/SKILL.md` and `.cursor/skills/diagnose-student-school-work/SKILL.md` to capture `context.question_page_map` during future marking runs.

## [0.2.8] - 2026-04-22

Patch: shared exclusion list for completion-files registry audit research (schema unchanged).

### Added

- `core/completion_registry_audit.py`:
  - `GOODNOTES_SCIENCE_REVISION_GUIDE_BOOK_FOLDERS_EXCLUDED` (exact GoodNotes `Book/<folder>` segment names)
  - `is_goodnotes_science_revision_guide_book_excluded(path)` to drop non-gradable Science revision guide trees from audit tallies

## [0.2.7] - 2026-04-22

Minor: bump canonical schema to `marking_result.v1.3` for partial-marking metadata.

### Changed

- `core/artifact_schema.py`:
  - `SCHEMA_VERSION` now defaults to `marking_result.v1.3`
  - validator now accepts `marking_result.v1`, `marking_result.v1.1`, `marking_result.v1.2`, and `marking_result.v1.3`
  - `marking_result.v1.3` requires `context.is_partial` as boolean
- `ai_study_buddy/schemas/marking/marking_result.v1.schema.json`:
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
- `ai_study_buddy/schemas/marking/marking_result.v1.schema.json`:
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
- `ai_study_buddy/schemas/marking/marking_result.v1.schema.json`:
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
