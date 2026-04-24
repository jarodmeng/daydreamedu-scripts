# AI Study Buddy Data Model (High-Level)

Version baseline: `v0.1.0`.

## 1) Canonical Stores

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

## 2) Primary Domain Objects

- Student
- Attempt (completion file)
- Marking Result (canonical grading facts)
- Student Review State (reflection/progress state)

## 3) Cross-Module Ownership

- `pdf_file_manager`: registry CRUD and grouping/mapping metadata
- `marking`: grading artifact creation, migration, validation, lookup
- `student_review`: attempt list/detail shaping + review-state read/write
- `review_workspace`: UI and backend adapter consuming domain payloads

## 4) Invariants

- Canonical marking and student review-state are separate stores.
- Attempt identity is registry file id (`pdf_files.id`).
- Latest marking resolution is deterministic via artifact lookup helper ordering.

