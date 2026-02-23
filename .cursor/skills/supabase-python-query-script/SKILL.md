---
name: supabase-python-query-script
description: Create Python scripts that query live Supabase/Postgres. Use when the user asks for a script to query Supabase, inspect the live DB, or run one-off SQL against the project's Supabase database.
---

# Supabase Python Query Script

Standard workflow for creating Python scripts that query the project's live Supabase (Postgres) database.

## Connection

- Use **psycopg** (direct Postgres). Do not use the Supabase REST/JS client for Python scripts.
- URL from environment: `os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")`.
- Never hardcode connection strings or credentials.
- Require `psycopg[binary]>=3.1`. If missing, print: `psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'` and `sys.exit(1)`.
- Connect with: `psycopg.connect(url, row_factory=dict_row)` (use `dict_row` from `psycopg.rows` for dict-like rows).
- If URL is unset, print a clear message (e.g. "DATABASE_URL or SUPABASE_DB_URL is not set.") and `sys.exit(1)`.

## Env loading

- Load `backend/.env.local` via `dotenv` when present, so local dev can override without exporting.
- Path from script: for a script in `backend/scripts/<subfolder>/script.py`, backend dir is `Path(__file__).resolve().parent.parent.parent`. So: `env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"`.
- Use `load_dotenv(env_file)` only if `env_file.exists()`. Wrap in `try/except ImportError` if `dotenv` is optional.

## Script location

- Place new scripts under **backend/scripts/** in the appropriate subfolder:
  - **utils/** — one-off queries, admin helpers (e.g. query by user, delete dev rows).
  - **pinyin_recall/**, **characters/**, **radicals/** — domain-specific tables and backfills.
- Run from **backend/**: `python3 scripts/<subfolder>/<script>.py [args]`.

## Docstring and usage

- Module docstring must state: "Requires DATABASE_URL or SUPABASE_DB_URL" and run instructions, e.g. "Run from backend/: python3 scripts/utils/script.py --option value."
- Use **argparse** for user/email/table/filters when relevant.
- Include a short "Usage" block in the docstring if the script has CLI args.

## Safety

- Prefer **read-only** queries (SELECT) for ad-hoc inspection scripts.
- No DDL or writes (CREATE, ALTER, INSERT, UPDATE, DELETE) unless the user explicitly asks for migrations, backfills, or schema changes.

## Minimal template

```python
#!/usr/bin/env python3
"""
<One-line purpose>.

Run from backend/: python3 scripts/<path>/<script>.py [args]
Requires DATABASE_URL or SUPABASE_DB_URL. Loads .env.local if present.
"""

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    env_file = Path(__file__).resolve().parent.parent.parent / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass

# ... argparse if needed ...

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
    sys.exit(1)

url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
if not url:
    print("DATABASE_URL or SUPABASE_DB_URL is not set.")
    sys.exit(1)

conn = psycopg.connect(url, row_factory=dict_row)
try:
    with conn.cursor() as cur:
        cur.execute("SELECT ...", (...))
        rows = cur.fetchall()
    # ...
finally:
    conn.close()
```

For script placement and subfolders, see the project rule at `.cursor/rules/chinese-chr-app-structure.mdc` when working under `chinese_chr_app/`.
