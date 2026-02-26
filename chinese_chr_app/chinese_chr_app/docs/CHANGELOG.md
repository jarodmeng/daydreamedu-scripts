# CHANGELOG

Release history and version notes. Newest releases are at the top.

**Versioning:** Initial app = **v0.1**. Minor update = +0.0.1 (e.g. v0.1 → v0.1.1). Major update = increment second digit (e.g. v0.1.11 → **v0.2**). Complete upgrade = increment first digit (e.g. v0.2.10 → **v1.0**).

---

## [v0.2.11]

- **Cloud Build smoke tests:** Allow Chinese chr app Cloud Build import smoke tests to run without DB env so basic import smoke still passes when database variables are missing.
- **CI e2e workflows:** Wire e2e DB env and secret preflight correctly in CI, add a manual `workflow_dispatch` trigger for Playwright e2e, and skip secretless PR runs to avoid noisy failures.

---

## [v0.2.10]

- **Log-character-view dev fallback:** `/api/log-character-view` now accepts the E2E/dev user fallback (same as profile and pinyin-recall endpoints), so E2E and local dev no longer see 401s or console errors when viewing characters. Backend suppresses expected fake-token JWT parse noise in logs before falling back to `PINYIN_RECALL_DEV_USER`.
- **E2E coverage:** New specs for profile category page (guest, invalid/valid category, click-through), search error states (backend error, stroke loading fallback), profile interactions (display name edit/cancel/save, category links), and pinyin recall edge paths (session/answer error surfacing).
- **Docs:** Added [TESTING.md](TESTING.md) (testing philosophy, mock-vs-real E2E guidance, coverage priorities) and linked it from the app README ToC.

---

## [v0.2.9]

- **Backend DB-only runtime (#22):** Removed `USE_DATABASE` branching and local JSON fallback; backend now requires `DATABASE_URL` (or `SUPABASE_URL`/`SUPABASE_DB_URL`) and uses the database exclusively. Local JSON files remain as backups only, not used at runtime.
- **E2E auth bypass:** Playwright e2e tests use the auth-bypass path as the authoritative flow; backend dev-user fallback and frontend E2E bypass are aligned for profile and pinyin-recall specs.

---

## [v0.2.8]

- **Profile 掌握度每日趋势 (#19):** Daily trend of the four character bands (难字 / 普通在学字 / 普通已学字 / 掌握字) on the 我的 page. Runtime-computed from `pinyin_recall_item_answered` (no schema change). Chart shown when user has ≥5 days of data. API `GET /api/profile/progress` returns `category_trend`. Script `user_daily_category_counts.py` for ad-hoc verification.

---

## [v0.2.7]

- **Profile name persistence (#18):** Persist user profile display name in the `user_profiles` table when `USE_DATABASE=true`, and have `/api/profile` read from it so names survive backend restarts and Cloud Run instance changes.
- **Logging alignment:** Character view logging (`character_views.display_name`) now prefers the same persisted profile name used on the 我的 page.
- **Ops:** New script `scripts/users/create_user_profiles_table.py` must be run once per DB-backed environment to create `user_profiles`.

---

## [v0.2.6]

- **Documentation refactor:** Modular docs (README as receptionist, VISION, ARCHITECTURE, CHANGELOG). PRD, plans, proposals, research and content-mapping plan moved to `docs/archive/`.

---

## [v0.2.5]

- **Auth/backend fixes:** Use certifi SSL context for PyJWKClient (auth). Use `datetime.now(timezone.utc)` instead of deprecated `utcnow()` in backend.
- Commits: e5d0d67, 69753c9.

---

## [v0.2.4]

- **Report Error (报错):** Users can report wrong character data from the pinyin-recall game. DB table `pinyin_recall_report_error`, API `POST /api/games/pinyin-recall/report-error`, frontend 报错 button and page.
- **Correct-answer page (Issue #7):** Correct-answer screen shows all pinyin, English meaning (英文翻译), and 基本解释 when available.
- Commits: b03a092, c7fd538.

---

## [v0.2.3]

- **Queue by five score-based categories:** Characters partitioned into five bands (未学字, 难字, 普通在学字, 普通已学字, 掌握字). Queue construction uses Active Load modes (Expansion / Consolidation / Rescue) and band-based slot recipes. Batch mode and batch character category logged in `pinyin_recall_item_presented` (`batch_mode`, `batch_character_category`).
- **batch_id:** `pinyin_recall_item_presented` rows include `batch_id` to identify the batch; migration and backfill scripts added.
- Commits: 21372eb, f2103fc.

---

## [v0.2.2]

- **Profile 汉字掌握度: 未学字 / 在学字 / 已学字 (#11):** Profile progress shows three categories (not tested, still learning, learned). API `GET /api/profile/progress` returns `learning_count` and `not_tested_count`; frontend shows stacked bar and counts.
- Commit: 76b15e5.

---

## [v0.2.1]

- **Symmetric scoring (+10/−10):** Pinyin recall score change on correct is +10 (cap 100), on wrong or 我不知道 is −10 (was −15). Backfill script recomputes scores from event log.
- **Score floor −50:** Pinyin recall score floor is −50 (was 0) so repeated wrongs are reflected; queue ordering uses negative scores for prioritization.
- Commits: 43c447f, 1b01b5a.

---

## [v0.2]

- **Major: MVP1 Pinyin Recall.** Personalized pinyin-recall micro-session: persistence in Supabase (character bank, two-table event log), open-ended session (batches of 20), session and next-batch APIs, answer API with score update and scheduling. UI: question flow, 4 pinyin choices + 我不知道, immediate feedback, English meaning on review screen. Slot reservation for 巩固 (up to 4 per batch); new items capped (e.g. 8 per batch).
- Commits: 3136a60, 637c418, e2b799b, 246ef5c.

---

## [v0.1.8]

- **Pinyin search (M6):** Search box accepts pinyin (e.g. ke, wo3); results page lists characters with that reading ranked by stroke count. Route `/pinyin/:query`, API `GET /api/pinyin-search?q=<query>`.
- **Character view logging:** Signed-in users’ character views on Search are logged to `character_views` when `USE_DATABASE=true`.
- **Profile API and page:** `GET /api/profile`, `PUT /api/profile`; Profile and progress page (Issue #2) with viewed characters, daily stats, proficiency (已学字 count).
- Commits: b98acc7, 616bf93, ca851ab, a51bb7b.

---

## [v0.1.7]

- **Supabase DB support:** Backend can read/write character and dictionary data from Supabase/Postgres when `USE_DATABASE=true` and `DATABASE_URL` are set. Tables: `feng_characters`, `hwxnet_characters`; scripts for create/migrate/verify.
- **Supabase Auth (Google login):** Sign in with Google via Supabase Auth; Bearer token used for profile and (later) pinyin-recall APIs.
- Commits: df3474d, a1bb8a9.

---

## [v0.1.6]

- **Stroke order animation (M4):** Search page shows HanziWriter stroke-order animation for the character; backend proxy/cache for stroke JSON (`GET /api/strokes?char=<character>`).
- **Segmentation dropdown (M3):** Nav bar: Search + 分类 dropdown (部首, later 笔画). 分类 acts as dropdown trigger, not standalone page.
- **Radicals from HWXNet:** Radicals data generated from HWXNet dictionary; alignment with hwxnet radical/stroke counts.
- Commits: 5694eaf, 6c43b1c, c341779.

---

## [v0.1.5]

- **Playwright E2E smoke tests:** Core flows (search, dictionary-only, radicals), routing, navigation.
- **zibiao_index and dictionary-only characters:** HWXNet union includes level-1 characters; characters in HWXNet but not in Feng set show dictionary + stroke animation only (no card). Search supports dictionary-only results.
- Commits: 48c936d, e2db121.

---

## [v0.1.4]

- **Remove structures page:** Structures segmentation removed; nav simplified (pivot).
- Commit: 33d6719.

---

## [v0.1.3]

- **Stroke-count (笔画) pages (M5):** Routes `/stroke-counts` and `/stroke-counts/:count`. Grid of stroke counts with character counts; detail page lists characters by stroke count. Data from HWXNet. APIs: `GET /api/stroke-counts`, `GET /api/stroke-counts/<count>`.
- Commit: fde29bf.

---

## [v0.1.2]

- **HWXNet dictionary view:** Dictionary (汉文学网) data shown alongside character metadata on Search page; HWXNet fields (拼音, 部首, 总笔画, 分类, 基本解释, 英文翻译) displayed.
- Commit: 1fbfb82.

---

## [v0.1.1]

- **Radicals page (M2):** 部首 (Radicals) page: grid of radicals with character counts, detail page per radical with characters (stroke then pinyin order), click-through to search.
- Commit: d874f96.

---

## [v0.1]

- **Initial app (M1):** Character search: search box, display of 3000 冯氏早教识字卡 characters with card images (page1/page2) and metadata (拼音, 部首, 笔画, 例句, 词组, 结构). Dictionary-style metadata table. Not-found handling. Web app only; no user profiles yet.
- Commits / PRD: 5a3ad7d, PRD Milestone 1.
