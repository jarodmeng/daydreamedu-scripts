# daydreamedu-scripts

Scripts and tooling for DaydreamEdu projects.

## Folder structure

```
daydreamedu-scripts/
├── chinese_chr_app/              # Chinese character learning app + extraction utilities
├── doc_info_store/               # Scanned-document info DB and PDF merge tools
├── math_multiplication/          # Multiplication practice web app (2–12)
├── math_practice_book_page_number/  # Page-number detection for primary math practice books
├── question_splitter/            # Split scanned PDF worksheets into per-question outputs
├── utility_scripts/              # One-off ad hoc scripts (PDF extraction, etc.)
└── README.md
```

## Subfolders

| Folder | Description |
|--------|-------------|
| **chinese_chr_app** | Full-stack web app for learning simplified Chinese characters (primary school). Includes backend/frontend and utilities for extracting character data from PDF card sets (AI, local OCR, PNG generation). |
| **doc_info_store** | Builds an information database for scanned files organized by child → grade → subject. Scripts: `collect_doc_info.py` (scan folder → CSV/JSON), `merge_scanned_pdfs.py` (merge raw PDFs with run log). |
| **math_multiplication** | Web app for lower primary students to practice multiplication of two whole numbers (each 2–12). Flask backend, React frontend; deployable to Cloud Run + Netlify. |
| **math_practice_book_page_number** | Scripts to detect and map page numbers in primary math practice books. Outputs page-number data and related artifacts. |
| **question_splitter** | Pipeline to split scanned PDF worksheets/exams into per-question PDFs and PNGs. Uses OCR to detect question boundaries (e.g. `1.`, `2.`, `19a`) and exports segments plus an index CSV. |
| **utility_scripts** | Small, usually one-off or ad hoc scripts (e.g. PDF extraction, merges, data conversions). Often hardcoded paths; run manually when needed. Example: `extract_epo_practices.py` — extracts practice sections from the English Practice 1000+ merged PDF using the Practice Page Index CSV. |
