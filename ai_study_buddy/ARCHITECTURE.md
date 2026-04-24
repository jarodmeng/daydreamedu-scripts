# AI Study Buddy Architecture

Status: active baseline.

Version baseline: `v0.1.0`.

## 1) System Shape

`ai_study_buddy` is a modular monorepo package with clear separation between:

1. canonical data engines (`marking`, `pdf_file_manager`)
2. domain orchestration (`student_review`)
3. app surfaces (`review_workspace`)
4. supporting utilities/workflows (`files`, `split_book_answer_by_unit_using_ai`)

## 2) Layering

### Core Data Layer

- `pdf_file_manager`: registry of PDFs, students, groups, and mappings.
- `marking`: canonical marking artifact contracts and lookup logic.

### Domain Layer

- `student_review`: builds student review domain responses from registry + marking artifacts and persists review-state companions.

### App Layer

- `review_workspace`: FastAPI app adapter and React UI for student review workflows.

### Utility/Workflow Layer

- `files`: filesystem discovery helpers.
- `split_book_answer_by_unit_using_ai`: segmentation workflows and scripts.

## 3) Data Boundaries

- Canonical grading facts are stored in `context/marking_results/**` and are treated as read-only by review UIs.
- Student reflection state is stored separately in `context/student_review_states/**`.
- Registry state is stored in `db/pdf_registry.db` (or `PDF_REGISTRY_PATH` override).

## 4) Key Integration Contracts

- App surfaces must consume backend/domain payloads rather than raw artifact files.
- `student_review` should reuse `marking` lookup helpers instead of reimplementing artifact matching.
- Writes from review surfaces must never mutate canonical marking artifacts.

## 5) Current Constraints

- Local/dev-first architecture; production auth/tenant boundaries are not fully implemented at package level.
- Some modules are still in early documentation and testing maturity relative to core flows.

