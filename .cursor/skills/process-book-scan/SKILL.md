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

## Recommended Mindset

Treat scanned-book boundary detection as a visual layout task first and an OCR task second.

The primary way to "read" the first pages of a scanned book is:

1. render a small page range to PNG images with `pdftoppm`
2. inspect those PNGs directly as images
3. read the `Contents`, divider pages, titles, and visible printed page numbers from the rendered images

In other words, prefer human-style visual inspection of rendered page images over trying to turn the whole scan into machine-readable text first.

Do not start by OCRing large page ranges. For scanned books, that is usually slower and less reliable than inspecting a small set of rendered page images. The fastest dependable path is usually:

1. Render a small front range such as pages `1-12`.
2. Find the `Contents` page visually.
3. Read the printed start pages from the contents.
4. Verify the printed-page-to-PDF-page offset with a few spot checks.
5. Convert printed boundaries into PDF boundaries.
6. Use OCR only on specific difficult pages if the contents or divider text is hard to read.

If `pdftotext` returns blank output or mostly form-feed characters, assume the PDF is image-only and pivot immediately to rendered-page inspection.

## Step-by-Step Tutorial

Use this workflow by default unless the PDF already has high-quality embedded text.

### 1. Inspect the file and render only a small front range

Start with the total page count and a small render window. Do not render the whole book yet.

```bash
pdfinfo "book.pdf"
pdftoppm -f 1 -l 12 -png "book.pdf" /tmp/book-scan
```

Look through those rendered pages for:

- `Preface`
- `Contents`
- section divider pages such as `Section A`
- chapter or unit start pages
- visible printed page numbers on the page footer or header

### 2. Prefer visual TOC detection over bulk OCR

The contents page often gives most or all unit starts immediately. Read it from the rendered page image first.

When the page is legible to the eye but OCR is noisy, continue reading the rendered image directly instead of forcing more OCR. The rendered PNG is the source of truth unless there is a specific reason to extract text.

Do not bulk-OCR the first 20, 50, or 200 pages just because the book is scanned. That usually wastes time and still leaves ambiguity.

Only OCR a specific page when:

- the contents text is hard to read visually
- the scan is faint
- a title page is visually unclear

Example targeted OCR:

```bash
tesseract /tmp/book-scan-004.png stdout --psm 6
```

### 3. Build a printed-page to PDF-page mapping

Use the contents page together with visible printed page numbers on real content pages to compute the offset:

`offset = pdf_page - printed_page`

Verify the offset from at least two or three spots, not just the first chapter.

Example:

- TOC says `Chapter 2` starts on printed page `19`
- PDF page `23` shows the `Chapter 2` title page
- therefore offset is `23 - 19 = 4`

Once verified, convert starts with:

`pdf_start = printed_start + offset`

### 4. Verify with deeper spot checks

Do not trust a single early match. Render a few deeper candidate start pages from different parts of the book and confirm they really are the expected unit starts.

Example:

```bash
pdftoppm -f 23 -l 23 -png "book.pdf" /tmp/check-ch2
pdftoppm -f 44 -l 44 -png "book.pdf" /tmp/check-ch3
pdftoppm -f 145 -l 145 -png "book.pdf" /tmp/check-section-b
```

This is usually faster and more accurate than OCRing large ranges.

### 5. Handle divider pages intentionally

Books often include section title pages such as `Section A` immediately before the first chapter content page.

Do not assume those divider pages must be split separately. If the printed page numbering and user intent suggest it, group a section divider page with the following chapter or unit.

State that grouping decision explicitly in the final response or manifest.

### 6. Fall back to OCR only when visual reading is insufficient

OCR is a fallback for specific pages, not the default engine for the whole task.

Good OCR use:

- one contents page
- one blurry chapter title page
- one ambiguous transition page near `Answers` or `Solutions`

Poor OCR use:

- OCRing the first 100 pages before checking whether the TOC is visually readable
- relying on noisy OCR alone to infer unit boundaries

## Fast Decision Rules

- If `pdftotext` is blank: stop text extraction and switch to images.
- If the TOC is readable visually: use it directly.
- If the TOC groups multiple units: inspect actual divider/title pages for each grouped unit.
- If OCR is noisy: inspect page images rather than guessing from partial text.
- If a boundary matters, verify it with a rendered page image.
- Prefer a few high-confidence spot checks over many low-confidence OCR guesses.

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
