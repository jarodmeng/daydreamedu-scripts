## Cursor Cloud specific instructions

### Overview

This is a monorepo with two full-stack web apps and several utility/script projects. See `README.md` for folder layout.

| App | Backend | Frontend | DB required? |
|-----|---------|----------|-------------|
| **Chinese chr app** (`chinese_chr_app/chinese_chr_app/`) | Flask :5001 | React+Vite :3000 | No (uses JSON files by default) |
| **Math multiplication** (`math_multiplication/`) | Flask :5001 | React+Vite :3000 | Yes (`DATABASE_URL` required) |

Both apps share ports 5001/3000 — only one can run at a time.

### Running the Chinese chr app

See the skill file at `.cursor/skills/start-local-servers/SKILL.md` for step-by-step instructions. In brief:

```
# Backend (background)
cd chinese_chr_app/chinese_chr_app/backend && python3 app.py

# Frontend (background)
cd chinese_chr_app/chinese_chr_app/frontend && npm run dev
```

The Vite dev server proxies `/api` to `http://localhost:5001` automatically.

### Running E2E tests (Chinese chr app)

From `chinese_chr_app/chinese_chr_app/frontend`:

```
npx playwright test
```

If the backend and frontend are already running, Playwright reuses them (`reuseExistingServer: true` outside CI). Otherwise it starts them via `webServer` config.

### Building frontends

Both frontends use `npm run build` (Vite). No lint command is configured in `package.json` — the build itself serves as the primary code quality check.

### Gotchas

- The Chinese chr app Vite config only enables the `/api` proxy when `NODE_ENV === 'development'`. Running `npm run dev` sets this automatically.
- The math multiplication app **cannot start** without `DATABASE_URL` set (no JSON fallback).
- Python packages install to user site-packages (`~/.local/lib/python3.12`). No virtualenv is needed in this cloud environment; `python3` picks them up directly.
- If `pip3 install` hits SSL errors, use `--trusted-host pypi.org --trusted-host files.pythonhosted.org` (see `.cursor/rules/pip-ssl-trusted-host.mdc`).
