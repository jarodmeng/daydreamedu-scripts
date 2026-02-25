## Cursor Cloud specific instructions

### Overview

This is a monorepo with two full-stack web apps and several utility/script projects. See `README.md` for folder layout.

| App | Backend | Frontend | DB required? |
|-----|---------|----------|-------------|
| **Chinese chr app** (`chinese_chr_app/chinese_chr_app/`) | Flask :5001 | React+Vite :3000 | No (uses JSON files by default) |
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
  USE_DATABASE=true \
  SUPABASE_URL="$VITE_SUPABASE_URL" \
  PINYIN_RECALL_DEV_USER=local-dev \
  GCS_BUCKET_NAME=chinese-chr-app-images \
  GOOGLE_APPLICATION_CREDENTIALS=~/.config/gcloud/sa-key.json \
  GOOGLE_CLOUD_PROJECT=daydreamedu \
  python3 app.py

# Frontend (background) — with auth bypass, unset Supabase vars to avoid conflict
cd chinese_chr_app/chinese_chr_app/frontend && \
  env -u VITE_SUPABASE_URL -u VITE_SUPABASE_ANON_KEY \
  VITE_E2E_AUTH_BYPASS=1 npm run dev
```

Without the secrets, the app still works: omit `USE_DATABASE`/`GCS_BUCKET_NAME` and the backend uses local JSON files and local PNG directory instead.

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
- **Backend**: Start with `PINYIN_RECALL_DEV_USER=local-dev python3 app.py`. All auth-gated endpoints (`/api/profile`, `/api/games/pinyin-recall/*`, `/api/profile/progress`) accept the dev user as a fallback when no valid Bearer token is present.

Combined, these allow full testing of Profile, Pinyin Recall game, and progress — without Supabase credentials or Google OAuth.

**Gotcha**: `VITE_E2E_AUTH_BYPASS=1` conflicts with real Supabase credentials on the frontend. When both `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` and `VITE_E2E_AUTH_BYPASS=1` are set, Supabase's `onAuthStateChange` fires and overrides the fake session with `null`. To use the E2E bypass, either:
- Don't pass `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` to the frontend: `env -u VITE_SUPABASE_URL -u VITE_SUPABASE_ANON_KEY VITE_E2E_AUTH_BYPASS=1 npm run dev`
- Or pass them to the backend only (the backend reads `DATABASE_URL` and `SUPABASE_URL` independently of the frontend)

The backend can still read real Supabase tables even when the frontend doesn't have Supabase vars — the `/api` proxy connects directly.

The only endpoint that does **not** support the dev user fallback is `/api/log-character-view` (requires a real Supabase JWT).

### Gotchas

- The Chinese chr app Vite config only enables the `/api` proxy when `NODE_ENV === 'development'`. Running `npm run dev` sets this automatically.
- The math multiplication app **cannot start** without `DATABASE_URL` set (no JSON fallback).
- Python packages install to user site-packages (`~/.local/lib/python3.12`). No virtualenv is needed in this cloud environment; `python3` picks them up directly.
- If `pip3 install` hits SSL errors, use `--trusted-host pypi.org --trusted-host files.pythonhosted.org` (see `.cursor/rules/pip-ssl-trusted-host.mdc`).
- **GCS images**: Character card images (字卡) are served from GCS when `GCS_BUCKET_NAME=chinese-chr-app-images` is set. The `GOOGLE_APPLICATION_CREDENTIALS_JSON` secret contains authorized_user ADC credentials; the agent writes them to `~/.config/gcloud/sa-key.json` and sets `GOOGLE_APPLICATION_CREDENTIALS` to that path. Since the ADC credentials lack a `project_id`, also pass `GOOGLE_CLOUD_PROJECT=daydreamedu`.
- **Remaining console error**: `/api/log-character-view` returns 401 with the E2E dev token because this endpoint uses `_get_profile_user()` only (no dev-user fallback). This is by design — it only logs views for real authenticated users. The frontend's `.catch(() => {})` silences the JS error but the browser still shows it in the console.
