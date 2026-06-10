# Changelog

All notable changes to `ai_study_buddy.marking` are documented in this file.

Committed changes under `ai_study_buddy/marking/` should add an entry here and bump **Current version** in `README.md` (semver: **patch** for docs or small renderer tweaks, **minor** for schema or public API changes). `SPEC.md` / `TESTING.md` titles do not carry the package version.

## [0.3.24] - 2026-06-10

Patch: tutor chat prompt evidence hierarchy (grader output challengeable; human amendments authoritative).

### Changed

- **`marking/review/tutor_chat_context_service.py`:** prompt labels base marking as **AI grader output — challengeable**; human amendments as **authoritative overrides**; tutor may dispute grader `correct_answer` / `diagnosis` when clues, page evidence, or student reasoning warrant it.
- **Docs:** [L4_REVIEW_WORKSPACE_QUESTION_TUTOR_CHAT.md](../docs/L4_REVIEW_WORKSPACE_QUESTION_TUTOR_CHAT.md) §System prompt policy; [buddy_console proposal 4](../buddy_console/docs/proposal/4-review-workspace-question-tutor-chat.md).
- **Tests:** `test_tutor_chat_context_service.py` asserts new prompt section headers and policy text.

### Notes

- Consumed by `buddy_console` **v0.2.1+**. Existing tutor threads keep prior first-turn policy until **Refresh & continue** or a new session.

## [0.3.23] - 2026-06-09

Minor: question-scoped tutor chat API and `tutor_chat.v1` persistence (`buddy_console` v0.2.0).

### Added

- **`marking/review/tutor_chat_context_service.py`:** server-side context bundle from `get_attempt_detail` + labeled review notes; optional pedagogy markdown; debug `context-preview` gate.
- **`marking/review/tutor_chat_stale.py`:** `context_snapshot` fingerprints and stale-context drift (`marking`, `review_notes`).
- **`marking/review/tutor_chat_repository.py`:** read/write `context/tutor_chats/…/<session_id>.json` (`tutor_chat.v1`).
- **`marking/review/tutor_chat_service.py`:** Cursor SDK local inference (`model="auto"`, `Agent.resume`), SSE (`status` heartbeats, `token`, `done`, `error`).
- **`marking/review/api_routes.py`:** `GET`/`POST …/questions/{result_id}/tutor-chat`, `POST …/tutor-chat/sessions`, debug `GET …/tutor-chat/context-preview`.
- **Schema:** `ai_study_buddy/schemas/marking/tutor_chat.v1.schema.json`.
- **Tests:** `test_tutor_chat_context_service.py`, `test_tutor_chat_repository.py`, `test_tutor_chat_api.py`, `test_tutor_chat_service.py`.

### Notes

- Tutor routes require backend `CURSOR_API_KEY`; rollback via `BUDDY_CONSOLE_DISABLE_TUTOR_CHAT=1` → **404**.
- Incremental token streaming during SDK `iter_text()` is deferred; tokens still emit in a burst after `run.wait()`.

### Consumers

- `buddy_console` v0.2.0 **Ask AI** ([proposal 4](../buddy_console/docs/proposal/4-review-workspace-question-tutor-chat.md), [L4](../docs/L4_REVIEW_WORKSPACE_QUESTION_TUTOR_CHAT.md)).
- Standalone `review_workspace` mounts the same API but is not a maintained UI ship target for tutor chat.

## [0.3.22] - 2026-06-09

Patch: clear stale page-map amendment overrides when reverted to AI base.

### Fixed

- **`marking/review/amendment_service.py`:** `_upsert_page_map_amendment` removes override rows when the panel sends no override keys (revert to base); partial updates replace only keys present in the payload.
- **Tests:** `test_panel_save_clears_stale_page_map_override_when_override_keys_omitted`, `test_panel_save_reverts_page_map_override_to_base_value`.

### Consumers

- `buddy_console` v0.1.19+ and `review_workspace` v0.1.13+ (mapped-page amendment save).

## [0.3.21] - 2026-06-08

Patch: GoodNotes share links on attempt detail for Review Workspace evidence toolbar.

### Added

- **`marking/review/detail_service.py`:** `viewer.goodnotes_share_link` and `viewer.goodnotes_review_share_link` on marked attempt detail — resolved via `pdf_file_manager.get_goodnotes_document_timestamps_for_file(..., folder_scope=)`.
- **Tests:** `marking/tests/test_review_workspace_goodnotes_share_link.py`.

### Consumers

- `buddy_console` v0.1.18+ (Attempt / Review evidence toolbar share link + AirDrop).

## [0.3.20] - 2026-06-07

Minor: supervised review redo evidence (Review Workspace v0.1.16).

### Added

- **`marking/review/review_redo_service.py`:** `review_redo_render_dir`, `render_review_redo_pages`, `list_review_redo_images`, `ensure_review_redo_images` — cache-first raster into `context/review_redo/<student_slug>/<subject_context>/<normal_name>/rendered_pages/`.
- **`marking/review/detail_service.py`:** `viewer.review_redo` on attempt detail (step i); `get_attempt_review_evidence` (step ii).
- **`GET /api/student/attempts/{attempt_id}/review-evidence`** in `marking/review/api_routes.py` — lazy render; **404** when Review PDF unavailable.
- **Tests:** `marking/tests/test_review_workspace_review_redo.py`.

### Consumers

- `buddy_console` v0.1.16 Review tab ([proposal 3](../buddy_console/docs/proposal/3-review-workspace-supervised-redo-tab.md)).
- Requires `ai_study_buddy.files` v0.3.13+ (`resolve_supervised_review_pdf_for_attempt`).

## [0.3.19] - 2026-06-05

Patch: clear stale question amendments when save sends empty fields.

### Changed

- `marking/review/amendment_service.py`: `_upsert_question_amendment` removes the row when incoming `fields` is empty; non-empty `fields` replaces the stored override (no merge with stale values).

### Added

- `marking/tests/test_review_workspace_amendments.py`: regression for clearing a stale override via `{ result_id, fields: {} }`.

## [0.3.18] - 2026-06-02

Patch: enforce score/outcome consistency for review amendments.

### Changed

- `marking/review/amendment_service.py`: auto-align amendment fields bidirectionally during merge:
  - `outcome=correct` forces `earned_marks=max_marks`.
  - `outcome=wrong` forces `earned_marks=0`.
  - when only `earned_marks` is amended, infer `outcome=wrong` at `0`, and `outcome=correct` when `earned_marks==max_marks` (including amended `max_marks`).

### Added

- `marking/tests/test_review_workspace_amendments.py`: regression coverage for outcome→marks and marks→outcome auto-alignment, including amended-`max_marks` full-credit inference.

## [0.3.17] - 2026-06-02

Patch: review-workspace viewer adds template evidence images from FQI `rendered_pages/`.

### Added

- `marking/review/detail_service.py`: `viewer.template_images[]` on `GET /api/student/attempts/{attempt_id}` — resolves linked template (`context.template_file_id` or registry `completed_from`), lists `file_question_info/.../rendered_pages/` via static URLs.
- `marking/tests/test_review_workspace_template_viewer.py`: template image listing and empty fallback when no template link.

### Changed

- `marking/review/detail_service.py`: `_list_images_in_directory` resolves paths before `relative_to` so macOS `/var` vs `/private/var` does not drop image URLs.

## [0.3.16] - 2026-05-30

Patch: amendment PUT returns freshly resolved marking (not stale DB reload).

### Fixed

- `marking/review/api_routes.py`: `PUT .../amendments` now returns `marking_result` / `marking_result_resolved` / `amendment_state` from the just-saved `put_amendments` overlay instead of overwriting them with a follow-up `get_attempt_detail` read that could miss soft-deleted or not-yet-projected DB rows.

### Added

- `marking/tests/test_review_workspace_amendments.py`: `test_upsert_marking_amendment_clears_soft_delete` (documents `learning_db` upsert reviving `is_deleted` amendment rows).

## [0.3.15] - 2026-05-29

Patch: batch marking artifact index for inventory enrichment and buddy_console cache invalidation.

### Added

- `marking/core/artifact_lookup.py`: `MarkingArtifactIndex`, `build_marking_artifact_index` (one `marking_results` scan); optional `artifact_index` on `find_marking_artifacts_for_attempt`.
- `marking/tests/test_artifact_index.py`: index grouping and index-backed lookup tests.

### Changed

- `marking/review/workflow_flags.py`: optional `artifact_index` on `load_completion_marking_context` / `completion_workflow_flags`.
- `marking/review/api_routes.py`: invalidate `buddy_console` enriched inventory cache after review-state and amendment writes.

## [0.3.14] - 2026-05-25

Patch: v3 batch re-mark hygiene and superseded-run cleanup.

### Changed

- `marking/workflows/mark_student_work_multi_agent_v3.py`: on a new v3 run, trash prior bundles for the same completion (including finalized siblings) plus companion `marking_results` JSON and learning reports; `cleanup_stale_partials_for_v3_run` uses shared `move_path_to_trash` / `trash_marking_run_for_bundle` helpers.
- `marking/tests/test_v3_workflow_helpers.py`: regression tests for superseded-bundle and artifact trash behavior.

### Added

- Batch marking orchestration (outside `marking/` but depends on this workflow): `utility_scripts/batch_mark_student_work/` grade/validate/persist scripts, `.cursor/skills/batch-mark-student-work/SKILL.md`, `.cursor/agents/mark-student-work-v3-batch-orchestrator.md`; `AGENTS.md` and `mark-student-work-multi-agent-v3` skill document one-orchestrator Task per queue item.

## [0.3.13] - 2026-05-25

Patch: `chinese-v1.5` question-section schema (parenthesised `question_index` aligned with math/science/english).

### Added

- `schemas/chinese_paper2_questions_section.v1.5.schema.json` — `chinese-v1.5` (`Q10(ii)`, `Q20(a)`, …); `chinese-v1.4` unchanged for bare `Q` + digits.
- `marking/file_question_info/api.py`: validator map entry for `chinese-v1.5`; `chinese-v1.5` included in strict `question_info.start_page` layout guards (with math-v1.2 / science-v1.2).
- `marking/tests/test_file_question_info.py`: chinese-v1.5 `question_index` acceptance/rejection tests; corpus parametrize includes `chinese-v1.5`; golden page-map row for `chinese-v1.5`.

### Changed

- `.cursor/agents/chinese-paper-2-question-section-detector.md`: agent **v1.6**; new detections emit `chinese-v1.5` with parenthesised `question_index` rules aligned to math/science/english.

## [0.3.12] - 2026-05-21

Patch: v3 finalize bundle/artifact path alignment and subject-scoped learning-report pairing.

### Fixed

- `marking/workflows/mark_student_work_multi_agent_v3.py`: `finalize_phase_e_artifact` derives the marking-result path and `context.marking_asset` from the actual `bundle_root` (fixes drift when prep resumes an older bundle).
- `marking/core/artifact_lookup.py`: `_build_report_path` supports `marking_results/<student>/<subject_context>/…` layouts.

### Added

- `marking/tests/test_v3_workflow_helpers.py`: regression test for resumed-bundle finalize path binding.
- `marking/tests/test_artifact_lookup.py`: `_build_report_path` test for subject-scope subfolders.
- `marking/README.md`: batch marking runbook pointer (`utility_scripts/batch_mark_student_work/`).

## [0.3.11] - 2026-05-21

Patch: `english-v1.4` question-section schema (parenthesised `question_index` aligned with math/science).

### Added

- `schemas/english_paper2_questions_section.v1.4.schema.json` — `english-v1.4` (`Q20(a)`, `Q51(2020)`, …); `english-v1.3` unchanged for bare `Q` + digits.
- `marking/file_question_info/api.py`: validator map entry for `english-v1.4`.
- `marking/tests/test_file_question_info.py`: english-v1.4 `question_index` acceptance/rejection tests; corpus parametrize includes `english-v1.4`.

### Changed

- `.cursor/agents/english-paper-2-question-section-detector.md`: agent **v1.4**; new detections emit `english-v1.4`.

## [0.3.10] - 2026-05-20

Patch: registry-sourced `attempt_sequence` and group id in marking writer.

### Added

- `marking/workflows/backfill_attempt_sequence_from_registry.py` — dry-run/apply backfill of `context.attempt_sequence` and `context.template_attempt_group_id` from `PdfFileManager` completion series (`pdf_files.added_at` order).

### Changed

- `marking/core/artifact_writer.py`: `_resolve_attempt_sequence` uses `PdfFileManager.next_attempt_sequence_for_completion` (distinct completion `file_id`s; re-mark idempotent). Degraded mode: `attempt_sequence = 1` when completion not in registry but `template_file_id` set.

## [0.3.9] - 2026-05-19

Patch: strengthen `question_sections` `start_page` validation and backfill `attempt_page_start` in v3 finalize.

### Added

- `marking/file_question_info/api.py`: structural `question_info.start_page` invariants (within `questions_page_range`, non-decreasing order; math-v1.2 / science-v1.2 require range start to match earliest question page).
- `marking/tests/test_file_question_info.py`: unit tests for the new start-page checks.
- `marking/tests/test_v3_workflow_helpers.py`: test that `prepare_finalize_rows` backfills `attempt_page_start` from authority.

### Changed

- `marking/workflows/mark_student_work_multi_agent_v3.py`: `prepare_finalize_rows` fills missing `attempt_page_start` from `question_page_map_from_question_sections` before QC.

## [0.3.8] - 2026-05-19

Patch: consolidate completion workflow flags for Review Workspace and Student File Browser.

### Fixed

- `files.completion_enrichment`: lazy-import `completion_workflow_flags` so importing `ai_study_buddy.files` (e.g. via `marking.core.artifact_lookup` → `files.roots`) does not circular-import `marking`.

### Changed

- `marking/review/workflow_flags.py`: `load_completion_marking_context` (single load); `completion_workflow_flags`; `_CompletionWorkflowFlags` is module-private.
- `marking/review/attempt_service.py`: `_attempt_summary` uses `load_completion_marking_context` (no duplicated artifact/review/amendment logic).
- `files.completion_enrichment` calls `completion_workflow_flags` only; public shape remains `RegisteredCompletionEnrichment`.
- `marking/tests/test_workflow_flags.py`: unit tests for shared loader.

## [0.3.7] - 2026-05-12

Patch: relax writer `unit_label` contract to presence-only validation and remove strict path-equivalence gate.

### Changed

- `marking/core/artifact_writer.py`:
  - removed fail-closed check requiring `context.unit_label` to equal normalized `context.unit_file_path` stem.
  - writer now requires `context.unit_label` to be a non-empty string.
- `marking/tests/test_artifact_core.py`:
  - replaced path-equivalence rejection test with drift-allowed write test.
  - added rejection test for blank `unit_label`.
- docs:
  - `marking/README.md` contract note updated: `unit_label` is required non-empty (no strict source-equality check).
  - `marking/SPEC.md` v1.6 context validation updated with required non-empty `unit_label`.

## [0.3.6] - 2026-05-10

Patch: make `subject_context` registry-sourced and strict across resolver/v3 finalization; remove path-token heuristics and add subject-failure debug artifact.

### Added

- `marking/core/subject_scope.py`:
  - shared mapper `subject_context_from_pdf_subject(subject)` for:
    - `english -> singapore_primary_english`
    - `math -> singapore_primary_math`
    - `science -> singapore_primary_science`
    - `chinese -> singapore_primary_chinese`
- `marking/workflows/audit_registry_subjects.py`:
  - one-shot registry audit command for missing/invalid `pdf_files.subject` coverage.

### Changed

- `marking/core/models.py`:
  - `MarkingContext.subject_context` is now required (`str`).
  - `MarkingArtifactContext.from_marking_context(...)` now defaults to `context.subject_context` when explicit override is omitted.
- `marking/core/context_resolver.py`:
  - resolver now computes `subject_context` from registry (`template.subject` first, then `attempt.subject`).
  - resolver now hard-fails when neither subject can be mapped.
- `marking/file_question_info/api.py`:
  - `_subject_scope_from_pdf_file(...)` now delegates to shared core subject mapper (single source of truth).
- `marking/workflows/mark_student_work_multi_agent_v3.py`:
  - removed path/filename subject heuristics from `_resolve_subject_context_from_runtime_context(...)`.
  - v3 finalization now hard-fails if `context.subject_context` is missing/unusable.
  - on this failure path, writes `debug/phasee_subject_context_failure.json` with diagnostic context.

### Tests

- updated resolver/v3 tests for strict subject behavior.
- added resolver test: template subject missing -> fallback to attempt subject.
- added resolver test: missing subjects on both files -> hard fail.
- updated v3 cleanup test to use an in-test trash move stub so it runs in sandboxed environments.

## [0.3.5] - 2026-05-09

Patch: drop unused `bundle_attempt_page_offset` from the question-sections → page-map bridge; stabilize corpus golden tests when multiple `question_sections.json` files share one `schema_version`.

### Changed

- `marking/file_question_info/api.py`:
  - `question_page_map_from_question_sections` no longer accepts `bundle_attempt_page_offset`; `attempt_page_start` is always each row’s `start_page` (template and completion are assumed aligned).
- `marking/docs/proposal/15-file-question-info-consumer-layer-and-marking-orchestration.md`:
  - signature and test checklist wording updated to match.
- `marking/tests/test_file_question_info.py`:
  - `_find_payload_for_schema_version` can narrow by `expected_question_count` and optional `expected_first3_page_map` so `test_question_page_map_golden_by_subject_family` picks a deterministic file among same-version corpora;
  - consumer/map helper assertions updated for the default mapping only.

## [0.3.4] - 2026-05-07

Patch: clarify teacher-annotated ink-color grading policy for v3 marking workers and align one live WA1 artifact with that policy.

### Changed

- `.cursor/agents/marking-phase2-fast-pass-grader-v3.md`:
  - added explicit ink policy for teacher-annotated runs:
    - black/blue writing = original student attempt evidence,
    - green ink = student correction/rework excluded from original-attempt scoring,
    - red ink = teacher-mark authority when clear.
- `.cursor/agents/marking-phase3-deep-dive-v3.md`:
  - added matching ink policy guidance for deep-dive adjudication.
- `.cursor/skills/mark-student-work-multi-agent-v3/SKILL.md`:
  - added prompt reminder so orchestrator Task prompts pass the same ink policy into Phase 2/3 workers.

### Operational follow-up

- Rewrote `P4 Science WA1__20260507_202635.json` through `write_marking_artifact(...)` after applying the ink policy to `Q13(b)`:
  - treated green correction as non-authoritative for original-attempt grading,
  - aligned to red teacher cross on original answer,
  - recomputed score and regenerated report.
- Backfilled `context.question_page_map` for that run from authoritative `question_sections` (`start_page`) and rewrote via package write boundary.

## [0.3.3] - 2026-05-05

Patch: add v3 multi-agent workflow implementation scaffolding (thin orchestrator + deterministic helper layer) and dedicated v3 phase subagent definitions.

### Added

- `marking/workflows/v3_helpers.py`:
  - deterministic v3 helper functions for:
    - phase-3 routing target selection (`select_phase3_question_ids`)
    - language-policy violation detection (`find_language_violations`)
    - human-note policy violation detection (`find_human_note_policy_violations`)
    - authoritative marks extraction from `file_question_info` (`build_authoritative_marks_by_question`)
    - phase-2/phase-3 merge with authority enforcement (`merge_phase2_phase3_rows`)
    - generation telemetry shaping (`build_generation_telemetry`)
- `marking/workflows/mark_student_work_multi_agent_v3.py`:
  - thin orchestration scaffolding for v3:
    - mode resolution (`book-practice`, `embedded-answer`, `teacher-annotated`, `redo-practice`)
    - contradiction hard-stop gate
    - template `question_sections` authority resolution handoff
    - deterministic finalize-prep wiring through helper layer
- new v3 phase subagent definitions:
  - `.cursor/agents/marking-phase2-fast-pass-grader-v3.md`
  - `.cursor/agents/marking-phase3-deep-dive-v3.md`
- tests:
  - `marking/tests/test_v3_workflow_helpers.py`

### Changed

- v3 merge path now enforces `file_question_info`-driven mark authority (no `max_marks` trust from phase subagent payloads).

## [0.3.2] - 2026-05-05

Patch: add `file_question_info` consumer/read tooling and document v3-readiness contracts.

### Added

- `marking/file_question_info/api.py` public consumer/read helpers:
  - `iter_sections_ordered(...)`
  - `iter_questions_ordered(...)`
  - `build_detector_question_id_list(...)`
  - `assert_unique_detector_question_ids(...)`
  - `question_page_map_from_question_sections(...)`
  - `section_hint_strings_for_context(...)`
  - `get_latest_question_sections_for_file_id(...)`
  - `get_latest_question_sections_for_pdf_file(...)`
  - `resolve_question_sections_for_template_file(...)` (reader-only)
- new typed consumer/lookup errors:
  - `QuestionSectionsConsumerError`
  - `QuestionSectionsDuplicateQuestionIdError`
  - `QuestionSectionsNotFoundError`
  - `QuestionSectionsLookupError`

### Changed

- `question_page_map_from_question_sections(...)` emits rows compatible with current `marking_result.v1.6` page-map schema (`result_id`, `attempt_page_start`, `confidence`, `source`, optional `note`).
- duplicate `question_index` handling is hard-fail in consumer/map helpers.
- lookup source behavior is governed by existing READ flags:
  - `LEARNING_DB_ENABLE_READS`
  - `LEARNING_DB_READ_FALLBACK_FILESYSTEM`
- transition divergence guard: when DB+filesystem artifacts exist and differ for same file, readers raise `QuestionSectionsLookupError` when divergence detection is enabled.

### Tests

- expanded `marking/tests/test_file_question_info.py` to cover:
  - iterator normalization and ordering
  - duplicate-ID hard-fail behavior
  - subject-family map goldens
  - compatibility with `marking_result` `question_page_map` validation
  - DB/FS lookup behavior under READ flags
  - invalid stored payload typed-error behavior

### Documentation

- `README.md`:
  - bump current version to `v0.3.2`
  - add consumer/read helper usage snippets and READ-flag behavior notes
- `SPEC.md`:
  - add reader/consumer contract section for `file_question_info`
- `ARCHITECTURE.md`:
  - document reader/consumer layer responsibilities and READ-flag source policy

## [0.3.1] - 2026-05-05

Patch: complete Proposal 14 persistence rollout for `file_question_info`, including DB migration/import/dual-write wiring, schema-version standardization updates, and run-level timestamp enforcement.

### Added

- `ai_study_buddy/learning_db/migrations/002_file_question_info.sql`:
  - adds `file_question_info_runs`, `file_question_info_sections`, `file_question_info_items`
  - expands import-family checks to include `file_question_info` in `import_identity_map` / `import_quarantine`
- `ai_study_buddy/marking/file_question_info/post_write.py`:
  - adds `finalize_question_sections_snapshot(...)` shared post-write helper for detector workflows (validate + dual-write mirror)

### Changed

- `learning_db/ingest/import_context_json.py`:
  - adds `upsert_file_question_info_run(...)`
  - extends scanner/import family support for `context/file_question_info/**/question_sections.json`
  - adds `file_question_info` quarantine routing/error-code mapping
  - enforces required run-level timestamps (`created_at`, `updated_at`) for `file_question_info` imports
- `learning_db/ingest/dual_write.py`:
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
