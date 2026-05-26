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

1. `items`
2. `meta.total_in_index`
3. `meta.total_after_filter`
4. `meta.index_size_warning`
5. inventory filter visibility metadata

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

Both link forms are expected to be stable enough for inventory card actions and
manual operator use.
