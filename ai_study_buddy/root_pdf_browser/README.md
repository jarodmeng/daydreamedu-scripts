# Root PDF browser

Local **two-pane** browser for PDFs under your configured **DaydreamEdu** and **GoodNotes** filesystem roots (dev / ops tooling). Runs a tiny HTTP server on loopback only; paths are constrained so requests cannot escape a chosen root.

**Current version:** `v0.1` — see [CHANGELOG.md](./CHANGELOG.md).

## Requirements

- Python 3 from the repo (same interpreter you use elsewhere in this workspace).
- At least one root configured via `DAYDREAMEDU_ROOT` and/or `GOODNOTES_ROOT`, or fallback files `ai_study_buddy/local_daydreamedu_root.txt` and `local_goodnotes_root.txt`. Resolution order and semantics are documented in [`ai_study_buddy/files/roots.py`](../files/roots.py).

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

## Tests

From the repo root:

```bash
python3 -m pytest ai_study_buddy/root_pdf_browser/tests -q
```

## See also

- [`.cursor/commands/start-root-pdf-browser.md`](../../.cursor/commands/start-root-pdf-browser.md) — operational notes for Cursor / IDE workflows.
- [`../../.vscode/tasks.json`](../../.vscode/tasks.json) — **start-root-pdf-browser** and attached **serve** task.
