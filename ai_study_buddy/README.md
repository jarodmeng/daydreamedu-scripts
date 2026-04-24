# AI Study Buddy

Top-level package for AI Study Buddy domain modules, workflows, and app surfaces.

Current version: `v0.1.0`

## Documentation

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [CHANGELOG.md](./CHANGELOG.md)
- [DATA_MODEL.md](./DATA_MODEL.md)
- Product and strategy docs: [`docs/`](./docs)

## Primary Submodules

- [`marking/`](./marking): canonical marking artifacts, lookup, validation, and workflows.
- [`student_review/`](./student_review): student review domain services (attempt index, detail shaping, review-state writes).
- [`review_workspace/`](./review_workspace): student-facing app surface (backend adapter + frontend UI).
- [`pdf_file_manager/`](./pdf_file_manager): registry-backed PDF metadata and relationship management.
- [`files/`](./files): registry-agnostic filesystem helpers.
- [`root_pdf_browser/`](./root_pdf_browser): local two-pane DaydreamEdu / GoodNotes PDF viewer over configured roots.
- [`split_book_answer_by_unit_using_ai/`](./split_book_answer_by_unit_using_ai): answer-book segmentation workflows.

## Utilities

- [`utils/`](./utils): cross-cutting CLI and helpers (e.g. `compress_pdf` for scan compression before ingestion).

## Data

- [`db/`](./db): default location for the PDF registry SQLite database (`pdf_registry.db`; typically gitignored).
- [`context/`](./context): runtime context artifacts (e.g. learning reports, marking outputs).
