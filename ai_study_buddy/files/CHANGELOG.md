# Changelog

All notable changes to the **`ai_study_buddy.files`** package are documented here. This changelog is scoped to this package only (not the monorepo-wide `pdf_file_manager` history).

---

## [v0.3.2] — `FilterCriteria.root_id` for Student File Browser

- **`FilterCriteria`:** `root_id` (`all` | `daydreamedu` | `goodnotes`); applied in `filter_main_pdf_cards`.
- **`FilterDropdownOptions`:** `root_ids` / `root_counts` for contextual Root filter meta.
- Consumer: `ai_study_buddy.student_file_browser` v0.1.3.

## [v0.3.1] — Lazy marking import in completion enrichment

- **`completion_enrichment`:** lazy-import `completion_workflow_flags` inside `enrich_registered_completion` to avoid `files` ↔ `marking` circular import when the `files` package is loaded during marking startup.

## [v0.3.0] — On-disk main-PDF inventory and enrichment

- **`path_facets`:** `PathFacets`, `infer_path_facets()` (Phase A: delegates to `PdfFileManager._infer_from_path`; catches `InvalidDocTypeError`).
- **`main_pdfs`:** `is_main_pdf_basename`, `is_inventory_main_pdf`, `list_main_pdfs_in_leaf_folder`, `build_main_pdf_index_for_roots` (explicit `None` skips a root; omit arg to auto-resolve). With `registry_index`, registered paths are mains only when `file_type='main'` (aligned with gap report); unregistered paths still use the non-`_raw_` basename heuristic.
- **`pdf_registry_paths`:** `RegistryPathIndex.file_by_resolved_path`, `registry_file_for_path`, `registry_file_type_for_path`, `has_template_link`.
- **`completion_enrichment`:** `enrich_registered_completion` via `marking.review.workflow_flags.completion_workflow_flags` (`RegisteredCompletionEnrichment` only; no exported marking flag type in `files`).
- **Boundary cleanup:** `attempt_service` shares `load_completion_marking_context` with inventory enrichment; `_CompletionWorkflowFlags` stays private to `marking.review.workflow_flags`.
- **`on_disk_inventory`:** `OnDiskMainPdfCard` (includes `student_id` from registry/path), `FilterCriteria`, `enrich_on_disk_main_pdf`, `filter_main_pdf_cards`, `inventory_meta`, `build_enriched_inventory`; `filter_meta_for_response` / `filter_dropdown_options` / `workflow_filter_options` expose contextual facet lists, per-option file counts (`*_counts`), and workflow filters (shown only when the slice has >1 distinct value).
- Tests: `test_path_facets`, `test_main_pdfs`, `test_on_disk_inventory`.
- Consumer: `ai_study_buddy.student_file_browser` v0.1.0.

## [v0.2.0] — Centralized PDF registry path correlation (`pdf_registry_paths`)

- New module **`pdf_registry_paths`**: **`resolved_path_from_registry_row`**, **`RegistryPathIndex.from_pdf_file_manager`**, **`direct_pdf_paths_in_leaf_folder`**, **`PdfFileRegistryStatus`**, **`is_pdf_registered`**, **`pdf_file_registry_status`**, **`leaf_pdf_file_registry_statuses`**, **`leaf_folder_registry_status`**, **`partition_daydreamedu_leaf_folders`**, **`partition_goodnotes_leaf_folders`**, **`leaf_registry_statuses_for_included_leaves`**, **`registration_buckets`** / **`ScanRootRegistrationBuckets`**, **`suspicious_all_leaves_marked_non_scan_root`** — aligns with DaydreamEdu / GoodNotes leaf-registry Cursor commands (resolved `str` path sets; no ad hoc SQL).
- Re-exported from **`ai_study_buddy.files`**. README / SPEC updated; tests in **`tests/test_pdf_registry_paths.py`**.

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
