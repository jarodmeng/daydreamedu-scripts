# Changelog

All notable changes to `ai_study_buddy.marking` are documented in this file.

Committed changes under `ai_study_buddy/marking/` should add an entry here and bump **Current version** in `README.md` (semver: **patch** for docs or small renderer tweaks, **minor** for schema or public API changes). `SPEC.md` / `TESTING.md` titles do not carry the package version.

## [0.1.4] - 2026-04-17

### Documentation

- `SPEC.md` / `TESTING.md`: removed semver from titles; version is tracked in `README.md` and this changelog only.

## [0.1.3] - 2026-04-17

Small documentation and report-rendering polish.

### Changed

- `workflows/report_renderer.py`: marking table uses ✅ / ⚠️ / ❌ / 🚫 icons (and legend text updated) instead of `OK` / `PART` / `X` / `DQ`, aligned with the mark-goodnote-completion skill.

### Documentation

- `SPEC.md` and `README.md`: document ephemeral per-run renders, crops, and `_*.py` helpers under `ai_study_buddy/context/.marking_scratch/`; README clarifies they are not kept at the package root.

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

