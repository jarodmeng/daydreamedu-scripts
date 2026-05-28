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

1. each item is derived from the enriched main-PDF inventory (`OnDiskMainPdfCard.to_dict()` from `ai_study_buddy.files`)
2. card content is used to drive inventory filters, PDF links, and review links

Completion vs registration (requires `files` v0.3.6+; `files_version` on inventory health is `files.__version__`):

| Field | UI | Meaning |
|-------|-----|---------|
| `completion_date` | **Completed {date}** | Student work date (`file_completion_dates`); `null` when unknown |
| `completion_date_source` | tooltip | e.g. `handwritten_page1`, `manual`, `goodnotes_last_modified` |
| `registry_added_at` | **Registered {date}** | `pdf_files.added_at` — scan/registry time only |

**Manual edit (Buddy Console v0.1.5+):** On registered completion cards (`scope=completion`, `registry_file_id` set), operators can PATCH a new `completion_date`. Writes use `source=manual` and `source_detail.set_via=buddy_console`; overwrites of inferred dates require browser confirmation. Audit: `operation_log` (`set_completion_date`) plus `previous_*` keys in `source_detail`. See [proposal 1-manual-completion-date-ui.md](./docs/proposal/1-manual-completion-date-ui.md).

Sort `recent` → **Completed (recent)** with unified recency ordering: primary `completion_date`, fallback `registry_added_at`, newest first across both (interleaved); unregistered remain last. See [proposal 17 §5.4](../pdf_file_manager/docs/proposals/17-completion-date.md#54-consumers-when-no-row-exists).

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
