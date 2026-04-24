# Specification — `ai_study_buddy.review_workspace`

Contract for Review Workspace backend routes, static serving behavior, and review-state persistence.

Version baseline: `v0.1.0`.

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
  - enriches question rows with `attempt_page_start` using `context.question_page_map`
  - returns attempt/answer image URLs from marking asset bundle when present
- for unmarked attempts:
  - returns `marking_status = not_marked`
  - `marking_result = null` and empty viewer image pools
- loads companion review-state file if present
- returns default review-state when missing/invalid

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

## 6) Explicit Non-Goals (v0.1.0)

- no auth token validation
- no API pagination yet
- no database persistence layer for review-state
- no concurrency guard for conflicting writes
- no schema migration engine for `student_review_state`
