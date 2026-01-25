# Database Logging Decision (Supabase)

## Summary

We replaced local JSON file logging (`data/games.json`) with **Supabase Postgres** so leaderboard logging works in production (Cloud Run) where filesystem writes are not durable.

## Decision

- **Database**: Supabase Postgres
- **Connection method**: Supabase **Transaction pooler** (`*.pooler.supabase.com:6543`) with `sslmode=require`
- **Backend ORM**: Flask + Flask-SQLAlchemy + SQLAlchemy
- **Driver**: `psycopg` v3 (works on Python 3.13)

## Data model

Single table: `games`

- `id` (int, primary key)
- `timestamp` (UTC) – when the game was completed
- `name` (string)
- `time_elapsed` (int, milliseconds)
- `rounds` (int)
- `total_questions` (int)
- `created_at` (UTC)

Notes:
- Backend returns timestamps as ISO-8601 **UTC with `Z`** (e.g. `2026-01-25T05:14:12Z`) so the browser renders the user’s local time correctly.

## Environment separation (test vs prod)

Supabase free tier is typically **one database per project**. Recommended options:

- **Recommended**: use **two Supabase projects** (one for testing, one for production), each with its own `DATABASE_URL`.
- Alternative: use **two schemas** (e.g. `test.games` and `prod.games`) and configure the backend to write to the schema based on `ENVIRONMENT`.

Current implementation uses a single `games` table in the connected database.

## Configuration

Backend uses a single environment variable:

- `DATABASE_URL` (Supabase pooler connection string)

Example (do not commit secrets):

```
DATABASE_URL=postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-<n>-<region>.pooler.supabase.com:6543/postgres?sslmode=require
```

If the password contains special characters (`/`, `@`, `:`, `%`), URL-encode it in the URL.

## Local setup & testing

See `backend/DATABASE_SETUP.md` for the short quickstart and curl tests.

## Migration from JSON (optional)

If you have existing `data/games.json`, run:

```
python backend/migrations/migrate_json_to_db.py
```

