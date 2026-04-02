# DaydreamEdu leaf folder vs PDF registry report

When this command runs, produce a **summary report** comparing **leaf folders** under the local DaydreamEdu sync root to the **pdf_file_manager** registry.

## Rules

- Follow `.cursor/skills/pdf-file-manager/SKILL.md`: use **`PdfFileManager`** from `ai_study_buddy/utils/pdf_file_manager/pdf_file_manager.py` (and `resolve_daydreamedu_root()`). Do **not** query the SQLite registry with ad hoc SQL for this task.
- Resolve the DaydreamEdu root with `resolve_daydreamedu_root()` (uses `DAYDREAMEDU_ROOT` or `ai_study_buddy/utils/pdf_file_manager/local_daydreamedu_root.txt`). If it returns `None`, say so and stop.

## Definitions

- **Leaf folder:** A directory under the DaydreamEdu root that has **no subdirectories** (when walking the tree, omit hidden dirs whose names start with `.`).
- **Registered:** A PDF’s **`Path.resolve()`** string matches a row from `PdfFileManager().find_files()` (build a set of resolved `path` strings).
- **Unregistered in a leaf:** At least one `*.pdf` file **directly in** that leaf folder whose resolved path is not in that set.
- **Scan root:** Compare each problematic leaf’s resolved path to `PdfFileManager().list_scan_roots()` (resolved paths); report whether it is already a configured scan root.

## What to run

Execute a short **Python one-shot** from the repo root: prepend `ai_study_buddy/utils/pdf_file_manager` to `sys.path` (same as `scripts/validate_pdf_registry_integrity.py`), then `from pdf_file_manager import PdfFileManager, resolve_daydreamedu_root`. Use the default registry path from the utility / `PDF_REGISTRY_PATH` if set.

Collect:

1. Count of registered PDF paths.
2. Count of scan roots.
3. Total leaf folders under DaydreamEdu.
4. Leaf folders with no PDFs (count only).
5. Leaf folders with at least one PDF where **all** are registered (count).
6. Leaf folders with **≥1 unregistered** PDF: for each, relative path from DaydreamEdu root, `unregistered/total` PDFs in that folder, whether it is a scan root (`yes`/`no`), and **list every unregistered basename**.

Optional extra (one line in the summary): count of **leaf folders that are scan roots** (should match number of scan roots if every root is a leaf in this tree).

## Report format (for the user)

1. One-line **context**: DaydreamEdu root path, registry DB path used.
2. **Summary** with the counts above.
3. **Detail section**: only if there are leaves with unregistered PDFs — grouped list or table with relative paths, scan-root flag, counts, and filenames.
4. **Footnote**: matching is **exact path**; if the user moved files on disk without updating the registry, old paths may still be “registered” while new locations appear unregistered (mention only if relevant).

Keep the final reply scannable; do not dump thousands of lines unless the data is that large.
