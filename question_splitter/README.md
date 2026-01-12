# PDF Question Splitter (scanned worksheets/exams)

This repo contains a reproducible pipeline to split a *scanned* PDF worksheet/exam into per-question outputs.

## What it does
1. Render PDF pages to images (default: 150 DPI)
2. OCR to detect question starts (supports:
   - `1.` / `2.` / `10.` style
   - plain `21` style (for sections that omit the dot)
   - subparts like `19a`, `19b`)
3. Build vertical segments (full-width crops) with padding (default top pad 40px, bottom pad 20px)
4. Export:
   - `pdf/` one PDF per question (multi-page if the question spans pages)
   - `png/` one PNG per segment page (p1, p2, ...)
   - `segments_index.csv` with exact crop rectangles (x0,y0,x1,y1) per segment

## Install
Python 3.9+ recommended.

### System dependency
- **Tesseract OCR** must be installed and available on PATH as `tesseract`.
  - macOS (Homebrew): `brew install tesseract`

### Python deps
```bash
pip install -r requirements.txt
```

## Run
```bash
python -m src.split_questions   --pdf "/path/to/input.pdf"   --out "/path/to/output_dir"   --dpi 150   --top-pad 40   --bottom-pad 20
```

Outputs land in `--out`:
- `pdf/`
- `png/`
- `segments_index.csv`
- `manifest.json` (run settings + detected markers)

### Subparts (e.g., 19a / 19b, 20a / 20b)

By default, subparts are **treated as part of the same question**:
- They are **NOT used as segmentation boundaries** (i.e., `19a` does not start a new clip after `19`).
- `19a` + `19b` → `pdf/Q019_19.pdf` (and corresponding `png/Q019_19_*.png`)

If you want the old behavior (each subpart as its own output), pass:

```bash
python -m src.split_questions --pdf "/path/to/input.pdf" --out "/path/to/output_dir" --split-subparts
```

## Notes / Heuristics
- Horizontal cropping is **full width** on purpose to avoid clipping diagrams/tables.
- **STEM re-assignment**: If a page begins with an instruction block such as
  "Refer to the table below for Questions 13 and 14", the tool will *attach that stem*
  to the referenced question(s) (duplicated) instead of the previous question.

If you want to tweak patterns or thresholds, see `src/split_questions.py`.
