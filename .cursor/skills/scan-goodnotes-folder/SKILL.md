---
name: scan-goodnotes-folder
description: Register a GoodNotes PDF folder in the AI Study Buddy registry, verify inferred metadata with a dry run, and then link the registered GoodNotes mains to mirrored DaydreamEdu templates. Use when the user wants a GoodNotes folder scanned into the registry or wants the matching DaydreamEdu template links created for that folder.
---

# Scan GoodNotes Folder

Use this workflow for one explicit GoodNotes folder at a time.

Prefer the `pdf_file_manager` utility through its Python API only. Do not query the registry SQLite database directly for normal lookup or mutation work.

## Scope

This skill is for folders like:

```text
.../GoodNotes/<subject>/<student-email>/<grade-or-scope>/Book/<book name>
.../GoodNotes/<subject>/<student-email>/<grade-or-scope>/Exam
.../GoodNotes/<subject>/<student-email>/<grade-or-scope>/Exercise
```

Important scan behavior:

- `scan_for_new_files(...)` scans only direct `*.pdf` children of the supplied folder.
- GoodNotes paths are handled in a preserve-input way; originals stay in place.
- By default (`auto_link_goodnotes=True`, v0.3.20+), scan also attempts GoodNotes→DaydreamEdu template linking for each **new** `c_` / `_c_` main; check `ScanResult.template_link` per file. Failures are non-aborting (scan still completes).

## Workflow

### 1. Confirm or add the scan root

Check whether the exact folder is already configured as a scan root.

- Python: `PdfFileManager().list_scan_roots()`

If missing, add that exact folder as a scan root. When the folder is student-specific, set `student_id`.

- Python: `PdfFileManager().add_scan_root(path, student_id=...)`

Do not assume a parent or sibling root is enough; use the exact leaf folder the user wants scanned.

### 2. Dry-run the exact folder

Run a dry run on the explicit folder first.

- Python: `PdfFileManager().scan_for_new_files(roots=[root], dry_run=True)`

Report:

- how many files would be registered
- the filenames
- the inferred metadata that matters for the user request
- per-file `template_link` preview when `auto_link_goodnotes=True` (would link / missing template / stem mismatch)

For `.../Book/<book name>/...` paths, expect `doc_type='book'`. For student-email paths, expect the student-specific `student_id` and usually `is_template=False`.

### 3. Real scan

If the dry run looks correct, run the real scan on that same explicit root.

- Python: `PdfFileManager().scan_for_new_files(roots=[root], dry_run=False)`

After the scan, summarize:

- how many files were registered
- whether they were `main` files
- inferred `doc_type`, `student_id`, `subject`, `is_template`
- any important `metadata` fields such as `grade_or_scope` and `unit`
- per-file `ScanResult.template_link` (linked / already linked / failure message)

For GoodNotes `c_` / `_c_` files, it is normal for them to register as `main` without creating raw archives.

### 4. Review / supplement template links

Scan with default `auto_link_goodnotes=True` already attempts linking per new main. Review `template_link` on each `ScanResult`.

If some files still need linking (auto-link off, stem mismatch, or unregistered DaydreamEdu template):

- One file: `PdfFileManager().link_goodnotes_template_for_file(main_path, auto_fix_template=True, inherit_metadata=True)`
- Whole folder (including already-registered mains): `PdfFileManager().link_goodnotes_templates_for_root(root, dry_run=False, auto_fix_template=True, inherit_metadata=True)`

For a folder-only pass without re-scanning:

1. Run `link_goodnotes_templates_for_root(root, dry_run=True)` and review outcomes.
2. Run the real linker; if unrelated files in the folder fail, link the matching subset individually.

Useful helper:

- Python: `PdfFileManager().resolve_goodnotes_template_path(main_path)`

To disable auto-link during scan: `scan_for_new_files(..., auto_link_goodnotes=False)`.

## Response Checklist

When finishing, tell the user:

- whether the folder was already a scan root or had to be added
- what the dry run would register
- what the real scan actually registered
- what each `template_link` reported (linked / would link / already linked / missing or unregistered template)
- any files that still do not have a resolvable or registered DaydreamEdu template (including stem mismatches per P1-3)

## Guardrails

- Use the exact folder the user named; do not widen to all scan roots unless explicitly requested.
- Do not run scan and a separate root-level template-link pass in parallel on the same folder.
- Do not treat a failed root-level template-link pass as proof that none of the files can be linked.
- Keep the explanation path-exact. Distinguish “registered at this exact GoodNotes path” from “same-name file exists elsewhere.”
