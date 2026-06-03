# Specification — `ai_study_buddy.files`

This document is the **contract** for the public Python API of `ai_study_buddy.files`. It is registry-agnostic: no SQLite, no `PdfFileManager`, no scan-root configuration.

**Version:** align with [README.md](./README.md) (package **v0.3.10**; runtime: `ai_study_buddy.files.__version__`).

Core leaf listing and root resolution are **registry-agnostic**. Optional correlation with `pdf_file_manager` / `pdf_registry.db` lives in **`pdf_registry_paths.py`** (see §3).

---

## 1. Root resolution (`roots.py`)

### 1.1 `resolve_daydreamedu_root() -> pathlib.Path | None`

Returns an **existing directory** or `None`.

**Precedence:**

1. Environment variable **`DAYDREAMEDU_ROOT`**: non-empty string → `Path.expanduser().resolve()`; return if `is_dir()`, else `None`.
2. Else read **`ai_study_buddy/local_daydreamedu_root.txt`** (path derived from package layout: parent of `ai_study_buddy/files/` + filename). First non-empty, non-`#` line → same path rules as (1). First winning line wins.
3. Else `None`.

### 1.2 `resolve_goodnotes_root() -> pathlib.Path | None`

Returns an **existing directory** or `None`.

**Precedence:**

1. **`GOODNOTES_ROOT`**: same rules as `DAYDREAMEDU_ROOT`.
2. Else **`ai_study_buddy/local_goodnotes_root.txt`**: same line rules as DaydreamEdu file.
3. Else if `resolve_daydreamedu_root()` returns `D`, let `S = (D.parent / "GoodNotes").resolve()`. If `S.is_dir()`, return `S`.
4. Else `None`.

**Note:** Step 3 uses whatever DaydreamEdu path step (1) or (2) produced; it does not read a separate “sibling file”.

---

## 2. Leaf folders (`leaf_folders.py`)

### 2.1 Definitions

- **Direct file:** a file entry immediately inside a directory (not in a subdirectory).
- **Leaf folder (for listing):** a directory that contains **at least one** direct file whose suffix (case-insensitive) is in `include_suffixes` after normalization (see 2.2).
- **Traversal:** `os.walk` from `root` (recursive). Every directory that qualifies as a leaf folder is collected.

### 2.2 Suffix normalization

Input set `include_suffixes` is normalized:

- Strip whitespace; lowercase.
- If a token does not start with `.`, prepend `.` (e.g. `pdf` → `.pdf`).
- Empty tokens are dropped.
- If, after normalization, the set is empty, `list_leaf_folders_under_root` returns `[]`.

### 2.3 `list_leaf_folders_under_root(root, *, include_suffixes, excluded_leaf_folders=None) -> list[pathlib.Path]`

- **`root`:** expanded and resolved; if not a directory, returns `[]`.
- **`excluded_leaf_folders`:** optional set of **absolute** directory paths. Any resolved leaf folder path contained in this set is omitted from the result.
- **Return value:** sorted list of **resolved absolute** `Path` objects (lexicographic sort on path string).

### 2.4 Profile wrappers

Both default `include_suffixes` to `{".pdf"}` when omitted.

#### `list_goodnotes_leaf_folders_under_root(root, *, include_suffixes=None, exclude_not_completed=True)`

Builds an internal excluded set from **all** leaves (under the same suffix set), then excludes any leaf that:

- equals `root` (resolved), or
- has any path segment matching regex `^x[A-Z].*$` (segment name only), or
- when **`exclude_not_completed`** is `True` (default): has any path segment equal to `Not completed` (case-insensitive). When `False`, those leaves stay **included** (e.g. browse WIP completion PDFs); root and x-prefix exclusions still apply.

Then calls `list_leaf_folders_under_root` with that excluded set.

#### `list_daydreamedu_leaf_folders_under_root(root, *, include_suffixes=None)`

Builds an internal excluded set: any leaf that equals `root` (resolved) — the root-relative `.` leaf when the sync root contains direct PDFs (`daydreamedu-leaf-registry-report` parity). Then calls `list_leaf_folders_under_root`.

### 2.5 `is_goodnotes_excluded_relative_path(rel: str, *, exclude_not_completed=True) -> bool`

- **Input *rel*:** a path string relative to ``GOODNOTES_ROOT``, using `/` segments (may be normalized by the caller). Empty or whitespace-only means the sync root itself → returns `False`.
- **True** if any non-empty path segment matches `^x[A-Z].*$`, or (when *exclude_not_completed* is `True`) any segment equals `Not completed` case-insensitively.
- **Purpose:** single source for GoodNotes “structural” exclusions when walking a tree (for example `root_pdf_browser`), without duplicating regex rules. Aligns with `list_goodnotes_leaf_folders_under_root` when the same *exclude_not_completed* flag is passed.

---

## 3. PDF registry path correlation (`pdf_registry_paths.py`)

**Depends on** ``ai_study_buddy.pdf_file_manager.PdfFileManager`` (no ad hoc SQLite in callers). **Does not** replace `PdfFileManager`; it builds **resolved path string** sets and per-leaf summaries using the same rules as the DaydreamEdu / GoodNotes leaf-registry Cursor commands.

### 3.1 Path strings (membership)

- **Registered paths:** `resolved_path_from_registry_row(row)` for each row from `PdfFileManager.find_files()` → `RegistryPathIndex.registered_resolved_paths` as `frozenset[str]`.
- **Scan roots:** same helper for each row from `PdfFileManager.list_scan_roots()` → `RegistryPathIndex.scan_root_resolved_paths`.
- **Never** mix `pathlib.Path` with `set[str]` membership tests: always `str(path.resolve())` (or the strings above) when checking leaves and direct PDFs.

### 3.2 Leaf folders

- **Direct PDFs in a leaf:** `direct_pdf_paths_in_leaf_folder(leaf_dir)` — direct `*.pdf` only, sorted.
- **One PDF vs registry (atomic):** `is_pdf_registered(pdf_path, index)` and `pdf_file_registry_status(pdf_path, index)` → `PdfFileRegistryStatus` (`is_pdf`, `is_registered`, `parent_is_scan_root`).
- **One leaf direct PDFs (atomic list):** `leaf_pdf_file_registry_statuses(leaf_dir, index)` → `list[PdfFileRegistryStatus]`.
- **One leaf vs registry (rollup):** `leaf_folder_registry_status(leaf, sync_root, index)` → `LeafFolderRegistryStatus` (relative path POSIX to sync root, registered/unregistered counts, unregistered basenames, `is_scan_root`).
- **Included vs excluded leaves (profile parity):**
  - DaydreamEdu: `partition_daydreamedu_leaf_folders(root)` → `(included, excluded)` matching `list_daydreamedu_leaf_folders_under_root` vs raw `list_leaf_folders_under_root(..., {".pdf"})` set difference.
  - GoodNotes: `partition_goodnotes_leaf_folders(root, exclude_not_completed=...)` — same idea; default `exclude_not_completed=True` matches the GoodNotes leaf-registry report.

### 3.3 Rollups

- **Four buckets:** `registration_buckets(list[LeafFolderRegistryStatus])` → `ScanRootRegistrationBuckets` (scan-root × all-registered / some-unregistered × non-scan-root × …).
- **Heuristic:** `suspicious_all_leaves_marked_non_scan_root(index, statuses)` — true when the registry lists scan roots but every included leaf is classified non-scan-root (path/string bug check).

---

## 4. Non-goals

- No PDF classification, compression, or registry mutation (including in `pdf_registry_paths`: read-only correlation only).
- No automatic creation of `local_*_root.txt` files.
- No network or cloud API access.

---

## 5. Import surface

Canonical imports:

```python
from ai_study_buddy.files import (
    resolve_daydreamedu_root,
    resolve_goodnotes_root,
    is_goodnotes_excluded_relative_path,
    list_leaf_folders_under_root,
    list_daydreamedu_leaf_folders_under_root,
    list_goodnotes_leaf_folders_under_root,
)
```

Registry-aware (optional):

```python
from ai_study_buddy.files import (
    RegistryPathIndex,
    resolved_path_from_registry_row,
    partition_daydreamedu_leaf_folders,
    partition_goodnotes_leaf_folders,
    PdfFileRegistryStatus,
    is_pdf_registered,
    pdf_file_registry_status,
    leaf_pdf_file_registry_statuses,
    leaf_folder_registry_status,
    leaf_registry_statuses_for_included_leaves,
    registration_buckets,
    suspicious_all_leaves_marked_non_scan_root,
)
```

Submodules may be imported directly (`ai_study_buddy.files.roots`, `ai_study_buddy.files.leaf_folders`, `ai_study_buddy.files.pdf_registry_paths`) for tests or narrow dependencies.

---

## 6. On-disk inventory (v0.3.0)

### 6.1 `path_facets.infer_path_facets(path, *, root_id) -> PathFacets`

Registry-agnostic. Catches `InvalidDocTypeError`; returns `parse_status="invalid"` with `unknown` facets.

### 6.2 `main_pdfs.build_main_pdf_index_for_roots`

- Omit `daydreamedu_root` / `goodnotes_root` to auto-resolve from env/local config.
- Pass explicit `None` to skip a root.
- **`registry_index`:** when provided, a path is a main PDF if it is registered with `file_type='main'`; unregistered paths use `is_main_pdf_basename` (non-`_raw_` name). Without an index, only the basename rule applies.
- GoodNotes: uses `list_goodnotes_leaf_folders_under_root` with default **`exclude_not_completed=True`** (leaf-registry report universe; used by `student_file_browser`).
- **`exclude_activity_note_completions=True`:** omit completion rows with `doc_type` in `activity`, `note` (`include_in_completion_operator_universe`; templates always kept). Used by `student_file_browser`.

### 6.3 `RegistryPathIndex.file_by_resolved_path`

Map built in `from_pdf_file_manager`. Use `registry_file_for_path` and `has_template_link`.

### 6.4 `completion_enrichment`

- `enrich_registered_completion` calls `marking.review.workflow_flags.load_completion_marking_context` (lazy import).
- Public type: `RegisteredCompletionEnrichment` — workflow flags plus optional `marking_earned_marks`, `marking_total_marks`, `marking_percentage` from resolved summary when marked.

### 6.5 `on_disk_inventory`

- `enrich_on_disk_main_pdf` — sets `student_id` on completion rows via `resolve_card_student_id`; unregistered completions get falsy workflow flags.
- `filter_main_pdf_cards(cards, FilterCriteria, pfm=...)` — `FilterCriteria.student` is registry `students.id` (email accepted for legacy callers); `FilterCriteria.root_id` is `all` | `daydreamedu` | `goodnotes`.
- `sort_main_pdf_cards(cards, sort=...)` — `name` (display name A–Z) or `recent` (unified recency: `completion_date` when set, else `registry_added_at`, newest first across both; unregistered last). `FilterCriteria.sort` defaults to `recent`. See [proposal 17 §5.4](../pdf_file_manager/docs/proposals/17-completion-date.md#54-consumers-when-no-row-exists).
- `OnDiskMainPdfCard.registry_added_at` — `PdfFile.added_at` when registered (shown as **Registered** in UIs).
- `OnDiskMainPdfCard.completion_date` / `completion_date_source` — from `PdfFileManager.get_completion_date` when registered (v0.3.6+; nullable). Shown as **Completed** in UIs; **not** derived from `added_at`.
- `filter_meta_for_response` — merged dict for UI: facet lists + `*_counts`, plus workflow option keys from `workflow_filter_options`.
- `filter_dropdown_options` — `scopes`, `root_ids`, `subjects`, `grades`, `doc_types`, `student_ids`, `book_names` (each omits its own criterion from the slice).
- `workflow_filter_options` — contextual `is_registered_options`, `has_template_options`, `has_marking_options`, `review_status_options` and matching `show_*_filter` flags (true only when >1 distinct value in slice).
- `inventory_meta` — index totals; `show_is_registered_filter` when slice mixes registered/unregistered.
- `should_show_is_registered_filter` — true when ≥1 unregistered main remains after applying criteria **except** `is_registered`.
- `distinct_book_group_names` — sorted book group names for `doc_type=book` after other filters (except `book`).

### 6.6 `OnDiskMainPdfCard` completion date fields (v0.3.6)

Populated in `enrich_on_disk_main_pdf` via `PdfFileManager.get_completion_date(file_id)` for registered rows.

| Field | Type | Meaning |
|-------|------|---------|
| `completion_date` | `str \| None` | `YYYY-MM-DD` SGT calendar day when no row → `null` |
| `completion_date_source` | `str \| None` | `handwritten_page1`, `filename_term`, `goodnotes_last_modified`, `drive_modified`, `manual`, … |

Registry: [`file_completion_dates`](../pdf_file_manager/DATA_MODEL.md#completion-dates-file_completion_dates). Design: [proposal 17](../pdf_file_manager/docs/proposals/17-completion-date.md).

### 6.7 `OnDiskMainPdfCard` completion series fields (v0.3.3)

Populated in `enrich_on_disk_main_pdf` via `PdfFileManager.get_completion_series_member` when the card is a **registered completion** with a template link (`has_template=true`). All are optional / nullable on the card and in `to_dict()` inventory JSON.

| Field | Type | Meaning |
|-------|------|---------|
| `template_file_id` | `str \| None` | Registry id of the linked template |
| `completion_series_id` | `str \| None` | `"<student_slug>::<template_file_id>"` — same formula as marking `template_attempt_group_id` |
| `attempt_sequence` | `int \| None` | 1-based ordinal of this completion within the series |
| `attempt_count` | `int \| None` | Total distinct completion `file_id`s in the series for this student + template |

**Ordering** matches `pdf_file_manager` completion series: `pdf_files.added_at` ascending, then resolved path. **Re-mark** does not change sequence. **No template link** → all four fields remain `null`. See [proposal 15](../pdf_file_manager/docs/proposals/15-completion-series-derived.md) and [L4_COMPLETION_MARKING_FRAMEWORK § Completion series](../docs/L4_COMPLETION_MARKING_FRAMEWORK.md#completion-series-registry-derived).
