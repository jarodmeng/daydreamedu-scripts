# Testing — `ai_study_buddy.review_workspace`

Validation guide for Review Workspace (`v0.0.900` baseline).

Current state:

- frontend build verification is available
- no dedicated automated backend/frontend test suite in this package yet
- manual smoke checks are required before runtime changes are considered safe

See:

- `SPEC.md` for expected route behavior
- `DATA_MODEL.md` for payload shape

## 1) Prerequisites

From repo root:

1. backend dependencies
```bash
python3 -m pip install -r ai_study_buddy/review_workspace/backend/requirements.txt
```
2. frontend dependencies
```bash
cd ai_study_buddy/review_workspace/frontend
npm install
```

Optional pilot override:

```bash
REVIEW_WORKSPACE_PILOT_JSON="/abs/path/to/marking_result.json"
```

## 2) Backend Smoke Tests

Run backend:

```bash
python3 -m uvicorn ai_study_buddy.review_workspace.backend.app:app --reload --port 8010
```

### 2.1 Health

```bash
curl -s http://localhost:8010/api/health
```

Expected:

- JSON includes `"status":"ok"`

### 2.2 Students

```bash
curl -s http://localhost:8010/api/students
```

Expected:

- one `students[]` item with non-empty `student_id`

### 2.3 Attempts

```bash
curl -s "http://localhost:8010/api/student/attempts?student_id=winston"
```

Expected:

- at least one `items[]` row for the seed artifact student id

### 2.4 Attempt detail

1. capture `attempt_id` from previous response
2. request:

```bash
curl -s "http://localhost:8010/api/student/attempts/<attempt_id>"
```

Expected:

- includes `marking_result.question_results[]`
- includes `viewer.attempt_images[]` and/or `viewer.answer_images[]`
- includes `review_state` object

### 2.5 Review-state write

```bash
curl -s -X PUT "http://localhost:8010/api/student/attempts/<attempt_id>/review-state" \
  -H "Content-Type: application/json" \
  -d '{
    "review_status":"in_progress",
    "question_reviews":[{"result_id":"Q1","review_status":"reviewed","note_text":"checked"}],
    "attempt_notes":[{"note_text":"attempt note"}],
    "student_subject_notes":[{"note_text":"subject note"}],
    "updated_by":"manual_smoke"
  }'
```

Expected:

- response contains `"ok": true`
- response includes `saved_path`
- file exists under `ai_study_buddy/context/student_review_states/**`

## 3) Frontend Checks

From `ai_study_buddy/review_workspace/frontend`:

### 3.1 Build check

```bash
npm run build
```

Expected:

- Vite build succeeds with no fatal errors

### 3.2 Local UI smoke

Run frontend dev server while backend is running:

```bash
npm run dev
```

Open `http://localhost:5178` and verify:

1. workspace loads without fetch error
2. question navigation buttons update active question
3. evidence mode toggle switches attempt/answer image pools
4. fit and zoom controls affect image rendering
5. note tabs (Question / Attempt / Student+Subject) load/save values
6. `Mark reviewed` updates question status and persists on reload

## 4) Regression Checklist (before merge)

1. `npm run build` passes in `frontend/`
2. backend endpoints return expected shapes from `SPEC.md`
3. write path remains limited to `student_review_states/**`
4. canonical `marking_results/**` files are unchanged
5. pilot override env var still works: `REVIEW_WORKSPACE_PILOT_JSON`

## 5) Planned Automated Coverage

Recommended additions after `v0.0.900`:

1. backend route tests with FastAPI `TestClient`
2. backend tests for invalid `review_status` and `attempt_id` mismatch
3. frontend component tests for note persistence logic
4. end-to-end smoke (Playwright) for workspace happy path
