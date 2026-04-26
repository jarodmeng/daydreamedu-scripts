# Proposal: Marking Amendment UI

## 1. Executive Summary

This proposal defines the **human amendment layer** for AI marking runs produced by the multi-agent workflow in [8-multi-agent-marking-architecture.md](../../../marking/docs/proposal/8-multi-agent-marking-architecture.md).

Phase 1 improves first-pass accuracy, but it does not remove the need for human review. The remaining errors will cluster around exactly the cases that are hardest for AI:
- messy handwriting or faint scans
- ambiguous page boundaries
- partial-credit judgment calls
- answer-key mismatches
- diagnoses that are directionally right but pedagogically weak

The Amendment UI is therefore not a cosmetic "edit some text" feature. It is the **review control plane** for turning an AI-generated marking artifact into a human-verified one quickly, safely, and with auditability.

The core design decision is:

1. Keep the original AI `marking_result.v1.4.json` as the immutable source artifact for provenance.
2. Store human changes in a separate **amendment overlay artifact**.
3. Let `review_workspace` render a **resolved view** = base marking result + amendment overlay.
4. Recompute resolved scores and display state from the resolved view.

This gives us the speed of inline editing without losing traceability or risking accidental corruption of the base AI output.

## 2. Problem Statement

Today, if the marking agent makes a mistake, the only practical fix is to manually edit raw JSON. That is not good enough for a workflow that is expected to be used repeatedly.

Current pain points:

- **Unsafe:** direct JSON edits can break schema validity.
- **Slow:** the reviewer has to manually find the relevant `result_id` and related fields.
- **Context-switch heavy:** the reviewer must bounce between page images, the report, and a text editor.
- **Non-auditable:** once a file is overwritten, it becomes harder to tell what the AI originally said versus what the human changed.
- **Not confidence-aware:** the current workspace can jump to incorrect/unreviewed items, but it cannot yet prioritize the exact rows the multi-agent system is least confident about.

This problem becomes more important, not less, once the multi-agent architecture lands:

1. The marking system will become faster and more parallel.
2. The absolute number of residual edge-case errors per paper may become small.
3. But those residual errors will be concentrated in high-value, high-ambiguity rows.

That means the review UI should make amendment available exactly where review is already happening, with optional signals that help the reviewer notice ambiguous rows when useful.

## 3. Design Goals

### 3.1 Primary Goals

1. **Fast correction of the final 5-10% of AI mistakes**
2. **Evidence-first review** with the relevant attempt page always visible
3. **Auditability** between AI output and human-amended output
4. **Schema-safe persistence** with server-side validation
5. **Minimal reviewer friction** for repeated "scan -> confirm -> amend -> next" workflows

### 3.2 Non-Goals (v1)

1. Not a full rubric authoring tool
2. Not collaborative multi-user review with real-time merging
3. Not free-form arbitrary JSON editing
4. Not a replacement for the separate `student_review_state` artifact used for student reflections and notes
5. Not a full visual annotation system on top of page images

## 4. Core Product Decision: Overlay, Not Direct Mutation

The first draft of this proposal suggested saving amendments directly back into `marking_result.v1.4.json`. That is simple, but it has hidden costs:

1. It destroys the original AI output.
2. It makes debugging Phase 1 harder because we can no longer see whether the error came from mapping, transcription, grading, or diagnosis.
3. It makes audit/history features much harder later.
4. It increases the chance that an interrupted or partial save leaves the canonical artifact in an inconsistent state.

So the recommended design is:

- `marking_result.v1.4.json`: immutable base artifact produced by AI
- `marking_amendment.v1.json`: human override layer
- `resolved_marking_result`: in-memory backend projection used by `review_workspace`

This approach is consistent with the repository's current separation of concerns:

- canonical marking data lives in the marking artifact
- review progress / notes live in companion artifacts
- app surfaces should not need to hand-edit raw storage formats

## 5. Proposed UX

## 5.1 Where It Lives

The Amendment UI will be built into the existing `review_workspace` application, specifically the right-hand Review panel, rather than as a separate tool.

Why this is the right surface:

1. The left panel already shows the attempt/answer evidence.
2. The bottom navigation already supports review traversal.
3. The workspace already persists separate review-state data.
4. Reviewing and amending are part of the same mental workflow.

## 5.2 Reviewer Workflow

The target loop is:

1. Open a marked attempt.
2. Navigate through the attempt using the normal review flow.
3. Compare the AI extraction against the evidence page whenever the reviewer wants to verify or correct something.
4. Amend any wrong fields inline from the Review panel.
5. See score and displayed row state update immediately.
6. Mark the row reviewed if appropriate.
7. Continue reviewing the attempt as usual.

This is meant to feel like a natural extension of review, not a separate queue-clearing task.

## 5.3 Confidence Signals and Navigation

The amendment workflow does not require a dedicated amendment queue. The primary interaction should remain the existing review flow, with amendment available inline whenever the reviewer decides a change is needed.

If Phase 1 exposes per-row confidence objects and page-map confidence, the workspace can surface them as lightweight review aids:

1. confidence badges on the active question card
2. confidence indicators in the question picker
3. optional navigation helpers such as `Next low confidence`

These are supporting affordances, not the core goal of the amendment feature.

## 5.4 Card Layout for a Single Question

Each active question card should show:

1. `result_id`
2. current resolved outcome and marks
3. base AI value for each editable field
4. amended value when present
5. AI confidence and page-map confidence badges
6. linked attempt page start / mapped evidence
7. a small "changed" indicator when any field has a human override

The reviewer should be able to understand, at a glance:

1. what the AI thought
2. whether the AI itself was unsure
3. what the human changed
4. whether the row is now reviewed

## 5.5 Editable Fields

The following fields should be editable in v1:

1. `question_results[].outcome`
2. `question_results[].earned_marks`
3. `question_results[].max_marks`
4. `question_results[].student_answer`
5. `question_results[].correct_answer`
6. `question_results[].feedback`
7. `question_results[].diagnosis.mistake_type`
8. `question_results[].diagnosis.reasoning`
9. `question_results[].skill_tags`
10. `question_results[].human_note`
11. `context.question_page_map[].attempt_page_start`
12. `context.question_page_map[].confidence`
13. `summary.human_note`

Fields that should remain non-editable in normal mode:

1. `result_id`
2. `scoring_status`
3. base artifact metadata (`created_at`, `generation`, raw telemetry/debug references)

Rationale:

- `result_id` defines row identity and should remain stable.
- `max_marks` may be wrong because it is still AI-detected, so it should be amendable, but with stronger guardrails than ordinary content fields.
- `scoring_status` should only change through explicit advanced workflows, because it affects semantics more deeply than a routine correction.
- generation/provenance fields are not reviewer-edit targets.

To make risk clearer in the UI, editable fields should be treated in three tiers:

1. low-risk content fields: `feedback`, `diagnosis.*`, `human_note`
2. standard scoring/content fields: `student_answer`, `correct_answer`, `earned_marks`, `outcome`, `skill_tags`
3. structural scoring/evidence fields: `max_marks`, `question_page_map.*`

Tier 3 edits should display a stronger visual treatment because they alter the structure of the AI interpretation, not just its explanation.

## 5.6 Edit Interaction Model

Use inline editing, but make the distinction between "viewing" and "overriding" explicit.

Suggested interaction:

1. Default state is read mode.
2. Double-clicking an editable field opens the appropriate editor:
   - dropdown for `outcome`
   - numeric input for `earned_marks` or `max_marks`
   - textarea for long text
   - token editor for `skill_tags`
3. The editor displays:
   - current resolved value
   - original AI value
   - `Revert` action
4. Saving creates or updates an amendment entry for that field.

Using double-click as the default edit trigger reduces accidental entry into edit mode while the reviewer is still scanning the panel, selecting text, or navigating between questions. This is better than silently replacing text in place because it keeps the reviewer aware that they are creating an override, not editing the original AI run.

## 5.7 Save Semantics

The amendment model should be based on **incremental saving**, not a separate attempt-level finalization step.

### Panel-level amendment state

The Review panel should allow the reviewer to make one or more amendment edits locally before deciding whether to keep them.

Recommended behavior:

1. Editing a field updates the Review panel into a dirty/unsaved state.
2. If the panel contains unsaved amendment changes, show a `Save amendment` button.
3. Also show a `Revert amendment` button that discards the unsaved panel changes.
4. `Revert amendment` should restore the panel to the current persisted resolved state sourced from the base `marking_result` plus any already-saved amendment overlay.
5. A visible save indicator should communicate `Unsaved`, `Saving...`, `Saved`, or `Error`.

This gives the reviewer a deliberate checkpoint before persisting changes, which is a better fit for double-click-to-edit and higher-risk structural amendments.

### Reload behavior

There should be no separate `Finalize amended review` button.

Instead:

1. `Save amendment` persists the current panel changes into the amendment overlay.
2. The attempt view continues showing the current in-memory resolved state.
3. Whenever the attempt is loaded fresh in `review_workspace`, the data should be recomputed from:
   - the pristine AI-generated `marking_result`
   - plus all saved amendments
4. If the user wants to confirm the whole attempt as reloaded-from-source truth, they can leave the attempt view and reopen it.

This keeps the mental model simple: saved amendments are already part of the attempt's effective reviewed state, and re-entering the attempt rebuilds the UI from canonical sources.

## 6. Data Model

## 6.1 New Companion Artifact: `marking_amendment.v1`

Recommended path:

- `ai_study_buddy/context/marking_amendments/<student_id>/<subject_context>/<artifact_stem>.json`

Suggested shape:

```json
{
  "schema_version": "marking_amendment.v1",
  "context": {
    "student_id": "emma",
    "subject_context": "singapore_primary_science",
    "attempt_file_id": "attempt_uuid",
    "marking_result_path": "marking_results/emma/singapore_primary_science/<artifact>.json"
  },
  "summary_overrides": {
    "human_note": "Teacher checked tricky open-ended answers."
  },
  "question_amendments": [
    {
      "result_id": "Q4(a)",
      "fields": {
        "earned_marks": 1,
        "outcome": "partial",
        "diagnosis.reasoning": "Student identified the organ correctly but did not explain its function."
      },
      "reviewer_reason": "AI over-awarded full marks for incomplete explanation.",
      "evidence": {
        "attempt_page_start": 3
      },
      "updated_at": "2026-04-24T20:15:00+08:00",
      "updated_by": "review_workspace_ui"
    }
  ],
  "question_page_map_amendments": [
    {
      "result_id": "Q4(a)",
      "attempt_page_start": 3,
      "confidence": "high",
      "updated_at": "2026-04-24T20:15:00+08:00",
      "updated_by": "review_workspace_ui"
    }
  ],
  "review_meta": {
    "updated_at": "2026-04-24T20:15:00+08:00",
    "updated_by": "review_workspace_ui"
  }
}
```

## 6.2 Why a Separate Amendment Artifact

This gives us:

1. a clean diff from AI output to human-reviewed output
2. the ability to revert all human changes
3. a clearer foundation for future analytics such as:
   - "what categories of AI error are most common?"
   - "how often do humans fix page mapping vs diagnosis?"
   - "which subjects still require heavy amendment?"

## 6.3 Resolved View

The backend should merge:

1. base `marking_result`
2. amendment overlay
3. existing `student_review_state`

and return a payload such as:

```json
{
  "marking_result_base": {},
  "marking_result_resolved": {},
  "amendment_state": {},
  "review_state": {}
}
```

The UI should render the resolved view by default while still being able to show original AI values inline.

## 7. Validation Rules

All amendment writes must be validated server-side before persistence.

## 7.1 Field-Level Validation

1. `outcome` must remain within the allowed enum.
2. `max_marks` must be numeric, finite, and non-negative.
3. `earned_marks` must be numeric, finite, non-negative, and not exceed the resolved `max_marks`.
4. `attempt_page_start` must refer to an existing attempt page in the bundle.
5. `question_page_map` amendments must reference an existing `result_id`.
6. `skill_tags` must be an array of strings.
7. Long text fields must be normalized for empty-string vs null handling.

## 7.2 Cross-Field Validation

1. Score-changing edits trigger recomputation of:
   - `summary.earned_marks`
   - `summary.total_marks`
   - `summary.percentage`
2. Mark-allocation edits (`max_marks`) also trigger recomputation of any per-row score display that depends on denominator changes.
3. If `earned_marks == max_marks`, the default expectation is usually `outcome = correct`.
4. If `earned_marks == 0`, the default expectation is usually `outcome = wrong`, unless the row is excluded/disqualified.
5. If a page-map amendment points to a different page, the UI should refresh the active evidence page immediately.

## 7.3 Workflow Validation

1. A row cannot be marked `reviewed` while it has invalid unsaved amendments.
2. Score-changing amendments should require a short reviewer reason.
3. `max_marks` amendments should always require a reviewer reason and should be labeled in the UI as a mark-allocation amendment.
4. `Save amendment` should fail fast if any amendment entry is structurally invalid.

## 8. Relationship to Phase 1 Multi-Agent Outputs

The Amendment UI should not be designed in isolation. It should explicitly consume the extra structure that Phase 1 produces.

## 8.1 Inputs from Phase 1 That Matter

1. per-question confidence from the Fast-Pass Grader
2. corrected page maps returned by Deep-Dive agents
3. debug traces for mapper / grader / remediation stages
4. telemetry counts such as fast-pass vs deep-dive rows

## 8.2 How the UI Uses Them

1. **Badging:** confidence chips can explain when the AI was unsure.
2. **Navigation support:** confidence can optionally power helper actions such as `Next low confidence`.
3. **Debugging:** when a reviewer sees an odd row, they can inspect whether the failure came from mapping, transcription, or grading.
4. **Trust calibration:** rows with high confidence and correct outcomes can be batch-reviewed more aggressively later if we add that feature.

## 9. Review Workspace Changes

## 9.1 Backend

Add new capabilities to `review_workspace` backend:

1. load amendment artifact if present
2. materialize resolved marking result
3. expose base vs resolved values to frontend
4. validate amendment writes
5. persist amendment artifact separately from `student_review_state`
6. rebuild resolved attempt payloads from base artifact plus saved amendments on each fresh load

Recommended endpoints:

1. keep existing `PUT /review-state` for review progress and notes
2. add `PUT /amendments` for amendment overlay persistence

This keeps review-progress writes distinct from factual grading overrides.

## 9.2 Frontend

Main changes in the right-hand Review panel:

1. replace static question detail text with field components that support:
   - read mode
   - edit mode
   - original vs amended display
   - revert action
2. add save-state indicator
3. add confidence indicators and optional navigation helpers
4. visually distinguish:
   - AI original
   - amended current value
   - reviewed status
5. update summary score live when resolved fields change

## 9.3 Navigation

Bottom bar should evolve from generic navigation into review operations:

1. `Mark reviewed`
2. `Next incorrect`
3. `Next unreviewed`
4. `Revert question`

Later, if the workflow proves stable, we can add:

1. `Mark reviewed and next`
2. optional helpers such as `Next low confidence` or `Next partial`

## 10. Auditability and Provenance

This proposal should preserve three separate truths:

1. **What the AI originally produced**
2. **What the human changed**
3. **What the currently resolved final result is**

That separation is important for:

1. debugging the multi-agent system
2. reviewer trust
3. future model evaluation
4. safe reconstruction of the resolved attempt view

Minimum audit features for v1:

1. per-amendment `updated_at`
2. per-amendment `updated_by`
3. reviewer reason for score-changing edits
4. field-level revert
5. question-level revert
6. clear documentation on whether attempt-level `revert all amendments` is included in v1 or deferred

## 11. Failure Modes and Safeguards

Potential failure modes:

1. reviewer enters invalid marks
2. reviewer changes page map and loses place in the viewer
3. base artifact and amendment artifact drift out of sync
4. the reloaded attempt view does not reflect the latest saved amendments
5. the UI makes it unclear whether a displayed value is AI-generated or human-amended

Safeguards:

1. server-side validation on every amendment write
2. immediate score recomputation in the resolved view
3. strict pairing to the target `marking_result_path`
4. base-value display beside overridden fields
5. explicit changed badges and revert controls
6. always rebuild a fresh resolved view from base artifact plus saved amendment overlay when the attempt is opened

## 12. Implementation Plan

The work should be delivered in small, testable slices. The recommended implementation order is:

1. backend schema and merge logic
2. backend amendment write API
3. frontend resolved-view rendering
4. frontend edit/save/revert interactions
5. confidence-display enhancements
6. reload-consistency hardening and polish

This order keeps the data model stable before the UI depends on it.

### Milestone 1: Core Amendment Workflow (Phases A-F)

Milestone 1 should now include the full path from backend contract through usable save/reload behavior:

1. Phase A: backend overlay contract
2. Phase B: backend merge and validation logic
3. Phase C: backend API surface
4. Phase D: frontend resolved-view read path
5. Phase E: frontend edit interaction
6. Phase F: save/rebuild lifecycle

This milestone should end with a reviewer being able to:

1. open a marked attempt
2. see base AI values and resolved amended values distinctly
3. edit supported fields safely in the Review panel
4. save an amendment overlay without mutating the base artifact
5. reload the attempt and see the same resolved state reconstructed from source

#### Milestone 1 sequencing

Recommended execution order inside the milestone:

1. lock Phase A docs and contracts first
2. build Phase B merge/validation helpers with unit tests before wiring routes
3. implement Phase C read/write API changes and stabilize payloads
4. switch frontend reads to resolved payloads in Phase D before adding editing
5. add edit/save/revert interactions in Phase E
6. harden persistence and reload behavior in Phase F

#### Milestone 1 implementation checklist

##### Track 1: Contract and docs lock

- [x] Freeze the canonical `marking_amendment.v1` artifact path under `ai_study_buddy/context/marking_amendments/<student>/<subject>/<artifact>.json`.
- [x] Freeze the top-level artifact keys:
  - `schema_version`
  - `context`
  - `summary_overrides`
  - `question_amendments`
  - `question_page_map_amendments`
  - `review_meta`
- [x] Freeze the editable field allowlist for `question_amendments[].fields`.
- [x] Freeze normalization rules for nullable text fields (`null` vs `""`).
- [x] Freeze when `reviewer_reason` is required:
  - score-changing edits
  - always for `max_marks`
- [x] Decide the write contract for `updated_at` and `updated_by` stamping.
- [x] Decide Milestone 1 save payload shape:
  - recommended: active-panel payload, not whole-attempt payload
- [x] Update `review_workspace/DATA_MODEL.md` with:
  - amendment artifact shape
  - resolved GET payload shape
  - amendment PUT payload/response shape
- [x] Update `review_workspace/SPEC.md` with:
  - new `PUT /api/student/attempts/{attempt_id}/amendments`
  - revised `GET /api/student/attempts/{attempt_id}` payload
  - validation and error behavior

##### Track 2: Backend domain helpers

- [x] Create a backend module dedicated to amendment loading, normalization, merge, and validation.
- [x] Add a helper to locate the amendment artifact path from the canonical marking artifact context.
- [x] Add a helper to load and normalize the saved amendment artifact when present.
- [x] Add a helper to return an empty/default amendment state when absent.
- [x] Add a helper to merge question-level overrides by `result_id`.
- [x] Add a helper to merge summary overrides.
- [x] Add a helper to merge `question_page_map` amendments by `result_id`.
- [x] Add a helper to preserve original AI values for frontend diff display.
- [x] Add a helper to recompute:
  - `summary.earned_marks`
  - `summary.total_marks`
  - `summary.percentage`
- [x] Add a helper to project `attempt_page_start` back onto resolved question rows for frontend use.

##### Track 3: Backend validation

- [x] Validate that amendment `result_id`s exist in base `question_results`.
- [x] Validate that page-map amendment `result_id`s exist in base `context.question_page_map` or can be joined by base row identity.
- [x] Validate `earned_marks` and `max_marks` as finite non-negative numbers.
- [x] Validate `earned_marks <= resolved max_marks`.
- [x] Validate `outcome` against the canonical enum.
- [x] Validate page-map `confidence` against the canonical enum.
- [x] Validate `skill_tags` as an array of strings.
- [x] Validate `attempt_page_start` against actual attempt image pages in the bundle.
- [x] Validate that unsupported keys in `fields` are rejected explicitly.
- [x] Validate `reviewer_reason` presence for score-changing edits.
- [x] Return structured validation errors with stable keys the frontend can map to fields.

##### Track 4: Backend API integration

- [x] Extend the attempt detail read path to return:
  - `marking_result_base`
  - `marking_result_resolved`
  - `amendment_state`
  - `review_state`
- [x] Keep existing review-state persistence unchanged and isolated from amendment writes.
- [x] Implement `PUT /api/student/attempts/{attempt_id}/amendments`.
- [x] Make amendment writes load base artifact, validate payload, persist overlay, and return refreshed resolved state.
- [x] Ensure save responses contain enough data for the frontend to:
  - clear dirty state
  - refresh per-field saved values
  - refresh summary totals
  - refresh evidence page mapping
- [x] Confirm non-marked attempts still behave correctly and reject amendment writes cleanly.

##### Track 5: Frontend resolved read path

- [x] Refactor frontend types so base, resolved, and amendment payloads are explicit instead of overloading `marking_result`.
- [x] Decide whether to keep `App.tsx` monolithic for Milestone 1 or extract:
  - review field row component
  - amendment editor component
  - save state indicator component
- [x] Render resolved values by default across:
  - score summary
  - active question card
  - question picker state
- [x] Show original AI value beside the resolved value when a field is amended.
- [x] Add a changed indicator at least at question level for saved overrides.
- [x] Update evidence image selection to follow resolved page-map values.
- [x] Keep non-amended questions visually unchanged enough that normal review remains fast.

##### Track 6: Frontend edit and local panel state

- [x] Introduce local amendment draft state separate from persisted amendment state.
- [x] Scope unsaved draft state to the active question/panel.
- [x] Add explicit read mode vs edit mode per field.
- [x] Support editor types for:
  - `outcome`
  - `earned_marks`
  - `max_marks`
  - text fields
  - `skill_tags`
  - page-map fields
- [x] Enter edit mode on double-click as proposed.
- [x] Show original AI value inside edit affordances when relevant.
- [ ] Add inline client-side validation for obvious failures before save.
- [x] Add panel-level save status:
  - `Unsaved`
  - `Saving...`
  - `Saved`
  - `Error`
- [ ] Show `Save amendment` only when local draft differs from persisted amendment state.
- [ ] Show `Revert amendment` only when local draft differs from persisted amendment state.
- [x] Ensure switching questions does not leak unsaved draft state into another row.

##### Track 7: Reload and persistence hardening

- [x] On successful save, replace local persisted amendment state with the server response.
- [x] Clear dirty state only after save success.
- [x] Preserve unsaved draft state on save failure.
- [x] Surface backend validation errors inline without dropping current edits.
- [x] Ensure leaving and reopening an attempt performs a fresh GET and rebuilds UI state from canonical sources.
- [x] Ensure reloaded evidence image selection matches resolved page-map data.
- [ ] Stamp and surface `review_meta.updated_at` / `updated_by` from the saved overlay.

##### Track 8: Milestone 1 test checklist

- [x] Backend unit tests for:
  - valid overlay merge
  - invalid `result_id`
  - invalid `earned_marks`
  - invalid page-map page
  - recomputed totals and percentage
- [ ] Backend API tests for:
  - successful amendment save
  - rejected invalid amendment save
  - fresh GET includes base + resolved + amendment state
- [ ] Frontend tests for:
  - resolved values render correctly
  - changed badge visibility
  - double-click opens correct editor
  - save clears dirty state on success
  - revert restores persisted resolved state
- [ ] End-to-end/manual verification for:
  - amend score
  - see totals update
  - change page map
  - save
  - reopen attempt
  - confirm resolved reconstruction is stable

##### Milestone 1 exit criteria

- [x] Base `marking_result` remains read-only throughout review workspace flows.
- [x] Human amendments persist only to `marking_amendment.v1`.
- [x] Attempt detail responses provide distinct base and resolved marking payloads.
- [x] Reviewers can edit, save, revert unsaved changes, and reload without ambiguity.
- [x] Score totals and evidence mapping update from resolved data, not stale frontend-only state.

### Phase A: Backend Overlay Contract

Goal: define the amendment artifact and the core merge rules before changing the UI.

Primary files likely involved:

- `ai_study_buddy/review_workspace/backend/app.py`
- `ai_study_buddy/review_workspace/DATA_MODEL.md`
- `ai_study_buddy/review_workspace/SPEC.md`
- new backend helper module(s) under `ai_study_buddy/review_workspace/backend/` or shared domain logic if that proves cleaner

Checklist:

- [ ] Define the `marking_amendment.v1` artifact shape and persistence path.
- [ ] Decide whether the amendment schema lives only in Review Workspace first or also gets a formal marking-side schema contract.
- [ ] Define top-level sections clearly:
  - `context`
  - `summary_overrides`
  - `question_amendments`
  - `question_page_map_amendments`
  - `review_meta`
- [ ] Define allowed field keys in `question_amendments[].fields`.
- [ ] Define how `reviewer_reason` is stored and when it is required.
- [ ] Define how null vs empty-string normalization works for amended text fields.
- [ ] Define how timestamps and `updated_by` are stamped on every saved amendment write.
- [ ] Document the artifact in `review_workspace/DATA_MODEL.md`.
- [ ] Document the route contract changes in `review_workspace/SPEC.md`.

Acceptance criteria:

- [ ] A maintainer can read the docs and know exactly what the amendment JSON looks like.
- [ ] The schema is specific enough that frontend and backend can be built against it without guesswork.

### Phase B: Backend Merge and Validation Logic

Goal: be able to load base marking data plus saved amendments and produce one resolved attempt payload safely.

Checklist:

- [ ] Implement a helper to load the amendment artifact if present.
- [ ] Implement a helper to produce the resolved marking result from:
  - base `marking_result`
  - saved amendment overlay
- [ ] Merge question-level overrides by `result_id`.
- [ ] Merge summary-level overrides such as `summary.human_note`.
- [ ] Merge page-map amendments by `result_id`.
- [ ] Recompute resolved summary totals after score-affecting changes.
- [ ] Recompute resolved percentage after score-affecting changes.
- [ ] Preserve access to original AI values so the frontend can show original vs amended values.
- [ ] Validate that all amendment `result_id`s exist in the base artifact.
- [ ] Validate that amended page mappings reference valid attempt pages.
- [ ] Validate `earned_marks <= resolved max_marks`.
- [ ] Validate `max_marks >= 0`.
- [ ] Validate enum fields such as `outcome` and page-map `confidence`.
- [ ] Fail writes with structured validation errors the frontend can surface cleanly.

Acceptance criteria:

- [ ] Given a base artifact and amendment overlay, the backend returns a deterministic resolved payload.
- [ ] Invalid amendments are rejected before they can be persisted.

### Phase C: Backend API Surface

Goal: expose explicit amendment persistence separately from review-progress persistence.

Checklist:

- [ ] Keep existing `PUT /api/student/attempts/{attempt_id}/review-state` behavior unchanged for notes/review progress.
- [ ] Add `PUT /api/student/attempts/{attempt_id}/amendments`.
- [ ] Define the request body shape for saving panel amendments.
- [ ] Decide whether the payload should save:
  - only the active question/panel delta
  - or the full current unsaved panel state
- [ ] Return the saved amendment state and refreshed resolved marking result in the response.
- [ ] Ensure save responses include enough data for the frontend to clear dirty state immediately.
- [ ] Ensure the `GET /api/student/attempts/{attempt_id}` payload includes:
  - `marking_result_base`
  - `marking_result_resolved`
  - `amendment_state`
  - existing `review_state`
- [ ] Keep backward compatibility for existing consumers where feasible, or document the breaking payload change clearly.

Acceptance criteria:

- [ ] The frontend can load an attempt, save an amendment, and refresh local state without needing undocumented assumptions.

### Phase D: Frontend Resolved-View Read Path

Goal: teach the Review panel to display resolved values while still exposing original AI output.

Primary files likely involved:

- `ai_study_buddy/review_workspace/frontend/src/App.tsx`
- possibly new React components under `ai_study_buddy/review_workspace/frontend/src/`

Checklist:

- [ ] Update frontend types to include:
  - base marking result
  - resolved marking result
  - amendment state
- [ ] Decide whether to keep one large `App.tsx` implementation or extract Review panel components first.
- [ ] Render resolved values by default in the active question card.
- [ ] Show original AI values alongside amended values when an override exists.
- [ ] Add a visible changed state per field or per row.
- [ ] Show whether the current question has any saved amendment.
- [ ] Ensure summary score display reads from resolved data, not base data.
- [ ] Ensure page-map amendments update the evidence image selection logic correctly.

Acceptance criteria:

- [ ] A reviewer can tell what the AI originally said and what the current saved amendment says without ambiguity.

### Phase E: Frontend Edit Interaction

Goal: add safe inline amendment editing to the Review panel.

Checklist:

- [ ] Introduce field components that support read mode and edit mode.
- [ ] Make editable fields enter edit mode on double-click.
- [ ] Support the correct editor per field type:
  - select/dropdown for enums
  - numeric input for marks
  - textarea for long text
  - token/tag editor for `skill_tags`
- [ ] Keep non-editable fields visually distinct from editable ones.
- [ ] Show original AI value inside the editor when editing an already-amended field.
- [ ] Add inline validation before save where practical.
- [ ] Track dirty/unsaved state at panel level.
- [ ] Show `Save amendment` only when the panel has unsaved changes.
- [ ] Show `Revert amendment` only when reverting would do something meaningful.
- [ ] Make `Revert amendment` discard current unsaved edits and restore the current persisted resolved state.
- [ ] Keep edit state isolated so switching questions does not silently mutate a different row.

Acceptance criteria:

- [ ] A reviewer can enter edit mode intentionally, make multiple changes, save them, or revert them without confusion.

### Phase F: Save/Rebuild Lifecycle

Goal: make saved amendments feel persistent and predictable across reloads.

Checklist:

- [ ] On successful `Save amendment`, update local amendment state from the server response.
- [ ] Clear dirty state only after the save succeeds.
- [ ] Keep failed saves from overwriting local unsaved edits.
- [ ] Surface save errors in the panel without losing current draft values.
- [ ] When the user leaves and reopens an attempt, fetch fresh data and rebuild the UI from:
  - base marking result
  - saved amendment overlay
- [ ] Ensure the reopened attempt view matches the last successfully saved amendment state.
- [ ] Stamp `review_meta.updated_at` and `updated_by` on successful saves.

Acceptance criteria:

- [ ] Reloading the attempt never depends on stale in-memory frontend state.
- [ ] The same saved amendment produces the same resolved UI after reload.

### Phase G: Confidence and Debug-Signal Integration

Goal: use Phase 1 confidence/debug signals as supportive context without making them the core workflow.

Checklist:

- [ ] Decide the exact payload shape for per-question confidence in the resolved attempt response.
- [ ] Expose page-map confidence where available.
- [ ] Add confidence badges on the active question card.
- [ ] Add confidence indicators in the question picker.
- [ ] Optionally add navigation helpers such as `Next low confidence` behind a lightweight feature flag or later-phase toggle.
- [ ] Ensure the absence of confidence data degrades gracefully.
- [ ] Decide whether any debug-trace linkage should be visible in v1 or deferred.

Acceptance criteria:

- [ ] Confidence data is helpful when present and non-blocking when absent.

### Phase H: Audit and Revert Depth

Goal: implement the minimum auditability promised earlier in the proposal.

Checklist:

- [ ] Support field-level revert within the editor.
- [ ] Support question-level revert of saved amendments for the active question.
- [ ] Define whether attempt-level `revert all amendments` is included in v1 or deferred.
- [ ] Ensure revert actions update resolved totals and resolved display state immediately.
- [ ] Preserve enough metadata to know when and by whom an amendment was last saved.

Acceptance criteria:

- [ ] Reviewers can safely undo amendments without hand-editing JSON.

### Phase I: Documentation and Rollout

Goal: leave the feature documented well enough that future changes do not reintroduce ambiguity.

Checklist:

- [ ] Update `review_workspace/SPEC.md` with new API routes and payload shapes.
- [ ] Update `review_workspace/DATA_MODEL.md` with amendment artifact and resolved payload structure.
- [ ] Update `review_workspace/README.md` or `TESTING.md` if new manual test steps are needed.
- [ ] Add implementation notes about reload behavior and the lack of a `Finalize amended review` button.
- [ ] Add screenshots or UI notes later if the feature becomes large enough to justify them.

Acceptance criteria:

- [ ] A future maintainer can understand the save model, reload model, and overlay model from docs alone.

### Milestone 2: Confidence, Auditability, and Rollout (Phases G-I)

Milestone 2 should cover the remaining phases after the core amendment workflow is stable:

1. Phase G: confidence and debug-signal integration
2. Phase H: audit and revert depth
3. Phase I: documentation and rollout

This milestone does not need the same level of implementation detail up front because it depends on:

1. the exact confidence/debug payloads exposed by the multi-agent marking workflow
2. what we learn from Milestone 1 reviewer behavior
3. whether broader revert actions such as attempt-level reset are worth shipping in v1

#### Milestone 2 lightweight plan

##### Phase G

- [ ] Finalize the contract for per-question confidence and any debug-link metadata.
- [ ] Surface confidence badges in the active question card and question picker.
- [ ] Add optional navigation helpers such as `Next low confidence` only if they prove useful after Milestone 1.
- [ ] Make all confidence UI fully optional when upstream data is absent.

##### Phase H

- [ ] Add field-level revert for already-saved amendments.
- [ ] Add question-level revert for the active question.
- [ ] Decide whether attempt-level `revert all amendments` ships or stays deferred.
- [ ] Preserve and expose enough metadata to support auditability without exposing raw storage details.

##### Phase I

- [ ] Update `SPEC.md`, `DATA_MODEL.md`, and user-facing review workspace docs to match shipped behavior.
- [ ] Add testing notes and manual QA steps for amendment save/reload/revert behavior.
- [ ] Capture screenshots or short UI notes if the amended Review panel becomes materially more complex.

#### Milestone 2 exit criteria

- [ ] Confidence signals are helpful when present and invisible when absent.
- [ ] Saved amendments can be safely undone at the shipped scope.
- [ ] Documentation matches the final overlay/save/reload mental model.

## 13. Testing Strategy

### Backend Tests

1. valid amendment overlay merges correctly
2. invalid `earned_marks` is rejected
3. invalid `result_id` amendment is rejected
4. page-map amendment updates resolved question mapping
5. summary totals recompute correctly after amendments

### Frontend Tests

1. double-click opens the correct edit control
2. `Save amendment` persists dirty panel changes correctly
3. `Revert amendment` restores the panel to the current persisted resolved state
4. changed badge appears only when override exists
5. confidence badges and optional helper navigation render correctly when confidence data is present

### End-to-End Tests

1. open a marked attempt with confidence data
2. amend a wrong score
3. see total score update immediately
4. mark question reviewed
5. leave the attempt view and reopen it
6. confirm resolved values persist and reload from pristine marking result plus saved amendments

## 14. Recommendation

Proceed with the Amendment UI as a **review + override system**, not as direct JSON editing.

The most important product decision is to treat human amendments as a first-class artifact layer with:

1. inline UX in `review_workspace`
2. separate persisted overlay data
3. server-side validation
4. resolved-view rendering
5. optional confidence-aware hints driven by the multi-agent architecture

That gives us a workflow that is fast for humans, safe for data, and useful for improving the AI system itself.
