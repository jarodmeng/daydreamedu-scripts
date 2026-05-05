# Proposal: Fold `student_review` into `marking.review`

Status: **Implemented**

**Landed:** marking package **v0.2.18** (2026-04-29). Authoritative entry: `ai_study_buddy/marking/CHANGELOG.md` under `[0.2.18]`.

**What shipped:**

- Review-domain code lives under `ai_study_buddy/marking/review/` (`api_routes`, `attempt_service`, `detail_service`, `note_service`, `amendment_service`, `repository`, `models`, plus `payload_reader`).
- **Option B** was used: the old top-level `ai_study_buddy/student_review/` package was removed (no compatibility shim).
- `review_workspace/backend/app.py` imports `CONTEXT_ROOT`, the router, and `STATIC_ROUTE_PREFIX` from `ai_study_buddy.marking.review`.
- `StudentReviewRepository` was **not** renamed in this pass (optional rename deferred per §8 Phase 4).
- Package docs (`marking/README.md`, `marking/ARCHITECTURE.md`, `marking/TESTING.md`) and changelog/version bump were updated in the same release.

Audience: Maintainers of `ai_study_buddy/marking`, Review Workspace maintainers, and workflow owners consuming review APIs for marked attempts

## 1) Goal

Move the `ai_study_buddy/student_review` backend/domain module under the marking package as `ai_study_buddy/marking/review`, while keeping `review_workspace` as the app surface and frontend home.

Primary outcomes:

1. Treat review of marked work as a natural extension of the marking lifecycle.
2. Keep canonical marking artifacts, marking amendments, review payload shaping, and review-state companion writes close to the same package boundary.
3. Preserve `review_workspace` as a thin FastAPI shell plus React frontend.
4. Reduce top-level module sprawl in `ai_study_buddy/` without weakening data ownership rules.
5. Make documentation reflect the actual dependency direction: Review Workspace consumes marking review services, not a separate peer domain package.

## 2) Problem Statement

The current architecture has three layers:

1. `marking`: canonical marking artifacts, schemas, lookup, assets, validation, and workflows.
2. `student_review`: attempt list/detail shaping, review-state writes, marking-amendment writes, and resolved marking payloads.
3. `review_workspace`: FastAPI app adapter and React UI.

This separation was useful during the MVP extraction because it avoided a monolithic app backend. However, `student_review` is now tightly coupled to `marking`:

1. It depends on `find_marking_artifacts_for_attempt(...)` for latest-artifact selection.
2. It reads canonical `marking_result.v1.x` payloads.
3. It normalizes marking results for frontend review flows.
4. It owns amendment merge behavior for artifacts stored under `context/marking_amendments/**`.
5. The amendment schema is already versioned inside `ai_study_buddy/schemas/marking/marking_amendment.v1.schema.json`.
6. Focused amendment tests already live under `marking/tests/`.

Keeping `student_review` as a top-level package now creates more conceptual overhead than boundary value.

## 3) Decision

Fold `ai_study_buddy/student_review` into:

```text
ai_study_buddy/marking/review/
```

The resulting responsibility split should be:

```text
ai_study_buddy/
  marking/
    core/           # canonical marking artifact contracts, lookup, schema validation, writer behavior
    assets/         # marking asset bundle paths, renders, manifests, and validation
    review/         # review-facing backend/domain services over marked attempts
    workflows/      # marking operator and migration workflows
    # schemas live at: ai_study_buddy/schemas/marking/
  review_workspace/
    backend/        # FastAPI app shell, CORS, static mount, route inclusion
    frontend/       # React + Vite UI
```

Use `ai_study_buddy.marking.review` as the public import path for review-domain backend services.

## 4) Non-Goals

1. Do not move the React frontend into `marking`.
2. Do not merge `review_workspace` into `marking`.
3. Do not mutate canonical `context/marking_results/**` from review flows.
4. Do not redesign the review-state artifact schema in this migration.
5. Do not redesign marking-amendment semantics beyond import/path ownership cleanup.
6. Do not introduce production auth, multi-tenant authorization, or optimistic locking in this migration.
7. Do not change public API routes unless separately approved.

## 5) Invariants To Preserve

1. Canonical marking artifacts remain immutable from review surfaces.
2. `context/marking_results/**` remains the source of grading truth.
3. Student reflection and review progress remain companion artifacts under `context/student_review_states/**`.
4. Human grading amendment overlays remain companion artifacts under `context/marking_amendments/**`.
5. Resolved marking payloads are computed views: base marking artifact plus amendment overlay.
6. Latest marking resolution continues to use `find_marking_artifacts_for_attempt(...)`.
7. Review Workspace frontend continues to call backend `/api/*` endpoints rather than reading artifact files directly.
8. Backend static serving of `context/**` remains routed through `/review-workspace-static/*`.

## 6) Proposed Module Mapping

| Current path | Target path | Notes |
|---|---|---|
| `student_review/models.py` | `marking/review/models.py` | Keep review payload helpers and constants here. |
| `student_review/repository.py` | `marking/review/repository.py` | Consider renaming class to `MarkingReviewRepository` during or after migration. |
| `student_review/attempt_service.py` | `marking/review/attempt_service.py` | Attempt discovery stays review-facing but marking-owned. |
| `student_review/detail_service.py` | `marking/review/detail_service.py` | Normalized frontend projection over marking payloads. |
| `student_review/note_service.py` | `marking/review/note_service.py` | Review-state companion writes. |
| `student_review/amendment_service.py` | `marking/review/amendment_service.py` | Amendment overlays are marking-adjacent and should live here. |
| `student_review/api_routes.py` | `marking/review/api_routes.py` | FastAPI router consumed by Review Workspace backend. |
| `student_review/*.md` | remove or migrate useful decision content | Do not keep long-lived duplicate module docs. |

## 7) Import Compatibility Strategy

Two implementation options are possible, but this proposal adopts Option B as the implementation path. The old `student_review` module is treated as internal to this repository, and no untracked external callers are expected.

### Option A: Compatibility shim for one release

Keep `ai_study_buddy/student_review/` as a thin compatibility layer that re-exports from `ai_study_buddy.marking.review` and emits no behavior of its own.

Pros:

1. Lower migration risk.
2. Existing scripts or tests using old imports keep working temporarily.
3. Allows docs and imports to migrate incrementally.

Cons:

1. Leaves a temporary top-level directory behind.
2. Requires a follow-up cleanup proposal or changelog entry.

Checklist (*Option A was not executed; Option B shipped in marking v0.2.18*):

- [ ] Move implementation files into `marking/review/`.
- [ ] Replace old files with import-forwarding shims only if external imports are suspected.
- [ ] Add a `TODO` or deprecation note in `student_review/README.md` if the directory remains.
- [ ] Add a follow-up task to remove the shim after one or two marking patch releases.

### Option B: Direct move with no compatibility shim

Remove `ai_study_buddy/student_review/` after updating all repository imports.

Pros:

1. Cleanest final tree immediately.
2. Avoids duplicate docs and import ambiguity.

Cons:

1. Breaks any untracked local scripts importing `ai_study_buddy.student_review`.
2. May be more than a patch-level public API change if the old module is considered public.

Checklist:

- [x] Confirm preflight found no in-repository callers that still need old imports.
- [x] Confirm the owner accepts the assumption that there are no untracked external callers.
- [x] Update all in-repo imports in one changeset.
- [x] Remove old module docs and source files.
- [x] Mention the breaking import move explicitly in `CHANGELOG.md`.

Recommended path: Option B. Move the implementation directly into `marking.review`, update all in-repository imports, and remove the old top-level `student_review` module in the same changeset.

## 8) Implementation Plan

### Phase 0: Preflight inventory

- [x] Run `rg -n "ai_study_buddy\.student_review|from ai_study_buddy.marking.review|student_review" ai_study_buddy -S`.
- [x] Classify references as code imports, docs, changelog history, or data-path references.
- [x] Identify tests that currently import `student_review` directly.
- [x] Confirm `review_workspace/backend/app.py` is the only app shell importing the router.
- [x] Confirm no CLI entrypoints reference the old module path.
- [x] Confirm the migration will use Option B direct removal unless preflight finds a concrete blocker.
- [x] Confirm current marking version in `marking/README.md` before choosing the changelog target version.

### Phase 1: Create `marking.review` package

- [x] Create `ai_study_buddy/marking/review/__init__.py`.
- [x] Move service files from `ai_study_buddy/student_review/` to `ai_study_buddy/marking/review/`.
- [x] Update intra-package imports within `ai_study_buddy.marking.review.*` after the move.
- [x] Keep module names stable initially to reduce diff size.
- [x] Avoid behavior changes during the move.
- [x] Run `python3 -m py_compile ai_study_buddy/marking/review/*.py`.

### Phase 2: Update Review Workspace backend integration

- [x] Update `review_workspace/backend/app.py` to import `CONTEXT_ROOT`, router, and static prefix from `ai_study_buddy.marking.review`.
- [x] Confirm backend app title/version does not need to change for this refactor.
- [x] Confirm route paths remain unchanged:
  - [x] `/api/health`
  - [x] `/api/students`
  - [x] `/api/student/attempts`
  - [x] `/api/student/attempts/{attempt_id}`
  - [x] `/api/student/attempts/{attempt_id}/review-state`
  - [x] `/api/student/attempts/{attempt_id}/amendments`
- [x] Confirm `/review-workspace-static/*` still serves `ai_study_buddy/context/**`.

### Phase 3: Remove old top-level module

Option A fallback, only if preflight discovers real external or hard-to-migrate callers:

**Not executed** — preflight proceeded with Option B (marking v0.2.18).

- [ ] Replace `student_review/__init__.py` with a compatibility note and re-exports where useful.
- [ ] Replace each old Python module with a thin forwarding import only if needed by tests or known local scripts.
- [ ] Add deprecation wording to `student_review/README.md` or replace it with a short relocation note.
- [ ] Ensure the shim does not contain duplicated business logic.

Default Option B path:

- [x] Delete `ai_study_buddy/student_review/*.py`.
- [x] Delete old `student_review/*.md` docs after migrating any useful decision content.
- [x] Remove `ai_study_buddy/student_review/` if it becomes empty.
- [x] Confirm `rg -n "ai_study_buddy\.student_review|from ai_study_buddy.marking.review" ai_study_buddy -S` returns no code imports.

### Phase 4: Rename repository class only if low-risk

Optional in first implementation pass:

- [ ] Consider renaming `StudentReviewRepository` to `MarkingReviewRepository` *(deferred; class name kept)*.
- [ ] If renamed, provide an alias `StudentReviewRepository = MarkingReviewRepository` for compatibility in the same release *(N/A — not renamed)*.
- [x] Keep persisted path names unchanged.
- [x] Do not rename `student_review_state.v1` in this migration.

Recommendation: defer class renaming unless the implementation diff is already small and tests are stable.

### Phase 5: Tests and verification

- [x] Run `python3 -m py_compile ai_study_buddy/marking/review/*.py ai_study_buddy/review_workspace/backend/app.py`.
- [x] Run existing marking tests that cover Review Workspace amendment behavior.
- [x] Run any student review smoke tests or update them to the new module path.
- [x] Run `rg -n "ai_study_buddy\.student_review|from ai_study_buddy.marking.review" ai_study_buddy -S` and verify no code imports remain.
- [x] Run `rg -n "student_review/" ai_study_buddy -S` and classify any remaining documentation references.
- [x] If local dependencies are available, start Review Workspace backend and confirm `/api/health` returns `{"status":"ok"}`.
- [x] If the frontend is available, run the Review Workspace manual smoke path:
  - [x] load attempt list
  - [x] open marked attempt detail
  - [x] save review-state note
  - [x] save amendment overlay
  - [x] reload and confirm resolved payload reflects saved state

### Phase 6: Final cleanup

- [x] Remove duplicate stale `student_review` docs.
- [x] If Option A fallback is unexpectedly needed, ensure relocation docs clearly mark old module as compatibility-only *(N/A — Option B only; no shim)*.
- [x] Confirm no generated `__pycache__` files are touched or committed.
- [x] Confirm no runtime context artifacts are accidentally modified.
- [x] Review `git diff --stat` for unexpected large moves or data changes.

## 9) Documentation Updates

This proposal should not bump the marking package version by itself. The version bump should land with the implementation changes, after the module move and documentation updates are complete.

Documentation checklist for the implementation landing:

- [x] Update `ai_study_buddy/ARCHITECTURE.md`:
  - [x] remove `student_review` as a top-level domain layer
  - [x] state that `marking.review` owns review-domain backend services
  - [x] keep `review_workspace` as the app surface
- [x] Update `ai_study_buddy/DATA_MODEL.md`:
  - [x] change `student_review` ownership references to `marking.review`
  - [x] preserve `context/student_review_states/**` path and schema name
  - [x] preserve `context/marking_amendments/**` as marking-owned companion overlays
- [x] Update `ai_study_buddy/README.md`:
  - [x] remove top-level `student_review/` description
  - [x] expand `marking/` description to include review services over marked attempts
  - [x] keep `review_workspace/` as the frontend/app shell description
- [x] Update `ai_study_buddy/review_workspace/ARCHITECTURE.md`:
  - [x] change backend import responsibility from `ai_study_buddy/student_review/` to `ai_study_buddy.marking.review`
  - [x] correct data ownership section so marking owns amendment overlay semantics
- [x] Update `ai_study_buddy/review_workspace/README.md`, `SPEC.md`, `DATA_MODEL.md`, and `TESTING.md` where they mention `student_review` as a module owner.
- [x] Remove `ai_study_buddy/student_review/README.md` as part of deleting the old top-level module.
- [x] Move useful `student_review/DECISIONS.md` content into this proposal or a new marking review decision note.
- [x] Update `ai_study_buddy/marking/ARCHITECTURE.md`:
  - [x] add `review/` as a marking subpackage
  - [x] document canonical artifact immutability from review flows
  - [x] document companion state and amendment overlay stores
- [x] Update `ai_study_buddy/marking/README.md` package scope to include review-domain services.
- [x] Update `ai_study_buddy/marking/SPEC.md` if it enumerates public subpackages or schemas.
- [x] Update `ai_study_buddy/marking/TESTING.md` with review-service verification commands.
- [x] Add an implementation changelog entry under the chosen marking version.
- [x] Update `Current version` in `ai_study_buddy/marking/README.md` in the same changeset as the changelog entry.

Versioning note:

- Option B removes the old `ai_study_buddy.student_review` import path, so the changelog must call out the direct relocation explicitly.
- If the old module is treated as internal-only and preflight confirms no in-repository callers remain, a patch bump is acceptable.
- If the old module is later deemed public API, use a minor bump instead.

## 10) Testing Plan

Minimum automated checks:

- [x] `python3 -m py_compile ai_study_buddy/marking/review/*.py`
- [x] `python3 -m py_compile ai_study_buddy/review_workspace/backend/app.py`
- [x] marking tests covering amendment behavior
- [x] any existing student-review smoke scripts updated to new import paths

Recommended targeted tests to add or update:

- [x] test that `review_workspace/backend/app.py` includes the `marking.review` router
- [x] test review-state write still saves under `context/student_review_states/**`
- [x] test amendment write still saves under `context/marking_amendments/**`
- [x] test resolved marking payload still overlays amendment state without mutating base artifact
- [x] test that old `ai_study_buddy.student_review` code imports are gone

Manual checks:

- [x] open Review Workspace frontend
- [x] select a student
- [x] open a marked attempt
- [x] confirm attempt and answer image pools load
- [x] save a review note
- [x] save an amendment
- [x] reload and confirm saved state persists

## 11) Risks and Mitigations

### Risk A: Hidden local imports of `ai_study_buddy.student_review`

Mitigation:

- Use Option B direct removal after preflight confirms no in-repo callers remain on the old path.
- Use `rg` to update all in-repo imports before deleting the old module.
- Make the direct relocation explicit in docs and changelog.
- If preflight unexpectedly finds real external or hard-to-migrate callers, pause and fall back to Option A.

### Risk B: Blurring canonical marking writes with review writes

Mitigation:

- Keep package structure explicit: `marking.core` owns canonical artifact writing; `marking.review` owns companion state and resolved views.
- Repeat immutability invariant in `marking/ARCHITECTURE.md`, `review_workspace/ARCHITECTURE.md`, and tests.
- Add or preserve tests that verify review writes do not modify base `marking_result` JSON.

### Risk C: Review Workspace docs become stale during move

Mitigation:

- Treat documentation updates as a first-class implementation phase.
- Run `rg` for old module names after implementation.
- Update high-level and package-level docs in the same changeset as imports.

### Risk D: Version bump ambiguity

Mitigation:

- Do not bump the marking version for this proposal-only change.
- Land the version bump with the implementation, docs, and changelog updates in one changeset.
- Because Option B removes the old import path, call the direct relocation out explicitly in the marking changelog.
- If the old module is treated as internal-only and preflight confirms no in-repository callers remain, a patch bump is acceptable.
- If the old module is later deemed public API, use a minor bump instead.

## 12) Acceptance Criteria

The migration is complete when:

- [x] Review-domain source code lives under `ai_study_buddy/marking/review/`.
- [x] Review Workspace backend imports its router from `ai_study_buddy.marking.review`.
- [x] Existing API route paths and payload contracts remain stable.
- [x] Review-state files continue to persist under `context/student_review_states/**`.
- [x] Amendment files continue to persist under `context/marking_amendments/**`.
- [x] Canonical `context/marking_results/**` artifacts remain read-only from review flows.
- [x] Tests or smoke checks cover attempt detail, review-state writes, amendment writes, and resolved payload recomputation (see `marking/tests/test_review_workspace_amendments.py` and changelog for v0.2.18).
- [x] Repository docs no longer present `student_review` as an active top-level domain module.
- [x] Marking changelog and README version are updated according to the versioning decision (v0.2.18 patch).
