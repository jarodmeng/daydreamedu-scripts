# Math Workbook Page Number Analysis

This document shows the book page numbers found in each PDF file. These files are scanned from the "Primary Mathematics 5A/5B Practice Book".

## Page Number Detection Results

| File | PDF Pages | Detected (found/total) | Detected Range (min-max) | Detected Values (unique, in-order; truncated) |
|------|-----------|------------------------|--------------------------|----------------------------------------------|
| p5.math.030.Chapter 1 Numbers to 10 Million.pdf | 4 | 4/4 | 1-4 | 1, 2, 3, 4 |
| p5.math.031.Chapter 2 Four Operations of Whole Numbers.pdf | 26 | 25/26 | 1-30 | 5, 6, 7, 3, 10, 1, 12, 13, 14, 15, 16, 18, 19, 20, 21, 22, 23, 24, ... |
| p5.math.032.Chapter 3 Fraction and Division.pdf | 10 | 10/10 | 43-52 | 43, 44, 45, 46, 47, 48, 49, 50, 51, 52 |
| p5.math.033.Chatper 4 Four Operations of Fractions.pdf | 14 | 14/14 | 34-66 | 53, 54, 55, 56, 57, 58, 34, 60, 61, 62, 63, 64, 65, 66 |
| p5.math.034.Review 2.pdf | 10 | 10/10 | 33-95 | 85, 86, 37, 33, 39, 90, 91, 92, 95, 94 |
| p5.math.035.Chapter 5 Area of Triangle.pdf | 16 | 16/16 | 7-110 | 95, 96, 7, 98, 49, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110 |
| p5.math.036.Chapter 6 Volume.pdf | 18 | 18/18 | 2-128 | 6, 2, 13, 14, 115, 16, 7, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127, 128 |
| p5.math.037.Review 3.pdf | 13 | 13/13 | 129-141 | 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141 |
| p5.math.038.Chapter 7 Decimals.pdf | 26 | 25/26 | 1-26 | 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 18, 19, 20, ... |
| p5.math.039.Chatper 8 Rate.pdf | 16 | 16/16 | 3-42 | 27, 28, 29, 30, 3, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42 |
| p5.math.040.Review 4.pdf | 20 | 20/20 | 34-62 | 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 34, 55, 56, 57, 58, 59, 60, ... |
| p5.math.041.Chapter 9 Percentage.pdf | 26 | 25/26 | 2-88 | 63, 64, 65, 66, 67, 68, 69, 7, 71, 72, 73, 14, 4, 16, 77, 78, 80, 31, ... |

## Notes

- **Page numbers are in the small orange badge (“pill”) in the bottom corners**
  - White text on orange background
  - Alternating positions: odd pages (RIGHT corner), even pages (LEFT corner)
  - Example confirmed: p5.math.030 has pages 1-4 in the orange badges

## Current Restrictions / Assumptions

- **Fixed visual layout**:
  - Assumes the printed book page number is inside the **orange pill** in the footer.
  - If a PDF page doesn’t contain that pill (covers, separators, cropped scans), detection may be **missing**.
- **Color-based pill detection**:
  - The script detects the pill by **HSV “orange” thresholding**.
  - If the scan’s color balance is off (pill too pale/dark), the pill detector can fail or crop the wrong region.
- **OCR is not deterministic**:
  - The script tries multiple Tesseract page-segmentation modes; OCR can still be inconsistent.
  - Even a visually clear ROI can be misread (e.g., `59 → 34`) depending on Tesseract’s segmentation/confidence.
- **Plausibility filter only**:
  - We currently only reject values outside `--min-page`/`--max-page`.
  - We do **not** (by default) enforce that pages form a consistent monotonic sequence.
- **Table interpretation**:
  - **Detected Values** is a list of **unique** detected numbers in order of first appearance (to keep the table short).
  - **Detected Range** is simply **min/max** of detected values; a single outlier can skew it.

## Current Limitations (What You’re Seeing in the Table)

- **Missed detections**: some pages produce no OCR digits (shown by found/total < 100%).
- **Wrong detections**: occasional OCR misreads show up as outliers (e.g., a single “34” inside an otherwise 53–66 run).
- Because of the above, for complete accuracy, **manual verification or sequence-based correction is recommended**.

## Current Status / Why Results Aren’t Perfect

These results are **the best we can reliably get at the moment with OCR-only** (no `--infer-missing` / no sequence-based correction).

Even when the orange pill is cropped correctly, OCR can still:
- **miss pages** (no digits recognized)
- **misread digits** (e.g., `61 → 6`, `45 → 43`, `58 → 53`)

So for some PDFs you’ll see:
- **high coverage but occasional wrong values**, and/or
- **correct values mixed with outliers** that skew the min/max range

## How We Could Improve Accuracy Further

### Quick wins (low effort, big impact)

- **Enable sequence-based correction**: use `--infer-missing --fix-outliers`
  - This uses the fact that within a file, printed page numbers should behave like:
    - \( \text{printed\_page} \approx \text{pdf\_page} + \text{offset} \)
  - It can fill gaps and correct obvious outliers (and would fix cases like `59 → 34`).
- **Add “sequence-aware chooser” (code change)**:
  - Keep multiple OCR candidates per page (from different PSMs) and choose the one that best fits a consistent sequence,
    instead of choosing purely by Tesseract confidence.

### Medium effort (more robust, less OCR pain)

- **Template matching / digit classifier (OCR-free)**:
  - Since the font/style is consistent, detect digits by template matching or a lightweight classifier.
  - This reduces systematic OCR confusions like `1↔7`, `3↔5`, `59↔34`.
- **Pill ROI preprocessing upgrades**:
  - Targeted de-noise + sharpen + adaptive contrast (e.g., CLAHE) on the pill crop
  - More robust digit separation when strokes merge

### High accuracy (highest effort)

- **Neural network trained on your pill crops**:
  - Keep the current pill detection, replace OCR with a small CNN/CRNN.
  - Workflow:
    - Export pill crops for every PDF page (we already write debug images).
    - Label crops (bootstrap with `--infer-missing --fix-outliers`, then spot-check).
    - Train and validate by holding out entire PDFs to ensure generalization.

### Human-in-the-loop (fast verification)

- **Auto “review list”**:
  - Output a small list of pages with low confidence / outliers so you can quickly confirm/correct them.

## Detection Method

- Tool: Tesseract OCR
- Approach: detect orange pill in the footer, isolate white digits, and OCR
- DPI: 300
- Flags: **no `--infer-missing`**; `--min-page 1 --max-page 200`
- Date: January 13, 2026

---

*For more accurate page ranges, manual verification recommended for files marked with asterisks*
