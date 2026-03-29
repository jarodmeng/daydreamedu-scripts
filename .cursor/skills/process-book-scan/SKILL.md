---
name: process-book-scan
description: Merge scanned book Part PDFs into whole books, apply Extra page replacements, detect split boundaries from the contents and page images, and export per-section or per-unit PDFs with the book name prefixed. Use this when the user wants scanned study books processed from filenames like "<book> Part <n>.pdf" and "<book> Extra <n> Page <xxx>.pdf".
---

# Process Book Scan

Use this skill for scanned study-book PDFs that follow the `Part` / `Extra` filename pattern.

## Scope

This workflow covers two recurring tasks:

1. Merge `Part` files into one whole-book PDF.
2. Apply `Extra` files as replacements for book pages and then split the whole book into atomic units or sections.

## Tools

Prefer these local tools when available:

- `pdfunite` for merging `Part` PDFs in order
- `qpdf` for rebuilding PDFs from selected page ranges
- `pdfinfo` for total page counts
- `pdftoppm` for rendering pages to images
- `tesseract` for OCR on contents pages or title pages

If image inspection is needed, render contact sheets and inspect the page images instead of guessing from OCR alone.

## Merge Workflow

1. List all PDFs in the target folder.
2. Group `Part` files by shared basename before ` Part <n>.pdf`.
3. Count distinct books from the grouped `Part` files.
4. Merge each book's parts in numeric order into `<book name>.pdf`.
5. Leave source `Part` and `Extra` files untouched unless the user later asks to trash them.

## Extra Replacement Workflow

Use this when files match `"<book name> Extra <n> Page <xxx>.pdf"`.

Rules:

- The `Page <xxx>` number is the first printed book page to replace.
- Each `Extra` PDF replaces 2 consecutive printed book pages.
- Example: `Page 187` replaces book pages `187-188`.

Procedure:

1. Determine the mapping from printed book page to PDF page.
2. Do not assume offset `0`; verify it from the book by contents pages, visible page numbers, or page images.
3. When PDF pages are identified, rebuild the whole-book PDF with the replacement pages inserted in place of the original pages.
4. Prefer writing to a temp output first, then replace the merged book only after success.
5. Verify the rebuilt PDF by checking total page count and spot-comparing replacement pages against the `Extra` source PDFs.

## Split Workflow

1. Inspect the front matter and contents pages first.
2. Detect whether `Preface + TOC` should be split separately or combined.
3. Extract section or unit starts from the contents page.
4. When the TOC groups multiple units together, inspect page images to find each individual unit start.
5. Convert printed book-page boundaries into PDF-page boundaries using the verified offset.
6. Export one PDF per atomic unit or per section, depending on the book structure and user intent.
7. Prefix every split filename with the full book name.

## Boundary Detection Heuristics

- Trust the contents page for section starts when OCR or image inspection is clear.
- When the TOC lists grouped ranges only, inspect rendered page images and look for title pages or worksheet headers.
- If OCR is noisy, use image contact sheets; do not guess from partial OCR output.
- For tails such as `Answers` or `Solutions`, verify the actual transition page visually before splitting.

## Naming Rules

Merged file:

- `<book name>.pdf`

Split folder:

- `<book name> split`

Split files:

- `<book name> - 00 Preface + TOC.pdf`
- `<book name> - 01 ...`

Keep zero-padded numeric prefixes so files sort naturally.

## Verification

After merge or split:

- confirm output files exist
- confirm representative page counts with `pdfinfo`
- for `Extra` replacements, verify the inserted pages visually or by rendered-image comparison
- mention any inferred page offset explicitly in the final response

## Reuse

If a book has already been analyzed, save or reuse a lightweight per-book boundary manifest if helpful. Generate a draft automatically when possible; do not require the user to hand-author one unless the structure is ambiguous.
