# Changelog

All notable changes to **root_pdf_browser** are documented here.

---

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
