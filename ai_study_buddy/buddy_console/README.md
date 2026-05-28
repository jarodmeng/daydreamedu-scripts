# Buddy Console

**Version: v0.1.4**

`buddy_console` is the new unified browser app for AI Study Buddy.

It is intended to replace the operator workflow currently spread across:

1. `student_file_browser`
2. `root_pdf_browser`
3. `review_workspace`

The current implementation uses `review_workspace` as the seed codebase, but
`buddy_console` is its own app and should be documented as its own product.

Current focus:

1. inventory hub parity with `student_file_browser`
2. PDF browsing parity with `root_pdf_browser`
3. preserved review functionality via the seeded review route
4. deep-link-driven workflow between inventory, PDF, and review

## Runtime

Local development uses two processes:

1. FastAPI backend on `:8010`
2. React + Vite frontend on `:5178`

Primary routes in the frontend:

- `/` and `/inventory` -> inventory hub
- `/pdf` -> root-style PDF browser
- `/review` -> review surface

Inventory cards show **Completed** (`completion_date`) and **Registered** (`registry_added_at`) separately when `files` v0.3.6+ is in use ([proposal 17](../pdf_file_manager/docs/proposals/17-completion-date.md) Phase 4). **Completed (recent)** sort uses unified recency fallback in `files` v0.3.7+. Inventory health reports `files_version` from `files.__version__` (`files` v0.3.8+).

## Docs

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [SPEC.md](./SPEC.md)
- [DATA_MODEL.md](./DATA_MODEL.md)
- [TESTING.md](./TESTING.md)
- [CHANGELOG.md](./CHANGELOG.md)

## Run Backend

From repo root:

```bash
python3 -m pip install -r ai_study_buddy/buddy_console/backend/requirements.txt
python3 -m uvicorn ai_study_buddy.buddy_console.backend.app:app --reload --port 8010
```

## Run Frontend

From repo root:

```bash
cd ai_study_buddy/buddy_console/frontend
npm install
npm run dev
```

Frontend runs on `http://localhost:5178` and proxies `/api` and
`/review-workspace-static` to backend `:8010`.

## Deep-Link Examples

Open review in a fresh tab:

```text
http://127.0.0.1:5178/review?attempt_id=<registry_uuid>&student_id=<students.id>
```

Open a specific PDF in a fresh tab:

```text
http://127.0.0.1:5178/pdf?id=<root_id>&rel=<root_relative_pdf_path>
```

Inventory is the operator hub. Card actions are expected to open PDF and review
targets in new tabs rather than navigating away from the inventory tab.

## Rollback

If `buddy_console` is not behaving acceptably for a workflow:

1. stop the `buddy_console` backend and frontend processes
2. return to the standalone apps:
   - `student_file_browser`
   - `root_pdf_browser`
   - `review_workspace`
3. use the existing startup commands and READMEs for those tools while the
   regression is fixed

`buddy_console` does not replace the old apps destructively. Rollback is
operational, not migrational.
