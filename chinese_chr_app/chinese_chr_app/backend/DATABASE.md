# Database (Supabase / Postgres)

Single source of truth for character and dictionary data. Use `USE_DATABASE=true` and `DATABASE_URL` to read/write from Supabase. Without them, the app uses JSON files (`characters.json`, `extracted_characters_hwxnet.json`).

---

## 1. Configuration

| Variable | Purpose |
|----------|--------|
| **DATABASE_URL** (or **SUPABASE_DB_URL**) | Postgres connection string. Supabase: Connect → Connection string → Transaction pooler. Example: `postgresql://postgres.<ref>:[PASSWORD]@...pooler.supabase.com:6543/postgres?sslmode=require` |
| **USE_DATABASE** | When `true`, backend uses DB for characters and HWXNet data and for character view logging. |

See `.env.local.example` and [DEPLOYMENT.md](DEPLOYMENT.md) for production (e.g. Cloud Run).

---

## 2. Tables and schema

### 2.1 `feng_characters`

冯氏早教识字卡 data (replaces `characters.json`).

| Column | Type | Notes |
|--------|------|--------|
| character | text | NOT NULL |
| index | text | NOT NULL; PK with character |
| zibiao_index | integer | |
| pinyin | jsonb | list |
| radical | text | |
| strokes | integer | |
| structure | text | |
| sentence | text | |
| words | jsonb | list |

**Indexes:** `idx_feng_characters_character`, `idx_feng_characters_zibiao_index` (partial).

**Create:** `python scripts/create_feng_characters_table.py` (use `--all` for full migration). **Verify:** `python scripts/verify_feng_characters.py`.

---

### 2.2 `hwxnet_characters`

汉文学网 dictionary data (replaces `extracted_characters_hwxnet.json`).

| Column | Type | Notes |
|--------|------|--------|
| character | text | NOT NULL |
| zibiao_index | integer | NOT NULL; PK with character |
| index | text | |
| source_url | text | |
| classification | jsonb | |
| pinyin | jsonb | list |
| radical | text | |
| strokes | integer | |
| basic_meanings | jsonb | |
| english_translations | jsonb | |
| **searchable_pinyin** | jsonb | Array of normalized pinyin keys for search (e.g. `["wo", "wo3"]`). Backfill: `scripts/add_searchable_pinyin_column.py`. |

**Indexes:** `idx_hwxnet_characters_character`, `idx_hwxnet_characters_index` (partial), **`idx_hwxnet_searchable_pinyin`** (GIN on `searchable_pinyin`).

**Create:** `python scripts/create_hwxnet_characters_table.py` (use `--all` for full migration). **Verify:** `python scripts/verify_hwxnet_characters.py`. **Pinyin column:** `python scripts/add_searchable_pinyin_column.py` (options: `--dry-run`, `--no-backup`, `--skip-filled`).

---

### 2.3 `character_views`

Logs which characters signed-in users view on Search (user_id, character, viewed_at, display_name). Used only when `USE_DATABASE=true`.

| Column | Type | Notes |
|--------|------|--------|
| id | uuid | PK, default gen_random_uuid() |
| user_id | text | NOT NULL |
| character | text | NOT NULL |
| viewed_at | timestamptz | NOT NULL, default now() |
| display_name | text | |

**Index:** `idx_character_views_user_viewed` on `(user_id, viewed_at DESC)`.

**Create:** `python scripts/create_character_views_table.py`.

---

## 3. Data access layer (`database.py`)

Psycopg 3 (`psycopg[binary]>=3.1`). All functions return dict shapes compatible with the rest of the app (same as JSON-based responses).

### Feng characters

| Function | Returns |
|----------|--------|
| `get_feng_characters()` | `List[Dict]` — all rows; keys: `Character`, `Index`, `zibiao_index`, `Pinyin`, `Radical`, `Strokes`, `Structure`, `Sentence`, `Words`. |
| `get_feng_character_by_index(index)` | `Optional[Dict]` — one row, same shape. |
| `get_feng_character_by_character(ch)` | `Optional[Dict]` — one row by character, same shape. |
| `update_feng_character(index, field, value)` | `(bool, Optional[str], Optional[Dict])` — success, error message, updated row. Allowed fields: Character, Pinyin, Radical, Strokes, Structure, Sentence, Words. |

**Column mapping (DB → response):** `character` → `Character`, `strokes` (int) → `Strokes` (string), `pinyin`/`words` (jsonb) → list.

### HWXNet characters

| Function | Returns |
|----------|--------|
| `get_hwxnet_lookup()` | `Dict[str, Dict]` — key = character; value has `character`, `部首`, `拼音`, `总笔画`, `index`, `zibiao_index`, `source_url`, `基本字义解释`, `英文翻译`, `分类`. |
| `get_characters_by_pinyin_search_keys(search_keys)` | `List[Dict]` — characters whose `searchable_pinyin` contains any of the keys. Dict keys: `character`, `radical`, `pinyin`, `strokes`, `zibiao_index`, `index`. Sorted by strokes ASC, then zibiao_index ASC; one entry per character. |

**Column mapping (DB → hwxnet dict):** `radical` → `部首`, `strokes` → `总笔画`, `pinyin` → `拼音`, `classification` → `分类`, `basic_meanings` → `基本字义解释`, `english_translations` → `英文翻译`.

### Character views

| Function | Purpose |
|----------|--------|
| `log_character_view(user_id, character, display_name=None)` | Insert one row into `character_views`. Table must exist (run create script once). |

---

## 4. Backend behavior (when `USE_DATABASE=true`)

- **load_characters()** — Uses `get_feng_characters()`; builds `characters_data` and `character_lookup` (same shapes as JSON).
- **load_hwxnet()** — Uses `get_hwxnet_lookup()`; builds `hwxnet_data` and `hwxnet_lookup`.
- **Search** — `GET /api/characters/search?q=<char>` unchanged; data comes from DB-backed loaders.
- **Pinyin search** — `GET /api/pinyin-search?q=<query>` uses `get_characters_by_pinyin_search_keys()` when DB is enabled (else in-memory index).
- **Update** — `PUT /api/characters/<index>/update` calls `update_feng_character()`; optional file backup or rely on Supabase + edit log.
- **Character view logging** — Search page logs views via `log_character_view()` when user is signed in.
- **Radicals / stroke counts** — Same `generate_radicals_data` and `generate_stroke_counts_data`; inputs come from DB-backed loaders.

API response shapes are unchanged; no frontend changes required for DB migration.

---

## 5. Scripts summary

| Script | Purpose |
|--------|--------|
| `scripts/create_feng_characters_table.py` | Create `feng_characters`, optionally insert from `data/characters.json` (`--all` for full). |
| `scripts/create_hwxnet_characters_table.py` | Create `hwxnet_characters`, optionally insert from `data/extracted_characters_hwxnet.json` (`--all` for full). |
| `scripts/create_character_views_table.py` | Create `character_views`. |
| `scripts/verify_feng_characters.py` | Verify row counts / sample from `feng_characters`. |
| `scripts/verify_hwxnet_characters.py` | Verify row counts / sample from `hwxnet_characters`. |
| `scripts/add_searchable_pinyin_column.py` | Add `searchable_pinyin` (jsonb) to `hwxnet_characters`, create GIN index, backfill from `pinyin`. Options: `--dry-run`, `--no-backup`, `--skip-filled`. |

All scripts use `DATABASE_URL` or `SUPABASE_DB_URL` (and load `backend/.env.local` if present). Run from `backend/`.

---

## 6. Deployment and testing

- **Production:** Set `DATABASE_URL` and `USE_DATABASE=true` in Cloud Run (or your host). See [DEPLOYMENT.md](DEPLOYMENT.md).
- **Tests:** Backend tests can use a test DB with seed data or a mock that returns the same dict shapes. E2E can run against an environment with DB enabled and tables populated.

---

## 7. Summary

| Area | Detail |
|------|--------|
| **Data source** | `feng_characters` and `hwxnet_characters` (and `character_views` for logging). |
| **Backend** | `database.py`; load_characters/load_hwxnet and update_character_field use it; API shapes unchanged. |
| **Pinyin search** | `hwxnet_characters.searchable_pinyin` (GIN index); backfill via `add_searchable_pinyin_column.py`. |
| **Config** | `DATABASE_URL` required when using DB; `USE_DATABASE=true` to enable. |
| **Frontend** | No contract change; same API responses. |
