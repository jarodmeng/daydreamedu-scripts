# Architecture — Student File Browser

## Layers

1. **Static UI** (`static/`) — filter bar, card grid, URL sync.
2. **HTTP server** (`serve.py`) — `ThreadingHTTPServer` on `localhost`, default port 8771.
3. **`ai_study_buddy.files` v0.3.0+** — all index and enrichment logic (marking/review flags via `marking.review.workflow_flags`).

## Startup

1. Resolve sync roots via `ai_study_buddy.files.roots`.
2. `build_main_pdf_index_for_roots(exclude_activity_note_completions=True, registry_index=...)` — main PDFs under leaf folders; registered rows only when `file_type='main'`; unregistered non-`_raw_` basenames kept for gap triage; excludes completion `activity`/`note` (gap-report universe); GoodNotes uses leaf-registry profile.
3. Build per-root sets of leaf directory paths for `/api/pdf` guard (same GoodNotes inclusion rules).

## Request flow

- **`GET /api/inventory`:** Load enriched cards once (cached on handler), apply `filter_main_pdf_cards` with `FilterCriteria` from query string.
- **`GET /api/config`:** Roots, students, filter enums; `show_is_registered_filter` is contextual (same query params as inventory — hidden when no unregistered mains match the other filters).

## Non-goals

- No registry mutations (scan/register/link).
- No marking or review editing (delegates to Review Workspace).
- No PDF thumbnails in v0.1.

## Security

Loopback bind only. `/api/pdf` uses `safe_resolve_under_root` and requires parent directory to be a known PDF leaf folder.
