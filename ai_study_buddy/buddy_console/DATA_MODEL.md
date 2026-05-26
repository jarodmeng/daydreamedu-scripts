# Buddy Console Data Model

Field-level reference for the main payloads currently used by `buddy_console`.

See:

- [SPEC.md](./SPEC.md)
- [ARCHITECTURE.md](./ARCHITECTURE.md)

## Inventory Models

### `GET /api/config`

Important top-level fields:

1. `roots[]`
   - `id`
   - `label`
   - `path`
2. `students[]`
   - `student_id`
   - `display_name`
   - `email`
3. filter metadata collections produced by `filter_meta_for_response(...)`

### `GET /api/inventory`

Top-level shape:

```json
{
  "items": [],
  "meta": {}
}
```

Important `meta` fields:

1. `total_in_index`
2. `total_after_filter`
3. `unregistered_in_index`
4. `index_size_warning`

Important `items[]` characteristics:

1. each item is derived from the enriched main-PDF inventory
2. card content is used to drive inventory filters, PDF links, and review links

## PDF Browser Models

### `GET /api/pdf-browser/config`

```json
{
  "roots": [
    {
      "id": "goodnotes",
      "label": "GoodNotes",
      "path": "/abs/path"
    }
  ]
}
```

### `GET /api/pdf-browser/list`

```json
{
  "dirs": ["P4", "P5"],
  "pdfs": ["worksheet.pdf"],
  "pdfRegistration": {
    "worksheet.pdf": true
  },
  "registryAvailable": true,
  "currentRel": "Singapore Primary Math/P4"
}
```

Notes:

1. `dirs` and `pdfs` are already filtered by allowed leaf-folder traversal rules
2. `pdfRegistration[name]` may be `true`, `false`, or absent

## Review Models

The review route currently uses the seeded review workspace payload family.

Important top-level attempt detail fields consumed by the frontend include:

1. `attempt`
2. `marking_status`
3. `marking_result`
4. `marking_result_base`
5. `marking_result_resolved`
6. `amendment_state`
7. `review_state`
8. `viewer`

Those models are still owned by the shared review domain, but they remain part
of the current `buddy_console` runtime contract because `/review` depends on
them.

## Client-Side Local State

### Inventory

Stored in URL query params rather than local storage.

Important fields:

1. scope
2. root id
3. student id
4. subject
5. grade
6. type
7. marking filter
8. review filter
9. sort

### PDF Browser

Stored in local storage:

1. `buddy_console.pdf.showRaw`
2. `buddy_console.pdf.bookmarks`
3. `buddy_console.pdf.sidebarWidthPx`

Stored in URL query params:

1. `id`
2. `rel`
