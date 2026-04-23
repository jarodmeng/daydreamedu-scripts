# Changelog

All notable changes to `ai_study_buddy/review_workspace` are documented here.

---

## [v0.0.900] — Documentation suite baseline (2026-04-23)

Initial package documentation baseline for Review Workspace.

Added:

- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `DATA_MODEL.md`
- `SPEC.md`
- `TESTING.md`

Baseline behavior covered by docs:

- FastAPI backend serving Review Workspace API and static evidence assets
- React frontend rendering the 4-panel workspace UI
- review-state persistence under `context/student_review_states/**`

Notes:

- this version establishes documentation/versioning governance
- no schema-breaking runtime behavior change is introduced by this doc baseline itself
