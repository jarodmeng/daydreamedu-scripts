# Changelog

All notable changes to the **`ai_study_buddy.files`** package are documented here. This changelog is scoped to this package only (not the monorepo-wide `pdf_file_manager` history).

---

## [v0.1.3] — `is_goodnotes_excluded_relative_path` for tree browsers

- Added **`is_goodnotes_excluded_relative_path(rel, *, exclude_not_completed=True)`** — single gate for GoodNotes x-prefix and optional *Not completed* segment rules (same flags as `list_goodnotes_leaf_folders_under_root`). Used by `root_pdf_browser` with `exclude_not_completed=False`.
- Re-exported from **`ai_study_buddy.files`**.

## [v0.1.2] — GoodNotes `Not completed` exclusion is optional

- **`list_goodnotes_leaf_folders_under_root`:** added keyword **`exclude_not_completed`** (default **`True`**) so leaf-registry/coverage flows keep omitting WIP `Not completed` subtrees, while callers such as `root_pdf_browser` can pass **`False`** to list those leaves for viewing.
- Root-as-leaf and **`^x[A-Z].*$`** segment exclusions are unchanged.

## [v0.1.1] — Leaf profile parity with L4 framework + registry-report commands

- **GoodNotes (`list_goodnotes_leaf_folders_under_root`):** dropped the obsolete top-level-only `Coding` segment rule. Exclusions now match `goodnotes-leaf-registry-report` / [`L4_FILE_FRAMEWORK.md`](../docs/L4_FILE_FRAMEWORK.md): root-as-leaf (`.`); any relative path segment `Not completed` (case-insensitive); any segment whose full name matches `^x[A-Z].*$` (lowercase `x`, uppercase second letter).
- **DaydreamEdu (`list_daydreamedu_leaf_folders_under_root`):** exclusions now match `daydreamedu-leaf-registry-report` — only the root-as-leaf (`.`); **`Note` / `Notes` final-segment exclusions removed.**
- Tests: fixture `goodnotes_profile_tree` gains `Math/xArchived/` for x-prefix coverage; adds `test_goodnotes_x_prefix_requires_uppercase_second_letter`.

## [v0.1.0] — Documentation suite and package baseline

- Added package-local documentation: `README.md`, `SPEC.md`, `TESTING.md`, and this `CHANGELOG.md`.
- Documented current public API:
  - `resolve_daydreamedu_root()`, `resolve_goodnotes_root()` in `roots.py`
  - `list_leaf_folders_under_root()`, `list_daydreamedu_leaf_folders_under_root()`, `list_goodnotes_leaf_folders_under_root()` in `leaf_folders.py`
- Documented local root config file locations under `ai_study_buddy/` and resolution precedence (env → file → GoodNotes sibling discovery).
- Cross-linked design proposal [L4_FILE_SYSTEM_MANAGEMENT.md](../docs/L4_FILE_SYSTEM_MANAGEMENT.md).
