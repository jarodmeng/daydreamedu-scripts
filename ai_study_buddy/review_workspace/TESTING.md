# Testing — `ai_study_buddy.review_workspace`

Validation guide for Review Workspace.

Current state:

- frontend build verification is available
- focused backend amendment tests live in `ai_study_buddy/marking/tests/test_review_workspace_amendments.py`
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

Optional registry override:

```bash
PDF_REGISTRY_PATH="/abs/path/to/pdf_registry.db"
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

- attempt items for that student from registry-backed completion rows

### 2.4 Attempt detail

1. capture `attempt_id` from previous response
2. request:

```bash
curl -s "http://localhost:8010/api/student/attempts/<attempt_id>"
```

Expected:

- includes `marking_result.question_results[]`
- includes `marking_result_base`, `marking_result_resolved`, and `amendment_state`
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

### 2.6 Amendment write

```bash
curl -s -X PUT "http://localhost:8010/api/student/attempts/<attempt_id>/amendments" \
  -H "Content-Type: application/json" \
  -d '{
    "updated_by":"manual_smoke",
    "question_amendments":[{
      "result_id":"Q1",
      "fields":{"feedback":"Checked manually."}
    }]
  }'
```

Expected:

- response contains `"ok": true`
- response includes `marking_result_base`, `marking_result_resolved`, and `amendment_state`
- file exists under `ai_study_buddy/context/marking_amendments/**`
- paired canonical `ai_study_buddy/context/marking_results/**` file is unchanged

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
7. double-clicking a Review field opens an amendment editor
8. `Save amendment` persists a changed value and reload keeps the resolved value

### Deep-link smoke

1. capture `attempt_id` from `GET /api/student/attempts?student_id=<id>` (marked row)
2. open `http://localhost:5178/?attempt_id=<attempt_id>&student_id=<id>` in a fresh tab (or clear localStorage first)
3. verify workspace opens on that attempt without using **My Work**
4. click back to **My Work** — URL should drop `attempt_id` but keep `student_id`
5. open attempt from **My Work** — URL should gain `attempt_id` again
6. open with unknown `attempt_id` — error on **My Work**, no crash
7. from **Student File Browser**, card **Review Workspace** opens the same attempt (requires browser v0.1.1+)

**Smoke verification (2026-05-19):** operator path **Student File Browser → Review Workspace** passed (same hostname for both apps, e.g. `localhost`).

## 4) Regression Checklist (before merge)

1. `npm run build` passes in `frontend/`
2. `python3 -m pytest ai_study_buddy/marking/tests/test_review_workspace_amendments.py` passes
3. backend endpoints return expected shapes from `SPEC.md`
4. review-state write path remains limited to `student_review_states/**`
5. amendment write path remains limited to `marking_amendments/**`
6. canonical `marking_results/**` files are unchanged
7. registry override env var still works: `PDF_REGISTRY_PATH`

## 5) Planned Automated Coverage

Recommended additions:

1. backend route tests with FastAPI `TestClient`
2. backend tests for invalid `review_status` and `attempt_id` mismatch
3. frontend component tests for note persistence logic
4. end-to-end smoke (Playwright) for workspace happy path
