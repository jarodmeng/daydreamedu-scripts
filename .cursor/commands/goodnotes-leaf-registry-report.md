# GoodNotes leaf folder vs PDF registry report

When this command runs, produce a **summary report** comparing **leaf folders** under the local GoodNotes sync root to the **pdf_file_manager** registry.

## Rules

- Follow `.cursor/skills/pdf-file-manager/SKILL.md`: use **`PdfFileManager`** from `ai_study_buddy/pdf_file_manager/pdf_file_manager.py`.
- Resolve the GoodNotes root with **`resolve_goodnotes_root()`** from `ai_study_buddy/files/roots.py` (uses `GOODNOTES_ROOT`, `ai_study_buddy/local_goodnotes_root.txt`, or sibling discovery). If it returns `None`, say so and stop.
- **Included / excluded leaves:** obtain **only** via **`partition_goodnotes_leaf_folders(root)`** (default **`exclude_not_completed=True`**; see §Centralized API). Do **not** call **`list_goodnotes_leaf_folders_under_root`** or **`list_leaf_folders_under_root`** yourself to build included/excluded sets — **`partition_*`** wraps the correct profile internally. Pass **`exclude_not_completed=False`** **only** when the user explicitly wants *Not completed* leaves in the included set.
- Do **not** query the SQLite registry with ad hoc SQL for this task.
- **Registry ↔ disk correlation (mandatory):** use **only** **`ai_study_buddy.files.pdf_registry_paths`** for resolved path sets, included/excluded leaf partitions, per-leaf registration status, and bucket rollups. Do **not** hand-build sets from `find_files()` / `list_scan_roots()`, reimplement **`resolved_path_from_registry_row`**, or duplicate **`partition_*`** / set-difference logic inline.

## Centralized API (required)

Implement this command **exclusively** through **`ai_study_buddy.files.pdf_registry_paths`** (also re-exported from **`ai_study_buddy.files`**):

- **`RegistryPathIndex.from_pdf_file_manager(pfm)`** — sole source for **`registered_resolved_paths`**, **`scan_root_resolved_paths`**, and row counts.
- **`partition_goodnotes_leaf_folders(root)`** — returns **`(included_leaves, excluded_leaves)`**; default **`exclude_not_completed=True`** matches this report. Do **not** call **`list_goodnotes_leaf_folders_under_root`** plus manual set difference. Pass **`exclude_not_completed=False`** **only** when the user explicitly wants *Not completed* leaves included (non-default).
- **`leaf_registry_statuses_for_included_leaves`**, **`leaf_folder_registry_status`** (for excluded-leaf stats), **`registration_buckets`**, **`suspicious_all_leaves_marked_non_scan_root`** — same roles as the DaydreamEdu command.

## Definitions

- **Leaf folder:** A directory under the GoodNotes root that has **at least one `*.pdf` file directly inside it**, regardless of whether it has subdirectories.
- **Excluded folder subtree:** Any directory whose path contains a segment named exactly `Not completed` (case-insensitive). Exclude these directories and all descendants from traversal and reporting.
- **Excluded folder subtree (x-prefix):** Any directory whose path contains a segment matching regex `^x[A-Z].*$` (lowercase `x`, second character uppercase). Exclude these directories and all descendants from traversal and reporting.
- **Excluded leaf folders:** Treat these relative paths as fully excluded from `leaf_folders_total` and every subsequent count/table in this report:
  - `.`
- **Registered:** A direct PDF's resolved path string is in **`RegistryPathIndex.registered_resolved_paths`** (populated only via **`RegistryPathIndex.from_pdf_file_manager`** — do not rebuild this set manually).
- **Unregistered in a leaf:** At least one direct `*.pdf` in that folder that is not registered per **`LeafFolderRegistryStatus`** / **`pdf_registry_paths`**.
- **Scan root:** The leaf folder's resolved path string is in **`RegistryPathIndex.scan_root_resolved_paths`**. Use **`leaf_folder_registry_status`** / **`LeafFolderRegistryStatus.is_scan_root`**; do not hand-compare paths to `list_scan_roots()` rows outside **`pdf_registry_paths`**.

## What to run

Execute a short **Python one-shot** from the repo root with package imports (no `sys.path` mutation). **Required imports:**

```python
from ai_study_buddy.pdf_file_manager import PdfFileManager
from ai_study_buddy.files.roots import resolve_goodnotes_root
from ai_study_buddy.files.pdf_registry_paths import (
    RegistryPathIndex,
    partition_goodnotes_leaf_folders,
    leaf_registry_statuses_for_included_leaves,
    leaf_folder_registry_status,
    registration_buckets,
    suspicious_all_leaves_marked_non_scan_root,
)
```

Use the default registry path from the utility / `PDF_REGISTRY_PATH` if set.

### Pipeline (required)

1. `root = resolve_goodnotes_root()`. If `None`, stop.
2. **`included_leaves, excluded_leaves = partition_goodnotes_leaf_folders(root)`** — default **`exclude_not_completed=True`** (registration-ready leaves only). **Only** this pair for included vs excluded (use **`partition_goodnotes_leaf_folders(root, exclude_not_completed=False)`** **only** when the user explicitly asked to include *Not completed* leaves).
3. `pfm = PdfFileManager()` then **`index = RegistryPathIndex.from_pdf_file_manager(pfm)`**.
4. **`statuses = leaf_registry_statuses_for_included_leaves(included_leaves, root, index)`**.
5. For excluded leaf stats: **`leaf_folder_registry_status(p, root, index)`** for each `p` in **`excluded_leaves`**.
6. **`buckets = registration_buckets(statuses)`**.
7. If **`suspicious_all_leaves_marked_non_scan_root(index, statuses)`** is true, flag possible Path/str misuse before finalizing scan-root-related counts.

**Path / `Path` rule:** rely on **`LeafFolderRegistryStatus`** and **`RegistryPathIndex`** only; do not build parallel path sets outside **`pdf_registry_paths`**.

Collect (derive **only** from **`RegistryPathIndex`** and **`LeafFolderRegistryStatus`** / **`registration_buckets`**):

1. Count of registered PDF paths — **`index.pdf_files_row_count`** (and/or **`len(index.registered_resolved_paths)`** if reporting unique resolved paths).
2. Count of scan roots — **`index.scan_roots_row_count`**.
3. **Excluded leaf folders**: list any present excluded leaf folders and their `unregistered/total` direct PDFs.
4. Total leaf folders under GoodNotes (after exclusions), using the direct-PDF definition above.
5. Of those leaf folders, count how many are scan roots vs not scan roots.
6. Registration breakdown by scan-root status (all four buckets):
   - scan-root + all direct PDFs registered
   - scan-root + some direct PDFs unregistered
   - non-scan-root + all direct PDFs registered
   - non-scan-root + some direct PDFs unregistered
7. Full folder table for all leaf folders included in this report (which already excludes excluded leaf folders): relative path, scan-root (`yes`/`no`), `unregistered/total` direct PDFs, and list of unregistered basenames (empty list if none). Keep this data available, but do not print it by default.

## Report format (for the user)

Default output (unless the user explicitly asks for details):

1. One-line **context**: GoodNotes root path, registry DB path used.
2. **Summary** with the counts above, including the 4-bucket registration breakdown by scan-root status.
3. **Excluded leaf folders** section (if present): relative path and `unregistered/total`, plus unregistered basenames.
4. **Footnote**: matching is **exact path**; if files moved on disk without updating the registry, old paths may still be "registered" while new locations appear unregistered (mention only if relevant).

Detailed output (only when explicitly requested by the user):

5. **Full table** of all included leaf folders (not only problematic ones): relative path, scan-root flag, `unregistered/total`, unregistered basenames.

Keep the final reply scannable; do not dump thousands of lines unless the data is that large.
