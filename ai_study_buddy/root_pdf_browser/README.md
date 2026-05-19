# Root PDF browser

Local **two-pane** browser for PDFs under your configured **DaydreamEdu** and **GoodNotes** filesystem roots (dev / ops tooling). Runs a tiny HTTP server on loopback only; paths are constrained so requests cannot escape a chosen root.

**Current version:** `v0.1.6` — see [CHANGELOG.md](./CHANGELOG.md).

## Requirements

- Python 3 from the repo (same interpreter you use elsewhere in this workspace).
- At least one root configured via `DAYDREAMEDU_ROOT` and/or `GOODNOTES_ROOT`, or fallback files `ai_study_buddy/local_daydreamedu_root.txt` and `local_goodnotes_root.txt`. Roots come from [`ai_study_buddy.files`](../files/) (`resolve_daydreamedu_root` / `resolve_goodnotes_root`).

## Quick start

**Foreground (attached; Ctrl+C stops the server):**

```bash
cd /path/to/daydreamedu-scripts
python3 -m ai_study_buddy.root_pdf_browser.serve
```

Default URL: `http://127.0.0.1:8770/`

**Background (parent exits immediately; useful from agents / scripts):**

```bash
python3 -m ai_study_buddy.root_pdf_browser.spawn_background
```

Forwarded flags apply to `serve`, e.g. `--port 8771 --no-browser`. Launcher-only: `--log /path/to.log` (default: `<temp>/root-pdf-browser.log`).

## CLI flags (`serve`)

| Flag | Default | Meaning |
|------|---------|---------|
| `--port` | `8770` | Listen port |
| `--no-browser` | off | Do not open the default browser after startup |

## HTTP surface

| Path | Method | Role |
|------|--------|------|
| `/`, `/app.css`, `/app.js` | GET | Static UI |
| `/api/config` | GET | JSON: available roots (`id`, `label`, absolute `path`) |
| `/api/list` | GET | Query `id`, `rel` — JSON: subdirectory names and `.pdf` basenames |
| `/api/pdf` | GET, HEAD | Query `id`, `rel` — PDF bytes or headers only |

All file access goes through `safe_resolve_under_root`; dotfiles are skipped in listings.

### Deep linking

Open a specific PDF in the two-pane UI with query parameters (also used by **Student File Browser** card links):

`http://127.0.0.1:8770/?id=<root_id>&rel=<posix/path/from/root/to/file.pdf>`

- `id` — `daydreamedu` or `goodnotes` (same as `/api/config` roots).
- `rel` — path relative to that sync root, using `/` separators (e.g. `completion/Singapore Primary English/winston@x.com/P6/Book/foo.pdf`).

On load, the app expands folders along `rel` (best effort), opens the PDF in the viewer, and keeps the URL in sync when you pick other files from the tree.

**Raw-file filter (UI-only):** by default the sidebar hides PDFs whose basename starts with **`_raw_`** (the registry's raw-archive convention). A leaf folder containing other PDFs gets a small "(N _raw_ files hidden)" hint; an otherwise-empty leaf collapses to that same hint instead of "(empty)". Toggle **Show `_raw_` files** at the top of the sidebar to reveal them; the choice is persisted in `localStorage` (`root_pdf_browser.showRaw`). The server still serves these files when requested directly via `/api/pdf` — the filter is purely client-side.

**Navigation model:** the tree is built from **`ai_study_buddy.files` PDF leaf folders** only — prefixes of **`list_daydreamedu_leaf_folders_under_root(daydreamedu_root)`** and **`list_goodnotes_leaf_folders_under_root(goodnotes_root, exclude_not_completed=False)`**. Directories that never lead to a leaf folder are hidden (for example stray top-level **`db/`** without PDF leaves). **`/api/pdf`** is served only when the PDF’s parent directory is itself a leaf folder in that snapshot. If a synced root contains **zero** qualifying leaf folders, that root opens with an empty tree at the top level. Restart the server to refresh the index after big filesystem changes.

## Tests

From the repo root:

```bash
python3 -m pytest ai_study_buddy/root_pdf_browser/tests -q
```

## See also

- [`.cursor/commands/start-root-pdf-browser.md`](../../.cursor/commands/start-root-pdf-browser.md) — operational notes for Cursor / IDE workflows.
- [`../../.vscode/tasks.json`](../../.vscode/tasks.json) — **start-root-pdf-browser** and attached **serve** task.
