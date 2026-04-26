# Changelog

All notable changes to `ai_study_buddy/student_review` are documented here.

---

## [v0.1.1] — Amendment overlay + resolved detail payloads (2026-04-26)

Added:

- `amendment_service.py`:
  - amendment overlay validation/merge helpers
  - persisted amendment write flow (`marking_amendment.v1`)
  - resolved marking-result projection (base artifact + amendment overlay)

Changed:

- `api_routes.py`:
  - adds `PUT /api/student/attempts/{attempt_id}/amendments`
  - amendment write response now returns refreshed:
    - `marking_result` (resolved alias)
    - `marking_result_base`
    - `marking_result_resolved`
    - `amendment_state`
- `detail_service.py`:
  - attempt detail payload includes base/resolved split:
    - `marking_result_base`
    - `marking_result_resolved`
    - `marking_result` alias to resolved payload
  - loads persisted amendment overlay state when present
- `repository.py`:
  - amendment overlay load/save paths under `context/marking_amendments/**`

Documentation:

- updated module docs to include amendment endpoint, overlay artifact contract, and resolved payload semantics.

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
