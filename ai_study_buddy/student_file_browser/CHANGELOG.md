# Changelog — `student_file_browser`

## [v0.1.11] — GoodNotes Review exclusion docs (2026-06-05)

- README: GoodNotes leaf listing excludes post-review `Review` subtrees (requires `files` v0.3.11+).

## [v0.1.10] — Multi-select Subject / Grade / Type (2026-06-03)

- Checkbox facet pickers for **Subject**, **Grade**, and **Type** (repeated query params, e.g. `?subject=math&subject=science`).
- `filters.py` parses multi-value facets via `normalize_facet_values` (`files` v0.3.10+).
- UI: click-outside and single-open-menu behavior; selecting every option in a facet equals **All**; facet lists preserved when contextual meta is empty.

## [v0.1.9] — Runtime files version from package (2026-05-28)

- `/api/health` `files_version` is `ai_study_buddy.files.__version__` (requires `files` v0.3.8+).

## [v0.1.8] — Unified recency sort (2026-05-28)

- **Completed (recent)** uses `files` v0.3.7 unified recency ordering (`completion_date` with `registry_added_at` fallback, interleaved; unregistered last).
- `/api/health` `files_version` is **0.3.7**.

## [v0.1.7] — Completion date on cards (2026-05-27)

- Cards show **Completed** date when `completion_date` is set; **Registered** date remains separate (`registry_added_at`).
- Sort label **Completed (recent)**; requires `files` v0.3.6 (`completion_date` sort per proposal 17 §5.4).
- `/api/health` `files_version` is **0.3.6**.

## [v0.1.6] — Marking score on marked cards (2026-05-21)

- Marked completion cards show **`X/Y (Z%)`** between the title and registry date (resolved summary from `files` v0.3.5).
- Requires `ai_study_buddy.files` v0.3.5; `/api/health` `files_version` is **0.3.5**.

## [v0.1.5] — Card sort order (2026-05-20)

- **Sort** filter bar control and URL param `sort=recent|name` (default **Recent first**; omitted from URL when default).
- Requires `ai_study_buddy.files` v0.3.4 (`sort_main_pdf_cards`, `registry_added_at` on inventory items).
- Registered cards show registry **added** date under the title (subtle grey line; full ISO on hover).
- **Sort** dropdown reapplies inventory immediately on change (no separate **Filter** click required for sort only).

## [v0.1.4] — Completion series chip (2026-05-20)

- Status chip **`Attempt {n} of {m}`** beside the card title when `attempt_count > 1` and `attempt_sequence` is set (from `ai_study_buddy.files` v0.3.3 inventory enrichment).
- Requires `files` v0.3.3+; `/api/health` reports `files_version` **0.3.3**.

## [v0.1.3] — Root filter (2026-05-20)

- **Root** filter bar control and URL param `root_id=all|daydreamedu|goodnotes` (requires `ai_study_buddy.files` v0.3.2).
- Default **All roots** (`root_id=all`; omitted from URL).
- Contextual `root_ids` / `root_counts` in `/api/config` and `/api/inventory` meta.

## [v0.1.2] — Sibling app links use localhost (2026-05-19)

- **Review Workspace** and **View PDF** deep links normalize `127.0.0.1` / `::1` to **`localhost`** so handoff matches Review Workspace and Root PDF Browser (Vite on `localhost:5178`, etc.).
- Server bind and startup URL use **`http://localhost:8771/`** instead of `127.0.0.1`.

## [v0.1.1] — Review Workspace attempt deep links (2026-05-19)

- Card **Review Workspace** links open port **5178** with `?attempt_id=<registry_file_id>&student_id=<student_id>` when marked and registered (requires `review_workspace` v0.1.4+).
- **View PDF** deep links into Root PDF Browser (port **8770**).
- Falls back to app root with console warning if `registry_file_id` is missing.

## [v0.1.0] — Initial release

- Filter-first card grid for on-disk main PDFs (completion/template, subject, grade, type, book, registration).
- **Registered** filter shown only when the current filter slice (excluding registration) still has unregistered mains.
- GoodNotes index uses the **leaf-registry report** leaf set (default `exclude_not_completed=True`), not the `root_pdf_browser` WIP browse profile.
- **Filter** button applies filters (no auto-refresh on each dropdown change); stale in-flight responses are ignored.
- **Reset** button restores default filters and reloads inventory.
- **Filter** refreshes all dropdown option lists from the current contextual slice (scope, facets, registration, template, marking, review — no fixed Has/No lists); each option shows file count as `Label (n)`.
- **Book name** is a dropdown (`book_names` from the index, scoped to current filters) when Type = Book.
- Card **workflow status** (registered, template, marking, review) shown as colored badges instead of plain text.
- Index excludes completion **activity** / **note** mains (same universe as `completion_template_link_gap_report`).
- Main-PDF index uses registry **`file_type='main'`** for registered paths (not basename-only); fixes duplicate GoodNotes cards when a non-`_raw_` file is registered as `raw` and `_c_*` is the real main.
- Conditional **Template**, **Marking**, and **Review** filters (shown when the slice has ≥2 registered completions or >1 distinct value for that flag).
- URL query-parameter sync; `localStorage` last student selection (`students.id`, not email).
- Flags: registered, template link, marking, amendment, review status (via `files` v0.3.0+ / `marking` v0.3.8 workflow loader).
- Actions: **View PDF** (deep link into Root PDF Browser), copy path, Review Workspace when marked.
- Default port **8771**; loopback only.
