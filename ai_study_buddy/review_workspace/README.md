# AI Study Buddy Review Workspace

This folder contains the backend/frontend app scaffold for the Review Workspace app.

Current version: `v0.1.0`

Current phase: `single-student alpha` (scope locked on April 23, 2026).

## Docs

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [CHANGELOG.md](./CHANGELOG.md)
- [DATA_MODEL.md](./DATA_MODEL.md)
- [SPEC.md](./SPEC.md)
- [TESTING.md](./TESTING.md)

## What this slice does

1. Reads students and completion attempts from `PdfFileManager` (registry-backed).
2. Resolves latest canonical marking JSON per attempt using `find_marking_artifacts_for_attempt(...)`.
3. Serves API routes for student picker, my-work attempt index, attempt detail, and review-state save.
4. Persists review notes under `context/student_review_states/**` without mutating canonical marking artifacts.
5. Serves `context/**` static assets for evidence image viewing and uses `question_page_map` for question-page tuning.

## Run backend

From repo root:

```bash
python3 -m pip install -r ai_study_buddy/review_workspace/backend/requirements.txt
python3 -m uvicorn ai_study_buddy.review_workspace.backend.app:app --reload --port 8010
```

## Run frontend

From repo root:

```bash
cd ai_study_buddy/review_workspace/frontend
npm install
npm run dev
```

Vite dev server runs on `http://localhost:5178` and proxies `/api` + `/review-workspace-static` to backend `:8010`.
