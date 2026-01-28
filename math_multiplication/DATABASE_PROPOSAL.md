# Database Logging Decision (Supabase)

## Summary

We replaced local JSON file logging with **Supabase Postgres** so leaderboard logging works in production (Cloud Run) where filesystem writes are not durable.

## Decision

- **Database**: Supabase Postgres
- **Connection method**: Supabase **Transaction pooler** (`*.pooler.supabase.com:6543`) with `sslmode=require`
- **Backend ORM**: Flask + Flask-SQLAlchemy + SQLAlchemy
- **Driver**: `psycopg` v3 (works on Python 3.13)

## Data model

Tables:

### `games`

- `id` (int, primary key)
- `timestamp` (UTC) – when the game was completed
- `user_id` (nullable UUID string) – set when the player is signed in
- `name` (string) – **snapshot** of the player’s display name at the time of play (Option A)
- `time_elapsed` (int, milliseconds)
- `rounds` (int)
- `total_questions` (int)
- `created_at` (UTC)

### `user_profiles`

- `user_id` (UUID string, primary key) – Supabase Auth `sub`
- `display_name` (string, editable)
- `created_at` (UTC)
- `updated_at` (UTC)

Notes:
- Backend returns timestamps as ISO-8601 **UTC with `Z`** (e.g. `2026-01-25T05:14:12Z`).
- Frontend formats leaderboard timestamps in **Singapore time**.

## Environment separation (test vs prod)

Supabase free tier is typically **one database per project**. For this app we use:

- A **single Supabase project** (`math_practice`, ref `bcyvuwcktwljsdbsjuyx`)
- Two **schemas** inside that project:
  - `public` schema for **production** data:
    - `public.games`
    - `public.user_profiles`
  - `test` schema for **local dev + e2e** data:
    - `test.games`
    - `test.user_profiles`

The backend selects the schema based on `ENVIRONMENT`:

- `ENVIRONMENT=production` → default schema (`public`)
- `ENVIRONMENT=test`       → `test` schema

Both environments share the same connection string (`DATABASE_URL`) but operate
on different schemas so production and test data stay isolated.

## Configuration

Backend uses these environment variables:

- `DATABASE_URL` (Supabase pooler connection string)
- `SUPABASE_URL` (e.g. `https://<PROJECT_REF>.supabase.co`) for verifying Supabase JWTs (Google login)
- `SUPABASE_JWT_AUD` (default: `authenticated`)

Example (do not commit secrets):

```
DATABASE_URL=postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-<n>-<region>.pooler.supabase.com:6543/postgres?sslmode=require
```

If the password contains special characters (`/`, `@`, `:`, `%`), URL-encode it in the URL.

## Local setup & testing

See `backend/DATABASE_SETUP.md` for the short quickstart and curl tests.

## Migration from JSON (completed)

The one-time JSON migration into Supabase has been completed, and the legacy files were removed from the repo.
