## Cursor Cloud specific instructions

### Overview

This is a monorepo with two full-stack web apps and several utility/script projects. See `README.md` for folder layout.

| App | Backend | Frontend | DB required? |
|-----|---------|----------|-------------|
| **Chinese chr app** (`chinese_chr_app/chinese_chr_app/`) | Flask :5001 | React+Vite :3000 | Yes (`DATABASE_URL`/`SUPABASE_URL` required; DB-only runtime) |
| **Math multiplication** (`math_multiplication/`) | Flask :5001 | React+Vite :3000 | Yes (`DATABASE_URL` required) |

Both apps share ports 5001/3000 — only one can run at a time.

### Running the Chinese chr app

See the skill file at `.cursor/skills/start-local-servers/SKILL.md` for basic instructions. For the full setup with real Supabase DB and GCS images:

```bash
# Write GCP credentials (if GOOGLE_APPLICATION_CREDENTIALS_JSON secret is set)
mkdir -p ~/.config/gcloud
echo "$GOOGLE_APPLICATION_CREDENTIALS_JSON" > ~/.config/gcloud/sa-key.json
chmod 600 ~/.config/gcloud/sa-key.json

# Backend (background) — with real DB + GCS + dev user bypass
cd chinese_chr_app/chinese_chr_app/backend && \
  SUPABASE_URL="$VITE_SUPABASE_URL" \
  PINYIN_RECALL_DEV_USER=local-dev \
  GCS_BUCKET_NAME=chinese-chr-app-images \
  GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/sa-key.json \
  GOOGLE_CLOUD_PROJECT=daydreamedu \
  python3 app.py

# Frontend (background) — with auth bypass (unsetting Supabase vars is optional defense-in-depth)
cd chinese_chr_app/chinese_chr_app/frontend && \
  env -u VITE_SUPABASE_URL -u VITE_SUPABASE_ANON_KEY \
  VITE_E2E_AUTH_BYPASS=1 npm run dev
```

Without DB credentials, the backend will now fail on startup (DB-only runtime). `GCS_BUCKET_NAME` is still optional; without it the backend serves local PNGs.

The Vite dev server proxies `/api` to `http://localhost:5001` automatically.

### Running E2E tests (Chinese chr app)

From `chinese_chr_app/chinese_chr_app/frontend`:

```
npx playwright test
```

If the backend and frontend are already running, Playwright reuses them (`reuseExistingServer: true` outside CI). Otherwise it starts them via `webServer` config.

### Building frontends

Both frontends use `npm run build` (Vite). No lint command is configured in `package.json` — the build itself serves as the primary code quality check.

### Testing signed-in user flows (no real credentials needed)

The codebase has built-in dev auth bypass mechanisms:

- **Frontend**: Start with `VITE_E2E_AUTH_BYPASS=1 npm run dev` (or append `?e2e_auth=1` to any URL). The UI creates a fake session so it behaves as if a user is signed in.
- **Backend**: Start with `PINYIN_RECALL_DEV_USER=local-dev python3 app.py`. Auth-gated learning/profile endpoints (including `/api/profile`, `/api/profile/progress*`, `/api/games/pinyin-recall/*`, and `/api/log-character-view`) accept the dev user as a fallback when no valid Bearer token is present.

Combined, these allow full testing of Profile, Pinyin Recall game, and progress without Google OAuth. Supabase DB credentials are still required because the backend is DB-only.

**Note (updated):** The frontend E2E auth bypass is now authoritative (the fake session is not overwritten by Supabase `onAuthStateChange`). You can still unset frontend Supabase vars as defense-in-depth / to reduce confusion in local testing:
- Optional hardening: don't pass `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` to the frontend: `env -u VITE_SUPABASE_URL -u VITE_SUPABASE_ANON_KEY VITE_E2E_AUTH_BYPASS=1 npm run dev`
- Or pass them to the backend only (the backend reads `DATABASE_URL` and `SUPABASE_URL` independently of the frontend)

The backend can still read real Supabase tables even when the frontend doesn't have Supabase vars — the `/api` proxy connects directly.

### Gotchas

- The Chinese chr app Vite config only enables the `/api` proxy when `NODE_ENV === 'development'`. Running `npm run dev` sets this automatically.
- The math multiplication app **cannot start** without `DATABASE_URL` set (no JSON fallback).
- Python packages install to user site-packages (`~/.local/lib/python3.12`). No virtualenv is needed in this cloud environment; `python3` picks them up directly.
- If `pip3 install` hits SSL errors, use `--trusted-host pypi.org --trusted-host files.pythonhosted.org` (see `.cursor/rules/pip-ssl-trusted-host.mdc`).
- **GCS images**: Character card images (字卡) are served from GCS when `GCS_BUCKET_NAME=chinese-chr-app-images` is set. The `GOOGLE_APPLICATION_CREDENTIALS_JSON` secret contains authorized_user ADC credentials; the agent writes them to `~/.config/gcloud/sa-key.json` and sets `GOOGLE_APPLICATION_CREDENTIALS` to that path. Since the ADC credentials lack a `project_id`, also pass `GOOGLE_CLOUD_PROJECT=daydreamedu`.
- **Auth bypass logging note**: In E2E/dev-user mode, expected fake-token JWT parse failures (for example `DecodeError`) are suppressed before the backend falls back to `PINYIN_RECALL_DEV_USER`, so local logs are less noisy. Unexpected auth failures may still be logged.
