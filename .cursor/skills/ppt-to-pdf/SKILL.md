---
name: ppt-to-pdf
description: Convert PowerPoint presentation files into PDF files with LibreOffice soffice. Use this when the user wants local batch or single-file PPT/PPTX to PDF conversion while keeping the same basename, especially for folders with spaces or cloud-synced paths like Google Drive.
---

# PPT To PDF

Use this skill for local `.ppt` or `.pptx` to `.pdf` conversion with `soffice`.

## Workflow

1. Check that `soffice` is installed with `command -v soffice`.
2. If the user gave a folder, run the shared utility script against that folder.
3. If the user gave a file, run the shared utility script against that file.
4. Verify the resulting `.pdf` files exist next to the source presentations and keep the same basename.

## Command

Run:

```bash
utility_scripts/convert_ppt_to_pdf.sh "/absolute/path/to/file-or-folder"
utility_scripts/convert_ppt_to_pdf.sh --delete-original "/absolute/path/to/file-or-folder"
```

The script:

- accepts a single `.ppt` or `.pptx` file, or a folder
- writes PDFs beside the source files
- keeps the same name apart from the extension
- safely handles spaces in paths
- can remove the original `.ppt` or `.pptx` after a successful conversion with `--delete-original`
- skips non-PowerPoint files

## Notes

- Prefer this script over hand-writing a `find ... | while ... soffice ...` loop each time.
- For folders outside the workspace sandbox, request escalation before writing output.
- Only use `--delete-original` when the user explicitly wants the source presentations removed after conversion.
- If `soffice` is missing, recommend installing LibreOffice and then rerun the script.
