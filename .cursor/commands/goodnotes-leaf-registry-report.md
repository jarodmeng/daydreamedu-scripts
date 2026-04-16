# GoodNotes leaf folder vs PDF registry report

When this command runs, produce a **summary report** comparing **leaf folders** under the local GoodNotes sync root to the **pdf_file_manager** registry.

## Rules

- Follow `.cursor/skills/pdf-file-manager/SKILL.md`: use **`PdfFileManager`** from `ai_study_buddy/pdf_file_manager/pdf_file_manager.py` and root resolution from `ai_study_buddy/files/roots.py` (`resolve_goodnotes_root()`). Do **not** query the SQLite registry with ad hoc SQL for this task.
- Resolve the GoodNotes root with `resolve_goodnotes_root()` (uses `GOODNOTES_ROOT`, `ai_study_buddy/local_goodnotes_root.txt`, or sibling discovery). If it returns `None`, say so and stop.

## Definitions

- **Leaf folder:** A directory under the GoodNotes root that has **at least one `*.pdf` file directly inside it**, regardless of whether it has subdirectories.
- **Excluded folder subtree:** Any directory whose path contains a segment named exactly `Not completed` (case-insensitive). Exclude these directories and all descendants from traversal and reporting.
- **Excluded leaf folders:** Treat these relative paths as fully excluded from `leaf_folders_total` and every subsequent count/table in this report:
  - `.`
  - `Coding`
- **Registered:** A PDF's **`Path.resolve()`** string matches a row from `PdfFileManager().find_files()` (build a set of resolved `path` strings).
- **Unregistered in a leaf:** At least one direct `*.pdf` in that folder whose resolved path is not in that set.
- **Scan root:** Compare each leaf folder's resolved path to `PdfFileManager().list_scan_roots()` (resolved paths).

## What to run

Execute a short **Python one-shot** from the repo root with package imports (no `sys.path` mutation): `from ai_study_buddy.pdf_file_manager import PdfFileManager` and `from ai_study_buddy.files.roots import resolve_goodnotes_root`. Use the default registry path from the utility / `PDF_REGISTRY_PATH` if set.

Collect:

1. Count of registered PDF paths.
2. Count of scan roots.
3. **Excluded leaf folders**: list any present excluded leaf folders and their `unregistered/total` direct PDFs.
4. Total leaf folders under GoodNotes (after exclusions), using the direct-PDF definition above.
5. Of those leaf folders, count how many are scan roots vs not scan roots.
6. Registration breakdown by scan-root status (all four buckets):
   - scan-root + all direct PDFs registered
   - scan-root + some direct PDFs unregistered
   - non-scan-root + all direct PDFs registered
   - non-scan-root + some direct PDFs unregistered
7. Full folder table for all leaf folders included in this report (which already excludes excluded leaf folders): relative path, scan-root (`yes`/`no`), `unregistered/total` direct PDFs, and list of unregistered basenames (empty list if none).

## Report format (for the user)

1. One-line **context**: GoodNotes root path, registry DB path used.
2. **Summary** with the counts above, including the 4-bucket registration breakdown by scan-root status.
3. **Excluded leaf folders** section (if present): relative path and `unregistered/total`, plus unregistered basenames.
4. **Full table** of all included leaf folders (not only problematic ones): relative path, scan-root flag, `unregistered/total`, unregistered basenames.
5. **Footnote**: matching is **exact path**; if files moved on disk without updating the registry, old paths may still be "registered" while new locations appear unregistered (mention only if relevant).

Keep the final reply scannable; do not dump thousands of lines unless the data is that large.
