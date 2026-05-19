# Changelog — `student_file_browser`

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
