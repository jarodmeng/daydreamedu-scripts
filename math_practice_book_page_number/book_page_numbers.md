# Math Workbook Page Number Analysis

This document shows the book page numbers found in each PDF file. These files are scanned from the "Primary Mathematics 5A/5B Practice Book".

## Page Number Detection Results

| File | PDF Pages | Detected (found/total) | Detected Range (min-max) | Detected Values (unique, in-order; truncated) |
|------|-----------|------------------------|--------------------------|----------------------------------------------|
| p5.math.030.Chapter 1 Numbers to 10 Million.pdf | 4 | 4/4 | 1-4 | 1, 2, 3, 4 |
| p5.math.031.Chapter 2 Four Operations of Whole Numbers.pdf | 26 | 25/26 | 1-30 | 5, 6, 11, 8, 10, 1, 12, 13, 14, 16, 17, 18, 19, 20, 21, 2... |
| p5.math.032.Review 2.pdf | 10 | 10/10 | 32-94 | 85, 86, 87, 83, 89, 90, 91, 32, 93, 94 |
| p5.math.033.Chapter 3 Fraction and Division.pdf | 10 | 10/10 | 43-52 | 43, 44, 45, 46, 47, 49, 50, 51, 52 |
| p5.math.034.Review 3.pdf | 14 | 14/14 | 124-142 | 124, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 14... |
| p5.math.035.Chapter 4 Four Operations of Fractions.pdf | 14 | 14/14 | 35-66 | 53, 54, 35, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66 |
| p5.math.036.Review 4.pdf | 20 | 20/20 | 4-62 | 43, 44, 46, 4, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 59... |
| p5.math.037.Chapter 5 Area of Triangle.pdf | 16 | 15/16 | 10-110 | 95, 96, 98, 99, 100, 10, 102, 103, 104, 106, 107, 108, 10... |
| p5.math.040.Chapter 6 Volume.pdf | 18 | 18/18 | 1-138 | 1, 112, 3, 114, 15, 116, 6, 138, 19, 120, 121, 122, 123, ... |
| p5.math.041.Chapter 7 Decimals.pdf | 26 | 25/26 | 1-26 | 1, 2, 3, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 18, 1... |
| p5.math.042.Chapter 8 Rate.pdf | 16 | 16/16 | 2-42 | 2, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 39, 40, 41, 42 |
| p5.math.043.Chapter 9 Percentage.pdf | 26 | 25/26 | 5-88 | 63, 64, 65, 66, 67, 71, 72, 73, 74, 5, 6, 62, 18, 79, 80,... |

## Notes

- **Page numbers are in the small orange badge (“pill”) in the bottom corners**
  - White text on orange background
  - Alternating positions: odd pages (RIGHT corner), even pages (LEFT corner)
  - Example confirmed: p5.math.030 has pages 1-4 in the orange badges
- **Limitations:**
  - Some pages not detected due to scan quality, faint text, or OCR errors
  - The “Detected Values” column is **unique** values in order of first appearance (to keep the table short)
  - The “Detected Range” is the min/max across detected values (so OCR outliers can skew it)
- For complete accuracy, manual verification recommended

## Current Status / Why Results Aren’t Perfect

These results are **the best we can reliably get at the moment with OCR-only** (no `--infer-missing` / no sequence-based correction).

Even when the orange pill is cropped correctly, OCR can still:
- **miss pages** (no digits recognized)
- **misread digits** (e.g., `61 → 6`, `45 → 43`, `58 → 53`)

So for some PDFs you’ll see:
- **high coverage but occasional wrong values**, and/or
- **correct values mixed with outliers** that skew the min/max range

## How We Could Improve Accuracy Further

- **Use `--infer-missing --fix-outliers`**:
  - This uses the fact that book page numbers should form a consistent sequence within a file.
  - It can fill gaps and correct obvious outliers, and it worked well on `p5.math.036` (43–62).
- **Template matching / custom digit classifier (OCR-free)**:
  - Since the font/style of the page numbers is consistent, we can detect digits by template matching rather than Tesseract.
  - This should reduce systematic OCR confusions like `1↔7`, `3↔5`, `45↔43`.
- **Neural network (learned digit reading for this specific pill)**:
  - **Why**: the orange pill is consistent, but scan noise and binarization artifacts cause systematic OCR mistakes.
  - **Approach** (recommended): keep the current pill detection, replace OCR with help of a small CNN:
    - **Step 1**: export pill crops for every PDF page (we already do this in debug images).
    - **Step 2**: label each crop with the true page number (semi-automate using `--infer-missing`, then spot-check).
    - **Step 3**: train a model to read the digits reliably.
  - **Model options**:
    - **Digit classifier**: segment 1–3 digits, classify each digit (0–9), then combine.
    - **Whole-number classifier**: classify the entire crop as a number (e.g., 1–200). Simple but needs more labeled examples per class.
    - **Sequence model (CRNN)**: predict a short digit string directly; most robust, more work.
  - **Data needs (rough)**:
    - A few hundred labeled crops may already improve accuracy.
    - 1–3k labeled crops should get very strong accuracy across books/scans.
  - **Training tricks**:
    - heavy augmentation (blur, brightness/contrast shifts, JPEG artifacts, small rotations, noise) to match scan variance
    - hold out entire PDFs for validation to ensure the model generalizes
- **Image pre-processing tuned per scan**:
  - de-noise + sharpen + adaptive contrast (CLAHE) targeted to the orange pill
  - more robust digit separation when two digits are close/merged
- **Human-in-the-loop verification**:
  - auto-generate a short “review list” of pages with low confidence or outlier values for quick manual confirmation.

## Detection Method

- Tool: Tesseract OCR
- Approach: detect orange pill in the footer, isolate white digits, and OCR
- DPI: 300
- Flags: **no `--infer-missing`**; `--min-page 1 --max-page 200`
- Date: January 12, 2026

---

*For more accurate page ranges, manual verification recommended for files marked with asterisks*
