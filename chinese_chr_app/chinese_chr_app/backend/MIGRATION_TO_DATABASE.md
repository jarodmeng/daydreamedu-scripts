# Migrate chinese_chr_app from JSON Files to Supabase Tables

**Status: Implemented.** Use `USE_DATABASE=true` and `DATABASE_URL` to read/write from Supabase tables. Without them, the app continues to use JSON files.

## Current state

- **Backend** reads:
  - `characters.json` → in-memory `characters_data` (list) and `character_lookup` (dict by character)
  - `extracted_characters_hwxnet.json` → in-memory `hwxnet_data` and `hwxnet_lookup` (dict by character)
- **Backend** writes:
  - Character edits: `PUT /api/characters/<index>/update` updates `characters.json` and rewrites the file; backups go to `data/backups/`.
- **API response shapes** (must be preserved for the frontend):
  - Search: `{ found, character: { Character, Index, Pinyin, Radical, Strokes, Structure, Sentence, Words }, dictionary: { character, 拼音, 部首, 总笔画, index, zibiao_index, source_url, 基本字义解释, 英文翻译, 分类 } }`
  - Radicals: list of `{ radical, characters: [{ Character, Pinyin, Strokes, Index?, zibiao_index? }] }`
  - Stroke counts: list of `{ count, character_count }` and lookup by count with `{ character, pinyin, radical, strokes, zibiao_index }`

## Target state

- **Single source of truth**: Supabase tables `feng_characters` and `hwxnet_characters`.
- **Backend** reads/writes via `DATABASE_URL` (Psycopg 3: `psycopg[binary]>=3.1`); no dependency on JSON files for runtime data.
- **Optional**: Keep JSON files as export/backup or remove them from the app’s data path after migration.

---

## 1. Backend: Data access layer

### 1.1 Add a small DB module

- **File**: `backend/database.py` (or `backend/db.py`).
- **Responsibilities**:
  - Get a connection using `os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")`.
  - Provide functions that return data in the **same dict shapes** the rest of the app and the API use today, so callers do not need to know whether data came from JSON or DB.

Suggested functions:

| Function | Returns | Notes |
|----------|---------|--------|
| `get_feng_characters()` | `List[Dict]` | All rows from `feng_characters`; map columns → keys: `Character`, `Index`, `zibiao_index`, `Pinyin`, `Radical`, `Strokes`, `Structure`, `Sentence`, `Words`. |
| `get_feng_character_by_index(index: str)` | `Optional[Dict]` | Single row by `index`; same key shape as above. |
| `get_feng_character_by_character(ch: str)` | `Optional[Dict]` | Single row by `character`; same shape. |
| `get_hwxnet_lookup()` | `Dict[str, Dict]` | All rows from `hwxnet_characters`; key = `character`, value = dict with keys `character`, `拼音`, `部首`, `总笔画`, `index`, `zibiao_index`, `source_url`, `基本字义解释`, `英文翻译`, `分类` (map DB column names to these). |
| `update_feng_character(index: str, field: str, value: Any)` | `(bool, Optional[str], Optional[Dict])` | Update one field for the row with `index`; return success, error message, and updated row dict (same shape as get). |

- **Mapping**:
  - DB `character` → response `Character` (for feng) or `character` (for hwxnet).
  - DB `strokes` (int) → feng response `Strokes` as string (e.g. `str(row['strokes'])`) if the frontend still expects a string; otherwise keep int and change frontend once.
  - DB `pinyin` (jsonb) → list; DB `words` (jsonb) → list.
  - hwxnet: DB `radical` → `部首`, `strokes` → `总笔画`, `pinyin` → `拼音`, `classification` → `分类`, `basic_meanings` → `基本字义解释`, `english_translations` → `英文翻译`.

### 1.2 Configuration

- **DATABASE_URL** is already in `.env.local.example` and used by the create/verify scripts. Keep it as the single way to configure the DB.
- **Feature flag (optional)**: e.g. `USE_DATABASE=true` to read/write from DB; if unset, keep current JSON behavior during rollout. Alternatively, migrate in one go and remove JSON code paths.

---

## 2. Backend: Replace load_characters / load_hwxnet

### 2.1 load_characters()

- **Current**: Reads `characters.json`, builds `characters_data` (list) and `character_lookup` (dict by character).
- **New** (when using DB):
  - Call `get_feng_characters()` from the DB module.
  - Build `character_lookup = { row['Character']: row for row in rows }` (using the same dict shape as today).
  - Set `characters_data = rows` (list in a deterministic order, e.g. by `index`).
- **Caching**: Either keep in-memory cache and invalidate on update, or remove cache and query DB on each request (simpler; Supabase/Postgres can handle it). Recommendation: keep a short-lived in-memory cache per process and invalidate after `update_feng_character` so behavior stays close to current.

### 2.2 load_hwxnet()

- **Current**: Reads `extracted_characters_hwxnet.json`, builds `hwxnet_lookup` (dict by character).
- **New** (when using DB):
  - Call `get_hwxnet_lookup()` from the DB module (returns dict by character with the same key names as the current JSON-based dict).
  - Set `hwxnet_data` / `hwxnet_lookup` from that.
- **Caching**: Same idea as feng: in-memory cache and invalidate only if you ever add “update hwxnet” in the future; for read-only hwxnet, no invalidation needed.

---

## 3. Backend: Character search and update

### 3.1 GET /api/characters/search?q=<char>

- **Current**: Uses `character_lookup` and `hwxnet_lookup` (from JSON).
- **New**: No change in logic; only the source of `character_lookup` and `hwxnet_lookup` is DB-backed (via load_characters / load_hwxnet). Response shape stays `{ found, character, dictionary }`.

### 3.2 PUT /api/characters/<index>/update

- **Current**: Updates in-memory data and writes the whole `characters.json`; creates a timestamped backup under `data/backups/`.
- **New** (when using DB):
  - Call `update_feng_character(index, field, value)` in the DB module.
  - **Backup**: Either (a) keep creating a backup by exporting the updated row or full table to a JSON file in `data/backups/`, or (b) rely on Supabase backups and an optional edit log (you already have `log_character_edit`). Recommendation: keep logging edits; add optional export of feng_characters to a backup file on each edit if you want a local audit trail.
  - Invalidate in-memory cache for feng (and radicals/structures if they depend on it).
  - Return the updated character dict (same shape as today).

### 3.3 log_character_edit()

- **Current**: Resolves character name by scanning `characters_data` for `Index == index`.
- **New**: Can resolve from DB with a single `get_feng_character_by_index(index)` and use the `Character` field, or keep using the in-memory cache after an update.

---

## 4. Backend: Radicals and stroke counts

### 4.1 generate_radicals_data(characters_data, hwxnet_lookup)

- **Current**: Prefers `hwxnet_lookup`; builds radical → list of character info; fallback to `characters_data`.
- **New**: Same function signature and return shape. Callers pass data from DB-backed loaders (list of feng dicts and hwxnet lookup dict). No change to the aggregation logic; only the inputs come from DB.

### 4.2 generate_stroke_counts_data(hwxnet_lookup)

- **Current**: Iterates `hwxnet_lookup`, uses `总笔画`, `部首`, `拼音`, `zibiao_index`.
- **New**: Same. `hwxnet_lookup` is now built from `get_hwxnet_lookup()` with keys like `总笔画`, `部首`, `拼音` (see mapping in 1.1).

### 4.3 load_radicals() / load_stroke_counts()

- **Current**: Call `load_characters()` and `load_hwxnet()`, then generate.
- **New**: No change; they still call the same loaders, which now read from DB.

---

## 5. Backend: Backup and startup

### 5.1 backup_character_files()

- **Current**: Copies `characters.json` to `data/backups/characters_YYYYMMDD_HHMMSS.json`.
- **New** (when using DB): Either (a) export `feng_characters` to a JSON file in the same path pattern (e.g. `exports/feng_characters_YYYYMMDD_HHMMSS.json`) before/after an edit, or (b) drop file backup and rely on DB + edit log. If you keep file backups, do a single query to fetch all feng rows and write them in the same list shape as current `characters.json` so the file is usable for diff/audit.

### 5.2 Startup

- **Current**: On first request, `load_characters()` and `load_hwxnet()` read JSON (or use cached in-memory data).
- **New**: Same flow, but loaders read from DB. Ensure `DATABASE_URL` is set in production (Cloud Run, etc.); otherwise fail fast with a clear error.

---

## 6. Frontend

- **No API contract change**: Backend continues to return the same JSON shapes for search, radicals, and stroke counts.
- **No frontend code changes** are required for the migration itself. Optional later: rename or normalize keys (e.g. `Strokes` vs `strokes`) if you standardize on one convention.

---

## 7. Deployment and environment

- **Env**: Set `DATABASE_URL` (or `SUPABASE_DB_URL`) in Cloud Run / local `.env.local` (already used by scripts).
- **JSON files**: 
  - **Option A**: Remove `characters.json` and `extracted_characters_hwxnet.json` from the app’s data directory in the image and from code paths so the app only uses DB.
  - **Option B**: Keep files in the repo for reference/seed data but do not read them at runtime; app uses DB only.

- **Dockerfile**: No need to copy the two JSON files into the image if you use Option A. Keep copying `data/png/` if images are still served from the filesystem.

---

## 8. Testing

- **Backend tests** (`tests/test_data.py`, `tests/test_api.py`, etc.): Currently load from `characters.json`. Update to either (a) use a test DB (e.g. Supabase branch or local Postgres) with seed data, or (b) keep a small JSON fixture and a “mock” DB module that returns that fixture so tests don’t need a real DB. Prefer (a) for integration tests.
- **E2E**: No change if API and response shapes are unchanged; continue to run against an environment that has `DATABASE_URL` set and tables populated (e.g. from the create scripts).

---

## 9. Implementation order (suggested)

1. Add `backend/database.py`: connection helper + `get_feng_characters()`, `get_feng_character_by_index()`, `get_feng_character_by_character()`, `get_hwxnet_lookup()`, `update_feng_character()`, with exact dict shapes expected by the rest of the app.
2. Add a feature flag or config (e.g. `USE_DATABASE=true`) and in `load_characters()` / `load_hwxnet()`: when set, use DB module; otherwise keep current JSON logic.
3. Implement backup/export in DB mode (optional file export of feng_characters on update).
4. Switch `update_character_field()` to call `update_feng_character()` and invalidate caches when DB is used.
5. Run backend and E2E tests with DB enabled; fix any mapping or cache issues.
6. Remove JSON code paths and the feature flag; make DB the only source.
7. Update docs (README, DEPLOYMENT.md) and Dockerfile (stop copying JSON if applicable).

---

## 10. Summary

| Area | Change |
|------|--------|
| **Data source** | `feng_characters` and `hwxnet_characters` tables instead of two JSON files. |
| **Backend** | New `database.py`; load_characters/load_hwxnet and update_character_field use it; same in-memory cache and API response shapes. |
| **Backup** | Either export feng_characters to timestamped JSON on edit or rely on Supabase + edit log. |
| **Frontend** | None. |
| **Config** | `DATABASE_URL` required in production. |
| **Tests** | Point to test DB or mock DB module. |

This keeps the current API and frontend behavior unchanged while moving the source of truth to Supabase.
