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

1. establish the printed-page offset (§1), using a small render or user input as needed
2. render a small page range to PNG images with `pdftoppm`
3. inspect those PNGs directly as images
4. read the `Contents`, divider pages, titles, and visible printed page numbers from the rendered images

In other words, prefer human-style visual inspection of rendered page images over trying to turn the whole scan into machine-readable text first.

Do not start by OCRing large page ranges. For scanned books, that is usually slower and less reliable than inspecting a small set of rendered page images. The fastest dependable path is usually:

1. Establish the printed-page-to-PDF-page offset (see §1 — ask the user first when applicable). This often needs only `pdfinfo`, a small render, or a user-provided number you verify.
2. Render a small front range such as pages `1-12`.
3. Find the `Contents` page visually.
4. Read the printed start pages from the contents.
5. Convert printed boundaries into PDF boundaries.
6. Use OCR only on specific difficult pages if the contents or divider text is hard to read.

If `pdftotext` returns blank output or mostly form-feed characters, assume the PDF is image-only and pivot immediately to rendered-page inspection.

## Step-by-Step Tutorial

Use this workflow by default unless the PDF already has high-quality embedded text.

### 1. Build a printed-page to PDF-page mapping

The goal is to find a single, consistent offset

`offset = pdf_page - printed_page`

for the whole book, then reuse it everywhere (including `Extra` replacements).

#### 1a. Ask the user before inferring the offset

In interactive runs, **do not** run `pdftoppm`, OCR, or offset math until you have gone through the questions below **in the conversation with the user**. Describing this section internally is not enough — **you must actually ask** (or clearly restate what you need and wait for a reply when the task requires user input). If the user has already answered in the same thread, reuse those answers. If there is no reply and the task must proceed, infer the offset using §1b/§1c, then report that fallback and confidence in the final response.

**Question A — offset known?** Ask whether they already know the **offset** for this book, using the same definition as everywhere else in this skill:

`offset = pdf_page - printed_page`

(one number for the whole book). Example phrasing: *“Do you already know the printed-page ↔ PDF-page offset for this book (i.e. `pdf_page = printed_page + offset`)? If yes, what is `offset`?”*

**After Question A:**

1. **If they give a number:** treat it as a hypothesis, not gospel. **Verify** it with a few spot checks (e.g. find printed page `1` or match a contents line to a rendered page). If checks agree, use their offset. If not, say what failed and only then fall back to inferring (§1b–§1c) or ask them to double-check.

2. **If they do not know the offset:** ask **Question B** before you infer.

**Question B — where are page numbers?** Ask **where the printed page number usually appears** on each page (e.g. footer vs header, left/center/right, odd/even pages different, or “no printed numbers on divider pages”). Example phrasing: *“Where does the printed page number usually appear in this scan — footer, header, which corner, and does it differ on odd/even pages?”*

**After Question B:**

3. **If they answer:** use that layout hint when rendering small ranges — look in the stated region first when matching printed numbers to PDF pages.

4. **If they skip or decline** (no answer): infer **where** page numbers appear by **visual inspection** of rendered pages (see §2 for rendering; use §1b or §1c for the offset).

#### 1b. Fast, small-offset method: visually locate printed page 1

For many workbooks, the offset is small (e.g. 2–4 pages of front matter). Instead of OCRing, do this:

1. Render just the first few PDF pages to images:

   ```bash
   pdftoppm -f 1 -l 8 -png "book.pdf" /tmp/book-front
   ```

2. Visually scan those PNGs and find the first page whose printed footer/header says `1`.
3. Let `k` be that PDF page index (e.g. `k = 5` if `book-front-005.png` shows printed page `1`).
4. Then the book-wide offset is:

   `offset = k - 1`

5. Use that same offset to map any printed page `p` to its PDF page:

   `pdf_page = p + offset`

This is usually faster and more reliable than trying to OCR page numbers.

#### 1c. TOC-based method (when helpful)

You can also use the contents page together with visible printed page numbers on real content pages:

1. From the TOC, note that a chapter or unit starts on printed page `p`.
2. Render candidate PDF pages and find where that title actually appears.
3. Compute `offset = pdf_page - printed_page` from that match.

Verify the offset from at least two or three spots, not just the first chapter. Once verified, convert all printed starts with:

`pdf_start = printed_start + offset`

### 2. Inspect the file and render only a small front range

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

### 3. Prefer visual TOC detection over bulk OCR

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

- Before inferring the printed-page offset: **ask Question A first in chat** (§1a). If the user does not know, ask Question B; do not skip straight to renders. If the user already answered in-thread, reuse. Verify a user-supplied offset with spot checks.
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

1. Determine the mapping from printed book page to PDF page (follow §1a: ask if the user knows the offset before inferring).
2. Do not assume offset `0`. If the user gave an offset, verify it; if not, infer and verify using contents pages, visible page numbers, or page images (§1b–§1c).
3. When PDF pages are identified, rebuild the whole-book PDF with the replacement pages inserted in place of the original pages.
4. Prefer writing to a temp output first, then replace the merged book only after success.
5. Verify the rebuilt PDF by checking total page count and spot-comparing replacement pages against the `Extra` source PDFs.

## Split Workflow

1. Establish or confirm the printed-page offset (§1), then inspect the front matter and contents pages.
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
- for splits, ensure that the **sum of all split page counts exactly equals** the page count of the original merged PDF (no gaps, no overlaps)
- for `Extra` replacements, verify the inserted pages visually or by rendered-image comparison
- mention the page offset explicitly in the final response (user-provided and verified, or inferred)

## Reuse

If a book has already been analyzed, save or reuse a lightweight per-book boundary manifest if helpful. Generate a draft automatically when possible; do not require the user to hand-author one unless the structure is ambiguous.
