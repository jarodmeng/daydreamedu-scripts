# AI Study Buddy Review Workspace Architecture

Status: active MVP architecture baseline.

Version baseline: `v0.0.900` (see `CHANGELOG.md`).

This document defines:

1. architecture boundaries for `ai_study_buddy/review_workspace/`
2. backend and frontend responsibilities
3. current constraints and intentional deferrals

See also:

- `README.md` for quick start
- `SPEC.md` for API contract
- `DATA_MODEL.md` for payload shape
- `TESTING.md` for validation workflow

## 1) Scope and Boundary

Review Workspace is a focused student-facing app surface that:

- reads one canonical marking artifact at a time
- renders review UI over attempt and answer evidence images
- persists student review-state notes separately from marking artifacts

Non-goals at this layer:

- editing canonical `marking_result` artifacts
- orchestration of marking jobs
- broad student auth and multi-tenant production controls

## 2) Runtime Architecture

The app has two local processes:

1. FastAPI backend (`:8010`)
2. React + Vite frontend (`:5178`)

Frontend requests:

- `/api/*` -> backend API routes
- `/review-workspace-static/*` -> backend static mount of `ai_study_buddy/context/**`

## 3) Backend Responsibilities

Backend module: `backend/app.py`.

Primary responsibilities:

- load pilot marking artifact (`REVIEW_WORKSPACE_PILOT_JSON`, fallback default)
- normalize question and viewer payload for frontend consumption
- provide student/attempt/detail endpoints for the current seed artifact
- persist review-state companion files under:
  - `ai_study_buddy/context/student_review_states/<student>/<subject>/<artifact>.json`

Backend rules:

- reads canonical marking artifact as source of truth
- writes only review-state companion artifacts
- validates `review_status` enum on write (`not_started|in_progress|completed`)

## 4) Frontend Responsibilities

Frontend module: `frontend/src/App.tsx`.

Primary responsibilities:

- bootstrap student -> attempt -> attempt detail flow
- render 4-panel workspace (header, evidence, review panel, status/footer)
- maintain local UI state (active question, viewer mode, fit/zoom, note scope)
- persist review state through backend `PUT` endpoint

Frontend rules:

- no direct filesystem reads/writes
- no direct parsing of `marking_result` JSON from disk
- backend remains the contract boundary

## 5) Data Ownership

Owned by `marking/`:

- canonical marking schema and artifacts (`marking_result.v1.3`/`v1.4`)

Owned by `review_workspace/`:

- review-state write behavior and UI integration
- local interaction model for workspace navigation and note-taking

Shared dependency:

- `ai_study_buddy/context/**` assets and artifact storage conventions

## 6) Known Constraints

- single-pilot artifact loading model in current backend
- student list and attempts list are derived from one artifact seed
- no backend auth/authorization in current implementation
- no automated test suite yet in this package (manual smoke testing currently)

## 7) Near-Term Evolution

Expected next steps after `v0.0.900`:

1. move from single-artifact seed to registry-driven attempt listing
2. extract backend domain modules from monolithic `app.py`
3. add typed API client and component split under `src/features/`
4. add automated backend and frontend tests
