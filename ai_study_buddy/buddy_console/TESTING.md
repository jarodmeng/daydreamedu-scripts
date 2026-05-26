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

In the PDF tab verify:

1. both roots render as root blocks
2. folder expansion works
3. selecting a PDF loads the viewer
4. `Show _raw_ files` toggles raw-file visibility
5. bookmarks can be added, reopened, and cleared

In the review tab verify:

1. a marked attempt deep link opens correctly
2. seeded review functionality still loads without fetch errors

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

## Rollback Steps

If validation uncovers a blocking regression:

1. stop the `buddy_console` backend and frontend
2. restart the standalone legacy apps needed for the affected workflow
3. keep `buddy_console` out of the default workflow until the regression is fixed

Current rollback targets:

1. `student_file_browser` for inventory-only work
2. `root_pdf_browser` for standalone PDF browsing
3. `review_workspace` for standalone review work
