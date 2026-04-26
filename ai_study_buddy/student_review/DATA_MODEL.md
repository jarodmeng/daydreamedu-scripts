# Data Model — `student_review`

## 1) Canonical Read Inputs

1. Registry-backed completion rows from `PdfFileManager`.
2. Canonical marking artifacts under `ai_study_buddy/context/marking_results/**`.
3. Companion review-state files under `ai_study_buddy/context/student_review_states/**`.
4. Companion amendment overlay files under `ai_study_buddy/context/marking_amendments/**`.

## 2) Core Output Shapes

### 2.1 Students list item

```json
{
  "student_id": "winston",
  "display_name": "Winston",
  "grade_level": "PSLE"
}
```

### 2.2 Attempt list item

```json
{
  "attempt_id": "6767bafa-a380-4e98-b1b8-47b2009cbadd",
  "title": "Part D P6 Topical Practice Percentage",
  "student_id": "winston",
  "subject_context": "singapore_primary_math",
  "grade_bucket": "PSLE",
  "collection_kind": "book",
  "book_label": "Power Pack Math PSLE",
  "marking_status": "marked",
  "review_status": "in_progress",
  "latest_marked_at": "2026-04-21T19:45:08+08:00",
  "attempt_sequence": 1,
  "is_partial": false,
  "score": {
    "earned_marks": 32,
    "total_marks": 40,
    "percentage": 80
  }
}
```

### 2.3 Attempt detail payload

Top-level:

```json
{
  "attempt": {},
  "marking_status": "marked",
  "marking_result": {},
  "marking_result_base": {},
  "marking_result_resolved": {},
  "amendment_state": {},
  "review_state": {},
  "viewer": {}
}
```

Notable behavior:

- `marking_result` is `null` for unmarked attempts.
- `marking_result` aliases `marking_result_resolved` for marked attempts.
- `marking_result_base` is the immutable canonical artifact projection.
- `marking_result_resolved` is base plus saved amendment overlay.
- `amendment_state` is always present (persisted or default empty state).
- `review_state` is always present (defaulted when missing).
- `question_results[].attempt_page_start` is derived from `context.question_page_map`.

### 2.4 Amendment write response payload

Top-level response keys:

```json
{
  "ok": true,
  "saved_path": "marking_amendments/<student>/<subject>/<artifact>.json",
  "amendment_state": {},
  "marking_result": {},
  "marking_result_base": {},
  "marking_result_resolved": {}
}
```

## 3) Review-State Artifact

Path:

- `ai_study_buddy/context/student_review_states/<student>/<subject>/<artifact_stem>.json`

Stored schema id:

- `student_review_state.v1`

Required top-level keys written by current module:

- `schema_version`
- `created_at`
- `updated_at`
- `context`
- `summary`
- `review_status`
- `question_reviews`
- `attempt_notes`
- `student_subject_notes`
- `review_meta`
- `updated_by`

## 4) Amendment Artifact

Path:

- `ai_study_buddy/context/marking_amendments/<student>/<subject>/<artifact_stem>.json`

Stored schema id:

- `marking_amendment.v1`

Key top-level fields:

- `schema_version`
- `context`
- `summary_overrides`
- `question_amendments`
- `question_page_map_amendments`
- `review_meta`
