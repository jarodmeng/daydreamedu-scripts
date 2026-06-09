# Changelog

All notable changes to `ai_study_buddy/buddy_console` are documented here.

## [v0.1.19] - Page-map amendment revert fix (2026-06-09)

### Fixed

1. **Review Workspace mapped-page amendments:** reverting `attempt_page_start` (or map confidence) to the AI base value now clears the persisted override instead of leaving a stale saved page (`App.tsx`, `App.test.ts`).

### Changed

1. `frontend/package.json` version aligned to `0.1.19`.
2. Requires `ai_study_buddy.marking` v0.3.22+.

## [v0.1.18] - GoodNotes share links and AirDrop in evidence toolbar (2026-06-08)

### Added

1. Review Workspace evidence toolbar shows GoodNotes share links for g_root completions — `viewer.goodnotes_share_link` (Attempt / original notebook) and `viewer.goodnotes_review_share_link` (Review / `.../Review` notebook).
2. **AirDrop** button beside the active share link — `POST /api/goodnotes/airdrop-share-link` launches `goodnotes_airdrop/AirDropShareLink.app` on macOS.
3. `goodnotes_airdrop/` macOS helper (`share_link_app.m`, `build_app.sh`, `airdrop_share_link`); built `.app` is gitignored and auto-built on first use.

### Changed

1. Requires `pdf_file_manager` **v0.3.36+** (`share_link`, `folder_scope` on Goodnotes lookup) and `marking` **v0.3.21+** (attempt-detail viewer fields).
2. `frontend/package.json` version aligned to `0.1.18`.

## [v0.1.17] - Review Workspace evidence page navigation fix (2026-06-08)

### Fixed

1. **Review Workspace evidence page navigation:** Answer (and Attempt/Template) Previous/Next and page dropdown no longer snap back on every render — `reviewImagesCache ?? []` had created a new empty-array reference each render, retriggering the image-sync effect (regression from v0.1.16 Review tab work). Covered by `viewerEvidence.test.ts`.

### Changed

1. `frontend/package.json` version aligned to `0.1.17`.

## [v0.1.16] - Review Workspace supervised redo tab (2026-06-07)

### Added

1. Review Workspace evidence toolbar **Review** mode — supervised redo pages from GoodNotes `Review/` exports (full template re-import; same page alignment as Attempt/Template).
2. Two-step load: attempt detail exposes `viewer.review_redo.available` (cheap stat); first tab click calls `GET /api/student/attempts/{attempt_id}/review-evidence` to cache-first raster into `context/review_redo/<student_slug>/<subject_context>/<normal_name>/rendered_pages/` (gitignored).
3. Page jump on **Review** reuses marking `question_page_map` (`attempt_page_start` per question).

### Changed

1. Requires `ai_study_buddy.files` **v0.3.13+** (`resolve_supervised_review_pdf_for_attempt`) and `ai_study_buddy.marking` **v0.3.20+** (review redo render + `review-evidence` API).
2. `frontend/package.json` version aligned to `0.1.16`.

See [proposal 3-review-workspace-supervised-redo-tab.md](./docs/proposal/3-review-workspace-supervised-redo-tab.md).

## [v0.1.15] - Review inventory facet + workspace deep links (2026-06-06)

### Fixed

1. **Student File Browser (review state):** unmarked completions no longer show **Review: not started** or appear in Review facet counts; Review “All” matches Marked count when Marking = Marked (inventory cards come from `ai_study_buddy.files` v0.3.12+).
2. **Review workspace deep links:** opening a marking review with `result_id` / `question_index` in the URL (including parenthetical IDs such as `Q17(b)`) now selects that question on load instead of defaulting to the first incorrect item (`WorkspaceView` initial state + image sync).

### Changed

1. Requires `ai_study_buddy.files` v0.3.12+ (restart inventory backend to refresh index).
2. `frontend/package.json` version aligned to `0.1.15`.

## [v0.1.14] - Inventory review-status toggle (2026-06-05)

### Added

1. Student File Browser card action **Mark review completed** / **Revert review** for marked completions (`ReviewStatusEditor`, `PATCH /api/inventory/items/{registry_file_id}/review-status`).

### Fixed

1. Student File Browser blank page on macOS: component import collided with helper module name on case-insensitive filesystem (`ReviewStatusEditor` + `reviewStatusEdit.ts`).

### Changed

1. `frontend/package.json` version aligned to `0.1.14`.

## [v0.1.13] - GoodNotes Review exclusion + amendment override cleanup (2026-06-05)

### Fixed

1. Amendment save: `pickAmendmentFieldsForSave` clears stale persisted overrides when the draft matches the AI base (`App.tsx`, `App.test.ts`).

### Changed

1. `frontend/package.json` version aligned to `0.1.13`.
2. Requires `ai_study_buddy.files` v0.3.11+ (GoodNotes `Review` subtree excluded from inventory index).
3. Requires `ai_study_buddy.marking` v0.3.19+.

## [v0.1.12] - Inventory multi-select facets (2026-06-03)

### Fixed

1. Review workspace (`/review`): in-attempt question navigation no longer overridden by re-parsing URL `result_id` after initial load (`App.tsx`; same fix as `review_workspace` v0.1.10).

### Added

1. **Subject**, **Grade**, and **Type** multi-select filters on Student File Browser (`MultiSelectFilter`, `inventoryFilterState`).
2. Repeated URL query params for facet values; **all options selected** in a facet is treated as no restriction before apply.

### Changed

1. `frontend/package.json` version aligned to `0.1.12`.
2. Requires `ai_study_buddy.files` v0.3.10+ for multi-value `FilterCriteria`.

## [v0.1.11] - Student portal marks by question type (2026-06-03)

### Fixed

1. Chinese picker: split standard vs higher Chinese stats by FQI `high-chinese` schema prefix (e.g. 字词改正 no longer rolls into standard Chinese when HC markings live under `singapore_primary_chinese`).

### Added

1. Route `/student` with four-choice subject picker and marks-by-type tables (serve-time compute).
2. `GET /api/student/marks-by-question-type` backed by `build_marked_completion_fqi_stats` (no static `student_understandings` JSON reads).
3. Backend `student_portal_api.py` / `student_portal_service.py`; frontend `StudentPortalApp.tsx` / `studentPortalApi.ts`.
4. Tests: `tests/test_student_marks_api.py`, Vitest helpers in `studentPortalMarks.test.ts`.

### Changed

1. `frontend/package.json` version aligned to `0.1.11`.

## [v0.1.10] - Question-level review deep links (2026-06-02)

### Added

1. Review deep links now support question-level targeting via `result_id` (canonical) with optional `question_index` (1-based fallback) in addition to existing `attempt_id`/`student_id`.
2. Workspace selection sync writes `result_id` into URL query params as users navigate questions, so copied links reopen the same question context.

### Changed

1. `frontend/package.json` version aligned to `0.1.10`.

## [v0.1.9] - Template evidence viewer (2026-06-02)

### Added

1. Review panel evidence toolbar **Template** mode (clean worksheet pages from linked template FQI `rendered_pages/`); shown only when `viewer.template_images` is non-empty.

### Changed

1. Depends on `marking` **v0.3.17** for `viewer.template_images[]` on attempt detail API.

## [v0.1.8] - Amendment save and overlay fixes (2026-05-30)

### Fixed

1. Review panel: amendment save payload diffs are computed against the immutable AI base question (aligned with dirty-state detection), avoiding empty `question_amendments` payloads when the resolved row already matched the draft.
2. Amendment overlays persist and display correctly when paired with `marking` **v0.3.16+** and `learning_db` **v0.1.9+** (API response uses freshly resolved marking; DB upsert revives soft-deleted amendment rows).

### Changed

1. Depends on `marking` **v0.3.16** and `learning_db` **v0.1.9** for amendment read/write consistency under DB-first reads.

## [v0.1.7] - Inventory load performance (2026-05-29)

### Fixed

1. Inventory enrichment is cached again in-process; cache invalidates when marking/review JSON under `context/` changes, on manual completion-date edits, and on review/amendment API writes — so review chips stay fresh without rebuilding on every `/api/config` + `/api/inventory` request.
2. Inventory UI loads config and list in parallel after the first enriched build (shared cache + mutex).

### Changed

1. Depends on `files` **v0.3.9** and `marking` **v0.3.15** for a single marking-artifact index per enrichment pass (one `marking_results` scan) instead of per-PDF `rglob` lookups.

## [v0.1.6] - Inventory review status freshness (2026-05-28)

### Fixed

1. Inventory API no longer serves stale review chips from a long-lived enriched-cache snapshot; review status is recomputed per request so cards reflect latest review workspace updates after refresh.

## [v0.1.5] - Manual completion date on inventory cards (2026-05-28)

### Added

1. `PATCH /api/inventory/items/{registry_file_id}/completion-date` — set/overwrite **Completed** via `PdfFileManager.set_completion_date` (`source=manual`, `source_detail.set_via=buddy_console`, audit `previous_*` on overwrite).
2. Inventory card date editor (registered completions only): date input + **Save**; confirm when replacing a non-manual inferred date; refetch inventory after success.

See [proposal 1-manual-completion-date-ui.md](./docs/proposal/1-manual-completion-date-ui.md).

## [v0.1.4] - Runtime files version from package (2026-05-28)

### Changed

1. Inventory `files_version` on `/api/inventory/health` is `ai_study_buddy.files.__version__` (no local duplicate constant).

## [v0.1.3] - Unified recency sort (2026-05-28)

### Changed

1. **Completed (recent)** inventory sort uses `files` v0.3.7 unified recency ordering (`completion_date` with `registry_added_at` fallback, interleaved; unregistered last).
2. `/api/inventory/health` and inventory config report `files_version` **0.3.7**.

## [v0.1.2] - Inventory sort apply-on-change fix (2026-05-28)

### Fixed

1. Inventory **Sort** now applies immediately on change (including **Name (A-Z)**), so card order refreshes without requiring a separate **Apply filters** click.

## [v0.1.1] - Inventory completion dates and load fixes (2026-05-27)

### Added

1. Inventory cards show **Completed** date (`completion_date` + source tooltip) and **Registered** date separately; sort **Completed (recent)** uses `files` v0.3.6 completion-date ordering.

### Fixed

1. Vite dev/preview now binds `127.0.0.1:5178` so deep links and README URLs using `http://127.0.0.1:5178/...` work on macOS (default `localhost` could be IPv6-only and reject `127.0.0.1`).
2. Inventory header subtitle no longer references the legacy Student File Browser port `8771`.
3. Inventory no longer appears hung on first load: enrichment is mutex-guarded (parallel `/api/config` + `/api/inventory` no longer double-build), warms on backend startup, loads config then inventory sequentially, skips duplicate draft `/api/config` until the first inventory load finishes, and shows a first-load timing hint from `/api/inventory/health`.

## [v0.1.0] - Seeded unified app baseline (2026-05-26)

Implemented:

1. created `buddy_console` as a new app package
2. seeded the app from `review_workspace` to preserve review functionality
3. added inventory route and backend inventory APIs
4. added PDF route and backend PDF browser APIs
5. preserved deep-link-driven workflow from inventory into PDF and review

Notes:

1. `buddy_console` is a new app identity even though the initial review surface is seeded
2. inventory and PDF parity work is ongoing
3. this changelog starts fresh for `buddy_console` rather than inheriting `review_workspace` history
