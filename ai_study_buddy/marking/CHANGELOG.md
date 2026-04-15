# Changelog

All notable changes to `ai_study_buddy.marking` are documented in this file.

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

