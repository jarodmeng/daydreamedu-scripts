# DaydreamEdu leaf folder vs PDF registry report

When this command runs, produce a **summary report** comparing **leaf folders** under the local DaydreamEdu sync root to the **pdf_file_manager** registry.

## Rules

- Follow `.cursor/skills/pdf-file-manager/SKILL.md`: use **`PdfFileManager`** from `ai_study_buddy/pdf_file_manager/pdf_file_manager.py`.
- Resolve the DaydreamEdu root with **`resolve_daydreamedu_root()`** from `ai_study_buddy/files/roots.py`. If it returns `None`, say so and stop.
- **Included / excluded leaves:** obtain **only** via **`partition_daydreamedu_leaf_folders(root)`** (see §Centralized API). Do **not** call **`list_daydreamedu_leaf_folders_under_root`** or **`list_leaf_folders_under_root`** yourself to build included/excluded sets — **`partition_*`** wraps the correct profile internally.
- Do **not** query the SQLite registry with ad hoc SQL for this task.
- **Registry ↔ disk correlation (mandatory):** use **only** **`ai_study_buddy.files.pdf_registry_paths`** for resolved path sets, included/excluded leaf partitions, per-leaf registration status, and bucket rollups. Do **not** hand-build sets from `find_files()` / `list_scan_roots()`, reimplement **`resolved_path_from_registry_row`**, or duplicate **`partition_*`** / set-difference logic inline.

## Centralized API (required)

Implement this command **exclusively** through **`ai_study_buddy.files.pdf_registry_paths`** (also re-exported from **`ai_study_buddy.files`**):

- **`RegistryPathIndex.from_pdf_file_manager(pfm)`** — sole source for **`registered_resolved_paths`**, **`scan_root_resolved_paths`**, and row counts (`pdf_files_row_count`, `scan_roots_row_count`).
- **`partition_daydreamedu_leaf_folders(root)`** — returns **`(included_leaves, excluded_leaves)`**; do **not** call **`list_daydreamedu_leaf_folders_under_root`** plus manual set difference.
- **`leaf_registry_statuses_for_included_leaves(included_leaves, root, index)`** — per included leaf → **`LeafFolderRegistryStatus`**.
- **`leaf_folder_registry_status(leaf_dir, root, index)`** — use for each **excluded** leaf when reporting excluded-folder stats (item 3 below).
- **`registration_buckets(statuses)`** — **`ScanRootRegistrationBuckets`** for the four-way breakdown.
- **`suspicious_all_leaves_marked_non_scan_root(index, statuses)`** — when `True`, treat scan-root totals as suspect until membership is re-checked (Path/str bug guard).

## Path layout (DaydreamEdu root)

Registered PDFs under `DAYDREAMEDU_ROOT` use a **branch-first** layout:

- **Template (general-scope):** `template/<subject folder>/<grade>/<type>/…/file.pdf`
- **Completion (student-scope):** `completion/<subject folder>/<student email>/<grade>/<type>/…/file.pdf`

The first path segment under the sync root is always `template` or `completion`. Leaf-folder reports and scan roots follow this layout (for example a scan root might be `…/DaydreamEdu/template/Singapore Primary Math/P6/Exam` or `…/DaydreamEdu/completion/…/winston.…/P5/Exam`). When interpreting **relative** paths in tables, they typically start with `template/` or `completion/`.

Legacy paths without a `template/` or `completion/` prefix are obsolete after the D_ROOT migration.

**Empty legacy directories:** After bulk moves, old directory trees may remain as empty shells. Finder also leaves **`.DS_Store`** (and sometimes **`.localized`**) files, so folders are not empty to `rmdir` until those are removed. Filesystem-only cleanup: `python3 -m ai_study_buddy.pdf_file_manager.scripts._prune_empty_dirs_d_root` (dry-run default; `--execute` removes empty dirs bottom-up). Use **`--evict-macos-metadata`** together with `--execute` to delete only `.DS_Store` / `.localized` when they are the sole files in a directory, then remove the directory—repeat once if needed so parents collapse. Does not change the registry.

## Definitions

- **Leaf folder:** A directory under the DaydreamEdu root that has **at least one `*.pdf` file directly inside it**, regardless of whether it has subdirectories.
- **Excluded leaf folders:** Treat the root relative path `.` as fully excluded from `leaf_folders_total` and every subsequent count/table in this report if it would otherwise qualify as a leaf folder (direct `*.pdf` on the DaydreamEdu root).
- **Registered:** A direct PDF's resolved path string is in **`RegistryPathIndex.registered_resolved_paths`** (populated only via **`RegistryPathIndex.from_pdf_file_manager`** — do not rebuild this set manually).
- **Unregistered in a leaf:** At least one direct `*.pdf` in that folder that is not registered per **`LeafFolderRegistryStatus`** / **`pdf_registry_paths`**.
- **Scan root:** The leaf folder's resolved path string is in **`RegistryPathIndex.scan_root_resolved_paths`**. Classification must come from **`leaf_folder_registry_status`** / **`LeafFolderRegistryStatus.is_scan_root`**, not ad hoc comparisons.

## What to run

Execute a short **Python one-shot** from the repo root with package imports (no `sys.path` mutation). **Required imports** (adapt only the import list if the package layout changes—**not** the mandated functions):

```python
from ai_study_buddy.pdf_file_manager import PdfFileManager
from ai_study_buddy.files.roots import resolve_daydreamedu_root
from ai_study_buddy.files.pdf_registry_paths import (
    RegistryPathIndex,
    partition_daydreamedu_leaf_folders,
    leaf_registry_statuses_for_included_leaves,
    leaf_folder_registry_status,
    registration_buckets,
    suspicious_all_leaves_marked_non_scan_root,
)
```

Use the default registry path from the utility / `PDF_REGISTRY_PATH` if set.

### Pipeline (required)

1. `root = resolve_daydreamedu_root()`. If `None`, stop.
2. `included_leaves, excluded_leaves = partition_daydreamedu_leaf_folders(root)` — **only** this pair for included vs excluded; do not recompute via `list_*` + set difference.
3. `pfm = PdfFileManager()` then `index = RegistryPathIndex.from_pdf_file_manager(pfm)` — **only** this object for registry path sets and counts.
4. `statuses = leaf_registry_statuses_for_included_leaves(included_leaves, root, index)` for all included-leaf rows.
5. For **excluded** leaf stats: `leaf_folder_registry_status(p, root, index)` for each `p` in `excluded_leaves`.
6. `buckets = registration_buckets(statuses)` for the four-way registration × scan-root breakdown.
7. If **`suspicious_all_leaves_marked_non_scan_root(index, statuses)`** is true, flag possible Path/str misuse before finalizing scan-root-related counts.

**Path / `Path` rule:** rely on **`LeafFolderRegistryStatus`** and **`RegistryPathIndex`** (resolved **`str`** paths). Do not build parallel `registered_paths` / `scan_root_paths` sets or mix **`pathlib.Path`** membership with **`set[str]`** outside this module.

Collect (derive **only** from **`RegistryPathIndex`** and **`LeafFolderRegistryStatus`** / **`registration_buckets`** — no parallel bookkeeping):

1. Count of registered PDF paths — **`index.pdf_files_row_count`** (and/or **`len(index.registered_resolved_paths)`** if reporting unique resolved paths).
2. Count of scan roots — **`index.scan_roots_row_count`**.
3. **Excluded leaf folders**: list any present excluded leaf folders and their `unregistered/total` direct PDFs.
4. Total leaf folders under DaydreamEdu (after excluding `.` root if applicable), using the direct-PDF definition above.
5. Of those leaf folders, count how many are scan roots vs not scan roots.
6. Registration breakdown by scan-root status (all four buckets):
   - scan-root + all direct PDFs registered
   - scan-root + some direct PDFs unregistered
   - non-scan-root + all direct PDFs registered
   - non-scan-root + some direct PDFs unregistered
7. Full folder table for all leaf folders included in this report (everything except an excluded `.` root if present): relative path, scan-root (`yes`/`no`), `unregistered/total` direct PDFs, and list of unregistered basenames (empty list if none). Keep this data available, but do not print it by default.

## Report format (for the user)

Pass criteria:

- The report **passes** only when **all** included leaf folders are in `scan-root + all direct PDFs registered`.
- Equivalently, pass requires:
  - `scan-root + some direct PDFs unregistered = 0`
  - `non-scan-root + all direct PDFs registered = 0`
  - `non-scan-root + some direct PDFs unregistered = 0`
- If any of the three buckets above is nonzero, report **fails**.

Default output (unless the user explicitly asks for details):

1. One-line **context**: DaydreamEdu root path, registry DB path used.
2. **Summary** with the counts above, including the 4-bucket registration breakdown by scan-root status.
3. **Excluded leaf folders** section (if present): relative path and `unregistered/total`, plus unregistered basenames.
4. **Footnote**: matching is **exact path**; if files moved on disk without updating the registry, old paths may still be "registered" while new locations appear unregistered (mention only if relevant).

Detailed output (only when explicitly requested by the user):

5. **Full table** of all included leaf folders (not only problematic ones): relative path, scan-root flag, `unregistered/total`, unregistered basenames.

Keep the final reply scannable; do not dump thousands of lines unless the data is that large.
