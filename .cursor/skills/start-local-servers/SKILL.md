---
name: start-local-servers
description: Starts the Chinese chr app local dev servers for testing. Frees ports 5001 and 3000 by killing any processes using them, then starts the Flask backend and Vite frontend in background. Use when the user asks to start local servers, run the app locally, or test in the browser.
---

# Start Local Servers for Testing

Use this workflow when the user wants to start the Chinese character app locally for testing.

## Ports

- **Backend (Flask):** 5001
- **Frontend (Vite):** 3000 (proxies `/api` to backend)

## Steps

Run from the **repository root** (e.g. `daydreamedu-scripts/`).

### 1. Free the ports

Kill any process listening on 5001 or 3000 so the servers can bind:

```bash
# Kill process on port 5001 (backend)
lsof -ti :5001 | xargs kill -9 2>/dev/null || true

# Kill process on port 3000 (frontend)
lsof -ti :3000 | xargs kill -9 2>/dev/null || true
```

On some systems `lsof -ti :PORT` may need to be quoted or run differently; if `lsof` is not available, use the platform’s equivalent (e.g. `fuser -k 5001/tcp` on Linux).

### 2. Start backend in background

```bash
cd chinese_chr_app/chinese_chr_app/backend && python3 app.py
```

Run this command with **is_background: true** so the Flask server keeps running.

### 3. Start frontend in background

```bash
cd chinese_chr_app/chinese_chr_app/frontend && npm run dev
```

Run this command with **is_background: true** so the Vite dev server keeps running.

### 4. Tell the user

- **App URL:** http://localhost:3000/
- **API:** http://localhost:5001/ (frontend proxies `/api` to this in dev)

## Stopping the servers

To stop them later, kill the background processes (e.g. by PIDs from the run output or by port again):

```bash
lsof -ti :5001 | xargs kill -9 2>/dev/null || true
lsof -ti :3000 | xargs kill -9 2>/dev/null || true
```

## Paths (from repo root)

| Server   | Directory                                      | Command        |
|----------|-------------------------------------------------|----------------|
| Backend  | `chinese_chr_app/chinese_chr_app/backend`       | `python3 app.py` |
| Frontend | `chinese_chr_app/chinese_chr_app/frontend`     | `npm run dev`  |
