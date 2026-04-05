# Exam PDF Pipeline

Reusable workflow for scanned exam collections with handwritten circled set numbers.

## Files

- `detect_exam_boundaries.py`
  Broad blue-ink detection plus targeted grayscale/dark-ink passes for missing gaps.
- `metadata_crop_tool/`
  Local browser tool for selecting title/metadata regions on each set's first page.
- `extract_metadata_from_crops.py`
  Cuts the saved regions and OCRs them into a review CSV.
- `build_exam_manifest.py`
  Combines the confirmed set/page mapping with reviewed metadata into a manifest.
- `split_pdf_by_manifest.py`
  Splits the merged PDF into one file per exam set.

## Typical Flow

1. Detect likely first pages with `detect_exam_boundaries.py`.
2. Confirm/fix a mapping CSV with `set_number,pdf_page`.
3. Generate crop-tool assets with `metadata_crop_tool/generate_assets.py`.
4. Review crops in the browser and export the JSON.
5. OCR the selected metadata with `extract_metadata_from_crops.py`.
6. Review/edit the metadata CSV if needed.
7. Build the final manifest with `build_exam_manifest.py`.
8. Split the PDF with `split_pdf_by_manifest.py`.
