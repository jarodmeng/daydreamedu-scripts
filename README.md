# daydreamedu-scripts

Scripts and tooling for DaydreamEdu projects.

## Folder structure

```
daydreamedu-scripts/
├── ai_study_buddy/               # AI Study Buddy package: PDF registry, marking, review app, docs
├── archive/                      # Archived one-off tooling (not wired into apps or CI)
│   ├── doc_info_store/
│   ├── math_practice_book_page_number/
│   └── question_splitter/
├── chinese_chr_app/              # Chinese character learning app + extraction utilities
├── coding_classes/               # Small Node tooling for coding-class materials
├── math_multiplication/          # Multiplication practice web app (2–12)
├── utility_scripts/              # One-off ad hoc scripts (PDF extraction, etc.)
└── README.md
```

## Subfolders

| Folder | Description |
|--------|-------------|
| **ai_study_buddy** | Modular AI Study Buddy package for local study-material ingestion, PDF registry workflows, marking artifacts, student review workflows, and product/architecture docs. See `ai_study_buddy/README.md` for details. |
| **chinese_chr_app** | Full-stack web app for learning simplified Chinese characters (primary school). Includes backend/frontend and utilities for extracting character data from PDF card sets (AI, local OCR, PNG generation). |
| **coding_classes** | Node scripts and assets for coding-class supporting files (see `coding_classes/package.json`). |
| **math_multiplication** | Web app for lower primary students to practice multiplication of two whole numbers (each 2–12). Flask backend, React frontend; deployable to Cloud Run + Netlify. |
| **utility_scripts** | Small, usually one-off or ad hoc scripts (e.g. PDF extraction, merges, data conversions). Often hardcoded paths; run manually when needed. Example: `extract_epo_practices.py` — extracts practice sections from the English Practice 1000+ merged PDF using the Practice Page Index CSV. |

### Archived (`archive/`)

| Path | Description |
|------|-------------|
| **archive/doc_info_store** | Builds an information database for scanned files organized by child → grade → subject. Scripts: `collect_doc_info.py` (scan folder → CSV/JSON), `merge_scanned_pdfs.py` (merge raw PDFs with run log). |
| **archive/math_practice_book_page_number** | Scripts to detect and map page numbers in primary math practice books. Outputs page-number data and related artifacts. |
| **archive/question_splitter** | Pipeline to split scanned PDF worksheets/exams into per-question PDFs and PNGs. Uses OCR to detect question boundaries (e.g. `1.`, `2.`, `19a`) and exports segments plus an index CSV. |
