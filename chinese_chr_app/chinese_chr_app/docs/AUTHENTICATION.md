# Authentication and Auth Bypass Audit (Chinese Chr App)

Audit date: 2026-02-26

Scope: `chinese_chr_app/chinese_chr_app/` frontend + backend auth flow, Supabase Google auth, local dev fallback user, and Playwright E2E bypass behavior.

## Executive Summary

Authentication behavior is controlled by 3 mostly independent switches:

1. Frontend identity source
- Real Supabase session (Google auth)
- E2E fake session (`VITE_E2E_AUTH_BYPASS=1` or `?e2e_auth=1`)
- Unauthenticated (`user = null`)

2. Backend auth acceptance
- Real Bearer JWT verified against Supabase JWKS
- Optional fallback dev user from `PINYIN_RECALL_DEV_USER`

3. Backend data/logging mode
- Supabase/Postgres (DB-only runtime; no JSON/file/in-memory fallback mode)

Important current behavior:
- The frontend E2E bypass is now authoritative (commit `bcc9ebf`): when bypass is active, `AuthContext` does not subscribe to Supabase `onAuthStateChange(...)`, so the fake session is not overwritten by a real session or `null`.
- `?e2e_guest=1` explicitly forces unauthenticated UI state even when Supabase is configured.

## Architecture Overview

### Frontend auth state (source of truth for UI)

The UI treats `useAuth().user` as the authenticated state.

- `Profile` page shows login prompt when `!user`: `frontend/src/pages/Profile.jsx:88`
- `PinyinRecall` page shows login prompt when `!user`: `frontend/src/pages/PinyinRecall.jsx:250`
- NavBar shows `我的` only when `user` exists: `frontend/src/NavBar.jsx:127`

This means a backend dev fallback alone is not enough to make the UI "look logged in"; the frontend must have a user/session (real Supabase or E2E fake session).

### Backend auth (API acceptance)

Backend auth is request-based and route-specific.

- Real auth path:
  - Extracts Bearer token from `Authorization` header
  - Verifies JWT against Supabase JWKS using `SUPABASE_URL`
  - Files: `backend/auth.py:23`, `backend/auth.py:52`, `backend/auth.py:86`

- Dev fallback path:
  - `PINYIN_RECALL_DEV_USER` creates a fake backend user object
  - File: `backend/app.py:1142`

- Most auth-gated routes use "real user OR dev user":
  - `_get_profile_user_or_dev()` -> `_get_profile_user() or _get_pinyin_recall_dev_user()`
  - File: `backend/app.py:1153`

- Backend precedence matters:
  - If a valid real Bearer JWT is present, backend uses the real user first and ignores `PINYIN_RECALL_DEV_USER`.

### Backend data/logging mode (DB-only runtime)

This is separate from authentication.

- The backend runtime is DB-only (no `USE_DATABASE` toggle)
- DB connection requires `DATABASE_URL` or `SUPABASE_DB_URL`
  - `backend/database.py:21`

## Frontend Auth Flow (Detailed)

Files:
- `frontend/src/supabaseClient.js`
- `frontend/src/AuthContext.jsx`

### Supabase client creation

`supabase` is created only when both are set:
- `VITE_SUPABASE_URL`
- `VITE_SUPABASE_ANON_KEY`

Reference: `frontend/src/supabaseClient.js:3`, `frontend/src/supabaseClient.js:14`

If either is missing:
- `supabase` is `null`
- Google sign-in is disabled
- E2E bypass can still create a fake frontend session

### E2E bypass logic

AuthContext bypass triggers when either is true:
- `VITE_E2E_AUTH_BYPASS === '1'`
- URL has `e2e_auth=1`

Reference: `frontend/src/AuthContext.jsx:31`

Bypass is disabled for guest tests when URL contains `e2e_guest=1`:
- `frontend/src/AuthContext.jsx:34`

Fake session used:
- `access_token = 'e2e-dev-token'`
- `user.id = 'e2e-dev'`
- `frontend/src/AuthContext.jsx:9`

### Current behavior: bypass is authoritative (fixed)

When E2E bypass is active, `AuthContext` now skips Supabase auth state subscription:
- no `supabase.auth.onAuthStateChange(...)` subscription in bypass mode
- `?e2e_guest=1` explicitly sets `session = null`

This prevents a real persisted Supabase session (or `null` in a fresh Playwright context) from overwriting the E2E fake session.

Historical note: before commit `bcc9ebf`, bypass mode could be overwritten by Supabase `onAuthStateChange`, which caused environment-dependent local Playwright failures.

## Backend Auth Flow (Detailed)

Files:
- `backend/auth.py`
- `backend/app.py`

### Real JWT verification (Supabase)

Backend verifies Supabase access tokens using JWKS.

Required env:
- `SUPABASE_URL`

Optional env:
- `SUPABASE_JWT_AUD` (defaults to `authenticated`)

References:
- `backend/auth.py:23`
- `backend/auth.py:39`
- `backend/auth.py:52`

### Dev fallback user

`PINYIN_RECALL_DEV_USER` creates a backend-only fake user object:
- `backend/app.py:1142`

The object shape is enough for route code that expects `user.user_id` and `user.user_metadata`.

Common values used in this codebase:
- Local manual / cloud-agent dev fallback often uses `local-dev`
- Playwright E2E backend launcher uses `e2e-dev` (`frontend/scripts/run-backend-for-e2e.mjs`)

### Route auth matrix (important)

Routes that accept real JWT OR dev fallback:
- `/api/profile` GET/PUT (`backend/app.py:1158`, `backend/app.py:1178`)
- `/api/profile/progress` (`backend/app.py:1201`)
- `/api/profile/progress/category/<category>` (`backend/app.py:1245`)
- `/api/games/pinyin-recall/session` (`backend/app.py:1363`)
- `/api/games/pinyin-recall/next-batch` (`backend/app.py:1438`)
- `/api/games/pinyin-recall/answer` (`backend/app.py:1511`)
- `/api/games/pinyin-recall/report-error` (`backend/app.py:1613`)

Route that requires real JWT only (no dev fallback):
- `/api/log-character-view` (`backend/app.py:1654`)

This is expected and explains the known 401 in auth-bypass mode for search view logging.

## Data Source and Logging Behavior (DB-only Runtime)

### DB-backed runtime behavior

The app uses Supabase/Postgres for:
- character data (`load_characters`) `backend/app.py:232`
- hwxnet dictionary (`load_hwxnet`) `backend/app.py:195`
- profile display name persistence (`backend/app.py:1165`, `backend/app.py:1191`)
- profile progress (`backend/app.py:1201`)
- pinyin recall learning state + event logging (`backend/app.py:1299`, `backend/app.py:1311`)
- pinyin recall answer/report-error writes (`backend/app.py:1542`, `backend/app.py:1628`)
- character view logging (`backend/app.py:1654`)

### DB connection requirements

Database layer requires one of:
- `DATABASE_URL`
- `SUPABASE_DB_URL`

Reference: `backend/database.py:21`

If missing, backend startup now fails fast.

## Playwright E2E Architecture (Important for your issue)

Files:
- `frontend/playwright.config.js`
- `frontend/scripts/run-backend-for-e2e.mjs`
- `frontend/e2e/profile.spec.js`
- `frontend/e2e/pinyin-recall.spec.js`

### Frontend E2E server behavior

Playwright frontend web server sets:
- `VITE_E2E_AUTH_BYPASS=1`

But it also inherits all parent environment variables via `...process.env`.

Reference: `frontend/playwright.config.js:48`

Implication:
- If local shell / `.env.local` makes `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` available to Vite, the frontend E2E bypass may conflict with real Supabase auth state.

### Backend E2E server behavior

`run-backend-for-e2e.mjs` always sets:
- `PINYIN_RECALL_DEV_USER = 'e2e-dev'`
- This is distinct from the commonly used local manual dev fallback user `local-dev`

Reference: `frontend/scripts/run-backend-for-e2e.mjs:73`

It passes `SUPABASE_URL` through if it detects one in env:
- checks `SUPABASE_URL || VITE_SUPABASE_URL`
- sets `SUPABASE_URL=<value>`

References:
- `frontend/scripts/run-backend-for-e2e.mjs:55`
- `frontend/scripts/run-backend-for-e2e.mjs:58`

### Server reuse behavior

Outside GitHub Actions, Playwright uses `reuseExistingServer: true` for both backend and frontend.

References:
- `frontend/playwright.config.js:32`
- `frontend/playwright.config.js:46`

Implication:
- E2E results can depend on whether Playwright reused already-running servers (with a certain env) or spawned fresh ones.

### Test expectations

`profile.spec.js` authenticated flow:
- pre-checks `/api/profile/progress` with fake token `Bearer e2e-dev-token`
- skips only if backend returns `503` (legacy expectation from before DB-only runtime)
- then expects frontend UI to appear authenticated and reach game/profile pages

Reference: `frontend/e2e/profile.spec.js:16`

This test depends on both:
- backend dev fallback working
- frontend auth bypass remaining active (not overwritten)

## Environment Variables and What They Control

### Frontend variables

- `VITE_SUPABASE_URL`
  - Enables real Supabase client when paired with anon key
  - Needed for real Google sign-in
  - `frontend/src/supabaseClient.js:3`

- `VITE_SUPABASE_ANON_KEY`
  - Enables real Supabase client when paired with URL
  - `frontend/src/supabaseClient.js:4`

- `VITE_E2E_AUTH_BYPASS`
  - Enables fake frontend session for auth-gated UI
  - `frontend/src/AuthContext.jsx:32`

- `VITE_API_URL`
  - API base in production-style setups
  - In local dev, Vite proxy is usually used instead
  - `frontend/src/AuthContext.jsx:4`, `frontend/src/pages/Profile.jsx:15`, `frontend/src/pages/Search.jsx:9`

- `NODE_ENV=development`
  - Required for Vite `/api` proxy activation in current config
  - `frontend/vite.config.js:11`

### Backend variables

- `SUPABASE_URL`
  - Required for backend JWT verification against Supabase JWKS
  - `backend/auth.py:23`

- `SUPABASE_JWT_AUD`
  - Optional JWT audience override (default `authenticated`)
  - `backend/auth.py:39`

- `PINYIN_RECALL_DEV_USER`
  - Enables backend dev fallback user for auth-gated routes (except `/api/log-character-view`)
  - `backend/app.py:1147`

- `DATABASE_URL` / `SUPABASE_DB_URL`
  - Required DB connection string (DB-only runtime)
  - `backend/database.py:24`

## Your 5 Environments Mapped to the Architecture

This section explains observed behavior in your reported environments.

### 1) Production (Cloud Run backend + Netlify frontend)

Observed result:
- Real Google auth works
- Authenticated profile and pinyin recall work

Why this fits:
- Frontend has real Supabase config (`VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY`)
- User signs in with Google via Supabase
- Backend verifies real JWT using `SUPABASE_URL`
- Backend uses `DATABASE_URL` for data and logging (DB-only runtime)

This is the intended production architecture.

### 2) Local manual testing (local backend + frontend)

Observed result:
- Previously used `local-dev`
- Now often uses your real Google identity (same browser used for prod)
- Still works

Why this fits:
- Current local `.env.local` keys (observed during audit, values not recorded):
  - Frontend: `VITE_SUPABASE_URL`, `VITE_SUPABASE_ANON_KEY` are present and non-empty
  - Backend: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_JWT_AUD`, `PINYIN_RECALL_DEV_USER` are present and non-empty
- Because your browser may already have a persisted Supabase session, frontend sends a real Bearer token.
- Backend tries real JWT first and only falls back to dev user if auth is absent/invalid.
- Therefore real user identity naturally "wins" over `local-dev`.

This is not a bug by itself; it is the expected precedence in current backend code.

### 3) Cursor Cloud agent local server environment

Observed result:
- Uses `local-dev`
- Can query Supabase data

Why this fits:
- Typical cloud-agent setup (per your AGENTS instructions) starts backend with DB credentials + dev-user fallback.
- Frontend often runs with `VITE_E2E_AUTH_BYPASS=1` and without frontend Supabase vars to avoid conflict.
- Result:
  - Frontend appears authenticated (fake session)
  - Backend uses dev fallback user (`local-dev`)
  - Data/logging still go to real Supabase DB (backend DB mode)

This matches your "always use real Supabase as data/logging destination" goal while avoiding real Google sign-in during testing.

### 4) Cursor Cloud agent Playwright E2E environment

Observed result:
- Authenticated pinyin recall/profile tests passed

Most likely explanation (inference):
- Playwright reused existing servers from environment (3), because `reuseExistingServer: true` outside GitHub Actions.
- Those reused servers likely already had the "safe" split:
  - frontend bypass active without frontend Supabase vars
  - backend dev fallback + DB-backed runtime active

If Playwright had started a fresh frontend with Supabase vars present, it could hit the same bypass-overwrite problem seen locally.

### 5) Local Playwright environment (same tests fail)

Observed result:
- Auth bypass appears not to work
- Local Playwright does not see authenticated profile page

Why this fit the pre-fix code (historical root cause):
- Playwright frontend sets `VITE_E2E_AUTH_BYPASS=1` (`frontend/playwright.config.js:51`)
- But frontend may still load/use real Supabase config (from local `.env.local`)
- AuthContext sets fake E2E session first
- Then `supabase.auth.onAuthStateChange(...)` subscription can overwrite it
  - often to `null` in fresh Playwright browser context
- UI becomes unauthenticated (`user == null`)
- `/profile` and `/games/pinyin-recall` show login prompts

This was the root cause of the local Playwright failure before the `AuthContext` bypass fix.

## Root Cause Summary (Local Playwright Failure, historical)

Root cause (before commit `bcc9ebf`):
- E2E bypass in frontend is not authoritative when Supabase is configured.
- `onAuthStateChange` continues to run and can replace the fake session.

Relevant code:
- Bypass sets fake session: `frontend/src/AuthContext.jsx:34`
- Supabase subscription still installed: `frontend/src/AuthContext.jsx:60`

Practical symptom (before fix):
- Same test can pass in one environment and fail in another depending on:
  - whether frontend Supabase vars are present
  - whether a persisted browser session exists
  - whether Playwright reused existing servers

## Non-obvious but Important Behaviors

### `/api/log-character-view` is intentionally stricter

`/api/log-character-view` requires real JWT. It does not use dev fallback.

Reference: `backend/app.py:1654`

This means in bypass/dev-user test mode:
- Search page logging may return 401 in the browser console
- Frontend catches and ignores the error (`.catch(() => {})`)
- `frontend/src/pages/Search.jsx:80`

This is expected with the current design.

### E2E bypass status (current)

The frontend E2E bypass issue described above has been fixed:
- E2E bypass mode is authoritative in `AuthContext`
- `e2e_guest=1` remains a reliable way to force unauthenticated UI state
- Local Playwright auth-related tests were reported passing after the patch

### Vite proxy only works in development mode

The frontend `/api` proxy to `http://localhost:5001` only activates when:
- `NODE_ENV === 'development'`

Reference: `frontend/vite.config.js:11`

This matters for local and E2E setups.

## Recommended Debug Checklist for Future Agents

When auth behavior is surprising, inspect these first:

1. Frontend auth mode
- Are `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` present?
- Is `VITE_E2E_AUTH_BYPASS=1` set?
- Is URL using `?e2e_auth=1` or `?e2e_guest=1`?

2. Backend auth mode
- Is `SUPABASE_URL` set?
- Is `PINYIN_RECALL_DEV_USER` set?
- Which token is actually sent in `Authorization`?

3. Backend data mode
- Is `DATABASE_URL` set?
- Is `SUPABASE_URL` set?
- If startup fails, is the DB reachable and schema present?

4. Playwright server behavior
- Did it reuse existing frontend/backend servers?
- What env vars were present for those reused servers?

## Implemented Fix and Remaining Hardening

Implemented (commit `bcc9ebf`):
- In `AuthContext`, E2E bypass mode now skips Supabase `onAuthStateChange` subscription so the fake session is not overwritten.
- `e2e_guest=1` explicitly forces unauthenticated state (`session = null`) even if Supabase is configured.

Optional defense-in-depth (still useful):
- In Playwright frontend webServer env, explicitly unset `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` when using `VITE_E2E_AUTH_BYPASS=1`.

This keeps test behavior deterministic and avoids hidden dependence on local `.env.local` contents.
