# Changelog

All notable changes to `ai_study_buddy/review_workspace` are documented here.

---

## [v0.1.0] — Student picker + registry-backed attempts (2026-04-23)

Implemented:

- backend extraction into `ai_study_buddy/student_review/`:
  - `models.py`
  - `repository.py`
  - `attempt_service.py`
  - `detail_service.py`
  - `note_service.py`
  - `api_routes.py`
- `review_workspace/backend/app.py` now acts as a thin shell that mounts static files and includes the new router.
- student list and attempts list now come from `PdfFileManager` (registry-backed), not a single seeded pilot artifact.
- latest canonical marking selection now uses `find_marking_artifacts_for_attempt(...)`.
- frontend now includes:
  - Student Picker screen
  - My Work attempts list with filters
  - Review Workspace detail screen

Scope lock:

- phase explicitly set to `single-student alpha` for current rollout slice.
- non-MVP additions remain deferred while core student review loop is stabilized.

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
