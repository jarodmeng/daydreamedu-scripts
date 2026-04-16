# Changelog

All notable changes to the **`ai_study_buddy.files`** package are documented here. This changelog is scoped to this package only (not the monorepo-wide `pdf_file_manager` history).

---

## [v0.1.0] — Documentation suite and package baseline

- Added package-local documentation: `README.md`, `SPEC.md`, `TESTING.md`, and this `CHANGELOG.md`.
- Documented current public API:
  - `resolve_daydreamedu_root()`, `resolve_goodnotes_root()` in `roots.py`
  - `list_leaf_folders_under_root()`, `list_daydreamedu_leaf_folders_under_root()`, `list_goodnotes_leaf_folders_under_root()` in `leaf_folders.py`
- Documented local root config file locations under `ai_study_buddy/` and resolution precedence (env → file → GoodNotes sibling discovery).
- Cross-linked design proposal [L4_FILE_SYSTEM_MANAGEMENT.md](../docs/L4_FILE_SYSTEM_MANAGEMENT.md).
