# Changelog

All notable changes to `ai_study_buddy/buddy_console` are documented here.

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
