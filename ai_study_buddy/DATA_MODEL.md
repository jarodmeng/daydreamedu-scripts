# AI Study Buddy Data Model (High-Level)

Version baseline: `v0.1.0`.

## 1) Data directories

- **`ai_study_buddy/db/`** — default home for the PDF registry SQLite file (`pdf_registry.db`); override via `PDF_REGISTRY_PATH`.
- **`ai_study_buddy/context/`** — parent for runtime JSON, markdown, and asset trees used by marking and review flows (see §2).

## 2) Canonical Stores

1. PDF registry (SQLite)
- default path: `ai_study_buddy/db/pdf_registry.db`
- owned by: `pdf_file_manager`
- stores: students, files, groups, mappings, metadata

2. Canonical marking artifacts (JSON)
- path: `ai_study_buddy/context/marking_results/**`
- owned by: `marking`
- schema family: `marking_result.v1.x`
- contract: read-only for review UIs

3. Student review-state artifacts (JSON)
- path: `ai_study_buddy/context/student_review_states/**`
- owned by: `student_review`
- schema id: `student_review_state.v1`
- contract: companion notes/status; separate from canonical marking

4. Learning reports (Markdown)
- path: `ai_study_buddy/context/learning_reports/**`
- owned by: marking / reporting workflows (derived from canonical marking runs)
- contract: human-readable sibling output; not a source of grading truth

5. Marking asset bundles (files on disk)
- path: `ai_study_buddy/context/marking_assets/**`
- owned by: `marking` (paths referenced from marking JSON)
- contract: renders, crops, and bundles linked via `context.marking_asset` (relative under `marking_assets/`)

## 3) Primary Domain Objects

- Student
- Attempt (completion file)
- Marking Result (canonical grading facts)
- Student Review State (reflection/progress state)

## 4) Cross-Module Ownership

- `pdf_file_manager`: registry CRUD and grouping/mapping metadata
- `marking`: grading artifact creation, migration, validation, lookup; marking asset path conventions
- `student_review`: attempt list/detail shaping + review-state read/write
- `review_workspace`: UI and backend adapter consuming domain payloads
- `root_pdf_browser`: reads configured filesystem roots only; does not own any canonical store above
- `utils`: standalone maintenance/ingestion CLIs; no canonical store ownership

## 5) Invariants

- Canonical marking and student review-state are separate stores.
- Attempt identity is registry file id (`pdf_files.id`).
- Latest marking resolution is deterministic via artifact lookup helper ordering.

