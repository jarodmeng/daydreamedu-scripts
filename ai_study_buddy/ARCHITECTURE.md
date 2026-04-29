# AI Study Buddy Architecture

Status: active baseline.

Version baseline: `v0.1.0`.

## 1) System Shape

`ai_study_buddy` is a modular monorepo package with clear separation between:

1. canonical data engines (`marking`, `pdf_file_manager`)
2. app surfaces (`review_workspace`, `root_pdf_browser`)
3. supporting utilities/workflows (`files`, `utils`, `split_book_answer_by_unit_using_ai`)

## 2) Layering

### Core Data Layer

- `pdf_file_manager`: registry of PDFs, students, groups, and mappings.
- `marking`: canonical marking artifact contracts and lookup logic.

### App Layer

- `review_workspace`: FastAPI app adapter and React UI for student review workflows.
- `root_pdf_browser`: local HTTP + static UI to browse DaydreamEdu / GoodNotes PDF roots (dev and ops).

### Utility/Workflow Layer

- `files`: filesystem discovery helpers.
- `utils`: cross-cutting CLIs (e.g. PDF compression before ingestion).
- `split_book_answer_by_unit_using_ai`: segmentation workflows and scripts.

## 3) Data Boundaries

- **`db/`** — registry SQLite at `db/pdf_registry.db` by default, or `PDF_REGISTRY_PATH` override.
- **`context/`** — runtime artifact trees (typically gitignored locally):
  - `context/marking_results/**`: canonical grading JSON; read-only for review UIs.
  - `context/student_review_states/**`: student reflection / progress companions.
  - `context/learning_reports/**`: derived markdown reports alongside marking runs.
  - `context/marking_assets/**`: page renders, crops, and bundles referenced from marking JSON.

## 4) Key Integration Contracts

- App surfaces must consume backend/domain payloads rather than raw artifact files.
- review-domain services in `marking/review` should reuse `marking` lookup helpers instead of reimplementing artifact matching.
- Writes from review surfaces must never mutate canonical marking artifacts.

## 5) Current Constraints

- Local/dev-first architecture; production auth/tenant boundaries are not fully implemented at package level.
- Some modules are still in early documentation and testing maturity relative to core flows.
