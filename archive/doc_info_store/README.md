The goal is to build an information database for the scanned files.

What are the files:
1) They are organized by child -> grade -> subject. For example, Winston's grade-five math files are stored in `Winston Primary School Documents/P5/Math`.
2) Raw scanned file follows the naming convention <grade>.<subject>.<index>.<title>. For example, `p5.math.001.P5 Term 1 Weenkend Worksheet 1.pdf` is grade-five math doc index 1.

The data storage table columns:
1) child
2) grade
3) subject
4) scanned file name
5) num of pages

Where to find the subject folders:
- Base folder (Google Drive): `My Drive/Winston Primary School documents/`
- Organized as: `<grade>/<subject>/`
  - Example (P5): `.../P5/Math`, `.../P5/Chinese`, `.../P5/English`, `.../P5/Science`

Scope / inclusion rules (current):
1) Only include raw scanned files whose basename starts with `p` (case-insensitive), e.g. `p5.math.001....pdf`.
2) Exclude derived variants like `c.p5.math.001....pdf`.
3) Exclude hidden files (basenames starting with `.`), e.g. `.DS_Store`.

Script:
- `collect_doc_info.py`: scan a folder and output a CSV/JSON with the columns above.
- `merge_scanned_pdfs.py`: merge all raw scanned PDFs in a folder into one PDF (ordered by filename index).
  - Output PDF name includes a run id, and the script writes a matching log JSON next to it: `<output_pdf>.log.json`

Freshness / outdated detection:
- Each run also writes a manifest JSON next to the CSV: `<output-csv>.manifest.json`
- The manifest records:
  - run time (`run_started_at_utc`, `run_finished_at_utc`)
  - input folder
  - row count
  - file snapshot (names + mtimes + sizes) so you can detect adds/deletes/changes later.