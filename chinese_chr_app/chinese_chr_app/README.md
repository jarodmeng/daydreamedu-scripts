# Chinese Character Learning App

A web application to help primary school students learn simplified Chinese characters.

Production deployment is live at:

- **Frontend**: `https://chinese-chr.daydreamedu.org/`
- **Backend API**: Google Cloud Run service (e.g. `https://chinese-chr-app-xxxxx-uc.a.run.app`)
- **Images**: Google Cloud Storage bucket `chinese-chr-app-images`

## Project Structure

Paths below are relative to the repo root. The app lives under `chinese_chr_app/chinese_chr_app/`.

```
chinese_chr_app/
├── chinese_chr_app/     # Main app (this folder)
│   ├── backend/         # Flask backend API
│   │   ├── app.py       # Main Flask application
│   │   ├── auth.py      # Supabase JWT verification
│   │   ├── database.py  # Supabase/Postgres layer (feng_characters, hwxnet_characters)
│   │   ├── requirements.txt
│   │   ├── MIGRATION_TO_DATABASE.md  # How to use DB instead of JSON
│   │   └── logs/        # Character edit logs
│   └── frontend/        # React frontend
│       ├── src/
│       │   ├── pages/   # Page components (Search, Radicals, RadicalDetail, StrokeCounts, StrokeCountDetail)
│       │   ├── App.jsx  # Main router + AuthProvider
│       │   ├── NavBar.jsx
│       │   ├── AuthContext.jsx  # Supabase Auth (Google login)
│       │   ├── supabaseClient.js
│       │   └── App.css
│       ├── e2e/         # Playwright E2E tests + fixtures
│       ├── scripts/     # Helper scripts (e.g. start backend for E2E)
│       ├── package.json
│       ├── playwright.config.js
│       └── vite.config.js
└── data/                # Character and dictionary data (JSON)
    ├── characters.json                   # Primary character metadata (from 冯氏早教识字卡, editable in app)
    ├── extracted_characters_hwxnet.json  # Dictionary data extracted from hwxnet (read-only in app)
    ├── level-1.json                      # Zibiao-style frequency list (top 3500)
    ├── level-2.json                      # Continuation list (3501-6500)
    └── level-3.json                      # Continuation list (6501-8105, includes some non-BMP chars)
```

## Data Model Notes (What We Learned)

- **`characters.json` (3000 chars)**: “primary curriculum” dataset with images + editable metadata.
  - Each entry now includes **`zibiao_index`**: the character’s index in the `level-*.json` lists.
- **`extracted_characters_hwxnet.json` (dictionary)**: keyed by character, contains HWXNet dictionary extraction.
  - After extending extraction, this file contains **3664 entries**:
    - **3000** characters from `characters.json` (have both `index` and `zibiao_index`)
    - **664** additional characters (have `zibiao_index` but **no** `index`, because `index` comes from `characters.json`)
- **`level-1/2/3.json` union**: **8105** unique characters; includes **196 non‑BMP** characters (some may not render with common fonts).

### Search behavior

- For characters in **`characters.json`**: app can show **all 4 panels** (笔顺动画 / 字典信息 / 字卡 / 字符信息).
- For “dictionary-only” characters (in `extracted_characters_hwxnet.json` but not `characters.json`): app shows only:
  - **笔顺动画**
  - **字典信息（hwxnet）**

## Setup Instructions

### Backend Setup

1. Navigate to the backend directory (from repo root):
```bash
cd chinese_chr_app/chinese_chr_app/backend
```

2. Create a virtual environment (recommended):
```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. (Optional) Create `.env.local` from `.env.local.example` in `backend/` and set:
   - **Supabase**: `SUPABASE_URL`, `SUPABASE_JWT_AUD` (for JWT verification).
   - **字卡 images**: Set `GCS_BUCKET_NAME=chinese-chr-app-images` so local 字卡 is served from GCS (same as prod). If unset, the backend uses local `data/png`. When using GCS locally, you must set up [Application Default Credentials](https://cloud.google.com/docs/authentication/external/set-up-adc): run `gcloud auth application-default login` once, then restart the backend.

4. Install dependencies:
```bash
pip install -r requirements.txt
```

5. Run the Flask server (with the venv activated from step 2, `python3` uses the venv and has psycopg for database mode):
```bash
source venv/bin/activate   # if not already activated from step 2
python3 app.py
```

Or in one line from `backend/`:
```bash
./venv/bin/python3 app.py
```

The backend will run on `http://localhost:5001`

**Local gotcha (Werkzeug debugger crash):** on some macOS/Python setups, enabling Flask debug can crash due to `_ctypes` import issues. Debug is **off by default**; enable explicitly with:

```bash
source venv/bin/activate
FLASK_DEBUG=1 python3 app.py
```

### Frontend Setup

1. Navigate to the frontend directory (from repo root):
```bash
cd chinese_chr_app/chinese_chr_app/frontend
```

2. Install dependencies:
```bash
npm install
```

3. (Optional) For **Sign in with Google** to work locally, create `.env.local` from `.env.example` and set `VITE_SUPABASE_URL` and `VITE_SUPABASE_ANON_KEY` (from your Supabase project → Project Settings → API). Leave `VITE_API_URL` empty to use the Vite proxy to the backend.

4. Start the development server:
```bash
npm run dev
```

The frontend will run on `http://localhost:3000`

In production, the frontend is built with Vite and deployed to Netlify. Set `VITE_API_URL`, `VITE_SUPABASE_URL`, and `VITE_SUPABASE_ANON_KEY` in Netlify site environment variables. API requests use `VITE_API_URL` to reach the Cloud Run backend.

### E2E tests (Playwright)

Playwright end-to-end tests live under `frontend/e2e/` and cover core flows:
- Search a character that exists in `characters.json` (4-panel view)
- Search a dictionary-only character (2-panel view)
- Navigate `/radicals` → a radical detail page → click a character back to search

From `chinese_chr_app/chinese_chr_app/frontend`:

```bash
npm install
npx playwright install
npm run test:e2e
```

Notes:
- If you already have the backend running on `http://localhost:5001`, Playwright will **reuse** it.
- If you don’t, Playwright will try to start it; make sure you’ve installed backend deps (from `chinese_chr_app/chinese_chr_app/backend`: `pip install -r requirements.txt`) and have a backend venv at `backend/venv` or `backend/.venv` (Playwright uses the venv’s Python so database/psycopg works).

### Stroke animation (HanziWriter) notes

HanziWriter loads per-character stroke data from `hanzi-writer-data`. In some environments, direct CDN fetches can be blocked; the backend provides a proxy + cache:

- `GET /api/strokes?char=<character>`
  - fetches from jsDelivr/unpkg
  - caches locally under `data/temp/hanzi_writer/`

If the backend cannot verify TLS certificates when fetching CDNs, it uses the `certifi` CA bundle. As a last resort, SSL verification can be disabled:

```bash
source venv/bin/activate
HW_STROKES_VERIFY_SSL=0 python3 app.py
```

## Usage

1. Open your browser and go to `http://localhost:3000`
2. **Sign in (optional)**: Use **Sign in with Google** in the top-right to sign in via Supabase Auth. Sign out when done.
3. **Search Page**: Enter a single simplified Chinese character in the search box
   - Click "搜索" (Search) or press Enter
   - Layout is **two rows**:
     - Row 1: **笔顺动画** + **字典信息（hwxnet）**
     - Row 2: **字卡** + **字符信息（冯氏早教识字卡）** *(only for characters in `characters.json`)*
   - View and edit character metadata (拼音, 部首, 笔画, 例句, 词组, 结构) for `characters.json` entries
3. **Radicals Page**: Click "部首 (Radicals)" in the navigation to browse characters by radical
   - View all radicals sorted by the number of associated characters
   - Click on a radical to see all characters with that radical
   - Characters are sorted by strokes (ascending), then by pinyin
   - Click on any character to search for it

## Using the database (Supabase)

The backend can read/write character data from Supabase tables instead of JSON files.

- Set **`USE_DATABASE=true`** and **`DATABASE_URL`** (Supabase Postgres connection string) in the backend environment.
- Tables: **`feng_characters`** (3000 冯氏早教识字卡 entries) and **`hwxnet_characters`** (3664 dictionary entries).
- Without these, the app uses `data/characters.json` and `data/extracted_characters_hwxnet.json` as before.
- See **`backend/MIGRATION_TO_DATABASE.md`** for details and scripts to create/seed the tables.

### If you see "psycopg is required for database support"

**1. Wrong Python / venv not used**  
If the backend is started without the venv (e.g. IDE using system Python), start it with the venv:

```bash
cd chinese_chr_app/chinese_chr_app/backend
source venv/bin/activate
python3 app.py
```

Or: `./venv/bin/python3 app.py`. In an IDE, set the run configuration to use `backend/venv/bin/python3`.

**2. macOS: Python 3.13 and broken _ctypes**  
On some macOS setups, Python 3.13 has a broken `_ctypes` (e.g. `symbol not found: __PyErr_SetLocaleString`), so `psycopg` fails to import even inside the venv. Use **Python 3.12** for the backend venv instead:

```bash
cd chinese_chr_app/chinese_chr_app/backend
rm -rf venv
python3.12 -m venv venv          # or: /usr/local/bin/python3.12 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
python3 app.py
```

Then keep using `USE_DATABASE=true` in `.env.local`; the backend will load from Supabase.

## API Endpoints

### Character Search
- `GET /api/characters/search?q=<character>` - Search for a character
  - Returns `character: null` but `dictionary` present for dictionary-only characters
- `PUT /api/characters/<index>/update` - Update character metadata

### Images
- `GET /api/images/<index>/<page>` - Get character card images (page1 or page2)

### Stroke data (HanziWriter)
- `GET /api/strokes?char=<character>` - Proxy/cached stroke JSON for HanziWriter

### Radicals
- `GET /api/radicals` - Get all radicals sorted by character count
- `GET /api/radicals/<radical>` - Get all characters for a specific radical

### System
- `GET /api/health` - Health check endpoint

**Note:** The backend uses port 5001 instead of 5000 to avoid conflicts with macOS AirPlay Receiver.
