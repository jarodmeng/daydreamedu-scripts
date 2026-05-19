# Specification — `ai_study_buddy.review_workspace`

Contract for Review Workspace backend routes, static serving behavior, review-state persistence, and amendment overlay persistence.

See:

- `README.md` for run commands
- `DATA_MODEL.md` for payload details
- `ARCHITECTURE.md` for boundaries
- `TESTING.md` for validation

---

## 1) Runtime Inputs

### 1.1 Environment variables

- `PDF_REGISTRY_PATH` (optional)
  - registry SQLite path consumed by `PdfFileManager`
  - if absent, backend uses default `ai_study_buddy/db/pdf_registry.db`

### 1.2 Filesystem dependencies

- Canonical context root:
  - `ai_study_buddy/context`
- Registry-backed completion rows:
  - via `PdfFileManager`
- Optional image asset folders:
  - `<marking_asset>/attempt/*`
  - `<marking_asset>/answers/*`

## 2) Static Asset Contract

Static route prefix:

- `/review-workspace-static`

Mounted source:

- `ai_study_buddy/context/**`

Image list behavior:

- include only file suffixes: `.png`, `.jpg`, `.jpeg`, `.webp`
- sort by trailing number parsed from filename stem, then lexical filename
- return image URL as:
  - `/review-workspace-static/<path-relative-to-context-root>`

## 3) API Routes

### 3.1 `GET /api/health`

Response:

```json
{ "status": "ok" }
```

### 3.2 `GET /api/students`

Behavior:

- lists students from `PdfFileManager`

Response:

```json
{
  "students": [
    {
      "student_id": "winston",
      "display_name": "Winston",
      "grade_level": "PSLE"
    }
  ]
}
```

### 3.3 `GET /api/student/attempts?student_id=<id>`

Behavior:

- lists completion attempts for the requested student id (non-template, non-raw)
- resolves latest canonical marking artifact per attempt using:
  - `find_marking_artifacts_for_attempt(...)`
- sorts marked attempts first by newest marking timestamp, then unmarked by recency

Response:

```json
{ "items": [/* attempt list item */] }
```

### 3.4 `GET /api/student/attempts/{attempt_id}`

Behavior:

- resolves attempt by registry `attempt_id` (`pdf_files.id`)
- returns `404` when attempt id is missing/invalid
- for marked attempts:
  - returns latest canonical marking payload normalized for frontend
  - returns base and resolved marking payloads:
    - `marking_result_base`: immutable AI artifact projection
    - `marking_result_resolved`: base artifact plus saved amendment overlay
    - `marking_result`: backward-compatible alias for `marking_result_resolved`
  - enriches question rows with `attempt_page_start` using `context.question_page_map`
  - returns attempt/answer image URLs from marking asset bundle when present
- for unmarked attempts:
  - returns `marking_status = not_marked`
  - `marking_result = null` and empty viewer image pools
- loads companion review-state file if present
- loads companion amendment overlay file if present
- returns default review-state when missing/invalid
- returns default empty amendment state when missing

### 3.5 `PUT /api/student/attempts/{attempt_id}/review-state`

Behavior:

- validates attempt id exists
- requires a canonical marking artifact for the attempt
- validates `review_status` enum:
  - `not_started`
  - `in_progress`
  - `completed`
- persists normalized payload under:
  - `context/student_review_states/<student>/<subject>/<artifact>.json`

Validation errors:

- `400` when attempt has no marking artifact
- `400` when `review_status` invalid

Response:

```json
{
  "ok": true,
  "saved_path": "student_review_states/<student>/<subject>/<artifact>.json",
  "review_state": { /* persisted payload */ }
}
```

### 3.6 `PUT /api/student/attempts/{attempt_id}/amendments`

Behavior:

- validates attempt id exists
- requires a canonical marking artifact for the attempt
- persists human grading overrides separately from review-state notes
- writes under:
  - `context/marking_amendments/<student>/<subject>/<artifact>.json`
- keeps the base `marking_result` artifact read-only
- returns refreshed base/resolved marking payloads so the frontend can clear dirty state

Request body:

```json
{
  "updated_by": "review_workspace_ui",
  "question_amendments": [
    {
      "result_id": "Q4(a)",
      "fields": {
        "earned_marks": 1,
        "outcome": "partial",
        "feedback": "Partially correct."
      },
      "reviewer_reason": "AI over-awarded the score."
    }
  ],
  "question_page_map_amendments": [
    {
      "result_id": "Q4(a)",
      "attempt_page_start": 3,
      "confidence": "high"
    }
  ],
  "summary_overrides": {
    "human_note": "Checked by teacher."
  }
}
```

Validation errors:

- `400` when attempt has no marking artifact
- `400` when an amendment references an unknown `result_id`
- `400` when marks are invalid or `earned_marks > max_marks`
- `400` when page-map amendments reference invalid attempt pages
- `400` when score-changing edits omit `reviewer_reason`

Response:

```json
{
  "ok": true,
  "saved_path": "marking_amendments/<student>/<subject>/<artifact>.json",
  "amendment_state": {},
  "marking_result_base": {},
  "marking_result_resolved": {},
  "marking_result": {}
}
```

## 4) Review-State Write Contract

Persisted payload fields:

- `schema_version`: always `student_review_state.v1`
- `context.student_id`
- `context.subject_context`
- `context.attempt_file_id`
- `context.marking_result_path`
- `review_status`
- `question_reviews` (list or `[]`)
- `attempt_notes` (list or `[]`)
- `student_subject_notes` (list or `[]`)
- `updated_by` (string or backend default `review_workspace`)

Encoding contract:

- UTF-8 text
- JSON pretty printed with indent 2
- newline at EOF
- `ensure_ascii=True`

## 5) Amendment Write Contract

Persisted payload fields:

- `schema_version`: always `marking_amendment.v1`
- `context.student_id`
- `context.subject_context`
- `context.attempt_file_id`
- `context.marking_result_path`
- `summary_overrides`
- `question_amendments`
- `question_page_map_amendments`
- `review_meta.updated_at`
- `review_meta.updated_by`

Allowed `question_amendments[].fields` keys:

- `outcome`
- `earned_marks`
- `max_marks`
- `student_answer`
- `correct_answer`
- `feedback`
- `diagnosis.mistake_type`
- `diagnosis.reasoning`
- `skill_tags`
- `human_note`

Encoding contract:

- UTF-8 text
- JSON pretty printed with indent 2
- newline at EOF
- `ensure_ascii=True`

## 6) Frontend Contract Expectations

Frontend expects:

- `GET /api/students` -> at least one student row
- `GET /api/student/attempts` -> at least one attempt row
- `GET /api/student/attempts/{id}` -> workspace payload including:
  - `attempt`
  - `marking_result`
  - `marking_result_base`
  - `marking_result_resolved`
  - `amendment_state`
  - `review_state`
  - `viewer`
- `PUT` endpoint accepts/save note state from UI scopes:
  - question
  - attempt
  - student_subject

### 6.1 URL deep-link bootstrap

Query parameters (frontend-only; no backend route change):

| Param | Required | Meaning |
|-------|----------|---------|
| `attempt_id` | for deep open | Registry `pdf_files.id`; same as API `{attempt_id}` |
| `student_id` | no | Registry `students.id`; pre-selects student when valid |

Boot behavior on initial load:

1. If `attempt_id` absent → existing picker / **My Work** flow (localStorage last student).
2. If `attempt_id` present → `GET /api/student/attempts/{attempt_id}`:
   - `marking_status === "marked"` → open workspace screen with resolved attempt payload.
   - `marking_status === "not_marked"` → error message + **My Work** for attempt's student; strip `attempt_id` from URL.
   - `404` / fetch error → error message + **My Work** or picker; strip `attempt_id` from URL.
3. When `student_id` is present and matches a known student, apply before attempt fetch (also updates localStorage).

In-app URL sync (`history.replaceState`, not `pushState`):

- Open attempt from **My Work** → set `attempt_id` (+ `student_id`).
- Back from workspace → remove `attempt_id`; keep `student_id`.
- Change student / picker → remove `attempt_id`; set or keep `student_id`.

Example:

`http://127.0.0.1:5178/?attempt_id=d88d78e1-0844-44c4-be4e-230651166612&student_id=winston`

## 7) Explicit Non-Goals

- no auth token validation
- no API pagination yet
- no database persistence layer for review-state
- no concurrency guard for conflicting writes
- no schema migration engine for `student_review_state`
