# Specification — `ai_study_buddy.review_workspace`

Contract for Review Workspace backend routes, static serving behavior, and review-state persistence.

Version baseline: `v0.0.900`.

See:

- `README.md` for run commands
- `DATA_MODEL.md` for payload details
- `ARCHITECTURE.md` for boundaries
- `TESTING.md` for validation

---

## 1) Runtime Inputs

### 1.1 Environment variables

- `REVIEW_WORKSPACE_PILOT_JSON` (optional)
  - absolute or relative path to one pilot `marking_result` JSON
  - if absent, backend uses package default pilot path

### 1.2 Filesystem dependencies

- Canonical context root:
  - `ai_study_buddy/context`
- Required pilot artifact:
  - must exist and be valid JSON
- Optional image asset folders:
  - `<marking_asset>/attempt/*`
  - `<marking_asset>/answers/*`

If pilot artifact path does not exist, backend raises runtime error on read.

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

- derives one student from pilot artifact context
- fallback student id/name: `winston`/`Winston`

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

- returns one seeded attempt when query `student_id` matches artifact `context.student_id`
- returns empty list when mismatch

Response:

```json
{ "items": [/* attempt list item */] }
```

### 3.4 `GET /api/student/attempts/{attempt_id}`

Behavior:

- resolves expected attempt id:
  - `context.attempt_file_id` when present
  - otherwise `artifact_path.stem`
- returns `404` if path id does not match resolved id
- requires `context.marking_asset`; returns `500` when missing
- enriches question rows with `attempt_page_start` using `context.question_page_map`
- loads companion review-state file if present
- returns default review-state when missing/invalid

### 3.5 `PUT /api/student/attempts/{attempt_id}/review-state`

Behavior:

- validates attempt id against pilot artifact resolution
- validates `review_status` enum:
  - `not_started`
  - `in_progress`
  - `completed`
- persists normalized payload under:
  - `context/student_review_states/<student>/<subject>/<artifact>.json`

Validation errors:

- `404` when attempt id mismatch
- `400` when `review_status` invalid

Response:

```json
{
  "ok": true,
  "saved_path": "student_review_states/<student>/<subject>/<artifact>.json",
  "review_state": { /* persisted payload */ }
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

## 5) Frontend Contract Expectations

Frontend expects:

- `GET /api/students` -> at least one student row
- `GET /api/student/attempts` -> at least one attempt row
- `GET /api/student/attempts/{id}` -> workspace payload including:
  - `attempt`
  - `marking_result`
  - `review_state`
  - `viewer`
- `PUT` endpoint accepts/save note state from UI scopes:
  - question
  - attempt
  - student_subject

## 6) Explicit Non-Goals (v0.0.900)

- no multi-attempt aggregation across many artifacts
- no database persistence layer for review-state
- no auth token validation
- no concurrency guard for conflicting writes
- no schema migration engine for `student_review_state`
