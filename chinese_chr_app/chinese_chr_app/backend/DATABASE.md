# Database (Supabase / Postgres)

Single source of truth for character and dictionary data. The backend runtime is DB-only and reads/writes from Supabase using `DATABASE_URL` (or `SUPABASE_DB_URL`).

---

## 1. Configuration

| Variable | Purpose |
|----------|--------|
| **DATABASE_URL** (or **SUPABASE_DB_URL**) | Postgres connection string. Supabase: Connect → Connection string → Transaction pooler. Example: `postgresql://postgres.<ref>:[PASSWORD]@...pooler.supabase.com:6543/postgres?sslmode=require` |

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

**Create:** `python3 scripts/characters/create_feng_characters_table.py` (use `--all` for full migration). **Verify:** `python3 scripts/characters/verify_feng_characters.py`.

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
| **searchable_pinyin** | jsonb | Array of normalized pinyin keys for search (e.g. `["wo", "wo3"]`). Backfill: `scripts/characters/add_searchable_pinyin_column.py`. |
| **common_phrases** | jsonb | Array of 常用词组 (common phrases) from HWXNet. Backfill: `scripts/characters/add_common_phrases_column.py`. |

**Indexes:** `idx_hwxnet_characters_character`, `idx_hwxnet_characters_index` (partial), **`idx_hwxnet_searchable_pinyin`** (GIN on `searchable_pinyin`).

**Create:** `python3 scripts/characters/create_hwxnet_characters_table.py` (use `--all` for full migration). **Verify:** `python3 scripts/characters/verify_hwxnet_characters.py`. **Pinyin column:** `python3 scripts/characters/add_searchable_pinyin_column.py` (options: `--dry-run`, `--no-backup`, `--skip-filled`). **Common phrases:** `python3 scripts/characters/add_common_phrases_column.py` (options: `--dry-run`, `--no-backup`). **Verify common_phrases:** `python3 scripts/characters/verify_common_phrases.py` (optional `--limit N`).

---

### 2.3 `character_views`

Logs which characters signed-in users view on Search (user_id, character, viewed_at, display_name).

| Column | Type | Notes |
|--------|------|--------|
| id | uuid | PK, default gen_random_uuid() |
| user_id | text | NOT NULL |
| character | text | NOT NULL |
| viewed_at | timestamptz | NOT NULL, default now() |
| display_name | text | |

**Index:** `idx_character_views_user_viewed` on `(user_id, viewed_at DESC)`.

**Create:** `python3 scripts/characters/create_character_views_table.py`.

---

### 2.4 `user_profiles`

Per-user profile data for the Chinese character app (currently only the profile display name shown on the 我的 page).

| Column | Type | Notes |
|--------|------|--------|
| user_id | text | PRIMARY KEY; Supabase auth user ID |
| display_name | text | NOT NULL; sanitized, max 32 chars; same value returned by `/api/profile` |
| created_at | timestamptz | NOT NULL, default `now()` |
| updated_at | timestamptz | NOT NULL, default `now()` |

**Create:** `python3 scripts/users/create_user_profiles_table.py`.

---

### 2.5 `pinyin_recall_character_bank`

Per-user, per-character state for MVP1 pinyin recall (score −50–100, stage, next_due_utc, counts). Score: correct +10 (cap 100), wrong/我不知道 −10 (floor −50). Used for queue building and persistence across restarts.

**Queue construction (Issue #12):** Characters are partitioned into five score bands: 难字 (score ≤ −20), 普通在学字 (−20 &lt; score ≤ 0), 普通已学字 (0 &lt; score &lt; 20), 掌握字 (score ≥ 20). **Total Load** = count(难字) + count(普通在学字) + 0.3×count(普通已学字). Batch mode: **Expansion** (Total Load &lt; 100), **Consolidation** (100–250), **Rescue** (&gt; 250). In Expansion/Consolidation, reserve 4–6 slots for 巩固 before 在学字. Rescue recipe: 4 掌握字 + 8 普通已学字 + 6 在学字 (难字 first) + 2 新字; within 在学字 slots, 难字 first (score asc), no cap. **Cooling intervals** (next_due_utc after correct answer): 难字 0 days, 普通在学字 1 day, 普通已学字 5 days, 掌握字 22 days.

| Column | Type | Notes |
|--------|------|--------|
| user_id | text | NOT NULL; PK with character |
| character | text | NOT NULL |
| score | integer | NOT NULL, default 0 (−50–100) |
| stage | integer | NOT NULL, default 0 (band-based for analytics) |
| next_due_utc | bigint | unix ts or null; set by band-based cooling |
| first_seen_at | timestamptz | NOT NULL, default now() |
| last_answered_at | timestamptz | NOT NULL, default now() |
| total_correct | integer | NOT NULL, default 0 |
| total_wrong | integer | NOT NULL, default 0 |
| total_i_dont_know | integer | NOT NULL, default 0 |

**Index:** `idx_pinyin_recall_bank_user_next_due` on `(user_id, next_due_utc)`.

**Create:** `python3 scripts/pinyin_recall/create_pinyin_recall_character_bank_table.py`.

---

### 2.6 Pinyin recall event log (two tables)

Session events are written to Supabase (two-table design).

**`pinyin_recall_item_presented`** — when a character is shown in a batch.

| Column | Type | Notes |
|--------|------|--------|
| id | uuid | PK, default gen_random_uuid() |
| user_id | text | NOT NULL |
| session_id | text | NOT NULL |
| batch_id | uuid | Identifies the batch (each session/next-batch call); NULL for rows before migration |
| batch_mode | text | Queue mode for the batch: expansion, consolidation, or rescue (Issue #12); NULL for rows before migration |
| batch_character_category | text | Character's five-band category at batch creation: new, hard, learning_normal, learned_normal, mastered; NULL for rows before migration |
| character | text | NOT NULL |
| prompt_type | text | NOT NULL |
| correct_choice | text | NOT NULL |
| choices | jsonb | NOT NULL |
| created_at | timestamptz | NOT NULL, default now() |

**`pinyin_recall_item_answered`** — when the user submits an answer.

| Column | Type | Notes |
|--------|------|--------|
| id | uuid | PK, default gen_random_uuid() |
| user_id | text | NOT NULL |
| session_id | text | NOT NULL |
| character | text | NOT NULL |
| selected_choice | text | |
| correct | boolean | NOT NULL |
| latency_ms | integer | |
| i_dont_know | boolean | NOT NULL |
| score_before | integer | |
| score_after | integer | |
| category | text | 新字/巩固/重测 (at answer time); backfill via `scripts/pinyin_recall/backfill_pinyin_recall_category.py` |
| created_at | timestamptz | NOT NULL, default now() |

**`pinyin_recall_report_error`** — when the user clicks "报错" in the pinyin recall game (Issue #6). One row per report: user, session, batch (nullable), character, page (which screen), reported_at.

| Column | Type | Notes |
|--------|------|--------|
| id | uuid | PK, default gen_random_uuid() |
| user_id | text | NOT NULL |
| session_id | text | NOT NULL |
| batch_id | uuid | Identifies the batch; NULL if client did not send it |
| character | text | NOT NULL |
| page | text | Which screen: question (stem), wrong (wrong-answer feedback), or correct (correct-answer feedback); NULL for rows before migration |
| reported_at | timestamptz | NOT NULL, default now() |

**Index:** `idx_pinyin_recall_report_error_user_reported` on `(user_id, reported_at DESC)`.

**Create:** `python3 scripts/pinyin_recall/create_pinyin_recall_report_error_table.py`. Run once per environment so the table exists before the first report. **Add page column (existing deployments):** `python3 scripts/pinyin_recall/add_pinyin_recall_report_error_page_column.py` (options: `--dry-run`).

**Create:** `python3 scripts/pinyin_recall/create_pinyin_recall_log_tables.py`. **Add batch_id column (existing deployments):** `python3 scripts/pinyin_recall/add_pinyin_recall_batch_id_column.py`. **Add batch columns (existing deployments):** `python3 scripts/pinyin_recall/add_pinyin_recall_batch_columns.py` (adds batch_mode and batch_character_category). **Backfill batch_id:** `python3 scripts/pinyin_recall/backfill_pinyin_recall_batch_id.py` (clusters by created_at within session; options: `--dry-run`, `--gap 10`). **Add category column (existing deployments):** `python3 scripts/pinyin_recall/add_pinyin_recall_category_column.py`. **Backfill category:** `python3 scripts/pinyin_recall/backfill_pinyin_recall_category.py` (run after adding the column). **Backfill score (symmetric +10/−10):** `python3 scripts/pinyin_recall/backfill_pinyin_recall_score.py` (replays item_answered, updates bank + item_answered; creates backup tables first; `--dry-run`, `--no-backup`). **Upload local log:** `python3 scripts/pinyin_recall/upload_pinyin_recall_log_to_db.py` (reads `logs/pinyin_recall.log`). **Migrate from legacy single table:** `python3 scripts/pinyin_recall/migrate_pinyin_recall_events_to_two_tables.py` (if you had data in `pinyin_recall_events`).

---

### 2.7 `radical_stroke_counts`

Mapping of radical character to its stroke count (e.g. for sorting the Radicals page by radical stroke count). Source: [汉文学网 按部首查字](https://zd.hwxnet.com/bushou.html); JSON at `data/radical_stroke_counts.json`.

| Column | Type | Notes |
|--------|------|--------|
| radical | text | NOT NULL; PK |
| stroke_count | integer | NOT NULL |

**Index:** `idx_radical_stroke_counts_stroke_count` on `stroke_count`.

**Create and load:** `python3 scripts/radicals/create_radical_stroke_counts_table.py` (reads `data/radical_stroke_counts.json`). Use `--dry-run` to validate without connecting.

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

### Profile

| Function | Purpose |
|----------|--------|
| `get_profile_display_name(user_id)` | Return `display_name` from `user_profiles` for the given user, or `None` if not set. |
| `upsert_profile_display_name(user_id, display_name)` | Insert or update the `display_name` for the given user in `user_profiles`. |

### Pinyin recall (character bank and event log)

| Function | Purpose |
|----------|--------|
| `get_pinyin_recall_learning_state(user_id)` | Load learning state for queue building: `Dict[character, { stage, next_due_utc, score }]`. |
| `upsert_pinyin_recall_character_bank(user_id, character, correct, i_dont_know)` | Update character bank after one answer. Returns `(score_before, score_after)`. |
| `insert_pinyin_recall_item_presented(payload)` | Insert one row into `pinyin_recall_item_presented`. |
| `insert_pinyin_recall_item_answered(payload)` | Insert one row into `pinyin_recall_item_answered`. |
| `insert_pinyin_recall_report_error(user_id, session_id, batch_id, character, page=None)` | Insert one row into `pinyin_recall_report_error`. `batch_id` may be None. `page`: question, wrong, or correct. |
| `bulk_insert_pinyin_recall_item_presented(payloads)` | Bulk insert into `pinyin_recall_item_presented` (e.g. upload script). |
| `bulk_insert_pinyin_recall_item_answered(payloads)` | Bulk insert into `pinyin_recall_item_answered` (e.g. upload script). |
| `get_pinyin_recall_category_daily_trend(user_id, days=60)` | Return daily end-of-day counts for the four bands (难字, 普通在学字, 普通已学字, 掌握字) by replaying `pinyin_recall_item_answered` for the user. No new table; used by `GET /api/profile/progress` for the 掌握度每日趋势 chart. |

---

## 4. Backend behavior (DB-only runtime)

- **load_characters()** — Uses `get_feng_characters()`; builds `characters_data` and `character_lookup` (same shapes as JSON).
- **load_hwxnet()** — Uses `get_hwxnet_lookup()`; builds `hwxnet_data` and `hwxnet_lookup`.
- **Search** — `GET /api/characters/search?q=<char>` unchanged; data comes from DB-backed loaders.
- **Pinyin search** — `GET /api/pinyin-search?q=<query>` uses `get_characters_by_pinyin_search_keys()`.
- **Update** — `PUT /api/characters/<index>/update` calls `update_feng_character()`; optional file backup or rely on Supabase + edit log.
- **Character view logging** — Search page logs views via `log_character_view()` when user is signed in.
- **Radicals / stroke counts** — Same `generate_radicals_data` and `generate_stroke_counts_data`; inputs come from DB-backed loaders.
- **Pinyin recall character bank** — Learning state (score, stage, next_due_utc) is loaded from `pinyin_recall_character_bank` and updated on each answer. Queue orders due items by score ascending.
- **Pinyin recall event log** — `item_presented` and `item_answered` are written to `pinyin_recall_item_presented` and `pinyin_recall_item_answered` (two-table design).
- **Pinyin recall report error (报错)** — `POST /api/games/pinyin-recall/report-error` inserts one row into `pinyin_recall_report_error` (user_id, session_id, batch_id, character, page, reported_at). `page` is one of question, wrong, or correct (which screen the report came from).

API response shapes are unchanged; no frontend changes required for DB migration.

---

## 5. Scripts summary

| Script | Purpose |
|--------|--------|
| `scripts/characters/create_feng_characters_table.py` | Create `feng_characters`, optionally insert from `data/characters.json` (`--all` for full). |
| `scripts/characters/create_hwxnet_characters_table.py` | Create `hwxnet_characters`, optionally insert from `data/extracted_characters_hwxnet.json` (`--all` for full). |
| `scripts/characters/create_character_views_table.py` | Create `character_views`. |
| `scripts/pinyin_recall/create_pinyin_recall_character_bank_table.py` | Create `pinyin_recall_character_bank` (MVP1 pinyin recall state). |
| `scripts/pinyin_recall/create_pinyin_recall_log_tables.py` | Create `pinyin_recall_item_presented` and `pinyin_recall_item_answered` (two-table event log). |
| `scripts/pinyin_recall/create_pinyin_recall_report_error_table.py` | Create `pinyin_recall_report_error` (Issue #6: 报错 button log). Run once per environment. |
| `scripts/pinyin_recall/add_pinyin_recall_report_error_page_column.py` | Add `page` column to `pinyin_recall_report_error` (question/wrong/correct). Options: `--dry-run`. |
| `scripts/pinyin_recall/add_pinyin_recall_batch_id_column.py` | Add `batch_id` column to `pinyin_recall_item_presented` (for existing deployments). Options: `--dry-run`. |
| `scripts/pinyin_recall/backfill_pinyin_recall_batch_id.py` | Backfill `batch_id` using created_at clustering per session. Creates backup table first. Options: `--dry-run`, `--gap N` (seconds), `--no-backup`. |
| `scripts/pinyin_recall/add_pinyin_recall_category_column.py` | Add `category` column to `pinyin_recall_item_answered` (for existing deployments). |
| `scripts/pinyin_recall/backfill_pinyin_recall_category.py` | Backfill `category` from chronological answer history per (user_id, character). Options: `--dry-run`. |
| `scripts/pinyin_recall/backfill_pinyin_recall_score.py` | Backfill `score` in character_bank and `score_before`/`score_after` in item_answered using symmetric +10/−10. Replays item_answered per (user_id, character). Creates backup tables first. Options: `--dry-run`, `--no-backup`. |
| `scripts/pinyin_recall/upload_pinyin_recall_log_to_db.py` | One-off: upload `logs/pinyin_recall.log` into the two log tables. Options: `--dry-run`. |
| `scripts/pinyin_recall/migrate_pinyin_recall_events_to_two_tables.py` | One-off: copy from legacy `pinyin_recall_events` into the two log tables. Options: `--dry-run`. |
| `scripts/utils/delete_local_dev_rows.py` | Delete all rows where `user_id = 'local-dev'` from tables with user_id (character_views, pinyin_recall_*, pinyin_recall_events). Creates backup tables first. Options: `--dry-run`, `--no-backup`. |
| `scripts/radicals/create_radical_stroke_counts_table.py` | Create `radical_stroke_counts`, insert from `data/radical_stroke_counts.json`. Options: `--dry-run`. |
| `scripts/characters/verify_feng_characters.py` | Verify row counts / sample from `feng_characters`. |
| `scripts/characters/verify_hwxnet_characters.py` | Verify row counts / sample from `hwxnet_characters`. |
| `scripts/characters/add_searchable_pinyin_column.py` | Add `searchable_pinyin` (jsonb) to `hwxnet_characters`, create GIN index, backfill from `pinyin`. Options: `--dry-run`, `--no-backup`, `--skip-filled`. |
| `scripts/utils/query_character_for_user.py` | Query Supabase for one character’s `pinyin_recall_character_bank` row and `pinyin_recall_item_answered` history for a user. **Options:** `--email "user@example.com"` or `--user-id "uuid"` (required), `--character 亚` (default). Resolves email via `auth.users`. Requires `DATABASE_URL` or `SUPABASE_DB_URL`. Run from `backend/`: `python3 scripts/utils/query_character_for_user.py --user-id "uuid" --character 丐`. |

All scripts use `DATABASE_URL` or `SUPABASE_DB_URL` (and load `backend/.env.local` if present). Run from `backend/`.

---

## 6. How to run ad‑hoc Supabase queries

For quick one‑off checks (e.g. verifying pinyin for a single character) without
leaving the repo, run a small inline Python script from `backend/`:

```bash
cd chinese_chr_app/chinese_chr_app/backend

# Ensure .env.local has DATABASE_URL or SUPABASE_DB_URL set, then:
python3 - << 'EOF'
import os, json
import psycopg
from psycopg.rows import dict_row

url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
if not url:
    raise SystemExit("No DATABASE_URL / SUPABASE_DB_URL set")

with psycopg.connect(url, row_factory=dict_row) as conn:
    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT character, pinyin, searchable_pinyin
            FROM hwxnet_characters
            WHERE character = %s
            ORDER BY zibiao_index
            LIMIT 5
            """,
            ("悔",),
        )
        rows = cur.fetchall()

print(json.dumps(rows, ensure_ascii=False, indent=2))
EOF
```

Key points:

- Use `psycopg.connect(url, row_factory=dict_row)` so rows come back as dicts.
- Read `DATABASE_URL` / `SUPABASE_DB_URL` from `.env.local` (loaded automatically by scripts, or `source .env.local` before running).
- Always parameterize (`WHERE character = %s, ("悔",)`) instead of string‑formatting SQL.

---

## 6. Deployment and testing

- **Production:** Set `DATABASE_URL` (or `SUPABASE_DB_URL`) in Cloud Run (or your host). See [DEPLOYMENT.md](DEPLOYMENT.md).
- **Tests:** Backend tests can use a test DB with seed data or a mock that returns the same dict shapes. E2E can run against an environment with DB enabled and tables populated.

---

## 7. Summary

| Area | Detail |
|------|--------|
| **Data source** | `feng_characters`, `hwxnet_characters`, `character_views`, `pinyin_recall_character_bank`, `pinyin_recall_item_presented`, `pinyin_recall_item_answered`. |
| **Backend** | `database.py`; load_characters/load_hwxnet and update_character_field use it; API shapes unchanged. |
| **Pinyin search** | `hwxnet_characters.searchable_pinyin` (GIN index); backfill via `add_searchable_pinyin_column.py`. |
| **Config** | `DATABASE_URL` (or `SUPABASE_DB_URL`) required. |
| **Frontend** | No contract change; same API responses. |
