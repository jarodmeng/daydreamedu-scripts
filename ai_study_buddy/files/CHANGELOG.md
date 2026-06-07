# Changelog

All notable changes to the **`ai_study_buddy.files`** package are documented here. This changelog is scoped to this package only (not the monorepo-wide `pdf_file_manager` history).

---

## [v0.3.13] — Supervised review redo path resolver

### Added

- **`supervised_review_redo.py`:** `SupervisedReviewRedoResolution`, `resolve_supervised_review_pdf_for_attempt(...)` — attempt → template → GoodNotes `Review/` PDF `stat` (no inventory scan; complements v0.3.11 `Review` leaf exclusion).
- **`SPEC.md` §2.6:** cross-link — inventory exclusion vs Review Workspace resolver.
- **Tests:** `files/tests/test_supervised_review_redo.py` (d_root / g_root / book paths; missing template / Review PDF).

### Consumers

- `marking.review.detail_service` (step i availability + step ii lazy render input path).
- `buddy_console` v0.1.16 Review tab ([proposal 3](../buddy_console/docs/proposal/3-review-workspace-supervised-redo-tab.md)).

## [v0.3.12] — Review facet scoped to marked completions

- **`enrich_on_disk_main_pdf`:** set `review_status` to `None` on inventory cards when `has_marking` is false (review applies only after a completion has been marked).
- **`workflow_filter_options`:** build review-status dropdown options and counts from marked completions only (`has_marking is True`); “All” count matches the marked subset so Review “All” aligns with Marking = Marked when that filter is active.
- **Filtering:** `review_status` query values no longer match unmarked cards (they carry `review_status=None` after enrichment).
- **Tests:** `test_on_disk_inventory.py` — marked-only review counts, review filter excludes unmarked, enrich omits review on unmarked.
- **Consumers:** `student_file_browser`, `buddy_console` inventory (restart backend to refresh index).

## [v0.3.11] — GoodNotes `Review` folder exclusion

- **`list_goodnotes_leaf_folders_under_root`** / **`is_goodnotes_excluded_relative_path`:** omit any leaf or relative path with a `Review` segment (case-insensitive), always (same structural class as x-prefix). GoodNotes post-review backup PDFs under `…/Review/` are not indexed for operator inventory or leaf-registry reports.
- Consumers: `student_file_browser`, `buddy_console` inventory (restart to refresh index).

## [v0.3.10] — Multi-select Subject / Grade / Type filters

- **`FilterCriteria`:** `subject`, `grade`, and `doc_type` are tuples (`()` = no restriction); legacy single-string values still normalize in `__post_init__`.
- **`filter_main_pdf_cards`:** OR within each facet dimension; `normalize_facet_values` helper.
- **`filter_dropdown_options`:** contextual facet lists clear each multi-value field with `()` instead of `"all"`.
- Consumers: `student_file_browser` v0.1.10, `buddy_console` v0.1.12.

## [v0.3.9] — Batch marking artifact index for inventory enrichment

- **`build_enriched_inventory`:** builds one `marking.core.artifact_lookup.build_marking_artifact_index` per pass and passes it through `enrich_on_disk_main_pdf` / `enrich_registered_completion` (avoids per-PDF `marking_results` `rglob`).
- Consumer: `buddy_console` v0.1.7 inventory load performance.

## [v0.3.8] — Package `__version__`

- **`__version__`:** single runtime version string on `ai_study_buddy.files` (importable; listed in `__all__`).
- Consumers: `student_file_browser` v0.1.9, `buddy_console` v0.1.4 — inventory health/config `files_version` reads `files.__version__` directly (no duplicated `FILES_VERSION` constant).

## [v0.3.7] — Unified recency sort fallback

- **`sort_main_pdf_cards` (`recent`):** single recency key per card — `completion_date` when set, else `registry_added_at`; newest first across both (interleaved). Unregistered (no recency key) remain last.
- Consumers: `student_file_browser` v0.1.8, `buddy_console` inventory `files_version` **0.3.7**.

## [v0.3.6] — Completion date on inventory cards

- **`OnDiskMainPdfCard`:** nullable `completion_date`, `completion_date_source` from `PdfFileManager.get_completion_date` when registered.
- **`sort_main_pdf_cards` (`recent`):** dated completions first (`completion_date` descending), then registered undated (path ascending), then unregistered tail — no `registry_added_at` proxy ([proposal 17](../../pdf_file_manager/docs/proposals/17-completion-date.md) §5.4).
- Consumers: `student_file_browser` v0.1.7, `buddy_console` inventory `files_version` **0.3.6**.

## [v0.3.5] — Marking score on inventory cards

- **`RegisteredCompletionEnrichment`:** `marking_earned_marks`, `marking_total_marks`, `marking_percentage` from resolved marking summary (via `load_completion_marking_context`).
- **`OnDiskMainPdfCard`:** same three fields when `has_marking` is true.
- Consumer: `student_file_browser` v0.1.6.

## [v0.3.4] — Card sort order for Student File Browser

- **`FilterCriteria.sort`:** `name` | `recent` (default `recent`).
- **`sort_main_pdf_cards`:** server-side ordering after `filter_main_pdf_cards`.
- **`OnDiskMainPdfCard.registry_added_at`:** copied from `PdfFile.added_at` when registered (all registered mains, including templates).
- Consumer: `student_file_browser` v0.1.5.

## [v0.3.3] — Completion series fields on inventory cards

- **`OnDiskMainPdfCard`:** `template_file_id`, `completion_series_id`, `attempt_sequence`, `attempt_count` (from `PdfFileManager.get_completion_series_member` when template-linked).
- Depends on `pdf_file_manager` completion series API ([proposal 15](../../pdf_file_manager/docs/proposals/15-completion-series-derived.md) Phases 1–3).

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
