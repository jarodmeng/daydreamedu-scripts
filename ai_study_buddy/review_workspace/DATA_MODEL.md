# review_workspace — Data Model

Field-level reference for Review Workspace payloads and persisted review-state artifacts.

Version baseline: `v0.0.900`.

See:

- `SPEC.md` for route-level contract
- `ARCHITECTURE.md` for ownership boundaries

## 1) Canonical Read Source

Primary read source:

- `ai_study_buddy/context/marking_results/**.json`

Expected schema compatibility:

- `marking_result.v1`
- `marking_result.v1.1`
- `marking_result.v1.2`
- `marking_result.v1.3`
- `marking_result.v1.4` (writer default / preferred)

Consumed source fields include:

- `context.student_id`
- `context.student_name`
- `context.subject_context`
- `context.attempt_file_id`
- `context.unit_label`
- `context.book_label`
- `context.template_attempt_group_id`
- `context.attempt_sequence`
- `context.marking_asset`
- `context.is_partial`
- `context.answer_page_start`
- `context.answer_page_end`
- `context.question_page_map[]`
- `summary.*`
- `question_results[]`

## 2) Backend Output Models

### 2.1 `GET /api/students`

```json
{
  "students": [
    {
      "student_id": "winston",
      "display_name": "Winston",
      "grade_level": "PSLE"
    }
  ]
}
```

### 2.2 `GET /api/student/attempts?student_id=<id>`

```json
{
  "items": [
    {
      "attempt_id": "d88d78e1-0844-44c4-be4e-230651166612",
      "title": "Part D Topical Practice Circles",
      "student_id": "winston",
      "subject_context": "singapore_primary_math",
      "grade_bucket": "PSLE",
      "collection_kind": "book",
      "book_label": "PP Math PSLE Part D P6 Topical Practice",
      "marking_status": "marked",
      "review_status": "not_started",
      "latest_marked_at": "2026-04-16T20:51:58+08:00",
      "attempt_sequence": 1,
      "is_partial": false,
      "score": {
        "earned_marks": 32,
        "total_marks": 40,
        "percentage": 80
      }
    }
  ]
}
```

### 2.3 `GET /api/student/attempts/{attempt_id}`

Top-level shape:

```json
{
  "attempt": {},
  "marking_status": "marked",
  "marking_result": {},
  "review_state": {},
  "viewer": {}
}
```

Notable fields:

- `marking_result.question_results[].attempt_page_start` is derived from `context.question_page_map`
- `viewer.attempt_images[]` and `viewer.answer_images[]` contain `name`, `page_num`, `url`
- `review_state` is either loaded persisted data or backend default:
  - `review_status: "not_started"`
  - empty arrays for note/review collections

### 2.4 `PUT /api/student/attempts/{attempt_id}/review-state`

Request body fields:

- `review_status`: required enum (`not_started|in_progress|completed`)
- `question_reviews`: list
- `attempt_notes`: list
- `student_subject_notes`: list
- `updated_by`: optional string

Response:

```json
{
  "ok": true,
  "saved_path": "student_review_states/winston/singapore_primary_math/<artifact>.json",
  "review_state": {}
}
```

## 3) Persisted Review-State Artifact

Path:

- `ai_study_buddy/context/student_review_states/<student_id>/<subject_context>/<artifact_stem>.json`

Persisted shape (`student_review_state.v1`):

```json
{
  "schema_version": "student_review_state.v1",
  "context": {
    "student_id": "winston",
    "subject_context": "singapore_primary_math",
    "attempt_file_id": "d88d78e1-0844-44c4-be4e-230651166612",
    "marking_result_path": "marking_results/winston/singapore_primary_math/<artifact>.json"
  },
  "review_status": "in_progress",
  "question_reviews": [
    {
      "result_id": "Q4",
      "review_status": "reviewed",
      "note_text": "I misread the ratio."
    }
  ],
  "attempt_notes": [
    {
      "note_text": "Check working carefully."
    }
  ],
  "student_subject_notes": [
    {
      "note_text": "Need more percentage/ratio practice."
    }
  ],
  "updated_by": "review_workspace_ui"
}
```

## 4) UI State Model (Frontend Local)

Primary local state domains:

- selection state:
  - `activeQuestionId`
  - `activeImageUrl`
- viewer state:
  - `viewerMode` (`attempt|answer`)
  - `viewerFitMode` (`fit_height|fit_width`)
  - `viewerZoomPct` (`50..300`)
- review state:
  - `noteScope` (`question|attempt|student_subject`)
  - `noteDraft`
  - `noteSaved`
  - transient `reviewed` set merged with persisted review flags

## 5) Invariants

- canonical marking artifact is read-only from Review Workspace
- review-state artifact write is idempotent per save action and path
- frontend computes `review_status` heuristically (`in_progress` when reviewed flags or notes exist)
- backend enforces `review_status` enum validity
