# Buddy Console Testing

Validation guide for `ai_study_buddy/buddy_console`.

See:

- [SPEC.md](./SPEC.md)
- [DATA_MODEL.md](./DATA_MODEL.md)

## Prerequisites

From repo root:

1. backend dependencies

```bash
python3 -m pip install -r ai_study_buddy/buddy_console/backend/requirements.txt
```

2. frontend dependencies

```bash
cd ai_study_buddy/buddy_console/frontend
npm install
```

## Backend Smoke Checks

Run backend:

```bash
python3 -m uvicorn ai_study_buddy.buddy_console.backend.app:app --reload --port 8010
```

### Health

```bash
curl -s http://localhost:8010/api/health
```

Expected:

- JSON contains `"status":"ok"`

### Inventory Config

```bash
curl -s http://localhost:8010/api/config
```

Expected:

1. configured `roots[]`
2. `students[]` when registry lookup is available
3. filter metadata payload

### Inventory List

```bash
curl -s "http://localhost:8010/api/inventory"
```

Expected:

1. `items[]`
2. `meta.total_in_index`
3. `meta.total_after_filter`

### PDF Browser Config

```bash
curl -s "http://localhost:8010/api/pdf-browser/config"
```

Expected:

1. `roots[]`

### PDF Browser List

```bash
curl -s "http://localhost:8010/api/pdf-browser/list?id=goodnotes&rel="
```

Expected:

1. `dirs[]`
2. `pdfs[]`
3. `currentRel`

### Student marks by question type (v0.1.11+)

Requires live `study_buddy.db` and marking data under `context/marking_results/`.

```bash
curl -s "http://localhost:8010/api/student/marks-by-question-type?student_id=winston&subject=math"
```

Expected:

1. **200** with `student_id`, `subject`, `generated_at`, `subjects[]`
2. each block has `display_label`, `type_order`, `marks_by_question_type.by_type`
3. empty scope → `subjects: []` and `message`

Chinese picker (schema split — should match report CLI flags):

```bash
# Standard Chinese only (exclude 高华 FQI under singapore_primary_chinese)
python3 ai_study_buddy/context/student_understandings/scripts/report_marked_completion_fqi_stats.py \
  --student-slug winston --subject-context singapore_primary_chinese \
  --exclude-fqi-schema-prefix high-chinese --json

# Higher Chinese only (include 高华 FQI from both marking paths)
python3 ai_study_buddy/context/student_understandings/scripts/report_marked_completion_fqi_stats.py \
  --student-slug winston \
  --subject-context singapore_primary_chinese \
  --subject-context singapore_primary_higher_chinese \
  --include-fqi-schema-prefix high-chinese --json

curl -s "http://localhost:8010/api/student/marks-by-question-type?student_id=winston&subject=chinese"
```

Portal `subjects[]` totals should match `marking_marks_by_type` from the corresponding report runs (standard block vs higher block).

Backend tests:

```bash
python3 -m pytest ai_study_buddy/buddy_console/tests/test_student_marks_api.py -q
```

## Frontend Checks

From `ai_study_buddy/buddy_console/frontend`:

### Build

```bash
npm run build
```

### Tests

```bash
npm test -- --run
```

Backend (completion date PATCH):

```bash
cd /path/to/daydreamedu-scripts
python3 -m pytest ai_study_buddy/buddy_console/tests/test_completion_date_patch.py -q
```

### Local UI Smoke

Run frontend dev server while backend is running:

```bash
npm run dev
```

Open `http://localhost:5178` and verify:

1. `/inventory` loads
2. inventory filters change result counts
3. `View PDF` opens `/pdf` in a new tab
4. `Review Workspace` opens `/review` in a new tab
5. inventory tab remains open and retains filter state

### Manual completion date (v0.1.5+)

On a **registered completion** card (not template):

1. Use **Set completed date** or **Edit completed date** (date input + **Save**).
2. Pick a date and save — card shows **Completed** with `source: manual` in the tooltip.
3. Under **Completed (recent)** sort, the card moves to the expected position after save (inventory refetches).
4. On a completion that already has an inferred date (e.g. `handwritten_page1`), saving a new date shows a **confirm** dialog with old date, source, and new date.
5. **Registered** line is unchanged after edit.

Optional API check (replace `FILE_ID` with `registry_file_id` from a card):

```bash
curl -s -X PATCH "http://localhost:8010/api/inventory/items/FILE_ID/completion-date" \
  -H "Content-Type: application/json" \
  -d '{"completion_date":"2026-03-15"}'
```

In the PDF tab verify:

1. both roots render as root blocks
2. folder expansion works
3. selecting a PDF loads the viewer
4. `Show _raw_ files` toggles raw-file visibility
5. bookmarks can be added, reopened, and cleared

In the review tab verify:

1. a marked attempt deep link opens correctly
2. seeded review functionality still loads without fetch errors
3. **Review tab (v0.1.16+):** when `viewer.review_redo.available` on a marked attempt with a GoodNotes `Review/` export, **Review** appears without waiting for render; first click shows loading then page images; second click uses cache; question nav jumps to same page as **Attempt**; attempts without Review redo show three tabs only and never call `review-evidence` on load

Optional API check (replace `ATTEMPT_ID` with registry `attempt_id` where Review redo exists):

```bash
curl -s "http://localhost:8010/api/student/attempts/ATTEMPT_ID" | jq '.viewer.review_redo'
curl -s "http://localhost:8010/api/student/attempts/ATTEMPT_ID/review-evidence" | jq '.review_images | length'
```

Backend tests (supervised redo):

```bash
python3 -m pytest ai_study_buddy/files/tests/test_supervised_review_redo.py \
  ai_study_buddy/marking/tests/test_review_workspace_review_redo.py -q
```

### Student portal (v0.1.11+)

Open:

```text
http://127.0.0.1:5178/student?student_id=winston
```

Verify:

1. subject picker shows; no table until a subject is selected
2. `http://127.0.0.1:5178/student?student_id=winston&subject=math` loads math table on landing
3. Chinese picker shows standard and higher blocks when data exists
4. footnote shows `Computed: <generated_at>`
5. no top-nav link to `/student` on inventory (deep link only)
6. after a marking or amendment change in `/review`, reload `/student` — numbers update without re-running `report_marked_completion_fqi_stats.py --write-artifacts`

## Regression Checklist

Before considering a `buddy_console` change safe:

1. `npm run build` passes
2. route-specific scrolling still works:
   - inventory scrolls
   - PDF stays fixed-height
   - review stays fixed-height
3. inventory deep links still open new tabs
4. PDF deep links still open the intended file
5. review deep links still open the intended marked attempt
6. `/student` marks API and UI still load when `study_buddy.db` is present
7. Review redo: `review-evidence` returns **404** when resolver misses; **200** with non-empty `review_images` when Review PDF exists

## Rollback Steps

If validation uncovers a blocking regression:

1. stop the `buddy_console` backend and frontend
2. restart the standalone legacy apps needed for the affected workflow
3. keep `buddy_console` out of the default workflow until the regression is fixed

Current rollback targets:

1. `student_file_browser` for inventory-only work
2. `root_pdf_browser` for standalone PDF browsing
3. `review_workspace` for standalone review work
