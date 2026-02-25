# Chinese Character Learning App

A web application to help primary school students learn simplified Chinese characters. It combines utility features (character search, radicals, stroke counts, pinyin search) with learning features (personalized pinyin-recall practice) and is data-driven and customized per logged-in user.

**Current version: v0.2.7**

---

## Production

- **Frontend:** [https://chinese-chr.daydreamedu.org/](https://chinese-chr.daydreamedu.org/)
- **Backend API:** Google Cloud Run (e.g. `https://chinese-chr-app-xxxxx-uc.a.run.app`)
- **Images:** Google Cloud Storage bucket `chinese-chr-app-images`

---

## Table of Contents

| Doc | Purpose |
|-----|---------|
| [VISION.md](docs/VISION.md) | Product strategy, goals, user stories, and future direction |
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | Technical specs, APIs, data model, and system flow |
| [DECISIONS.md](docs/DECISIONS.md) | Architecture decision records and technical rationale |
| [CHANGELOG.md](docs/CHANGELOG.md) | Version history and release notes |

---

## Setup (Quick Start)

### Backend

1. From repo root: `cd chinese_chr_app/chinese_chr_app/backend`
2. Create and activate a virtual environment: `python3 -m venv venv` then `source venv/bin/activate` (Windows: `venv\Scripts\activate`)
3. (Optional) Copy `.env.local.example` to `.env.local` and set Supabase and/or GCS variables. For DB mode set `USE_DATABASE=true` and `DATABASE_URL`.
4. Install and run: `pip3 install -r requirements.txt` then `python3 app.py`

Backend runs at **http://localhost:5001**.

### Frontend

1. From repo root: `cd chinese_chr_app/chinese_chr_app/frontend`
2. Install and run: `npm install` then `npm run dev`
3. (Optional) For Sign in with Google, create `.env.local` from `.env.example` and set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY`.

Frontend runs at **http://localhost:3000**.

### E2E tests (Playwright)

From `chinese_chr_app/chinese_chr_app/frontend`: `npm install`, `npx playwright install`, `npm run test:e2e`. The backend should be running on port 5001 (or Playwright will attempt to start it).

---

## Troubleshooting

- **"psycopg is required for database support"** — Run the backend with the venv activated (`source venv/bin/activate` then `python3 app.py`), or use `./venv/bin/python3 app.py` from `backend/`. In an IDE, set the run configuration to use `backend/venv/bin/python3`.
- **macOS Python 3.13 and broken _ctypes** — If psycopg fails to import even inside the venv, use Python 3.12 for the backend: `rm -rf venv`, `python3.12 -m venv venv`, `source venv/bin/activate`, `pip3 install -r requirements.txt`, then `python3 app.py`.
- **Flask debug crash (Werkzeug/_ctypes)** — Debug is off by default. If you enable `FLASK_DEBUG=1` and see crashes on some macOS/Python setups, run without debug.
- **HanziWriter CDN / SSL** — If stroke data fails to load, the backend proxies and caches it. As a last resort set `HW_STROKES_VERIFY_SSL=0` when starting the backend.

For full API, data model, and deployment details see [ARCHITECTURE.md](docs/ARCHITECTURE.md) and `backend/DATABASE.md`.
