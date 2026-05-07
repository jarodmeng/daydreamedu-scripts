# Changelog

All notable changes to **root_pdf_browser** are documented here.

---

## [v0.1] — Initial documented release

- Package-local README and changelog; version baseline for this surface.
- **Serve:** `ThreadingHTTPServer` on `127.0.0.1`; static SPA-style UI under `static/`; JSON APIs `/api/config`, `/api/list`, `/api/pdf` with path confinement (`safe_resolve_under_root`, `list_dir_children`).
- **Roots:** DaydreamEdu and GoodNotes via `ai_study_buddy.files.roots` (`DAYDREAMEDU_ROOT`, `GOODNOTES_ROOT`, `local_*_root.txt` fallbacks).
- **Launcher:** `spawn_background` detaches `serve` with `--log` and forwarded `serve` flags (default port `8770`, optional `--no-browser`).
- **Tests:** pytest coverage for path guard, listings, PDF-only filtering, and `Content-Disposition` filename handling.
