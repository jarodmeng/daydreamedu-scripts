# AI Study Buddy — Review Workspace

> Status: **Proposal (`v0.2`) with active implementation tracking**.
>
> Scope lock note (April 23, 2026): current delivery phase is **single-student alpha** focused on Student Picker, My Work index, and Review Workspace core loop. Non-core expansions remain deferred until this slice is stable.
>
> Related docs: [USER_EXPERIENCE](./L3_USER_EXPERIENCE.md), [MARKING_RESULT_ARTIFACT](./L4_MARKING_RESULT_ARTIFACT.md), [INGESTION_PIPELINE](./L4_INGESTION_PIPELINE.md), [ROADMAP](./L1_ROADMAP.md)

---

## Why This Proposal Exists

The previous version of this doc framed the MVP as a read-only **"Work + Marking Inbox"**. That is too weak for the current operational problem and too narrow for the longer-term AI Study Buddy architecture.

Current reality in the repo:

1. Canonical marking already exists as structured JSON under `ai_study_buddy/context/marking_results/**`.
2. The current review workflow still relies heavily on opening markdown learning reports in Cursor beside the underlying completion files.
3. That workflow does not scale well across Winston, Emma, and Abigail because it:
   - forces constant switching between report text and actual workings
   - keeps Jarod as the interpreter/bottleneck during review
   - treats the markdown report as the practical interface, even though the markdown is already a derived artifact

Audit context as of **2026-04-22** (see [`notes/completion_files_registry_audit.md`](./notes/completion_files_registry_audit.md)):

- **213** primary completion files in the audit population
- **139** audit completions with `has_marking`
- **140** marking JSON files on disk under `context/marking_results/**`

The current artifact shape is strong enough to support a better first product surface immediately. Real canonical marking artifacts already include fields such as:

- `context.attempt_file_id`
- `context.template_file_id`
- `context.unit_label`
- `context.book_label`
- `context.template_attempt_group_id`
- `context.attempt_sequence`
- `context.marking_asset`
- `context.is_partial`
- `summary.*`
- `question_results[].result_id`
- `question_results[].student_answer`
- `question_results[].correct_answer`
- `question_results[].skill_tags`
- `question_results[].diagnosis`

And with the new `marking_result.v1.4` pilot, we now also have:

- `context.question_page_map[]` with `result_id -> attempt_page_start` mapping

Pilot anchor for alpha testing:

- `ai_study_buddy/context/marking_results/winston/singapore_primary_math/PP Math PSLE Part D P6 Topical Practice Percentage__20260421_194508.json`

So the right MVP is not "a better markdown report viewer."  
It is **Review Workspace**, built on canonical attempt + marking data.

This aligns better with the broader AI Study Buddy vision:

- **Question-centric** rather than report-centric
- **Learning loop** rather than passive reading
- **Structured memory foundation** rather than one-off documents
- **Future-compatible** with planner, tutor, parent summary, and gamification layers

---

## Scope

### In Scope

1. A student-scoped **attempt index** built from registered completion files.
2. A student-facing **review workspace** for one attempt at a time.
3. Rendering of the **latest canonical marking result** for a completion attempt.
4. Showing the student's **actual source work** through attempt/answer document viewers, not markdown alone.
5. A persisted **review-note layer** for question-level, attempt-level, and student-subject-level notes.
6. Support for current artifact semantics:
   - `marking_result.v1.x` read compatibility (`v1` / `v1.1` / `v1.2` / `v1.3` / `v1.4`)
   - multiple attempts per template (`template_attempt_group_id`, `attempt_sequence`)
   - partial marking (`context.is_partial`)
   - optional `marking_asset`
   - `context.question_page_map` for active-question page tuning
7. A thin backend API that hides file-system details from the frontend.

### Out of Scope

1. Tutor chat, hint ladder, or Socratic tutoring loop.
2. Quest board as the primary home screen.
3. Parent dashboard and admin ingestion/review tooling.
4. Full question-object extraction with bounding boxes and per-question image crops.
5. Editing marking results from the student UI.
6. Automated re-marking or workflow orchestration for marking jobs.
7. Proper production auth; MVP may still use local student selection.

---

## Design

### Core Product Decision

The first student-facing surface is a **Review Workspace**, not a report reader and not a blank tutor chat.

The product loop is:

1. Student selects self
2. Student sees all their attempts in one place
3. Student opens one attempt
4. Student reviews marked questions while seeing the real source work
5. Student records their own reflections

This loop is immediately valuable even before questing, chat tutoring, or question-object extraction are complete.

### Primary Domain Objects

The MVP should explicitly model four objects:

1. **Student**
2. **Attempt**
3. **Marking Result**
4. **Student Review State**

The frontend should not think in markdown files.

### Canonical Data Sources

#### 1) Completion registry

Source of truth for attempts:

- `PdfFileManager`
- student-scoped completion files (`is_template=False`, non-`raw`)

This is the authoritative source for "what work exists for this student."

#### 2) Canonical marking artifact

Source of truth for scoring and diagnosis:

- `ai_study_buddy/context/marking_results/<student>/<subject_context>/*.json`
- schema: `marking_result.v1.x` (current writer default: `v1.4`)

This is the authoritative source for:

- score
- correctness
- diagnosis
- skill tags
- book/unit/answer linkage
- attempt-group metadata

Markdown learning reports remain derived read-only companions only.

#### 3) New companion review-state artifact

The review-note layer should **not** overwrite the canonical marking JSON.

Reason:

- `summary.human_note` and `question_results[].human_note` in canonical `marking_result` artifacts are closer to tutor/parent/admin notes
- review notes in the student-facing workspace are a different kind of data with different semantics and future uses
- keeping them separate preserves the factual integrity of the marking artifact

Proposed path:

`ai_study_buddy/context/student_review_states/<student>/<subject_context>/<artifact_basename>.json`

Proposed schema identifier:

`student_review_state.v1`

This companion artifact should support multiple note scopes and explicit note authorship.

Supported MVP note scopes:

- `question`
- `attempt`
- `student_subject`

Supported MVP author roles:

- `student`
- `parent`
- `teacher`

Suggested MVP shape:

```json
{
  "schema_version": "student_review_state.v1",
  "created_at": "2026-04-22T11:10:00+08:00",
  "updated_at": "2026-04-22T11:18:00+08:00",
  "context": {
    "student_id": "winston",
    "subject_context": "singapore_primary_math",
    "attempt_file_id": "d88d78e1-0844-44c4-be4e-230651166612",
    "marking_result_path": "marking_results/winston/singapore_primary_math/PP Math PSLE Part D P6 Topical Practice Ratio__20260422_105703.json",
    "template_attempt_group_id": "winston::ec15795f-9da5-463f-89c5-fd8e7fe111ed",
    "attempt_sequence": 1
  },
  "summary": {
    "review_status": "in_progress"
  },
  "attempt_notes": [
    {
      "author_role": "parent",
      "note_text": "This paper shows repeated computation slips under pressure.",
      "updated_at": "2026-04-22T11:14:00+08:00"
    }
  ],
  "student_subject_notes": [
    {
      "author_role": "teacher",
      "note_text": "Winston still needs stronger habits for science open-ended explanations.",
      "updated_at": "2026-04-22T11:15:00+08:00"
    }
  ],
  "question_reviews": [
    {
      "result_id": "Q4",
      "review_status": "reviewed",
      "notes": [
        {
          "author_role": "student",
          "note_text": "I used stars:circles instead of stars:total.",
          "updated_at": "2026-04-22T11:16:00+08:00"
        }
      ]
    },
    {
      "result_id": "Q10",
      "review_status": "reviewed",
      "notes": [
        {
          "author_role": "student",
          "note_text": "I found one unit correctly but answered the wrong quantity.",
          "updated_at": "2026-04-22T11:17:00+08:00"
        }
      ]
    }
  ],
  "review_meta": {
    "updated_by": "student:winston"
  }
}
```

MVP rules:

- Missing review-state file means `review_status = not_started`
- Creating the first note creates the companion file
- Note authorship should be explicit in stored data even if the first implementation exposes only one active role at a time in the UI

### User Experience Model

Three screens are sufficient for MVP:

1. **Student Picker**
2. **My Work**
3. **Review Workspace**

### 1) Student Picker

Purpose:

- establish the active student context before data fetch

MVP implementation:

- local student selector
- persist selected `student_id` in local storage

This is an MVP access shim, not the long-term auth model.

### 2) My Work

Purpose:

- show all attempts for the active student
- help the student choose what to review next

This is not just an inbox of reports. It is an index of attempts.

Each list item should be derived from the completion registry row plus latest marking artifact (if any).

Recommended fields:

- `attempt_id` — stable registry file id
- `title` — prefer `unit_label`, else friendly normalized basename
- `subject_context`
- `grade_bucket` — inferred from path segments such as `P6` or `PSLE`
- `collection_kind` — `exam` or `book`
- `book_label` — nullable
- `marking_status` — `marked` or `not_marked`
- `review_status` — `not_started` | `in_progress` | `completed`
- `latest_marked_at` — nullable
- `score` — nullable `{ earned_marks, total_marks, percentage }`
- `attempt_sequence` — nullable
- `is_partial` — nullable/false

Recommended filters:

- subject
- exam vs book
- marked vs unmarked
- review status
- partial vs full marking

Recommended sort:

1. marked attempts with newest `latest_marked_at` first
2. then unmarked attempts by best available recency signal

### 3) Review Workspace

Purpose:

- let the user review one marked attempt using the real source work plus structured diagnosis

The MVP workspace should use a **4-panel layout**:

1. top horizontal header panel
2. middle-left evidence panel
3. middle-right review panel
4. bottom horizontal status/meta panel

This is an evolution of the earlier split-pane idea. The core principle stays the same: keep evidence and interpretation visible together, while making question navigation and workspace state explicit.

#### Active question model

The atomic unit of attention inside the workspace is one **active gradable question**.

For MVP, this should map directly to the current marking artifact boundary:

- one `question_results[]` row
- one gradable leaf unit such as `Q4` or `Q7(b)`

For reliable evidence-pane page tuning, the workspace should use:

- `context.question_page_map` (`result_id -> attempt_page_start`) when present

This mapping is essential to implementing "jump to the active gradable question's starting page."

When a user chooses a question:

1. that question becomes `active_question_id`
2. the top header highlights it in the navigator
3. the evidence panel reorients to the best available page context for that question
4. the review panel loads the full review data for that question
5. the bottom bar updates current status/action state for that question

#### Panel 1: top header panel

Purpose:

- establish attempt-level context
- provide question navigation
- offer the entrypoint for attempt-level notes

Recommended contents:

- attempt title
- student name
- subject
- book/exam label
- score summary
- partial/full marking indicator
- current question indicator such as `Q4 of 30`
- question navigator
- previous / next question controls
- `Attempt note` entrypoint

Attempt-level notes belong here because this panel is dedicated to the attempt as a whole.

The `Attempt note` entrypoint should open an on-demand drawer, popover, or modal rather than permanently occupying main review space.

#### Panel 2: middle-left evidence panel

Purpose:

- display the source material that grounds the active review

Recommended contents:

- completion attempt viewer
- answer/template viewer
- page context for the active question

Viewer mode should support:

- `Attempt`
- `Answer`

Future mode:

- `Split`

MVP behavior:

- default to `Attempt`
- when the active question changes, tune the viewer using `context.question_page_map[result_id].attempt_page_start` when available
- when mapping is absent, use graceful fallback (current page or attempt page 1)
- do **not** wait for per-question cropping before shipping

This is the grounded near-term solution to the current "switching between report and file" pain.

#### Panel 3: middle-right review panel

Purpose:

- show the structured review data for the active question
- provide the main question-scoped note-entry surface

This panel is question-scoped by default, not attempt-scoped.

It should display:

- `result_id`
- `outcome`
- `earned_marks` / `max_marks`
- `student_answer`
- `correct_answer`
- `feedback`
- `skill_tags`
- `diagnosis.mistake_type`
- `diagnosis.reasoning`
- tutor/admin note from `human_note` when present
- question-level review notes from `student_review_state.v1`

This panel should feel like an active-question inspector, not a full markdown report rendered on screen.

Use cards or an accordion list, not a dense spreadsheet grid.

#### Panel 4: bottom horizontal status/meta panel

Purpose:

- show low-height, always-visible workspace state
- provide lightweight quick actions
- provide the entrypoint for student-subject-level notes

Recommended contents:

- current viewer mode: `Attempt` or `Answer`
- active question label
- note save state: `Saved` / `Unsaved`
- question review state: `Reviewed` / `Not reviewed`
- quick actions:
  - `Mark reviewed`
  - `Next`
  - `Next unreviewed`
- `Student-subject note` entrypoint

Student-subject-level notes belong here because they are broader than the current attempt and operate as longitudinal meta-observations rather than attempt-specific comments.

The `Student-subject note` entrypoint should open an on-demand drawer, popover, or modal keyed to `(student_id, subject_context)`.

#### Note-scope to panel mapping

The panel layout should teach the scope hierarchy clearly:

- top panel: `attempt` scope
- middle-right panel: `question` scope
- bottom panel: `student_subject` scope

This is important because tutoring insight exists at multiple levels:

- what went wrong on this question
- what pattern appeared in this attempt
- what pattern keeps recurring for this student in this subject

### Grounded Example: Real Existing Artifact

For:

`PP Math PSLE Part D P6 Topical Practice Ratio__20260422_105703.json`

the workspace header can already show:

- student: `Winston Meng`
- subject: `singapore_primary_math`
- book: `Power Pack Math PSLE`
- unit: `Part D P6 Topical Practice Ratio`
- status: `Partial marking`
- score: `25 / 30 (83.33%)`
- attempt grouping: `Attempt #1` when useful

The question cards can already surface rows such as:

- `Q4`
  - outcome: `wrong`
  - student answer: `(1) 3 : 5`
  - correct answer: `(4) 3 : 8`
  - mistake type: `concept_gap`
  - reasoning: stars-to-circles was used instead of stars-to-total
- `Q10`
  - outcome: `wrong`
  - diagnosis: `misread_question`

This is enough to make a useful review experience immediately, even before question crops exist.

For this attempt, the workspace could behave like:

- top panel: `Winston Meng • Power Pack Math PSLE • Part D P6 Topical Practice Ratio • Q4 of 30 • Attempt note`
- middle-left panel: attempt viewer tuned to the page where `Q4` begins, with optional toggle to answer pages
- middle-right panel: `Q4` review card showing the wrong answer, correct answer, and concept-gap diagnosis
- bottom panel: `Viewing: Attempt • Note: Saved • Question: Not reviewed • Mark reviewed • Student-subject note`

### Alpha Test Target (v1.4 page mapping)

Use this artifact as the first alpha-test target for active-question page-jump behavior:

- `ai_study_buddy/context/marking_results/winston/singapore_primary_math/PP Math PSLE Part D P6 Topical Practice Percentage__20260421_194508.json`

Why this pilot is suitable:

- schema version is `marking_result.v1.4`
- `context.question_page_map` is populated for gradable rows
- `context.marking_asset` points to an existing attempt PNG bundle

Alpha expectation:

- changing the active question in the top navigator should move the evidence pane to the mapped `attempt_page_start`

### Backend Read/Write Model

#### Attempt identity

Use the completion registry `file_id` as the stable `attempt_id`.

Reason:

- it exists independent of marking runs
- multiple marking runs may exist for one attempt
- the attempt is the thing the student recognizes as "my work"

#### Marking run selection

Use `find_marking_artifacts_for_attempt(...)` to resolve artifacts for an attempt.

MVP default:

- pick the newest canonical JSON artifact as the active marking result

Future:

- expose prior marking runs in the UI if useful

#### Review-state identity

Key the review-state file to the selected marking artifact basename.

Reason:

- review comments refer to a specific feedback version
- avoids ambiguity if a completion is re-marked later

Within one review-state artifact, note storage should preserve:

- `scope_type`
- `author_role`
- `updated_at`

MVP note scopes:

- `question`
- `attempt`
- `student_subject`

MVP author roles:

- `student`
- `parent`
- `teacher`

### API Contract

The frontend should consume backend-shaped domain objects, not raw JSON files.

#### `GET /api/students`

Response:

```json
{
  "students": [
    { "student_id": "winston", "display_name": "Winston", "grade_level": "P6" },
    { "student_id": "emma", "display_name": "Emma", "grade_level": "P4" },
    { "student_id": "abigail", "display_name": "Abigail", "grade_level": "P2" }
  ]
}
```

#### `GET /api/student/attempts?student_id=winston`

Response shape:

```json
{
  "items": [
    {
      "attempt_id": "d88d78e1-0844-44c4-be4e-230651166612",
      "title": "Part D P6 Topical Practice Ratio",
      "student_id": "winston",
      "subject_context": "singapore_primary_math",
      "grade_bucket": "PSLE",
      "collection_kind": "book",
      "book_label": "Power Pack Math PSLE",
      "marking_status": "marked",
      "review_status": "in_progress",
      "latest_marked_at": "2026-04-22T10:57:03+08:00",
      "attempt_sequence": 1,
      "is_partial": true,
      "score": {
        "earned_marks": 25,
        "total_marks": 30,
        "percentage": 83.33
      }
    }
  ]
}
```

Grounded MVP rule:

- do not return `processing` unless real job metadata exists
- current deterministic statuses are `marked` and `not_marked`

#### `GET /api/student/attempts/{attempt_id}`

Response should merge:

1. attempt metadata from registry
2. selected latest marking result
3. student review state
4. viewer URLs resolved by backend

Suggested response shape:

```json
{
  "attempt": {
    "attempt_id": "d88d78e1-0844-44c4-be4e-230651166612",
    "title": "Part D P6 Topical Practice Ratio",
    "student_id": "winston",
    "subject_context": "singapore_primary_math",
    "collection_kind": "book",
    "book_label": "Power Pack Math PSLE"
  },
  "marking_status": "marked",
  "marking_result": {
    "artifact_path": "marking_results/winston/singapore_primary_math/PP Math PSLE Part D P6 Topical Practice Ratio__20260422_105703.json",
    "schema_version": "marking_result.v1.4",
    "created_at": "2026-04-22T10:57:03+08:00",
    "context": {
      "unit_label": "Part D P6 Topical Practice Ratio",
      "attempt_sequence": 1,
      "template_attempt_group_id": "winston::ec15795f-9da5-463f-89c5-fd8e7fe111ed",
      "answer_page_start": 41,
      "answer_page_end": 49,
      "is_partial": true,
      "question_page_map": [
        {
          "result_id": "Q4",
          "attempt_page_start": 2,
          "confidence": "high",
          "source": "manual_visual",
          "evidence_image": "attempt/attempt-page-02.png"
        }
      ]
    },
    "summary": {
      "earned_marks": 25,
      "total_marks": 30,
      "percentage": 83.33,
      "overall_assessment": "..."
    },
    "question_results": [
      {
        "result_id": "Q4",
        "outcome": "wrong",
        "earned_marks": 0,
        "max_marks": 1,
        "student_answer": "(1) 3 : 5",
        "correct_answer": "(4) 3 : 8",
        "feedback": null,
        "skill_tags": ["Number and Algebra > Ratio > Ratio"],
        "diagnosis": {
          "mistake_type": "concept_gap",
          "reasoning": "The question asks for stars to the total..."
        },
        "tutor_note": null
      }
    ]
  },
  "review_state": {
    "review_status": "in_progress",
    "student_note": "I keep mixing up part-to-part and part-to-total ratios.",
    "question_reviews": [
      {
        "result_id": "Q4",
        "review_status": "reviewed",
        "student_note": "I compared the wrong two quantities."
      }
    ]
  },
  "viewer": {
    "attempt_pdf_url": "/api/student/attempts/d88d78e1-0844-44c4-be4e-230651166612/attempt.pdf",
    "answer_pdf_url": "/api/student/attempts/d88d78e1-0844-44c4-be4e-230651166612/answer.pdf",
    "answer_page_start": 41,
    "answer_page_end": 49,
    "marking_asset_url": "/api/student/attempts/d88d78e1-0844-44c4-be4e-230651166612/marking-assets"
  }
}
```

#### `PUT /api/student/attempts/{attempt_id}/review-state`

Purpose:

- create or update `student_review_state.v1`

Allowed MVP writes:

- question-level notes
- attempt-level notes
- student-subject-level notes
- attempt-level `review_status`
- per-question `review_status`
- note `author_role`

Disallowed writes:

- any mutation to canonical `marking_result` artifacts (`v1.x`; current writer default `v1.4`)

### Target Code Map (MVP)

This section pins where implementation code should live so work does not drift across unrelated folders.

#### Keep existing package responsibilities

`ai_study_buddy/marking/` remains responsible for:

- canonical marking artifact schema/validation/writer
- completion -> artifact lookup helpers
- marking migration/backfill workflows

The Review Workspace should consume these APIs; it should not reimplement them.

#### Add a new app-domain module (not a standalone package)

Create:

- `ai_study_buddy/student_review/`

Recommended module split:

1. `ai_study_buddy/student_review/models.py`
   - API-facing DTOs (`AttemptListItem`, `AttemptDetail`, `ReviewState`, `QuestionReviewCard`, viewer payload types).
2. `ai_study_buddy/student_review/repository.py`
   - filesystem read/write for `context/student_review_states/**`.
3. `ai_study_buddy/student_review/attempt_service.py`
   - builds "My Work" list from completion registry + latest marking artifact.
4. `ai_study_buddy/student_review/detail_service.py`
   - builds Review Workspace detail payload (attempt context + active-question review data + viewer metadata).
5. `ai_study_buddy/student_review/note_service.py`
   - handles scoped note updates and validation (`question`, `attempt`, `student_subject`; author role checks).
6. `ai_study_buddy/student_review/api_routes.py`
   - route handlers for:
   - `GET /api/students`
   - `GET /api/student/attempts`
   - `GET /api/student/attempts/{attempt_id}`
   - `PUT /api/student/attempts/{attempt_id}/review-state`

This keeps domain logic near data contracts while allowing route handlers to stay thin.

#### Frontend feature placement

Place workspace UI under a feature folder in the app frontend codebase (the exact app path depends on where Review Workspace is hosted):

- `src/features/review-workspace/`
- `src/features/my-work/`
- `src/services/studentReviewApi.ts`

Recommended component split for the 4-panel workspace:

1. `ReviewWorkspacePage.tsx`
2. `TopHeaderPanel.tsx`
3. `EvidencePanel.tsx`
4. `ReviewPanel.tsx`
5. `StatusBarPanel.tsx`

#### File ownership summary

1. `marking/` owns canonical grading data contract.
2. `student_review/` owns review-workspace read/write orchestration.
3. frontend feature folders own rendering and interaction.

This boundary is the default unless we later decide to extract a dedicated service.

### Status Rules

#### Marking status

For the first implementation, use deterministic status only:

1. `marked`
   - at least one valid canonical marking JSON exists for the attempt
2. `not_marked`
   - no valid canonical marking JSON exists for the attempt

Do not invent `processing` until queue/job tracking actually exists.

#### Review status

This is independent of marking status:

1. `not_started`
   - no review-state file exists, or file exists but contains no notes / reviewed flags
2. `in_progress`
   - at least one note exists, but the attempt is not marked complete
3. `completed`
   - student explicitly marks attempt review complete

### Handling Real Current Constraints

#### No question-level crops yet

This MVP should deliberately ship before `question_objects` or bbox anchoring exists.

Near-term UX answer:

- 4-panel workspace
- attempt/answer viewer toggle in the left panel
- question-focused review panel on the right
- status/meta bar at the bottom
- page tuning driven by `context.question_page_map` when available

Later upgrade path:

- when question-index / bbox data becomes available, add deep links from each question card to exact page regions without changing the overall screen model

#### Partial marking

If `context.is_partial = true`:

- display a prominent "Partial marking" banner
- show `question_selection.raw_text`
- do not imply the whole paper has been fully reviewed

#### Multiple attempts of same template

If `template_attempt_group_id` and `attempt_sequence` exist:

- show `Attempt #<n>`
- optionally show related attempts in the same group later

This is especially useful for revision and retakes.

---

## Migration Plan

### Existing marking artifacts

No blocking migration is required for initial read-path support.

Read-path requirement:

- support `marking_result.v1.x` (`v1` through `v1.4`)

Page-tuning requirement:

- prefer `v1.4` artifacts with populated `context.question_page_map`
- use fallback behavior for older/map-missing artifacts (for example pre-`v1.4` entries without `question_page_map`)

### Markdown learning reports

No migration is required.

They remain:

- useful for human inspection in Cursor
- derived outputs only
- not a frontend data dependency

### Review-note persistence

This MVP introduces a new companion store:

- `student_review_state.v1`

Migration rule:

- none required
- absent files mean "no reflection yet"

### Future question-object upgrade

When question-object extraction becomes available:

- keep `attempt_id` stable
- keep the review workspace route stable
- enrich viewer/question card linking non-breakingly

This proposal intentionally avoids coupling the MVP to bbox extraction.

---

## Risks and Mitigations

### 1) No exact visual anchor per question yet

Risk:

- students may still need to scan a page manually

Mitigation:

- ship the 4-panel workspace with attempt/answer viewer toggle first
- use `context.question_page_map` from `v1.4` artifacts to anchor starting pages
- keep UI question-centric so future bbox links slot in naturally

### 2) Cross-student leakage

Risk:

- exposing wrong student's attempts or PDFs would be a serious privacy error

Mitigation:

- all attempt lookup and file-serving routes must enforce server-side `student_id` scoping
- never trust frontend-selected student alone

### 3) Mixing student notes with canonical marking

Risk:

- review notes could accidentally overwrite adult review or grading facts

Mitigation:

- store workspace review notes in separate `student_review_state.v1`
- keep canonical `marking_result` artifacts read-only from this UI

### 4) Schema variability across subjects

Risk:

- some rows have empty `skill_tags`, sparse `feedback`, or uneven diagnosis quality

Mitigation:

- frontend must gracefully handle missing optional fields
- UI copy should not assume every question has a rich diagnosis

### 5) Multiple marking runs per attempt

Risk:

- confusing which feedback version is being reviewed

Mitigation:

- default to newest valid artifact
- persist review state against the chosen artifact path
- expose version-switching later if needed

### 6) Unmarked attempts dilute the experience

Risk:

- if most visible items are unmarked, the student may hit dead ends

Mitigation:

- default list filters may prioritize `marked` first
- unmarked items remain visible but secondary

---

## Detailed TODO Checklist (Implementation Monitoring)

### Phase 1 — Backend read model

- [ ] Create `ai_study_buddy/student_review/` module skeleton with `models.py`, `repository.py`, `attempt_service.py`, `detail_service.py`, `note_service.py`, and `api_routes.py`.
- [ ] Implement student-scoped attempt listing in `attempt_service.py` backed by `PdfFileManager` completion rows.
- [ ] Reuse `find_marking_artifacts_for_attempt(...)` to resolve latest marking artifact per attempt.
- [ ] Define deterministic "latest artifact" selection rule and cover it with tests.
- [ ] Expose backend serializers in `models.py` that map canonical `marking_result` (`v1.x`, with `v1.4` default) into review-workspace response shapes.
- [ ] Expose server-resolved document/viewer URLs from `detail_service.py` without leaking raw local paths.
- [ ] Implement active-question page resolver in `detail_service.py` that uses `context.question_page_map` when present.

### Phase 2 — Student review-state persistence

- [ ] Define and document `student_review_state.v1`.
- [ ] Implement read/write helpers for `context/student_review_states/**` in `repository.py`.
- [ ] Create review-state files lazily on first write.
- [ ] Ensure note updates in `note_service.py` never mutate canonical `marking_result` artifacts (`v1.x`).
- [ ] Add validation for allowed `review_status` values, note scopes, note author roles, and per-question note mapping by `result_id`.

### Phase 3 — Frontend MVP

- [ ] Build student picker with local persistence of active `student_id`.
- [ ] Build `My Work` list with filters for subject, collection kind, marking status, and review status.
- [ ] Build `Review Workspace` 4-panel layout.
- [ ] Implement top-panel question navigation with active-question highlighting and previous/next controls.
- [ ] Implement left-panel evidence viewer with `Attempt` / `Answer` toggle.
- [ ] Wire active-question page jump to `context.question_page_map` with fallback when missing.
- [ ] Render attempt header, score summary, partial-marking banner, and active-question review cards.
- [ ] Add question-level note editing in the middle-right review panel.
- [ ] Add attempt-level note entry via the top panel.
- [ ] Add student-subject-level note entry via the bottom panel.
- [ ] Add visible save state and quick actions such as `Mark reviewed` and `Next unreviewed` in the bottom panel.
- [ ] Add clear empty/error/loading states for missing marking results, missing answer source, and sparse diagnosis data.

### Phase 4 — Verification and safeguards

- [ ] Add backend tests for cross-student access boundaries on list/detail/file-serving routes.
- [ ] Add tests for attempts with no marking artifact.
- [ ] Add tests for partial-marking artifacts (`context.is_partial=true`).
- [ ] Add tests for multiple attempts in one `template_attempt_group_id`.
- [ ] Add tests that review-state persistence survives reload and reappears in detail responses.

### Phase 5 — Rollout and documentation

- [ ] Update the implementation docs to reflect the shipped route contracts and response shapes.
- [ ] Update any UI/architecture docs that still describe the first student surface as a report inbox.
- [ ] Keep markdown report generation intact during rollout as a fallback debugging surface.
- [ ] Verify the shipped MVP on at least one real attempt each for Winston, Emma, and Abigail.
- [ ] Run alpha test using `PP Math PSLE Part D P6 Topical Practice Percentage__20260421_194508.json` and record page-jump correctness against `question_page_map`.
- [ ] Record which real attempts were used for acceptance testing and note any evidence-viewer gaps.

---

## Decision

Build the first student-facing MVP as a **Review Workspace** over registered attempts and canonical marking artifacts, with `v1.4` question-page mapping as the primary enabler for active-question page tuning.

Keep the canonical marking artifact read-only in the student UI.

Persist question-level, attempt-level, and student-subject-level review notes in a separate `student_review_state.v1` companion store with explicit author roles.

Ship with attempt-level/answer-level document viewing and `question_page_map`-driven page tuning first, then add deeper question-level visual anchoring (for example bbox/crops) later without changing the core workspace model.
