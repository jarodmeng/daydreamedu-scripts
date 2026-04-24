# Specification — `ai_study_buddy.student_review`

Version baseline: `v0.1.0`.

This spec defines service and route-level behavior for student review domain operations.

## 1) Inputs

### 1.1 Registry data

- students from `PdfFileManager.list_students()`
- attempts from `PdfFileManager.find_files(student_id=..., is_template=False)`

### 1.2 Marking artifacts

- resolved through `find_marking_artifacts_for_attempt(...)`
- latest artifact is first in returned order

### 1.3 Review-state storage

- read/write path:
  - `context/student_review_states/<student>/<subject>/<artifact_stem>.json`

## 2) Attempt Listing Contract

`list_attempts_for_student(...)` must:

1. exclude template and raw completion files
2. include both marked and unmarked attempts
3. expose deterministic fields required by UI list view
4. sort marked attempts first by latest marking timestamp desc
5. sort remaining attempts by best available recency desc

## 3) Attempt Detail Contract

`get_attempt_detail(...)` must:

1. resolve attempt by registry id
2. return `marking_status = not_marked` with `marking_result = null` when no artifact exists
3. normalize question rows when artifact exists
4. derive `attempt_page_start` from `context.question_page_map`
5. always return a review-state object (persisted or default)

## 4) Review-State Write Contract

`put_review_state(...)` must:

1. validate `review_status` enum:
   - `not_started`
   - `in_progress`
   - `completed`
2. fail when attempt has no canonical marking artifact
3. write UTF-8 JSON with `indent=2` and newline at EOF
4. write to companion path only (never mutate canonical marking artifacts)

## 5) API Route Contract (current adapter)

`api_routes.py` exposes:

- `GET /api/health`
- `GET /api/students`
- `GET /api/student/attempts?student_id=<id>`
- `GET /api/student/attempts/{attempt_id}`
- `PUT /api/student/attempts/{attempt_id}/review-state`

## 6) Non-Goals

- auth/session verification
- pagination/offset APIs
- write-conflict detection
- schema migration framework

