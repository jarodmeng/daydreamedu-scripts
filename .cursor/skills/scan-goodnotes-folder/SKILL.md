---
name: scan-goodnotes-folder
description: Register a GoodNotes PDF folder in the AI Study Buddy registry, verify inferred metadata with a dry run, and then link the registered GoodNotes mains to mirrored DaydreamEdu templates. Use when the user wants a GoodNotes folder scanned into the registry or wants the matching DaydreamEdu template links created for that folder.
---

# Scan GoodNotes Folder

Use this workflow for one explicit GoodNotes folder at a time.

Prefer the `pdf_file_manager` utility through its Python API or the MCP `pdf_*` tools. Do not query the registry SQLite database directly for normal lookup or mutation work.

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
- Scan/register must happen before GoodNotes template-linking.

## Workflow

### 1. Confirm or add the scan root

Check whether the exact folder is already configured as a scan root.

- Python: `PdfFileManager().list_scan_roots()`
- MCP: `pdf_list_scan_roots`

If missing, add that exact folder as a scan root. When the folder is student-specific, set `student_id`.

- Python: `PdfFileManager().add_scan_root(path, student_id=...)`
- MCP: `pdf_add_scan_root`

Do not assume a parent or sibling root is enough; use the exact leaf folder the user wants scanned.

### 2. Dry-run the exact folder

Run a dry run on the explicit folder first.

- Python: `PdfFileManager().scan_for_new_files(roots=[root], dry_run=True)`
- MCP: `pdf_scan_for_new_files`

Report:

- how many files would be registered
- the filenames
- the inferred metadata that matters for the user request

For `.../Book/<book name>/...` paths, expect `doc_type='book'`. For student-email paths, expect the student-specific `student_id` and usually `is_template=False`.

### 3. Real scan

If the dry run looks correct, run the real scan on that same explicit root.

- Python: `PdfFileManager().scan_for_new_files(roots=[root], dry_run=False)`
- MCP: `pdf_scan_for_new_files`

After the scan, summarize:

- how many files were registered
- whether they were `main` files
- inferred `doc_type`, `student_id`, `subject`, `is_template`
- any important `metadata` fields such as `grade_or_scope` and `unit`

For GoodNotes `c_` / `_c_` files, it is normal for them to register as `main` without creating raw archives.

### 4. Link mirrored DaydreamEdu templates

After registration, link the GoodNotes mains to their mirrored DaydreamEdu templates.

- One file: `PdfFileManager().link_goodnotes_template_for_file(main_path, auto_fix_template=True, inherit_metadata=True)`
- One folder: `PdfFileManager().link_goodnotes_templates_for_root(root, dry_run=False, auto_fix_template=True, inherit_metadata=True)`
- MCP fallbacks: `pdf_link_goodnotes_template_for_file`, `pdf_link_goodnotes_templates_for_root`

Preferred order:

1. First run the root-level linker in dry-run mode (`dry_run=True`) and review which files would link vs fail.
2. If the dry run looks good for all intended files, run the real root-level linker for the folder.
3. If the real root-level run fails because some unrelated files in that folder have no matching DaydreamEdu template, do not stop there.
4. Resolve which files are failing.
5. Link the matching subset individually so the newly scanned files still get connected.

Useful helper:

- Python: `PdfFileManager().resolve_goodnotes_template_path(main_path)`
- MCP: `pdf_resolve_goodnotes_template`

## Response Checklist

When finishing, tell the user:

- whether the folder was already a scan root or had to be added
- what the dry run would register
- what the real scan actually registered
- what the template-link dry run predicted (for example: would link / already linked / missing template)
- whether template links were created
- any files in the folder that still do not have a resolvable DaydreamEdu template

## Guardrails

- Use the exact folder the user named; do not widen to all scan roots unless explicitly requested.
- Do not run scan and template-linking in parallel.
- Do not treat a failed root-level template-link pass as proof that none of the files can be linked.
- Keep the explanation path-exact. Distinguish “registered at this exact GoodNotes path” from “same-name file exists elsewhere.”
