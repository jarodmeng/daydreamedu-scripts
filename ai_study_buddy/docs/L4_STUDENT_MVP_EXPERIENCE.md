# AI Study Buddy — Review Workspace

> Status: **Implemented (`v0.3` spec) — shipped app `review_workspace` v0.1.3 (May 2026), single-student alpha rollout in progress**.
>
> Scope lock (April 23, 2026, unchanged): delivery phase is **single-student alpha** — Student Picker, My Work index, and Review Workspace core loop. Non-core expansions remain deferred until alpha exit criteria are met.
>
> **Shipped package:** [`ai_study_buddy/review_workspace/`](../review_workspace/) (`README.md`, `SPEC.md`, `CHANGELOG.md`, `TESTING.md`). Backend domain: [`ai_study_buddy/marking/review/`](../marking/review/).
>
> Related docs: [USER_EXPERIENCE](./L3_USER_EXPERIENCE.md), [MARKING_RESULT_ARTIFACT](./L4_MARKING_RESULT_ARTIFACT.md), [INGESTION_PIPELINE](./L4_INGESTION_PIPELINE.md), [ROADMAP](./L1_ROADMAP.md)

### Implementation snapshot (May 2026)

| Area | Status |
|------|--------|
| Backend read model (`marking/review/*`) | Shipped (v0.1.0 → consolidated v0.1.2) |
| Review-state persistence (`student_review_state.v1`) | Shipped |
| Human grading amendments (`marking_amendment.v1`) | Shipped (v0.1.1; save-diff fix v0.1.3) — canonical `marking_result` JSON stays read-only |
| Frontend (picker, My Work, 4-panel workspace) | Shipped in `review_workspace/frontend/` (monolithic `App.tsx` for now) |
| Automated tests | Partial — amendment/API tests in `marking/tests/test_review_workspace_*.py`; manual smoke per `review_workspace/TESTING.md` |
| Alpha exit (3 students + pilot `question_page_map` acceptance) | **Not recorded** — see Phase 5 checklist below |

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
8. **Human grading amendments** (teacher/parent overlay) persisted separately from canonical marking JSON — resolved at read time as `marking_result_resolved` (shipped v0.1.1).

### Out of Scope

1. Tutor chat, hint ladder, or Socratic tutoring loop — **exception:** question-scoped **Ask AI** in `buddy_console` `/review` (v0.2.0+, `VITE_REVIEW_TUTOR_CHAT=1`); see [L4_REVIEW_WORKSPACE_QUESTION_TUTOR_CHAT](./L4_REVIEW_WORKSPACE_QUESTION_TUTOR_CHAT.md). Still out of scope for `/student` and production student portal.
2. Quest board as the primary home screen.
3. Parent dashboard and admin ingestion/review tooling.
4. Full question-object extraction with bounding boxes and per-question image crops.
5. **In-place mutation** of canonical `marking_result` artifacts from the student UI (amendments use a companion overlay instead; shipped).
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
- supervised redo viewer (GoodNotes `Review/` export — shipped `buddy_console` v0.1.16)
- page context for the active question

Viewer mode should support:

- `Attempt`
- `Answer`
- `Template` (linked template FQI renders — shipped v0.1.9+)
- `Review` (supervised redo evidence — shipped `buddy_console` v0.1.16; lazy render)

Future mode:

- `Split`

MVP behavior:

- default to `Attempt`
- when the active question changes, tune the viewer using `context.question_page_map[result_id].attempt_page_start` when available (applies to **Attempt**, **Template**, and **Review** — same page indices)
- when mapping is absent, use graceful fallback (current page or attempt page 1)
- do **not** wait for per-question cropping before shipping

**Supervised redo load (v0.1.16+, two-step):**

| Step | When | Behavior |
|------|------|----------|
| **i** | Attempt detail load | `viewer.review_redo.available` from attempt → template → GoodNotes `Review/` PDF `stat`; show **Review** tab when true; `viewer.review_images` stays `[]` |
| **ii** | First **Review** tab click | `GET …/review-evidence` cache-first raster into `context/review_redo/`; client caches `review_images`; **404** hides tab if PDF gone |

Review-folder PDFs stay **excluded** from operator inventory (`files` v0.3.11+); Review Workspace resolves them deliberately via `resolve_supervised_review_pdf_for_attempt`. No marking of Review PDFs. See [buddy_console proposal 3](../buddy_console/docs/proposal/3-review-workspace-supervised-redo-tab.md) and [`files` SPEC §2.6](../files/SPEC.md#26-goodnotes-review-folder-vs-review-workspace).

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
2. selected latest marking result (plus amendment overlay when present)
3. student review state
4. viewer URLs resolved by backend

**Shipped additions (v0.1.1+):** `marking_result_base`, `marking_result_resolved`, `amendment_state`; `marking_result` aliases resolved payload. Evidence viewer uses `viewer.attempt_images` / `viewer.answer_images` from marking-asset bundles when present (see [`review_workspace/SPEC.md`](../review_workspace/SPEC.md)).

Suggested response shape (illustrative; field names may differ slightly from shipped DTOs):

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

#### `PUT /api/student/attempts/{attempt_id}/amendments` (shipped v0.1.1)

Purpose:

- create or update `marking_amendment.v1` human grading overrides without touching canonical marking JSON

Persisted under:

- `context/marking_amendments/<student>/<subject_context>/<artifact_basename>.json`

Attempt detail exposes:

- `marking_result_base` — immutable AI artifact projection
- `marking_result_resolved` — base + amendment overlay
- `marking_result` — backward-compatible alias to resolved payload

Contract details: [`review_workspace/SPEC.md`](../review_workspace/SPEC.md) §3.6 and [`review_workspace/DATA_MODEL.md`](../review_workspace/DATA_MODEL.md).

### Target Code Map (MVP)

This section pins where implementation code lives (shipped as of `review_workspace` v0.1.3).

#### Keep existing package responsibilities

`ai_study_buddy/marking/` remains responsible for:

- canonical marking artifact schema/validation/writer
- completion -> artifact lookup helpers
- marking migration/backfill workflows

The Review Workspace should consume these APIs; it should not reimplement them.

#### App-domain module (shipped)

- `ai_study_buddy/marking/review/` — review-workspace orchestration (consolidated from legacy `student_review/` in v0.1.2)

Module split (as shipped):

1. `models.py` — API-facing DTOs and serializers
2. `repository.py` — filesystem read/write for `context/student_review_states/**` and `context/marking_amendments/**`
3. `attempt_service.py` — My Work list from `PdfFileManager` + latest artifact via `find_marking_artifacts_for_attempt(...)[0]`
4. `detail_service.py` — detail payload, viewer URLs, `question_page_map` → `attempt_page_start` enrichment
5. `note_service.py` — `student_review_state.v1` validation and writes
6. `amendment_service.py` — `marking_amendment.v1` validation, merge, resolved marking projection
7. `payload_reader.py` — marking payload read (filesystem with optional learning-DB reads)
8. `api_routes.py` — route handlers:
   - `GET /api/students`
   - `GET /api/student/attempts`
   - `GET /api/student/attempts/{attempt_id}`
   - `PUT /api/student/attempts/{attempt_id}/review-state`
   - `PUT /api/student/attempts/{attempt_id}/amendments`

Thin app shell: `ai_study_buddy/review_workspace/backend/app.py` (static mount + router include).

#### Frontend placement (shipped)

Standalone Vite app (not yet split into feature folders):

- `ai_study_buddy/review_workspace/frontend/src/App.tsx` — Student Picker, My Work, 4-panel Review Workspace (top / left evidence / right review / bottom actions)
- `ai_study_buddy/review_workspace/frontend/src/styles.css`

Future refactor may extract the originally suggested `ReviewWorkspacePage.tsx`, `EvidencePanel.tsx`, etc., without changing API contracts.

#### File ownership summary

1. `marking/` owns canonical grading data contract.
2. `marking/review` owns review-workspace read/write orchestration.
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

Companion store (shipped):

- `student_review_state.v1` under `context/student_review_states/**`

Migration rule:

- none required
- absent files mean "no reflection yet"

### Human grading amendments (shipped v0.1.1)

Companion store:

- `marking_amendment.v1` under `context/marking_amendments/**`

Migration rule:

- none required
- absent files mean "no human overrides yet"
- canonical `marking_result` JSON is never rewritten by the Review Workspace app

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
- store human grading corrections in separate `marking_amendment.v1`
- keep canonical `marking_result` artifacts read-only from this UI (amendments merge at read time only)

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

> Last synced with shipped code: **review_workspace v0.1.3** (2026-05-08). Route-level contracts: [`review_workspace/SPEC.md`](../review_workspace/SPEC.md).

### Phase 1 — Backend read model

- [x] Create `ai_study_buddy/marking/review/` module skeleton with `models.py`, `repository.py`, `attempt_service.py`, `detail_service.py`, `note_service.py`, and `api_routes.py` (plus `amendment_service.py`, `payload_reader.py`).
- [x] Implement student-scoped attempt listing in `attempt_service.py` backed by `PdfFileManager` completion rows.
- [x] Reuse `find_marking_artifacts_for_attempt(...)` to resolve latest marking artifact per attempt.
- [x] Define deterministic "latest artifact" selection rule and cover it with tests (`refs[0]` after `created_at` desc, then path asc — see `marking/core/artifact_lookup.py` and `marking/tests/test_artifact_lookup.py`).
- [x] Expose backend serializers in `models.py` that map canonical `marking_result` (`v1.x`) into review-workspace response shapes (including base/resolved split when amendments exist).
- [x] Expose server-resolved document/viewer URLs from `detail_service.py` without leaking raw local paths (static URLs under `/review-workspace-static/...`).
- [x] Implement active-question page resolver in `detail_service.py` that uses `context.question_page_map` when present.

### Phase 2 — Student review-state persistence

- [x] Define and document `student_review_state.v1` ([`review_workspace/DATA_MODEL.md`](../review_workspace/DATA_MODEL.md)).
- [x] Implement read/write helpers for `context/student_review_states/**` in `repository.py`.
- [x] Create review-state files lazily on first write.
- [x] Ensure note updates in `note_service.py` never mutate canonical `marking_result` artifacts (`v1.x`).
- [x] Add validation for allowed `review_status` values, note scopes, note author roles, and per-question note mapping by `result_id`.

### Phase 2b — Human grading amendments (added after initial proposal; shipped v0.1.1)

- [x] Define and document `marking_amendment.v1` ([`review_workspace/SPEC.md`](../review_workspace/SPEC.md) §5).
- [x] Implement read/write/merge in `amendment_service.py` + `repository.py` under `context/marking_amendments/**`.
- [x] Expose `PUT /api/student/attempts/{attempt_id}/amendments` and base/resolved fields on attempt detail.
- [x] Frontend inline amendment editing with save/reload (v0.1.1; save-diff against resolved state v0.1.3).

### Phase 3 — Frontend MVP

- [x] Build student picker with local persistence of active `student_id` (`localStorage` key `review_workspace.student_id`).
- [x] Build `My Work` list with filters for subject, collection kind, marking status, and review status.
- [x] Build `Review Workspace` 4-panel layout.
- [x] Implement top-panel question navigation with active-question highlighting and previous/next controls.
- [x] Implement left-panel evidence viewer with `Attempt` / `Answer` toggle.
- [x] Wire active-question page jump to `context.question_page_map` with fallback when missing.
- [x] Render attempt header, score summary, partial-marking banner, and active-question review cards.
- [x] Add question-level note editing in the middle-right review panel.
- [x] Add attempt-level note entry via the top panel (notes scope toggle).
- [x] Add student-subject-level note entry via the bottom panel.
- [x] Add visible save state and quick actions in the bottom/top panels (`Review completed`, `Next incorrect`; **`Next unreviewed` not implemented** — use question nav + review filters instead).
- [x] Add clear empty/error/loading states for missing marking results, missing answer source, and sparse diagnosis data (basic states; polish as needed during alpha).

### Phase 4 — Verification and safeguards

- [ ] Add backend tests for cross-student access boundaries on list/detail/file-serving routes.
- [ ] Add tests for attempts with no marking artifact.
- [ ] Add tests for partial-marking artifacts (`context.is_partial=true`).
- [ ] Add tests for multiple attempts in one `template_attempt_group_id`.
- [ ] Add tests that review-state persistence survives reload and reappears in detail responses.
- [x] Amendment overlay tests (`marking/tests/test_review_workspace_amendments.py`, `test_review_workspace_preflight.py`).

### Phase 5 — Rollout and documentation

- [x] Update the implementation docs to reflect the shipped route contracts and response shapes (`review_workspace/SPEC.md`, `DATA_MODEL.md`, `CHANGELOG.md`).
- [ ] Update any UI/architecture docs that still describe the first student surface as a report inbox (e.g. sweep `L3_USER_EXPERIENCE.md` if needed).
- [x] Keep markdown report generation intact during rollout as a fallback debugging surface (unchanged in marking pipeline).
- [ ] Verify the shipped MVP on at least one real attempt each for Winston, Emma, and Abigail.
- [ ] Run alpha test using `PP Math PSLE Part D P6 Topical Practice Percentage__20260421_194508.json` and record page-jump correctness against `question_page_map`.
- [ ] Record which real attempts were used for acceptance testing and note any evidence-viewer gaps.

---

## Decision

Build the first student-facing MVP as a **Review Workspace** over registered attempts and canonical marking artifacts, with `v1.4` `question_page_map` as the primary enabler for active-question page tuning.

**Shipped (v0.1.0–v0.1.3):** registry-backed Student Picker and My Work, 4-panel Review Workspace, `student_review_state.v1` notes, and `marking_amendment.v1` human grading overlays — all without mutating canonical `marking_result` JSON.

Keep the canonical marking artifact read-only in the student UI; human corrections use the amendment companion store and `marking_result_resolved` at read time.

Persist question-level, attempt-level, and student-subject-level review notes in `student_review_state.v1` with explicit author roles.

**Remaining before alpha exit:** Phase 4 boundary/partial/multi-attempt tests, Phase 5 multi-student acceptance runbook, and optional `Next unreviewed` navigation if still desired after alpha feedback.

Ship with attempt-level/answer-level document viewing and `question_page_map`-driven page tuning first; add deeper question-level visual anchoring (bbox/crops) later without changing the core workspace model.
