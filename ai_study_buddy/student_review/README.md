# AI Study Buddy `student_review`

Domain module for student review workflows consumed by app surfaces like Review Workspace.

Current version: `v0.1.0`

## Docs

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [CHANGELOG.md](./CHANGELOG.md)
- [DATA_MODEL.md](./DATA_MODEL.md)
- [DECISIONS.md](./DECISIONS.md)
- [SPEC.md](./SPEC.md)
- [TESTING.md](./TESTING.md)

## What this module does

1. Lists students and student-scoped attempts from `PdfFileManager`.
2. Resolves latest canonical marking artifact per attempt.
3. Builds attempt detail payloads for review UIs.
4. Persists companion review-state artifacts under `context/student_review_states/**`.

## What this module does not do

1. Mutate canonical `marking_result` artifacts.
2. Orchestrate marking jobs.
3. Handle production auth.

