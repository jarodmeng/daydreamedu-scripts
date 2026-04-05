## Metadata Crop Tool

Generic local crop tool for selecting metadata/title regions from each set's first page.

Typical workflow:

1. Prepare a mapping CSV with `set_number,pdf_page`.
2. Generate page assets:

```bash
python3 utility_scripts/exam_pdf_pipeline/metadata_crop_tool/generate_assets.py \
  --pdf "/path/to/Exam Sets.pdf" \
  --mapping-csv "/path/to/mapping.csv"
```

3. Serve the repo locally:

```bash
cd /Users/jarodm/github/jarodmeng/daydreamedu-scripts
python3 -m http.server 8765
```

4. Open:

```text
http://localhost:8765/utility_scripts/exam_pdf_pipeline/metadata_crop_tool/
```

5. Export the crop JSON and process it with `utility_scripts/exam_pdf_pipeline/extract_metadata_from_crops.py`.
