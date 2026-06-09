# AI Study Buddy Review Workspace

This folder contains the backend/frontend app for Review Workspace, including
student review-state notes and human grading amendment overlays.

> Legacy standalone review app. **`buddy_console` is the ship target** for Review
> Workspace and new review features (including tutor chat v0.2.0). This package
> remains available for rollback and reference only.

Current version: `v0.1.13`

## Maintenance policy (June 2026+)

| Layer | Policy |
|-------|--------|
| **`marking.review` API** | Shared — new review/tutor routes land here; both backends mount the same router. |
| **`buddy_console` frontend** | **Required** — all new Review Workspace UI work ships here (`/review`). |
| **`review_workspace` frontend** | **Not mirrored** — tutor chat UI removed; use `buddy_console` `/review` for **Ask AI**. |
| **`review_workspace` backend** | Thin shell only — keep mounting `marking.review.api_routes` for rollback; no feature logic here. |
| **Tests** | `marking/tests/test_tutor_chat_api.py` may use this app's FastAPI entrypoint as a minimal host; that does not require frontend parity. |

Use `buddy_console` for day-to-day review and tutor chat. Run standalone `review_workspace` only when debugging rollback or comparing legacy `:5178` behavior.

See [L4 browser consolidation](../docs/L4_BROWSER_APP_CONSOLIDATION.md) and [buddy_console README](../buddy_console/README.md).

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
6. Persists human grading amendments under `context/marking_amendments/**` and renders resolved marking results without mutating canonical marking artifacts.

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

### Deep linking

Open a specific marked attempt directly (also used by **Student File Browser** card links):

`http://127.0.0.1:5178/?attempt_id=<registry_uuid>&student_id=<students.id>`

- `attempt_id` — required for deep open; equals `pdf_files.id` / Review Workspace list `attempt_id`.
- `student_id` — optional but recommended when known; pre-selects the student before attempt load.
- `result_id` — optional canonical question key; opens the workspace on that question when found.
- `question_index` — optional 1-based fallback selector used when `result_id` is missing/invalid.

Question-specific examples:

- `http://127.0.0.1:5178/?attempt_id=<registry_uuid>&student_id=<students.id>&result_id=Q4`
- `http://127.0.0.1:5178/?attempt_id=<registry_uuid>&student_id=<students.id>&question_index=3`

On load the app fetches `GET /api/student/attempts/{attempt_id}` and opens the workspace when `marking_status === "marked"`. In-app navigation syncs the URL via `history.replaceState`.
