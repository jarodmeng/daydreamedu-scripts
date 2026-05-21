# Specification — Student File Browser

## HTTP routes

| Path | Method | Description |
|------|--------|-------------|
| `/` | GET | Static UI |
| `/api/health` | GET | `{ status, index_count, files_version }` |
| `/api/config` | GET | Roots, students, filter options; accepts same query params as inventory for contextual `show_is_registered_filter` |
| `/api/inventory` | GET | Filtered cards; query params below |
| `/api/pdf` | GET, HEAD | `id` + `rel` under root; leaf-folder guard |

## Inventory query parameters

| Param | Values | Default |
|-------|--------|---------|
| `scope` | `completion`, `template` | `completion` |
| `root_id` | `all`, `daydreamedu`, `goodnotes` | `all` (omitted from URL when default) |
| `student` | registry `students.id` (e.g. `winston`) or empty | empty |
| `subject` | `chinese`, `english`, `math`, `science`, `all` | `all` |
| `grade` | `P1`…`P6`, `PSLE`, `all` | `all` |
| `doc_type` | `exam`, `book`, `exercise`, `all` | `all` |
| `book` | book group name (path segment after `Book/`) | empty (= all books) |
| `is_registered` | `true`, `false` | omitted |
| `has_template` | `true`, `false` | omitted |
| `has_marking` | `true`, `false` | omitted |
| `review_status` | `not_started`, `in_progress`, `completed` | omitted |
| `sort` | `name`, `recent` | `recent` (omitted from URL when default) |

## Inventory item fields

See `OnDiskMainPdfCard.to_dict()` in `ai_study_buddy.files.on_disk_inventory`.

## UI behaviour

- Filter controls do not refresh results on change; click **Filter** to run `/api/inventory` and update the URL. **Sort** applies immediately on change (also via **Filter**); server orders by `recent` (registry `added_at` newest first) or `name` (display name A–Z). Each apply refreshes dropdown options from the contextual slice (`root_ids`, `subjects`, `grades`, `doc_types`, `student_ids`, `book_names`, workflow visibility) in response `meta`. **Reset** restores defaults and reloads.
- Card **View PDF** opens Root PDF Browser with `?id=` + `rel=` deep link (not inline `/api/pdf`).
- Card **Review Workspace** (when `has_marking=true` and registered) opens Review Workspace at **`http://localhost:5178/`** (port **5178**) with `?attempt_id=<registry_file_id>` and `student_id=<student_id>` when available. Links normalize `127.0.0.1` / `::1` to `localhost` so the handoff matches how Review Workspace is served.
- Card **View PDF** uses the same **`localhost`** normalization for Root PDF Browser (port **8770**).
- Changing **Scope** or **Type** updates dependent controls (student disabled, book name dropdown when Type = Book) without loading inventory. Book options come from `book_names` in `/api/config` and `/api/inventory` meta (contextual to other filters).
- **Registered** when the slice mixes registered and unregistered. **Template** / **Marking** / **Review** when the slice has ≥2 registered completions or more than one distinct value for that dimension; workflow filters apply to registered completions only.
- In-flight inventory requests are dropped when a newer **Filter** click supersedes them.
- When `attempt_count > 1` and `attempt_sequence` is set, show **`Attempt {attempt_sequence} of {attempt_count}`** beside the card title (registry-derived; requires `files` v0.3.3+).
- When `has_marking` and score fields are present, show **`X/Y (Z%)`** between title and registry date (`.card-marking-score`; requires `files` v0.3.5+).
- When `registry_added_at` is set, show a locale-formatted date under the title (`.card-registry-date`; full ISO in `title` tooltip; requires `files` v0.3.4+).
- **Sort** control lives in the filter actions row after **Reset**; changing it reloads inventory immediately.

## Environment

- `PDF_REGISTRY_PATH` — registry SQLite (optional)
- `AI_STUDY_BUDDY_CONTEXT_ROOT` — marking/review context (default `ai_study_buddy/context`)
