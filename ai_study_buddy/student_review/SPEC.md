# Specification — `ai_study_buddy.student_review`

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

### 1.4 Amendment overlay storage

- read/write path:
  - `context/marking_amendments/<student>/<subject>/<artifact_stem>.json`

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
5. return base/resolved payload split for marked attempts:
   - `marking_result_base`
   - `marking_result_resolved`
   - `marking_result` alias to resolved
6. load amendment state (persisted or default empty state)
7. always return a review-state object (persisted or default)

## 4) Review-State Write Contract

`put_review_state(...)` must:

1. validate `review_status` enum:
   - `not_started`
   - `in_progress`
   - `completed`
2. fail when attempt has no canonical marking artifact
3. write UTF-8 JSON with `indent=2` and newline at EOF
4. write to companion path only (never mutate canonical marking artifacts)

## 5) Amendment Write Contract

`put_amendments(...)` must:

1. fail when attempt has no canonical marking artifact
2. validate amendment `result_id` references against base artifact rows
3. enforce score-edit guardrails (`earned_marks <= max_marks`, score-changing edits require `reviewer_reason`)
4. validate page-map amendments against available attempt pages when discoverable
5. write UTF-8 JSON with `indent=2` and newline at EOF
6. write to companion amendment path only (never mutate canonical marking artifacts)
7. return resolved projection consistent with persisted overlay

## 6) API Route Contract (current adapter)

`api_routes.py` exposes:

- `GET /api/health`
- `GET /api/students`
- `GET /api/student/attempts?student_id=<id>`
- `GET /api/student/attempts/{attempt_id}`
- `PUT /api/student/attempts/{attempt_id}/review-state`
- `PUT /api/student/attempts/{attempt_id}/amendments`

## 7) Non-Goals

- auth/session verification
- pagination/offset APIs
- write-conflict detection
- schema migration framework
