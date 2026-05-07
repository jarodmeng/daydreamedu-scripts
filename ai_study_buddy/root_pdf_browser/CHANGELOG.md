# Changelog

All notable changes to **root_pdf_browser** are documented here.

---

## [v0.1.4] — Registry badges and runtime correlation

- **Registry-aware badges:** `/api/list` now resolves **scan-root** and **per-PDF registration** at request time via `ai_study_buddy.files.pdf_registry_paths.RegistryPathIndex` and friends. The tree shows small 📁 / 📄 glyphs beside scan-root folders and registered PDFs (idempotent, no duplicated tags).
- **Runtime snapshot:** registry information is pulled fresh for each listed folder; filesystem contents are still read live from disk.
- **Layout tweaks:** denser tree spacing, smaller indents, and compact bookmark/filename gap so long filenames fit better.

## [v0.1.3] — Hide `_raw_*` files by default with sidebar toggle

- **Sidebar control:** new **Show `_raw_` files** checkbox (top of sidebar). Default **off**: PDFs whose basename starts with **`_raw_`** are hidden from the tree on the client. Toggle is persisted in `localStorage` (`root_pdf_browser.showRaw`).
- **In-place visibility (no re-render):** every PDF is rendered once per folder; `_raw_*` rows are tagged `is-raw-row` and shown/hidden via `body.hide-raw` CSS rules. Flipping the toggle no longer collapses already-expanded `<details>` along the path you were traversing.
- **Hint UX:** any leaf folder that contains `_raw_` files always renders a faint "N _raw_ files hidden" hint line; the same CSS rule (`body:not(.hide-raw)`) hides that hint once `_raw_` rows are visible. Truly empty folders still show "(empty)".
- **Server unchanged:** filter is purely UI-side; `/api/list` still returns every PDF, and `/api/pdf` still serves `_raw_*.pdf` directly when requested. No changes to path confinement or leaf-folder logic.

## [v0.1.2] — Leaf-prefix navigation from `files` leaf-folder lists

- **Browse tree** = POSIX prefixes of **`list_daydreamedu_leaf_folders_under_root`** / **`list_goodnotes_leaf_folders_under_root(..., exclude_not_completed=False)`** (computed once at startup; printed counts per root).
- **No full-directory walk** from the sync root UI: orphaned folders (no leaf descendant) disappear; stray **`db`**-style dirs without PDF leaf paths no longer clutter DaydreamEdu.
- **`/api/pdf`** only when the resolved file’s parent path is exactly one of those leaf-folder keys (`''` denotes PDFs sitting directly under the sync root when that leaf exists).
- **Rel normalization:** filesystem root resolves to POSIX key `''`, not `"."`.

## [v0.1.1] — `ai_study_buddy.files` integration; GoodNotes *Not completed* visible

- Roots via **`from ai_study_buddy.files import resolve_daydreamedu_root, resolve_goodnotes_root`** (package surface).
- GoodNotes **`/api/list`** and **`/api/pdf`** use **`is_goodnotes_excluded_relative_path(..., exclude_not_completed=False)`** on canonical paths under the sync root: hides **x-prefix** segments; **shows *Not completed* subtrees**.
- Depends on **`files` [v0.1.3]** (`is_goodnotes_excluded_relative_path`).

## [v0.1] — Initial documented release

- Package-local README and changelog; version baseline for this surface.
- **Serve:** `ThreadingHTTPServer` on `127.0.0.1`; static SPA-style UI under `static/`; JSON APIs `/api/config`, `/api/list`, `/api/pdf` with path confinement (`safe_resolve_under_root`, `list_dir_children`).
- **Roots:** DaydreamEdu and GoodNotes via `ai_study_buddy.files.roots` (`DAYDREAMEDU_ROOT`, `GOODNOTES_ROOT`, `local_*_root.txt` fallbacks).
- **Launcher:** `spawn_background` detaches `serve` with `--log` and forwarded `serve` flags (default port `8770`, optional `--no-browser`).
- **Tests:** pytest coverage for path guard, listings, PDF-only filtering, and `Content-Disposition` filename handling.
