# Proposal 15: `file_question_info` consumer tooling for v3 readiness

## Status

Implemented as of 2026-05-05.

Proposal 13 and Proposal 14 are implemented and are prerequisites:

- Proposal 13: `file_question_info` path/render/load/validate foundations.
- Proposal 14: validated `question_sections.json` mirrored into `study_buddy.db`.

## Goal

Build a robust reader/consumer layer for `question_sections.json` so a future v3 orchestrator can consume authoritative question structure without ad hoc JSON traversal.

This proposal intentionally does **not** implement the `mark-student-work-multi-agent-v3` workflow itself.

## Scope boundaries

In scope:

- Reader/consumer APIs in `ai_study_buddy.marking.file_question_info`.
- Deterministic bridge to `context.question_page_map`.
- Template-oriented lookup helpers that v3 orchestration can call.
- Duplicate-ID and structure QC helper APIs.
- Tests and docs for the tooling surface.

Out of scope:

- Editing `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md` for behavior migration.
- Updating `marking-phase*.md` orchestration behavior.
- Designing v3 mode policies end-to-end.
- Any detector writing/OCR logic.

## Design principles for v3-readiness

1. **Template-first structure authority:** tooling should make template-linked `question_sections` retrieval first-class.
2. **Fail-closed defaults:** missing/invalid structure should raise typed errors, not degrade silently.
3. **Immutable normalized views:** consumer helpers return stable row contracts detached from raw payload shape drift.
4. **Deterministic mapping:** same payload produces identical `question_page_map` output.
5. **Explicit ambiguity handling:** duplicate `question_index` values are hard errors.

## Proposed API surface

Add the following public helpers to `ai_study_buddy.marking.file_question_info`.

### A. Payload normalization and iteration

- `iter_sections_ordered(payload: Mapping[str, object]) -> tuple[SectionRow, ...]`
- `iter_questions_ordered(payload: Mapping[str, object]) -> tuple[QuestionRow, ...]`

Behavior contract:

- Require pre-validated payload (`validate_question_sections_dict`).
- Preserve source order.
- Use canonical `answers_page_range` only.
- Do not mutate input payload.

### B. QC and identity helpers

- `build_detector_question_id_list(payload: Mapping[str, object]) -> tuple[str, ...]`
- `assert_unique_detector_question_ids(payload: Mapping[str, object]) -> None`

Behavior contract:

- `build_detector_question_id_list` is raw ordered extraction.
- `assert_unique_detector_question_ids` raises typed error with duplicate IDs listed and stable message format for caller UX.

### C. Page-map bridge

- `question_page_map_from_question_sections(payload: Mapping[str, object], *, source: str = "detector_layout", confidence: str = "high", note: str | None = None) -> dict[str, dict[str, object]]`
- `section_hint_strings_for_context(payload: Mapping[str, object]) -> tuple[str, ...]`

Behavior contract:

- Build deterministic rows keyed by `question_index`.
- Compute `attempt_page_start`/`attempt_page_end` deterministically from ordered rows and section ranges.
- Attach `source`/`confidence`/`note` metadata fields consistently.
- Duplicate `question_index` is hard-fail (no production merge policy).

### D. Template-oriented lookup helpers (new for v3 readiness)

- `get_latest_question_sections_for_file_id(file_id: str, *, conn: sqlite3.Connection | None = None, context_root: Path | None = None, require_valid: bool = True, detect_divergence: bool = True) -> QuestionSectionsSource`
- `get_latest_question_sections_for_pdf_file(pdf_file: PdfFile, *, conn: sqlite3.Connection | None = None, context_root: Path | None = None, require_valid: bool = True, detect_divergence: bool = True) -> QuestionSectionsSource`

`QuestionSectionsSource` should include:

- `payload: dict[str, object]`
- `schema_version: str`
- `source_kind: Literal["db", "filesystem"]`
- `source_locator: str` (for example run_id or absolute json path)
- `template_file_id: str`
- `validated_at_runtime: bool`

Lookup behavior:

- Regulate source-of-truth behavior using existing learning DB READ flags:
  - `LEARNING_DB_ENABLE_READS`
  - `LEARNING_DB_READ_FALLBACK_FILESYSTEM`
- Transitional safety policy: when both DB row and filesystem JSON exist for the same logical artifact, compare them. If they diverge, raise `QuestionSectionsLookupError` (debug-first hard fail).
- If both exist and match, default to DB as returned source while recording provenance.
- Always run runtime `validate_question_sections_dict` when `require_valid=True`.
- Return typed not-found error when no artifact exists.

### E. Orchestrator-facing resolution helper (reader-only)

- `resolve_question_sections_for_template_file(*, template_file: PdfFile, detect_divergence: bool = True) -> QuestionSectionsSource`

Behavior contract:

- Reader-only helper that resolves authoritative template question sections via the lookup APIs in this proposal.
- It does not invoke detectors. Detector fallback orchestration is owned by Proposal 16/v3 workflow logic.

### Typed errors

Add consumer-specific typed errors under `marking.file_question_info.errors`:

- `QuestionSectionsConsumerError` (base)
- `QuestionSectionsDuplicateQuestionIdError`
- `QuestionSectionsNotFoundError`
- `QuestionSectionsLookupError`

## Detailed implementation plan

### Phase A: Core consumer rows and iteration

Objective: stable normalized section/question iteration.

Todo checklist:

- [x] Implement `SectionRow` and `QuestionRow` contracts.
- [x] Implement `iter_sections_ordered` and `iter_questions_ordered`.
- [x] Enforce canonical `answers_page_range` handling.
- [x] Export helpers in `api.py` and package `__init__.py`.

Test checklist:

- [x] Coverage for all supported schema families/versions.
- [x] Ordering and immutability tests.
- [x] Empty-section and mixed-section edge cases.
- [x] Canonical field handling covered (no legacy alias support).

Success criteria:

- deterministic row outputs and zero raw `sections[i]` dependency in consumers.

### Phase B: QC and mapping bridge helpers

Objective: deterministic `question_page_map` generation and duplicate-ID enforcement.

Todo checklist:

- [x] Implement `build_detector_question_id_list`.
- [x] Implement `assert_unique_detector_question_ids`.
- [x] Implement `question_page_map_from_question_sections`.
- [x] Implement `section_hint_strings_for_context`.

Test checklist:

- [x] duplicate-ID failures have stable error shape.
- [x] map output golden tests by subject family.
- [x] page-map bridge tests (`start_page` → `attempt_page_start`).
- [x] compatibility checks with current `question_page_map` consumers.

Success criteria:

- map generation is reproducible and QC errors are actionable.

### Phase C: Template-oriented lookup APIs

Objective: provide v3-ready retrieval APIs for authoritative template question structure.

Todo checklist:

- [x] Implement DB-first lookup by `file_id` (Proposal 14 tables).
- [x] Implement filesystem fallback lookup only when `LEARNING_DB_READ_FALLBACK_FILESYSTEM=1`.
- [x] Implement `QuestionSectionsSource` wrapper contract.
- [x] Implement strict validation behavior with `require_valid=True` default.

Test checklist:

- [x] DB-hit path returns expected payload/source metadata.
- [x] filesystem-fallback path returns expected payload/source metadata.
- [x] no-data path raises `QuestionSectionsNotFoundError`.
- [x] invalid payload path raises validation/lookup typed errors.

Success criteria:

- caller can ask for authoritative question sections by template `file_id` with one API call.

### Phase D: Consolidation and handoff to v3 workflow proposal

Objective: lock tooling interface before orchestration migration.

Todo checklist:

- [x] finalize public exports and docstrings.
- [x] add usage snippets for "template file_id -> validated payload -> map" flow.
- [x] ensure errors are documented for orchestrator consumption.
- [x] add proposal handoff notes to Proposal 16 (v3 workflow).

Test checklist:

- [x] full marking-related test run includes consumer + lookup suites.
- [x] import path smoke tests for all new public helpers.
- [x] docs snippet smoke tests.

Success criteria:

- Proposal 15 delivers a stable tooling layer that Proposal 16 can consume directly.

Implementation notes (completed):

Usage snippet: template `file_id` -> validated payload -> map

```python
from ai_study_buddy.marking.file_question_info import (
    get_latest_question_sections_for_file_id,
    question_page_map_from_question_sections,
)

source = get_latest_question_sections_for_file_id(template_file_id)
payload = source["payload"]
question_page_map = list(question_page_map_from_question_sections(payload).values())
```

Usage snippet: template `PdfFile` -> validated payload -> section hints

```python
from ai_study_buddy.marking.file_question_info import (
    get_latest_question_sections_for_pdf_file,
    section_hint_strings_for_context,
)

source = get_latest_question_sections_for_pdf_file(template_pdf_file)
payload = source["payload"]
section_hints = section_hint_strings_for_context(payload)
```

Orchestrator error contract (reader layer):

- `QuestionSectionsNotFoundError`: no authoritative artifact found for template file under current READ-flag policy.
- `QuestionSectionsValidationError`: payload exists but fails schema/runtime validation.
- `QuestionSectionsDuplicateQuestionIdError`: duplicate `question_index` detected during map/QC helpers.
- `QuestionSectionsLookupError`: lookup/path divergence or DB/FS read failures.
- `QuestionSectionsConsumerError`: normalized-row construction failed (defensive structural guard).

Proposal 16 handoff notes:

- Proposal 16 should call reader-only lookup helpers first (`get_latest_question_sections_for_file_id` / `..._for_pdf_file` / `resolve_question_sections_for_template_file`).
- Detector fallback orchestration remains owned by Proposal 16 (outside Proposal 15 reader layer).
- Section-level Phase 2 and question-level Phase 3 routing should consume:
  - `iter_sections_ordered`
  - `iter_questions_ordered`
  - `question_page_map_from_question_sections`
  - `section_hint_strings_for_context`
- `question_page_map_from_question_sections` output is compatible with current `marking_result` page-map schema (`result_id`, `attempt_page_start`, `confidence`, `source`, optional `note`).

### Phase E: Marking module documentation updates

Objective: ensure `ai_study_buddy/marking` docs accurately reflect the shipped consumer/read APIs and lookup behavior.

Todo checklist:

- [x] update `ai_study_buddy/marking/README.md` with new `file_question_info` consumer/lookup usage.
- [x] update `ai_study_buddy/marking/SPEC.md` with reader contracts and fail-closed behaviors.
- [x] update `ai_study_buddy/marking/ARCHITECTURE.md` with DB-read and filesystem-fallback behavior via READ flags.
- [x] add `CHANGELOG` entry under `ai_study_buddy/marking/CHANGELOG.md` for user-visible API additions/behavior.

Test checklist:

- [x] verify all documentation code snippets/import paths run successfully in a clean shell.
- [x] run a terminology consistency pass (`question_sections`, `question_page_map`, duplicate-ID hard fail, READ flags).
- [x] confirm no docs contradict Proposal 13/14/16 boundaries.

Success criteria:

- `marking/` documentation is internally consistent and matches implemented behavior with no stale guidance.

## Decisions

Decided:

1. Source regulation will follow existing learning DB READ flags:
   - `LEARNING_DB_ENABLE_READS`
   - `LEARNING_DB_READ_FALLBACK_FILESYSTEM`
2. Duplicate `question_index` is hard-fail in consumer/map helpers.
3. During transition, when both DB and JSON exist for the same artifact and differ, raise exception for debugging.
4. `resolve_question_sections_for_template_file(...)` is reader-only in Proposal 15; detector fallback stays in Proposal 16 workflow orchestration.

5. Keep `attempt_page_end` inference fixed and deterministic in Proposal 15 (not strategy-configurable yet).
6. Use `TypedDict` (or Protocol-like mapping contract) for public row outputs to preserve schema-evolution flexibility; internal implementation may still use frozen dataclasses.
7. Keep `section_hint_strings_for_context(...)` for orchestrator/UI prompt narrowing, and include section index prefixes by default (for example `S1: MCQ`, `S2: Open-ended`) to reduce ambiguity.

## References

- [13-file-question-info-marking-python-apis.md](13-file-question-info-marking-python-apis.md)
- [14-persist-file-question-info-in-study-buddy-db.md](14-persist-file-question-info-in-study-buddy-db.md)
- [16-mark-student-work-multi-agent-v3-workflow.md](16-mark-student-work-multi-agent-v3-workflow.md)
