# Start Root PDF browser

Start the **Root PDF browser** local server (browse `DAYDREAMEDU_ROOT` / `GOODNOTES_ROOT` and view PDFs).

## What to do

1. **Working directory:** repository root (`daydreamedu-scripts` workspace folder).

2. **Run this command (foreground is OK — it exits immediately):**

   ```bash
   python3 -m ai_study_buddy.root_pdf_browser.spawn_background
   ```

   This **detaches** the real server (`serve`) with `subprocess.Popen(..., start_new_session=True)` so the agent shell **does not wait** on `serve_forever()` (avoids “Agent is waiting for a command to finish” even when a “background” terminal is flaky).

   Forward flags to the server, e.g.:

   ```bash
   python3 -m ai_study_buddy.root_pdf_browser.spawn_background --port 8771 --no-browser
   ```

   Optional launcher-only flag: **`--log /path/to.log`** (append server stdout/stderr; default: `<temp>/root-pdf-browser.log`).

3. **Tell the user:** read the printed **URL**, **PID**, and **log path**. The server process still **opens the default browser** by default (same as `serve`). Use forwarded **`--no-browser`** to skip.

### Deep links (v0.1.6)

Open a specific PDF in the two-pane UI:

`http://127.0.0.1:8770/?id=<root_id>&rel=<posix/path/from/root/to/file.pdf>`

- `id` — `daydreamedu` or `goodnotes` (from `/api/config`).
- `rel` — path under that sync root with `/` separators.

Used by **Student File Browser** **View PDF** links. The app expands the tree on load (best effort) and keeps `id` / `rel` in the URL when navigating.

### Attached mode (optional)

If the user explicitly wants one terminal with **Ctrl+C** stopping the server (blocking `serve_forever`), run instead:

```bash
python3 -m ai_study_buddy.root_pdf_browser.serve
```

(Only for a real interactive terminal — **not** for the default Cursor agent flow.)

## Roots / config

- `DAYDREAMEDU_ROOT`, `GOODNOTES_ROOT`, or `ai_study_buddy/local_daydreamedu_root.txt` / `local_goodnotes_root.txt` — see [`ai_study_buddy/files/roots.py`](../../ai_study_buddy/files/roots.py).
- If both roots are missing, the **child** exits with a short message (check the log).

## Port in use

If bind fails, check the log; suggest `--port` (e.g. `8771`) or freeing **8770**, then spawn again.

## IDE shortcut

[`../../.vscode/tasks.json`](../../.vscode/tasks.json):

- **start-root-pdf-browser** — uses `spawn_background` (task finishes immediately; stop with printed `kill` PID).
- **start-root-pdf-browser (attached)** — runs `serve` with `isBackground` + problem matcher; **Tasks: Terminate Task** stops it.
