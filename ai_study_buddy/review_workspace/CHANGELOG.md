# Changelog

All notable changes to `ai_study_buddy/review_workspace` are documented here.

---

## [v0.1.11] — Amendment override cleanup (2026-06-05)

### Fixed

- Amendment save: `pickAmendmentFieldsForSave` clears stale persisted overrides when the draft matches the AI base (`App.tsx`; same fix as `buddy_console` v0.1.13).

### Changed

- `frontend/package.json` version aligned to `0.1.11`.
- Requires `ai_study_buddy.marking` v0.3.19+.

## [v0.1.10] — Question navigation vs URL deep link (2026-06-03)

### Fixed

- `frontend/src/App.tsx`: stop re-applying `result_id` / `question_index` from the URL on every question-list effect pass. Deep-link targeting still runs once when the attempt loads; in-workspace question changes are no longer overridden by stale query params.

## [v0.1.9] — Question-level deep links (2026-06-02)

Implemented:

- frontend deep links now accept `result_id` for canonical question targeting and optional `question_index` (1-based) fallback.
- workspace URL sync now keeps `result_id` in query params as users change active questions, so copied links preserve question context.
- `frontend/package.json` version aligned to `0.1.9`.

## [v0.1.8] — Review completion + amendment consistency fixes (2026-06-02)

Implemented:

- `frontend/src/App.tsx`: completion gating now treats explicit `outcome=correct` as correct (mark-based fallback no longer overrides explicit corrected outcome).
- `frontend/src/App.tsx`: after amendment save, review status is immediately recomputed/persisted from resolved question results so attempts can move to **Review completed** without requiring separate manual review-state edits.
- Depends on backend `marking` **v0.3.18+** for amendment outcome↔score auto-alignment (wrong/correct with zero/full-credit inference).

## [v0.1.7] — Template evidence viewer (2026-06-02)

Implemented:

- Evidence toolbar **Template** mode: clean worksheet pages from linked template FQI `rendered_pages/` (shown only when images exist).
- Backend `GET /api/student/attempts/{attempt_id}` viewer payload adds `template_images[]` (`marking` **v0.3.17+** / `marking/review/detail_service.py`).
- `frontend/package.json` version aligned to `0.1.7`.

## [v0.1.6] — Amendment save diff vs AI base (2026-05-30)

Implemented:

- `frontend/src/App.tsx`: `meaningfulAmendmentDraftForSave` compares draft fields to the AI base question (same baseline as dirty-state), not the resolved row, so score/outcome edits are included in the PUT payload reliably.
- Backend amendment behavior is unchanged in this package (routes live under `marking.review`); use `marking` **v0.3.16+** and `learning_db` **v0.1.9+** for API response and DB soft-delete revival fixes.

## [v0.1.5] — Vite bind to 127.0.0.1 (2026-05-27)

Implemented:

- Vite dev and preview servers bind to `127.0.0.1` so documented deep links match the served host.

## [v0.1.4] — Attempt deep links (2026-05-19)

Implemented:

- frontend URL bootstrap for marked attempts via `?attempt_id=` (+ optional `student_id=`).
- on load, fetches `GET /api/student/attempts/{attempt_id}` and opens workspace when marked; graceful errors for not found / not marked.
- in-app navigation syncs query params via `history.replaceState`.
- pure URL helpers in `frontend/src/deepLink.ts` with Vitest coverage.
- fixed React Strict Mode dev double-mount leaving the app stuck on **Loading...** during bootstrap.

Scope lock:

- phase remains `single-student alpha`.
- unmarked attempts are not openable via deep link (error + **My Work**).

## [v0.1.3] — Amendment save-diff hotfix (2026-05-08)

Implemented:

- fixed amendment save payload shaping so field diffs are computed against the current resolved question state (base + saved overlay), not only the immutable AI base.
- this resolves a persistence gap where setting a field back to the AI base value could be dropped from the save payload and leave a stale prior override in place.

Scope lock:

- phase remains `single-student alpha`.
- canonical `marking_result` artifacts remain read-only from this app surface.

## [v0.1.2] — Marking review-domain consolidation (2026-04-29)

Implemented:

- Review Workspace backend domain ownership is now consolidated under `ai_study_buddy.marking.review`.
- `review_workspace/backend/app.py` now imports route/model dependencies from:
  - `ai_study_buddy.marking.review.api_routes`
  - `ai_study_buddy.marking.review.models`
- top-level `ai_study_buddy/student_review/` module was removed as part of Option B direct migration.

Scope lock:

- phase remains `single-student alpha`.
- canonical `marking_result` artifacts remain read-only from this app surface.

## [v0.1.1] — Amendment overlay + resolved marking model (2026-04-26)

Implemented:

- review workspace now supports human grading amendments as a first-class flow:
  - `PUT /api/student/attempts/{attempt_id}/amendments`
  - persisted under `context/marking_amendments/<student>/<subject>/<artifact>.json`
- attempt detail now exposes a base/resolved split:
  - `marking_result_base` (immutable AI artifact projection)
  - `marking_result_resolved` (base + amendment overlay)
  - `marking_result` retained as backward-compatible alias to resolved payload
- backend amendment validation and merge logic is implemented in shared `student_review` domain services.
- frontend now supports inline amendment edits and save/reload of resolved values.
- review workspace docs updated to describe amendment overlay contracts and testing.

Scope lock:

- phase remains `single-student alpha`.
- canonical `marking_result` artifacts remain read-only from this app surface.

## [v0.1.0] — Student picker + registry-backed attempts (2026-04-23)

Implemented:

- backend extraction into `ai_study_buddy/student_review/`:
  - `models.py`
  - `repository.py`
  - `attempt_service.py`
  - `detail_service.py`
  - `note_service.py`
  - `api_routes.py`
- `review_workspace/backend/app.py` now acts as a thin shell that mounts static files and includes the new router.
- student list and attempts list now come from `PdfFileManager` (registry-backed), not a single seeded pilot artifact.
- latest canonical marking selection now uses `find_marking_artifacts_for_attempt(...)`.
- frontend now includes:
  - Student Picker screen
  - My Work attempts list with filters
  - Review Workspace detail screen

Scope lock:

- phase explicitly set to `single-student alpha` for current rollout slice.
- non-MVP additions remain deferred while core student review loop is stabilized.

## [v0.0.900] — Documentation suite baseline (2026-04-23)

Initial package documentation baseline for Review Workspace.

Added:

- `ARCHITECTURE.md`
- `CHANGELOG.md`
- `DATA_MODEL.md`
- `SPEC.md`
- `TESTING.md`

Baseline behavior covered by docs:

- FastAPI backend serving Review Workspace API and static evidence assets
- React frontend rendering the 4-panel workspace UI
- review-state persistence under `context/student_review_states/**`

Notes:

- this version establishes documentation/versioning governance
- no schema-breaking runtime behavior change is introduced by this doc baseline itself
