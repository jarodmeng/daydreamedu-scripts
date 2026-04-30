# DaydreamEdu leaf folder vs PDF registry report

When this command runs, produce a **summary report** comparing **leaf folders** under the local DaydreamEdu sync root to the **pdf_file_manager** registry.

## Rules

- Follow `.cursor/skills/pdf-file-manager/SKILL.md`: use **`PdfFileManager`** from `ai_study_buddy/pdf_file_manager/pdf_file_manager.py` and root resolution from `ai_study_buddy/files/roots.py` (`resolve_daydreamedu_root()`). Do **not** query the SQLite registry with ad hoc SQL for this task.
- Resolve the DaydreamEdu root with `resolve_daydreamedu_root()` (uses `DAYDREAMEDU_ROOT` or `ai_study_buddy/local_daydreamedu_root.txt`). If it returns `None`, say so and stop.

## Definitions

- **Leaf folder:** A directory under the DaydreamEdu root that has **at least one `*.pdf` file directly inside it**, regardless of whether it has subdirectories.
- **Excluded leaf folders:** Treat the root relative path `.` as fully excluded from `leaf_folders_total` and every subsequent count/table in this report if it would otherwise qualify as a leaf folder (direct `*.pdf` on the DaydreamEdu root).
- **Registered:** A PDF's **`Path.resolve()`** string matches a row from `PdfFileManager().find_files()` (build a set of resolved `path` strings).
- **Unregistered in a leaf:** At least one direct `*.pdf` in that folder whose resolved path is not in that set.
- **Scan root:** Compare each leaf folder's resolved path to `PdfFileManager().list_scan_roots()` (resolved paths).

## What to run

Execute a short **Python one-shot** from the repo root with package imports (no `sys.path` mutation): `from ai_study_buddy.pdf_file_manager import PdfFileManager` and `from ai_study_buddy.files.roots import resolve_daydreamedu_root`. Use the default registry path from the utility / `PDF_REGISTRY_PATH` if set.

### Implementation hardening (required)

- Treat `PdfFileManager().find_files()` and `PdfFileManager().list_scan_roots()` rows as **typed objects first** (`row.path`), not dicts.
- Add a defensive path extractor that supports both object and dict shapes, and fails loudly if no path can be read:

```python
from pathlib import Path

def resolved_path_from_row(row) -> str:
    raw_path = getattr(row, "path", None)
    if raw_path is None and isinstance(row, dict):
        raw_path = row.get("path")
    if not raw_path:
        raise ValueError(f"Row has no path attribute/key: {type(row)!r}")
    return str(Path(raw_path).resolve())
```

- Build sets as:
  - `registered_paths = {resolved_path_from_row(f) for f in pfm.find_files()}`
  - `scan_root_paths = {resolved_path_from_row(r) for r in pfm.list_scan_roots()}`
- Add a **sanity check** before counting folders:
  - if `len(pfm.find_files()) > 0` and `len(registered_paths) == 0`, stop and report an extraction bug instead of returning misleading coverage counts.

Collect:

1. Count of registered PDF paths.
2. Count of scan roots.
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

Default output (unless the user explicitly asks for details):

1. One-line **context**: DaydreamEdu root path, registry DB path used.
2. **Summary** with the counts above, including the 4-bucket registration breakdown by scan-root status.
3. **Excluded leaf folders** section (if present): relative path and `unregistered/total`, plus unregistered basenames.
4. **Footnote**: matching is **exact path**; if files moved on disk without updating the registry, old paths may still be "registered" while new locations appear unregistered (mention only if relevant).

Detailed output (only when explicitly requested by the user):

5. **Full table** of all included leaf folders (not only problematic ones): relative path, scan-root flag, `unregistered/total`, unregistered basenames.

Keep the final reply scannable; do not dump thousands of lines unless the data is that large.
