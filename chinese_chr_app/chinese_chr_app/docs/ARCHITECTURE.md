# ARCHITECTURE — Technical Specs and System Flow

This document describes the current technical implementation. For product strategy see [VISION.md](VISION.md). For release history see [CHANGELOG.md](CHANGELOG.md). For full database schema and scripts see [backend/DATABASE.md](../backend/DATABASE.md).

---

## 1. System Overview

- **Frontend:** React (Vite), deployed to Netlify. Routes: Search (`/`), Radicals, Stroke counts, Pinyin results (`/pinyin/:query`), Pinyin Recall game (`/games/pinyin-recall`), Profile and profile-by-category.
- **Backend:** Flask API on port **5001** (to avoid conflict with macOS AirPlay on 5000). Deployed to Google Cloud Run.
- **Auth:** Supabase Auth (Google login). Bearer token required for profile and pinyin-recall APIs; optional for search/radicals/stroke-counts.
- **Data:** Character and dictionary data are served from Supabase/Postgres (`DATABASE_URL` / `SUPABASE_DB_URL`, DB-only runtime). Images: local `data/png` or Google Cloud Storage bucket `chinese-chr-app-images`.

---

## 2. Project Structure

Paths are relative to the repo root. The app lives under `chinese_chr_app/chinese_chr_app/`.

- **`backend/`** — Flask app (`app.py`), auth (`auth.py`), database layer (`database.py`), pinyin recall logic (`pinyin_recall.py`), pinyin search parsing (`pinyin_search.py`). Scripts under `backend/scripts/` by domain: `characters/`, `pinyin_recall/`, `radicals/`, `utils/`. Schema and scripts are documented in [backend/DATABASE.md](../backend/DATABASE.md).
- **`frontend/`** — Vite + React. Pages under `src/pages/` (Search, PinyinResults, Radicals, RadicalDetail, StrokeCounts, StrokeCountDetail, Profile, ProfileCategory, PinyinRecall). Shared: `App.jsx`, `NavBar.jsx`, `AuthContext.jsx`, `supabaseClient.js`. E2E under `e2e/`.
- **`data/`** — JSON: `characters.json` (Feng 3000), `extracted_characters_hwxnet.json` (HWXNet ~3664), `level-1/2/3.json` (Zibiao-style lists), `radical_stroke_counts.json`. Optional local PNGs under `data/png/`.

---

## 3. Data Model (high-level)

- **Feng (3000 characters):** Primary curriculum set with card images and maintained metadata (拼音, 部首, 笔画, 例句, 词组, 结构). Stored in Supabase table `feng_characters`.
  - Feng rows carry both legacy flat `Words` and structured `WordsByPinyin` / `words_by_pinyin`.
  - `WordsByPinyin` is the preferred source for reading-aware consumers such as Pinyin Recall.
  - Legacy `Words` remains compatibility/fallback data for character-centric consumers.
- **HWXNet (~3664 characters):** Dictionary source for display, radicals, stroke-counts, and pinyin search. Union of Feng and level-1 commonly used characters. Stored in Supabase table `hwxnet_characters`. Includes `searchable_pinyin` for pinyin search.
  - HWXNet rows carry both legacy flat `常用词组` / `common_phrases` and structured `常用词组按拼音` / `common_phrases_by_pinyin`, plus both legacy flat `英文翻译` / `english_translations` and structured `英文解释按拼音` / `english_translations_by_pinyin`.
  - Reading-aware consumers prefer the structured buckets; legacy flat fields remain compatibility/fallback data for consumers that still operate at the character level.
- **Pinyin Recall reading units:** The pinyin-recall learning identity is now `character + reading`, represented by stable `unit_id`s such as `行|xing2`. These units are derived from the character rows rather than materialized as a standalone dictionary table.
- **Pinyin Recall disabled units:** Units reported by real authenticated users can be removed from future circulation globally. Current disable state is stored in `pinyin_recall_disabled_units` and consumed at runtime as `recall_enabled = false` overrides.
- **Per-user learning state:** Pinyin-recall learner state is stored in `pinyin_recall_unit_bank`, keyed by `(user_id, unit_id)`. Presented/answered/report rows also carry `unit_id`, `reading_key`, and `reading_display`.
- **Stroke order:** Fetched on demand from HanziWriter-compatible CDN; backend proxies and may cache under `data/temp/hanzi_writer/`.
- **Radical stroke counts:** Used to sort the Radicals page by 按部首笔画. Stored in Supabase table `radical_stroke_counts`.

Full schema, indexes, and creation/backfill scripts are in [backend/DATABASE.md](../backend/DATABASE.md).

---

## 4. Search Behavior

- **Input:** One Chinese character or one pinyin syllable (e.g. `ke`, `wo3`). Single CJK character → character search; otherwise → pinyin search.
- **Character search:** If the character is in the Feng set, the Search page shows four panels: 笔顺动画, 字典信息（hwxnet）, 字卡, 字符信息（冯氏早教识字卡）. If the character is only in HWXNet (dictionary-only), the page shows 笔顺动画 and 字典信息 only. Current Feng field display remains read-only. The `词组` row now renders grouped `WordsByPinyin` buckets for Feng characters so polyphonic readings are visually separated, with legacy flat `Words` used only as a fallback when structured bucket data is unavailable.
- **Pinyin search:** Results page at `/pinyin/:query` lists characters matching that reading, ranked by stroke count (ascending). Clicking a result opens the character detail (Search) view. The backend primarily uses `hwxnet_characters.searchable_pinyin`, but also recomputes normalized keys from `pinyin` at read time as a safety net if legacy rows contain stale or malformed search keys.

---

## 5. API Endpoints

All under `/api/`. Base URL in development: `http://localhost:5001`.

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/characters/search?q=<character>` | Character search; returns card + dictionary data or dictionary-only. |
| GET | `/api/pinyin-search?q=<pinyin>` | Pinyin search; returns characters ranked by stroke count. |
| PUT | `/api/characters/<index>/update` | Update Feng character metadata (dormant backend edit surface; current Search UI is read-only). |
| POST | `/api/log-character-view` | Log signed-in user’s character view (body: `character`, optional `display_name`). Requires Bearer token. |
| GET | `/api/images/<index>/<page>` | Character card images (page1 or page2). |
| GET | `/api/strokes?char=<character>` | Proxy/cached stroke JSON for HanziWriter. |
| GET | `/api/radicals` | All radicals sorted by character count. |
| GET | `/api/radicals/<radical>` | Characters for one radical. |
| GET | `/api/stroke-counts` | Stroke counts that have at least one character. |
| GET | `/api/stroke-counts/<count>` | Characters with that stroke count. |
| GET | `/api/profile` | Current user profile (display name). Requires Bearer token. |
| PUT | `/api/profile` | Update display name. Requires Bearer token. |
| GET | `/api/profile/progress` | Progress summary: viewed characters, daily stats, and pinyin-recall progress (`读音掌握度`) over the enabled reading-unit pool, plus `category_trend` (daily counts for 难项/普通在学项/普通已学项/掌握项, computed from pinyin-recall history). Requires Bearer token. |
| GET | `/api/profile/progress/category/<category>` | Reading-unit entries in a given category (e.g. learning_hard, learned_normal). Category pages still link through to character detail pages by design. Requires Bearer token. |
| GET | `/api/games/pinyin-recall/session` | First batch of pinyin-recall items (20). Requires Bearer token. |
| POST | `/api/games/pinyin-recall/next-batch` | Next batch of 20 items. Optional body: `session_id`. Requires Bearer token. |
| POST | `/api/games/pinyin-recall/answer` | Submit one answer. Requires Bearer token. |
| POST | `/api/games/pinyin-recall/report-error` | Log 报错 (wrong data report). Real authenticated users also globally disable the reported unit for future queues. Requires Bearer token. |
| GET | `/api/health` | Health check. |

---

## 6. Auth

- **Production:** Supabase Auth (Google login). Frontend sends Bearer JWT; backend verifies it against Supabase JWKS (`SUPABASE_URL`). UI treats `useAuth().user` as the authenticated state (Profile and Pinyin Recall show login prompts when `!user`).
- **Dev/E2E:** Backend accepts an optional dev user when `PINYIN_RECALL_DEV_USER` is set (real JWT takes precedence). Frontend can use E2E bypass (`VITE_E2E_AUTH_BYPASS=1` or `?e2e_auth=1`); when bypass is active, the fake session is authoritative (Supabase `onAuthStateChange` is not subscribed). `?e2e_guest=1` forces unauthenticated UI for guest tests.
- **Stricter route:** `POST /api/log-character-view` requires a real JWT only (no dev fallback); other auth-gated routes accept real user or dev user.
- Full flows, env matrix, and troubleshooting: [AUTHENTICATION.md](AUTHENTICATION.md).

---

## 7. Database (Supabase / Postgres)

The backend runtime is DB-only and requires `DATABASE_URL` (or `SUPABASE_DB_URL`):

- Character and dictionary data are read/written from Supabase tables `feng_characters` and `hwxnet_characters`.
- Signed-in users’ character views (Search) are logged to `character_views`.
- Pinyin recall state and events use `pinyin_recall_unit_bank`, `pinyin_recall_item_presented`, `pinyin_recall_item_answered`, `pinyin_recall_report_error`, and `pinyin_recall_disabled_units`. Legacy `pinyin_recall_character_bank` is retained as historical migration-era state, not the active runtime bank. Radical stroke counts are served from table `radical_stroke_counts`.

Schema, configuration, data-access layer, and all migration/backfill scripts are documented in [backend/DATABASE.md](../backend/DATABASE.md).

---

## 8. Pinyin Recall (learning game)

### 8.1 Session and queue

- **Session:** User gets a first batch of 20 items from `GET /api/games/pinyin-recall/session`. After finishing a batch, `POST /api/games/pinyin-recall/next-batch` returns the next 20. Session is open-ended until the user ends it.
- **Batch size:** 20 items per batch. `new_count` cap per batch is 8 (at most 8 新字 per batch).
- **Queue construction:** Total Load = count(难项) + count(普通在学项) + 0.3×count(普通已学项). Three modes:
  - **Expansion** (Total Load < 100): 10 新字 + 10 review; reserve 4 slots for 巩固 before 在学项.
  - **Consolidation** (100 ≤ Total Load ≤ 250): 5 新字 + 15 review; reserve 6 slots for 巩固 before 在学项.
  - **Rescue** (Total Load > 250): 4 掌握项 + 8 普通已学项 + 6 在学项 (难项 first) + 2 新字; within 在学项 slots, 难项 first (score ascending), no cap.
- **Slot reservation:** In Expansion/Consolidation, reserve slots for 巩固 (普通已学项 + 掌握项) before allocating to 在学项, so 巩固 is never crowded out.

### 8.2 Score and categories

- **Score range:** −50 to 100. Correct: +10 (cap 100). Wrong or 我不知道: −10 (floor −50).
- **Proficiency threshold:** score ≥ 10 = 已学项 (learned item). Used for profile `读音掌握度` and for 巩固 vs 重测.
- **Five bands (for queue selection):** 难项 (score ≤ −20), 普通在学项 (−20 < score ≤ 0), 普通已学项 (0 < score < 20), 掌握项 (score ≥ 20). 未学项 = not yet in `pinyin_recall_unit_bank`.
- **Display categories (three):** 新字 (first time), 重测 (retest / still learning), 巩固 (consolidation / maintenance). Session items include `is_polyphonic`; when true, a 多音字 tag is shown next to the category in the question header.

### 8.3 Cooling (next_due_utc)

After a correct answer, `next_due_utc` is set by band:

- 难项: 0 days  
- 普通在学项: 1 day  
- 普通已学项: 5 days  
- 掌握项: 22 days  

Only due items (and new items within cap) are eligible for the next batch.

### 8.4 Prompt and distractors

- **Prompt:** Hanzi reading recall as multiple-choice pinyin. The tested identity is one reading unit, not just the character. Stem words and learner-facing meaning content are built from reading-aware sources in priority order: Feng `WordsByPinyin`, HWXNet `common_phrases_by_pinyin`, then reading-matched HWXNet `basic_meanings`. 我不知道 is always offered.
- **Distractors:** Same syllable different tone, same tone different syllable, tone confusions. For polyphonic characters, sibling readings are excluded from the main answer identity and the prompt/feedback are built for the tested unit only.
- **Logging:** Events are written to `pinyin_recall_item_presented` (with `batch_id`, `batch_mode`, `batch_character_category`, `unit_id`, `reading_key`, `reading_display`) and `pinyin_recall_item_answered` (with `score_before`, `score_after`, `category`, `unit_id`, `reading_key`, `reading_display`).
- **Global disable-on-report:** When a real authenticated user reports a unit with `POST /api/games/pinyin-recall/report-error`, that unit is written to the global disabled-unit registry and excluded from future queues and enabled-unit totals. Synthetic/dev fallback users can still log report rows, but do not disable units globally. This applies to future queue construction only; already-issued in-flight items remain answerable.

### 8.5 Feedback and review UI

- **Correct-answer screen:** Character, the tested reading, sibling readings as secondary context when relevant, reading-specific English meaning / 基本解释 when available, and reading-specific stem words.
- **Wrong-answer / 我不知道 screen:** 答错了 (and 你选了: …), correct character and tested reading, then a learning block with reading-specific English meaning / 基本解释 plus the usual supporting metadata.
- **Final review (复习这些字):** For each missed item, the same reading-specific learning block used by the wrong-answer flow.

---

## 9. Stroke Animation (HanziWriter)

- **Endpoint:** `GET /api/strokes?char=<character>` proxies stroke-order JSON from jsDelivr/unpkg (hanzi-writer-data). Backend may cache under `data/temp/hanzi_writer/`.
- **SSL:** Backend uses the `certifi` CA bundle. To disable SSL verification for CDN fetches (e.g. dev/CI): `HW_STROKES_VERIFY_SSL=0` when starting the backend.

---

## 10. Frontend Routes and Navigation

- **Routes:** `/` (Search), `/radicals`, `/radicals/:radical`, `/stroke-counts`, `/stroke-counts/:count`, `/pinyin/:query`, `/games/pinyin-recall`, `/profile`, `/profile/category/:category`. Unknown paths redirect to `/`.
- **Nav bar:** Search (link to `/`), 分类 dropdown (部首, 笔画), 游戏 dropdown (拼音记忆). Active tab is indicated by style (e.g. Search or 分类 when on a segmentation page).

---

## 11. Testing (E2E)

Playwright tests under `frontend/e2e/` cover:

- **Core:** Character search (4-panel and dictionary-only), radicals list/detail, click-through to search.
- **Pinyin search:** Redirect on pinyin input, results page, no match / invalid format, placeholder.
- **Routing:** Unknown path → home; direct URLs to radical and stroke-count detail.
- **Navigation:** Logo, search link, 分类 and 游戏 dropdowns.
- **Profile:** Unauthenticated → login prompt and return link.
- **Pinyin Recall:** Unauthenticated → login prompt.

Run from `frontend/`: `npm run test:e2e`. Backend should be on port 5001 (or Playwright will try to start it).
