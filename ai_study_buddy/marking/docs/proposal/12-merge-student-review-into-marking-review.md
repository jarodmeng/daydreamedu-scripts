# Proposal: Fold `student_review` into `marking.review`

Status: Proposed

Target marking version: implementation bump, patch if the old import path is treated as internal-only

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

Checklist:

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

1. Breaks any untracked local scripts importing `ai_study_buddy.marking.review`.
2. May be more than a patch-level public API change if the old module is considered public.

Checklist:

- [ ] Confirm preflight found no in-repository callers that still need old imports.
- [ ] Confirm the owner accepts the assumption that there are no untracked external callers.
- [ ] Update all in-repo imports in one changeset.
- [ ] Remove old module docs and source files.
- [ ] Mention the breaking import move explicitly in `CHANGELOG.md`.

Recommended path: Option B. Move the implementation directly into `marking.review`, update all in-repository imports, and remove the old top-level `student_review` module in the same changeset.

## 8) Implementation Plan

### Phase 0: Preflight inventory

- [ ] Run `rg -n "ai_study_buddy\.student_review|from ai_study_buddy.marking.review|student_review" ai_study_buddy -S`.
- [ ] Classify references as code imports, docs, changelog history, or data-path references.
- [ ] Identify tests that currently import `student_review` directly.
- [ ] Confirm `review_workspace/backend/app.py` is the only app shell importing the router.
- [ ] Confirm no CLI entrypoints reference the old module path.
- [ ] Confirm the migration will use Option B direct removal unless preflight finds a concrete blocker.
- [ ] Confirm current marking version in `marking/README.md` before choosing the changelog target version.

### Phase 1: Create `marking.review` package

- [ ] Create `ai_study_buddy/marking/review/__init__.py`.
- [ ] Move service files from `ai_study_buddy/student_review/` to `ai_study_buddy/marking/review/`.
- [ ] Update intra-package imports from `ai_study_buddy.marking.review.*` to `ai_study_buddy.marking.review.*`.
- [ ] Keep module names stable initially to reduce diff size.
- [ ] Avoid behavior changes during the move.
- [ ] Run `python3 -m py_compile ai_study_buddy/marking/review/*.py`.

### Phase 2: Update Review Workspace backend integration

- [ ] Update `review_workspace/backend/app.py` to import `CONTEXT_ROOT`, router, and static prefix from `ai_study_buddy.marking.review`.
- [ ] Confirm backend app title/version does not need to change for this refactor.
- [ ] Confirm route paths remain unchanged:
  - [ ] `/api/health`
  - [ ] `/api/students`
  - [ ] `/api/student/attempts`
  - [ ] `/api/student/attempts/{attempt_id}`
  - [ ] `/api/student/attempts/{attempt_id}/review-state`
  - [ ] `/api/student/attempts/{attempt_id}/amendments`
- [ ] Confirm `/review-workspace-static/*` still serves `ai_study_buddy/context/**`.

### Phase 3: Remove old top-level module

Option A fallback, only if preflight discovers real external or hard-to-migrate callers:

- [ ] Replace `student_review/__init__.py` with a compatibility note and re-exports where useful.
- [ ] Replace each old Python module with a thin forwarding import only if needed by tests or known local scripts.
- [ ] Add deprecation wording to `student_review/README.md` or replace it with a short relocation note.
- [ ] Ensure the shim does not contain duplicated business logic.

Default Option B path:

- [ ] Delete `ai_study_buddy/student_review/*.py`.
- [ ] Delete old `student_review/*.md` docs after migrating any useful decision content.
- [ ] Remove `ai_study_buddy/student_review/` if it becomes empty.
- [ ] Confirm `rg -n "ai_study_buddy\.student_review|from ai_study_buddy.marking.review" ai_study_buddy -S` returns no code imports.

### Phase 4: Rename repository class only if low-risk

Optional in first implementation pass:

- [ ] Consider renaming `StudentReviewRepository` to `MarkingReviewRepository`.
- [ ] If renamed, provide an alias `StudentReviewRepository = MarkingReviewRepository` for compatibility in the same release.
- [ ] Keep persisted path names unchanged.
- [ ] Do not rename `student_review_state.v1` in this migration.

Recommendation: defer class renaming unless the implementation diff is already small and tests are stable.

### Phase 5: Tests and verification

- [ ] Run `python3 -m py_compile ai_study_buddy/marking/review/*.py ai_study_buddy/review_workspace/backend/app.py`.
- [ ] Run existing marking tests that cover Review Workspace amendment behavior.
- [ ] Run any student review smoke tests or update them to the new module path.
- [ ] Run `rg -n "ai_study_buddy\.student_review|from ai_study_buddy.marking.review" ai_study_buddy -S` and verify no code imports remain.
- [ ] Run `rg -n "student_review/" ai_study_buddy -S` and classify any remaining documentation references.
- [ ] If local dependencies are available, start Review Workspace backend and confirm `/api/health` returns `{"status":"ok"}`.
- [ ] If the frontend is available, run the Review Workspace manual smoke path:
  - [ ] load attempt list
  - [ ] open marked attempt detail
  - [ ] save review-state note
  - [ ] save amendment overlay
  - [ ] reload and confirm resolved payload reflects saved state

### Phase 6: Final cleanup

- [ ] Remove duplicate stale `student_review` docs.
- [ ] If Option A fallback is unexpectedly needed, ensure relocation docs clearly mark old module as compatibility-only.
- [ ] Confirm no generated `__pycache__` files are touched or committed.
- [ ] Confirm no runtime context artifacts are accidentally modified.
- [ ] Review `git diff --stat` for unexpected large moves or data changes.

## 9) Documentation Updates

This proposal should not bump the marking package version by itself. The version bump should land with the implementation changes, after the module move and documentation updates are complete.

Documentation checklist for the implementation landing:

- [ ] Update `ai_study_buddy/ARCHITECTURE.md`:
  - [ ] remove `student_review` as a top-level domain layer
  - [ ] state that `marking.review` owns review-domain backend services
  - [ ] keep `review_workspace` as the app surface
- [ ] Update `ai_study_buddy/DATA_MODEL.md`:
  - [ ] change `student_review` ownership references to `marking.review`
  - [ ] preserve `context/student_review_states/**` path and schema name
  - [ ] preserve `context/marking_amendments/**` as marking-owned companion overlays
- [ ] Update `ai_study_buddy/README.md`:
  - [ ] remove top-level `student_review/` description
  - [ ] expand `marking/` description to include review services over marked attempts
  - [ ] keep `review_workspace/` as the frontend/app shell description
- [ ] Update `ai_study_buddy/review_workspace/ARCHITECTURE.md`:
  - [ ] change backend import responsibility from `ai_study_buddy/student_review/` to `ai_study_buddy.marking.review`
  - [ ] correct data ownership section so marking owns amendment overlay semantics
- [ ] Update `ai_study_buddy/review_workspace/README.md`, `SPEC.md`, `DATA_MODEL.md`, and `TESTING.md` where they mention `student_review` as a module owner.
- [ ] Remove `ai_study_buddy/student_review/README.md` as part of deleting the old top-level module.
- [ ] Move useful `student_review/DECISIONS.md` content into this proposal or a new marking review decision note.
- [ ] Update `ai_study_buddy/marking/ARCHITECTURE.md`:
  - [ ] add `review/` as a marking subpackage
  - [ ] document canonical artifact immutability from review flows
  - [ ] document companion state and amendment overlay stores
- [ ] Update `ai_study_buddy/marking/README.md` package scope to include review-domain services.
- [ ] Update `ai_study_buddy/marking/SPEC.md` if it enumerates public subpackages or schemas.
- [ ] Update `ai_study_buddy/marking/TESTING.md` with review-service verification commands.
- [ ] Add an implementation changelog entry under the chosen marking version.
- [ ] Update `Current version` in `ai_study_buddy/marking/README.md` in the same changeset as the changelog entry.

Versioning note:

- Option B removes the old `ai_study_buddy.marking.review` import path, so the changelog must call out the direct relocation explicitly.
- If the old module is treated as internal-only and preflight confirms no in-repository callers remain, a patch bump is acceptable.
- If the old module is later deemed public API, use a minor bump instead.

## 10) Testing Plan

Minimum automated checks:

- [ ] `python3 -m py_compile ai_study_buddy/marking/review/*.py`
- [ ] `python3 -m py_compile ai_study_buddy/review_workspace/backend/app.py`
- [ ] marking tests covering amendment behavior
- [ ] any existing student-review smoke scripts updated to new import paths

Recommended targeted tests to add or update:

- [ ] test that `review_workspace/backend/app.py` includes the `marking.review` router
- [ ] test review-state write still saves under `context/student_review_states/**`
- [ ] test amendment write still saves under `context/marking_amendments/**`
- [ ] test resolved marking payload still overlays amendment state without mutating base artifact
- [ ] test that old `ai_study_buddy.marking.review` code imports are gone

Manual checks:

- [ ] open Review Workspace frontend
- [ ] select a student
- [ ] open a marked attempt
- [ ] confirm attempt and answer image pools load
- [ ] save a review note
- [ ] save an amendment
- [ ] reload and confirm saved state persists

## 11) Risks and Mitigations

### Risk A: Hidden local imports of `ai_study_buddy.marking.review`

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

- [ ] Review-domain source code lives under `ai_study_buddy/marking/review/`.
- [ ] Review Workspace backend imports its router from `ai_study_buddy.marking.review`.
- [ ] Existing API route paths and payload contracts remain stable.
- [ ] Review-state files continue to persist under `context/student_review_states/**`.
- [ ] Amendment files continue to persist under `context/marking_amendments/**`.
- [ ] Canonical `context/marking_results/**` artifacts remain read-only from review flows.
- [ ] Tests or smoke checks cover attempt detail, review-state writes, amendment writes, and resolved payload recomputation.
- [ ] Repository docs no longer present `student_review` as an active top-level domain module.
- [ ] Marking changelog and README version are updated according to the versioning decision.
