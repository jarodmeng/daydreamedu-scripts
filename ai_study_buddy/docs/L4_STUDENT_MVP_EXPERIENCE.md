# AI Study Buddy — Student-Facing MVP Experience

> Status: **Proposal (`v0.1`)** — implementation-oriented MVP design for the first student UI.
>
> Related docs: [USER_EXPERIENCE](./L3_USER_EXPERIENCE.md), [MARKING_RESULT_ARTIFACT](./L4_MARKING_RESULT_ARTIFACT.md), [INGESTION_PIPELINE](./L4_INGESTION_PIPELINE.md)

---

## Why This L4 Exists

`L3_USER_EXPERIENCE.md` describes the long-term "three faces" product direction (kid, parent, admin).  
This L4 narrows scope to the **first student-facing MVP**, focused on one immediate value loop:

1. Student picks their name from a student picker.
2. Student sees their uploaded GoodNotes completion files ("my workings").
3. Student sees whether marking is ready.
4. Student opens marking details when available.

This turns the existing JSON-first marking pipeline into visible student value instead of back-office output only.

---

## MVP Product Goal

Deliver a reliable "Work + Marking Inbox" for each student:

- **Workings visibility:** Student can see their own completion attempts in one place.
- **Marking visibility:** Student can immediately see whether each attempt is `marked`, `processing`, or `not started`.
- **Learning feedback visibility:** Student can open marked attempts and review per-question outcomes.

Non-goal for this MVP: full tutor chat, quest board, parent controls, and ingestion-review tooling.

---

## User and Access Model (MVP)

Primary user: a selected student profile (for example `winston`, `emma`, `abigail`).

MVP access rules:

1. Student sees **only** attempts owned by the currently selected student profile.
2. Student can read:
   - attempt metadata
   - marking summary
   - per-question rows from canonical marking JSON
3. Student cannot mutate marking results from this UI.

Session implementation for MVP:

- No proper sign-in flow is required.
- Use a student picker menu to set the active student session locally.
- Persist the selected student in local storage for convenience.

---

## Information Architecture

Three student screens are enough for MVP:

1. **Student Picker / Session Gate**
2. **My Workings** (attempt list)
3. **Attempt Detail** (workings + marking result)

Navigation model:

- Default post-selection route: `My Workings`.
- `My Workings` -> tap one attempt -> `Attempt Detail`.
- Back navigation returns to filtered list state.

---

## Screen Design and Behavior

### 1) Student Picker / Session Gate

Purpose: establish the active student profile before any data fetch.

MVP UI:

- simple student dropdown/menu (`Winston`, `Emma`, `Abigail`)
- clear active student label after selection
- explicit "switch student" action

Failure states:

- no student selected: show picker prompt
- invalid/unknown selected student id: reset selection and ask user to pick again

### 2) My Workings (Attempt List)

Purpose: show all completion attempts relevant to the student.

Each row should display:

- attempt title (normalized filename or friendly title when available)
- subject context (for example `singapore_primary_math`)
- attempt timestamp
- marking status badge:
  - `Marked`
  - `Marking in progress`
  - `No marking yet`
- quick summary when marked: `score`, `percentage`

Suggested default sort:

- newest attempt first

Suggested filters (lightweight MVP):

- subject context
- marking status

Empty states:

1. no attempts yet: "No workings uploaded yet."
2. attempts exist but none marked: "Marking not ready yet."

### 3) Attempt Detail (Workings + Marking)

Purpose: one place to review the attempt and feedback.

Sections:

1. **Attempt context**
   - student
   - subject context
   - attempt file path/name
   - template/answer linkage info (human-readable)
2. **Marking summary**
   - total marks, earned marks, percentage
   - overall assessment
3. **Question results table**
   - result id (for example `Q3(b)`)
   - outcome icon/text (`correct`, `partial`, `wrong`, `disqualified`)
   - student answer
   - correct answer
   - marks earned / max
   - concise feedback
4. **Skill and diagnosis panel** (collapsible in MVP)
   - skill tags
   - mistake type and reasoning

Data-state handling:

- if marking not available, show attempt context + "marking pending" card
- if partial/broken artifact, show available fields and a safe fallback message

---

## Data Contract for the Frontend (MVP)

Canonical source remains filesystem JSON artifact (`marking_result.v1`):

- `ai_study_buddy/context/marking_results/<student>/<subject_context>/*.json`

Derived reports remain optional read-only companion:

- `ai_study_buddy/context/learning_reports/<student>/<subject_context>/*.md`

MVP frontend should consume a thin backend API that adapts storage details into stable response shapes.

### API 1: List Student Attempts

`GET /api/student/attempts`

Response fields (MVP):

- `attempt_id` (stable key)
- `title`
- `student_id`
- `subject_context`
- `attempt_timestamp`
- `marking_status` (`marked` | `processing` | `not_started`)
- `summary` (nullable): `earned_marks`, `total_marks`, `percentage`

### API 2: Attempt Detail

`GET /api/student/attempts/{attempt_id}`

Response fields (MVP):

- `context`
- `summary` (nullable)
- `question_results` (possibly empty)
- `generation` metadata
- `marking_status`

### API 3: Student Profiles (optional but useful)

`GET /api/students`

Response fields:

- `students`: list of `{ student_id, display_name, grade_level }`

---

## Marking Status Resolution Rules

To avoid ambiguous UX, define one deterministic status per attempt:

1. `marked`:
   - a valid `marking_result.v1` JSON exists for the attempt
2. `processing`:
   - pipeline is running or queued for this attempt (if job metadata exists)
3. `not_started`:
   - no marking artifact and no active job

If multiple JSON artifacts exist for one attempt basename:

- pick newest by timestamp suffix as default visible result
- expose "previous marking runs" later (out of MVP)

---

## MVP Technical Delivery Plan

### Phase A — Backend read APIs

1. Add student-scoped list/detail endpoints.
2. Implement adapter from `marking_result.v1` to API response.
3. Add status-resolution logic and tests.

### Phase B — Frontend shell

1. Build student picker gate + active-student session guard.
2. Build `My Workings` list view with status badges.
3. Build `Attempt Detail` view with summary + question table.

### Phase C — UX polish and reliability

1. Add loading/empty/error states.
2. Add basic filters in list view.
3. Add telemetry events for first usage insights.

---

## MVP Acceptance Criteria

1. User can pick a student and see only that student's attempts.
2. At least one marked attempt displays score and per-question rows correctly.
3. Unmarked attempts show clear pending/not-started states.
4. Attempt detail loads without exposing raw internal file-system complexity to student UI.
5. No write operations are allowed from student UI to marking artifacts.

---

## Risks and Guardrails

1. **Cross-student leakage risk:** strict server-side scoping by selected `student_id` is mandatory.
2. **Schema drift risk:** frontend must tolerate missing optional fields and unknown enum values.
3. **Pipeline latency risk:** status messaging must set expectation ("marking may take time").
4. **Interpretation risk for children:** use simple, encouraging labels over technical diagnostics by default.

---

## Out of Scope (Explicit)

1. Parent dashboard and controls.
2. Admin ingestion review interface.
3. Quest board, tutor chat, hint ladder.
4. Editing/re-marking from UI.
5. Deep analytics, gamification, or notifications.

---

## Open Decisions

1. Should student picker options be hardcoded in MVP or fetched from registry-backed metadata?
2. Should the MVP prioritize mobile portrait (iPad) or desktop/tablet landscape first?
3. Should student-facing detail show full diagnosis text by default, or keep it collapsed behind "See explanation"?
4. Do we need a "teacher/parent view-as student" capability in MVP, or can it wait?

---

## Suggested Next Implementation Doc

After alignment on this L4 UX scope, create a follow-up engineering doc:

- `L4_STUDENT_MVP_BACKEND_FRONTEND_PLAN.md`

It should pin:

1. exact route contracts
2. component tree and state model
3. API-to-artifact mapping details
4. test plan (API + UI)
