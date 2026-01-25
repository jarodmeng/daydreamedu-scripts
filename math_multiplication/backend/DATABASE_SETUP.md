# Supabase DB Quickstart

## 1) Get the connection string (recommended)

In Supabase, click **Connect** (top bar) → **Connection string** → **Transaction pooler**.

It looks like:

```
postgresql://postgres.<PROJECT_REF>:<PASSWORD>@aws-<n>-<region>.pooler.supabase.com:6543/postgres?sslmode=require
```

Notes:
- Use the **pooler** hostname (`*.pooler.supabase.com`). Some projects won’t have a working `db.<ref>.supabase.co` DNS record.
- If your password has special characters (`/`, `@`, `:`, `%`), **URL-encode** it in the URL.

## 2) Configure local env

From `math_multiplication/backend`:

```bash
cp .env.local.example .env.local
```

Set:
- `DATABASE_URL=<the pooler URL above>`

## 3) Run the backend

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python app.py
```

Tables are created automatically on first run.

## 4) Test

```bash
curl http://localhost:5001/api/health
curl -X POST http://localhost:5001/api/games -H "Content-Type: application/json" \
  -d '{"name":"TestUser","time_elapsed":12345,"rounds":1,"total_questions":20}'
curl http://localhost:5001/api/games
```

Verify the row in Supabase: **Table Editor** → `games`.

## Legacy JSON migration (completed)

The one-time migration from local JSON into Supabase has been completed, and the legacy migration utilities/files were removed.

## Production note (Cloud Run)

Store `DATABASE_URL` in **Secret Manager** and inject it as an env var in Cloud Run (avoid hardcoding it in the service config).

