# Buddy Console Specification

Route and behavior contract for `ai_study_buddy/buddy_console`.

See:

- [README.md](./README.md)
- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [DATA_MODEL.md](./DATA_MODEL.md)
- [TESTING.md](./TESTING.md)

## Runtime Inputs

### Environment

- `PDF_REGISTRY_PATH` optional
  - consumed through `PdfFileManager`
- `AI_STUDY_BUDDY_CONTEXT_ROOT` optional
  - overrides the default context root used by inventory/review services

### Filesystem Dependencies

- `ai_study_buddy/context/**`
- configured DaydreamEdu / GoodNotes roots
- registry-backed PDF metadata via `PdfFileManager`

## Frontend Route Contract

### `/` and `/inventory`

Inventory hub route.

Expected behavior:

1. load filter metadata from `/api/config`
2. load inventory cards from `/api/inventory`
3. preserve filter/query state in URL
4. open PDF and review targets in new tabs

### `/pdf`

PDF browser route.

Expected behavior:

1. show both configured roots
2. allow tree expansion through leaf-folder branches only
3. allow opening a specific PDF by `id` + `rel`
4. support bookmark state and raw-file toggle in client storage

### `/review`

Review route.

Currently backed by the seeded review workspace flow.

Expected behavior:

1. preserve direct attempt deep links
2. allow inventory cards to open a marked attempt directly

### `/student`

Student portal route (marks by question type).

Expected behavior:

1. require `student_id` query param (same trust model as `/review`)
2. four-choice subject picker (English, Chinese, Math, Science); default none selected — no API call until chosen
3. optional `subject` query param pre-selects picker and loads on first paint
4. fetch `GET /api/student/marks-by-question-type` only after a subject is selected
5. Chinese picker shows standard and higher Chinese as separate table blocks when data exists (split by FQI `high-chinese` schema — see API behavior below)

No top-nav link to `/student` in v0.1.11 (bookmark / deep link only).

## Backend API Contract

### `GET /api/health`

Response:

```json
{ "status": "ok" }
```

### `GET /api/config`

Inventory configuration and filter metadata.

Response includes:

1. `roots`
2. `students`
3. filter option metadata returned by `filter_meta_for_response(...)`

### `GET /api/inventory`

Inventory list response.

Response includes:

1. `items` — enriched cards (`completion_date`, `completion_date_source`, `registry_added_at`, …); see [DATA_MODEL.md](./DATA_MODEL.md#inventory-models)
2. `meta.total_in_index`
3. `meta.total_after_filter`
4. `meta.index_size_warning`
5. inventory filter visibility metadata

Inventory uses `files` **v0.3.9+**; `files_version` on inventory health is `ai_study_buddy.files.__version__` at runtime. Sort `recent` = **Completed (recent)** with unified recency ordering (`completion_date` first, fallback to `registry_added_at`, newest first across both; unregistered remain last) ([proposal 17 §5.4](../pdf_file_manager/docs/proposals/17-completion-date.md#54-consumers-when-no-row-exists)).

### `PATCH /api/inventory/items/{registry_file_id}/completion-date`

Set or overwrite the completion calendar date for a registered **completion main** (`pdf_files.id`).

Request body:

```json
{ "completion_date": "2026-03-15" }
```

Response **200**:

```json
{
  "registry_file_id": "<uuid>",
  "completion_date": "2026-03-15",
  "completion_date_source": "manual"
}
```

Behavior:

1. Persists via `PdfFileManager.set_completion_date(..., source="manual")` with `source_detail.set_via = "buddy_console"` and previous row fields on overwrite.
2. Clears `InventoryRuntime.enriched_cache` so the next inventory list rebuilds from registry.
3. Returns **404** when `registry_file_id` is unknown; **400** for ineligible targets (template, raw, missing `student_id`) or invalid date.

The inventory UI refetches `GET /api/inventory` after success (slim PATCH body is not merged into cards alone). See [proposal 1-manual-completion-date-ui.md](./docs/proposal/1-manual-completion-date-ui.md).

### `GET /api/pdf-browser/config`

Returns available PDF roots.

### `GET /api/pdf-browser/list?id=<root_id>&rel=<folder_rel>`

Returns allowed child folders and PDFs for the requested branch.

Response fields:

1. `dirs`
2. `pdfs`
3. `pdfRegistration`
4. `registryAvailable`
5. `currentRel`

### `GET /api/pdf?id=<root_id>&rel=<pdf_rel>`

Streams a single PDF when:

1. the path stays under the configured root
2. the file exists
3. the file belongs to an allowed leaf-folder path

### `GET /api/student/marks-by-question-type`

Serve-time marks rollup by FQI `question_type` (amendment-resolved), one student × subject picker.

Query:

1. `student_id` — required (`students.id` / marking slug)
2. `subject` — required: `english` | `chinese` | `math` | `science`

Response **200**:

```json
{
  "student_id": "winston",
  "subject": "math",
  "generated_at": "2026-06-03T10:00:00+08:00",
  "subjects": [
    {
      "subject_context": "singapore_primary_math",
      "display_label": "Math",
      "type_order": ["MCQ", "SAQ", "LAQ"],
      "marks_by_question_type": {
        "question_count": 412,
        "earned_marks": 318.5,
        "max_marks": 420.0,
        "percentage": 75.8,
        "by_type": {}
      }
    }
  ]
}
```

Behavior:

1. Computes via `build_marked_completion_fqi_stats` (same logic as `report_marked_completion_fqi_stats.py`); does **not** read `student_understandings/**/*.json`.
2. `chinese` returns up to two blocks (standard first, then higher), each omitted when `question_count` is 0:
   - **Standard Chinese** — `singapore_primary_chinese` markings only; **exclude** FQI schemas whose `schema_version` starts with `high-chinese` (Higher Chinese work often lives under this path).
   - **Higher Chinese** — markings under `singapore_primary_chinese` and `singapore_primary_higher_chinese`; **include only** `high-chinese` FQI (e.g. 字词改正, 综合填空).
3. Other pickers: one block per subject context, no FQI prefix filters.
4. Empty scope → `subjects: []` and `message`.
5. **400** when `student_id` or `subject` missing/invalid.
6. **503** when study DB or context root unavailable.

See [proposal 2](./docs/proposal/2-student-marks-by-question-type.md).

### Review APIs

The backend also includes the seeded review API contract from
`ai_study_buddy.marking.review.api_routes`.

That currently provides:

1. student list and attempt detail endpoints
2. review-state persistence
3. amendment persistence

`buddy_console` consumes those routes through the `/review` surface.

## Deep-Link Contract

### Review

```text
/review?attempt_id=<registry_uuid>&student_id=<students.id>
```

### PDF

```text
/pdf?id=<root_id>&rel=<root_relative_pdf_path>
```

### Student portal

```text
/student?student_id=<students.id>
/student?student_id=<students.id>&subject=<english|chinese|math|science>
```

Both link forms are expected to be stable enough for inventory card actions and
manual operator use.
