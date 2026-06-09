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

### `viewer` (evidence modes)

Image entry shape (all pools): `{ "name", "page_num", "url" }` where `url` is under `/review-workspace-static/…`.

| Field | Source | Notes |
|-------|--------|-------|
| `attempt_images[]` | `context/marking_assets/…/attempt/` | `page-NN.png` naming |
| `answer_images[]` | `context/marking_assets/…/answers/` | answer-page slice |
| `template_images[]` | `context/file_question_info/…/rendered_pages/` | `page_NNN.png`; empty when no template link or no renders |
| `review_redo.available` | GoodNotes `Review/` PDF resolver | v0.1.16+; tab gating — not `review_images.length` |
| `review_redo.resolved_path` | Same resolver | Relative to `goodnotes_root`; debug only |
| `review_images[]` | Empty on detail load | Filled client-side from `review-evidence` response |
| `goodnotes_share_link` | GoodNotes `document_share` via `get_goodnotes_document_timestamps_for_file(..., folder_scope="attempt")` | Original notebook (outside `Review` leaf folder); shown in Attempt evidence toolbar |
| `goodnotes_review_share_link` | Same lookup with `folder_scope="review"` | Supervised-redo notebook under `.../Review`; shown in Review evidence toolbar |

### `context/review_redo/` (generated cache, gitignored)

Supervised redo page PNGs (v0.1.16+). Not under `file_question_info/` (avoids slug collision with template FQI renders).

```text
<context_root>/review_redo/<student_slug>/<subject_context>/<normal_name>/rendered_pages/page_%03d.png
```

| Segment | Helper |
|---------|--------|
| `<student_slug>` | `slugify_student(student_id, student_name)` — same as `marking_assets/` |
| `<subject_context>` | Marking artifact `context.subject_context` |
| `<normal_name>` | `normalize_pdf_display_name(template.name)` — same as FQI slug / marking stem (no `__timestamp` suffix) |

Static URL example:

```text
/review-workspace-static/review_redo/winston/singapore_primary_math/P6 Math WA1/rendered_pages/page_001.png
```

Those models are still owned by the shared review domain, but they remain part
of the current `buddy_console` runtime contract because `/review` depends on
them.

### Tutor chat (v0.2.0+)

Filesystem companion artifact `tutor_chat.v1` (not in git):

```text
context/tutor_chats/<student_id>/<subject_context>/<marking_artifact_stem>/<result_id>/<session_id>.json
```

#### `GET /api/student/attempts/{attempt_id}/questions/{result_id}/tutor-chat`

```json
{
  "session_id": "550e8400-e29b-41d4-a716-446655440000",
  "messages": [
    { "role": "student", "content": "…", "at": "2026-06-09T10:00:00Z" },
    {
      "role": "assistant",
      "content": "…",
      "at": "2026-06-09T10:00:15Z",
      "model": "auto",
      "runtime": "cursor-sdk-local",
      "run_id": "…"
    }
  ],
  "stale_context": {
    "marking": false,
    "review_notes": false
  }
}
```

#### `POST …/tutor-chat` (SSE)

| Event | Payload |
|-------|---------|
| `status` | `{ "phase": "started" \| "running" }` |
| `token` | `{ "text": "…" }` |
| `done` | `{ "session_id", "stale_context", "message" }` |
| `error` | `{ "code", "message" }` |

Schema: `ai_study_buddy/schemas/marking/tutor_chat.v1.schema.json`. See [proposal 4](./docs/proposal/4-review-workspace-question-tutor-chat.md).

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
4. `buddy-console-tutor-chat-height` (sessionStorage; v0.2.0+)
5. `buddy-console-tutor-chat-expanded` (sessionStorage; v0.2.0+)

Stored in URL query params:

1. `id`
2. `rel`
