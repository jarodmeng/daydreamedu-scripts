# AI Study Buddy Review Workspace

This folder contains the backend/frontend app scaffold for the Review Workspace app.

Current version: `v0.0.900`

## Docs

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [CHANGELOG.md](./CHANGELOG.md)
- [DATA_MODEL.md](./DATA_MODEL.md)
- [SPEC.md](./SPEC.md)
- [TESTING.md](./TESTING.md)

## What this slice does

1. Loads one pilot `marking_result.v1.4` artifact.
2. Exposes API routes for student, attempts list, and attempt detail.
3. Serves `context/marking_assets/**` images to the frontend.
4. Renders a 4-panel Review Workspace UI.
5. Uses `context.question_page_map` to jump evidence pages when active question changes.

Pilot artifact default:

- `ai_study_buddy/context/marking_results/winston/singapore_primary_math/PP Math PSLE Part D P6 Topical Practice Circles__20260416_205158.json`

## Run backend

From repo root:

```bash
python3 -m pip install -r ai_study_buddy/review_workspace/backend/requirements.txt
python3 -m uvicorn ai_study_buddy.review_workspace.backend.app:app --reload --port 8010
```

Optional override:

```bash
REVIEW_WORKSPACE_PILOT_JSON="/abs/path/to/another_marking_result.json" \
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
