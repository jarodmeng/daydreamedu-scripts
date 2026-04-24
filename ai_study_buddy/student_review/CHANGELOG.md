# Changelog

All notable changes to `ai_study_buddy/student_review` are documented here.

---

## [v0.1.0] — Initial extraction baseline (2026-04-23)

Added:

- `models.py`
- `repository.py`
- `attempt_service.py`
- `detail_service.py`
- `note_service.py`
- `api_routes.py`

Baseline behavior:

- registry-backed student and attempt listing
- latest-artifact selection via `find_marking_artifacts_for_attempt(...)`
- attempt detail payload shaping for review UIs
- review-state persistence under `context/student_review_states/**`

