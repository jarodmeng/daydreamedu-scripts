# CHANGELOG

Release history and version notes. Newest releases are at the top.

**Versioning:** Initial app = **v0.1**. Minor update = +0.0.1 (e.g. v0.1 → v0.1.1). Major update = increment second digit (e.g. v0.1.11 → **v0.2**). Complete upgrade = increment first digit (e.g. v0.2.10 → **v1.0**).

---

## [v0.3.5]

- **Profile 掌握度 trend consistency:** Align `掌握度每日趋势` with the table counts by filtering the daily-trend computation to enabled recall reading-units (and ignoring legacy rows without `unit_id`), so `掌握项` / other bands don’t include disabled units.

## [v0.3.4]

- **Profile multi-period practice summaries (#37):** Add a `阶段汇总` subsection inside `每日练习统计` on the 我的 page with rolling `最近7天`, `最近1个月`, `最近1季度`, and `累计` summary rows.
- **Profile progress API extension:** `GET /api/profile/progress` now returns `practice_summary` alongside `daily_stats`, including `活跃天数`, totals, accuracy, and `新字` / `巩固` / `重测` breakdowns for each period.
- **Coverage and UI polish:** Reuse the existing daily-stat category cell style for the new summary table, keep the daily detail table below it, and add focused backend plus Playwright coverage for both populated and empty-history states.

## [v0.3.3]

- **AI review + operator confirmation for low-learning-value units:** Add a dedicated workflow to review enabled polyphonic units, save true/false-positive decisions, and produce a confirmed-removals artifact.
- **Permanent removal rollout:** Remove confirmed low-learning-value `character + reading` units from HWXNet source data and matching user Pinyin Recall history, with backup-first sync/cleanup steps for local JSON and Supabase tables.
- **Prompt/candidate refinement and docs:** Exclude Feng-supported readings from the candidate pool, tighten the AI prompt toward standalone learner value, and document the workflow/apply steps with focused test coverage.

## [v0.3.2]

- **User-prioritized Pinyin Recall queueing:** Add `user_prioritized_characters` support so per-user reading-level priority targets can front-load eligible 新字 without changing Expansion / Consolidation / Rescue slot counts, including explicit out-of-window overrides for targeted new items.
- **Priority-aware review ordering:** Weak due items that match a user priority row now sort earlier within the existing due pools, while mastered items keep their current ordering.
- **In-game priority labels:** Session items now expose `priority_label`, `priority_source`, and `from_user_priority`, and the Pinyin Recall question UI renders the priority label as a neutral chip alongside the existing category and 多音字 tags.
- **Operator tooling for Emma-style imports:** Add scripts to regenerate a user’s missing reading-level priorities from a source readings JSON and upsert them into `user_prioritized_characters`.

## [v0.3.1]

- **Globally disable real-user-reported recall units:** When a real authenticated user reports a Pinyin Recall unit via 报错, that `character + reading` unit is now removed from future circulation for everyone. Disabled units no longer enter newly built queues, but already-issued in-flight items remain answerable.
- **Dedicated disabled-unit registry + reading-aware tooling:** Add a global `pinyin_recall_disabled_units` table and runtime override path, keep `pinyin_recall_report_error` append-only, and update the report-error query utility to surface `unit_id` by default for polyphonic triage.
- **Profile enabled-unit totals now derive fresh state:** Remove the in-process enabled-unit cache so Profile/progress totals always recompute against the current globally enabled unit pool, including newly disabled units.
- **Docs and decision record:** Add a proposal for global disable-on-report behavior, record the decision in `DECISIONS.md`, and update architecture/auth/database docs for the real-user-only trigger rule and synthetic-user exclusion.

---

## [v0.3.0]

- **Major pinyin-recall upgrade: reading units for polyphonic characters.** Pinyin Recall now treats the learning unit as `character + reading` rather than just `character`, so polyphonic siblings like `行|xíng` and `行|háng` can be scheduled, prompted, answered, and reviewed separately. Runtime prompts, distractors, stem words, English glosses, and wrong-answer feedback are now reading-specific instead of leaking content across sibling readings.
- **Persistence migrated to unit-level state.** Learner state now uses `pinyin_recall_unit_bank`, and the pinyin-recall event tables carry `unit_id`, `reading_key`, and `reading_display`. Existing learner state was migrated with backups, and legacy `pinyin_recall_item_presented` / `pinyin_recall_item_answered` rows were backfilled to unit-level identity as well.
- **Profile/progress now use reading-unit accounting.** The Profile page now reports `读音掌握度` against the enabled reading-unit pool instead of the old character denominator. Category pages can now show separate entries for different readings of the same Hanzi while still linking through to the same character detail page by design.
- **Data/model cleanup and validation.** The upgrade formalizes reading-aware consumption of Feng `WordsByPinyin`, HWXNet `常用词组按拼音` / `common_phrases_by_pinyin`, and HWXNet `英文解释按拼音` / `english_translations_by_pinyin`, adds focused backend coverage for the new contract/API/profile behavior, and completes live-DB migration validation with backup tables and zero remaining null `unit_id` rows in `pinyin_recall_item_presented` and `pinyin_recall_item_answered`.

---

## [v0.2.24]

- **Feng Search fixes for `嘛` / `嗯` (#34, #35):** Correct the Feng-side Search data for `嘛` so it now exposes both readings `ma -> 喇嘛`, `má -> 干嘛`, and fix `嗯` so its Feng pinyin uses `ǹg` for the `嗯声` row instead of the incorrect `èn`.
- **Targeted Supabase sync:** Update only the live `feng_characters` rows for `嘛` and `嗯` so `pinyin`, `words`, and `words_by_pinyin` match the reviewed `data/characters.json` entries without requiring a broader table reload.

---

## [v0.2.23]

- **Feng data cleanup for issue #31:** Fixed the remaining bad Feng sample-word rows so split idioms are merged correctly (`来日方长`, `人来人往`, `惹事生非`), removed the `朗 -> 吊儿郎当` source-card typo, and corrected Feng index `2328` from a long-mislabeled `谴` row to the actual `遣` card with matching metadata and phrases.
- **Supabase sync + regression coverage:** Backed up the live `feng_characters` table, synced the reviewed rows from `data/characters.json`, and added focused backend invariants coverage for Feng phrase quality plus the corrected `2328 -> 遣` identity.

---

## [v0.2.22]

- **Search English grouped by pinyin:** The HWXNet `英语` row on the Search page now renders `英文解释按拼音` buckets directly instead of flattening all glosses into a single `|`-separated line, so polyphonic characters clearly separate English meanings by reading.
- **UI consistency + coverage:** Reuse the existing pinyin-chip grouped layout from the Feng `词组` row for HWXNet English buckets, keep legacy flat `英文翻译` as a fallback when structured data is missing, and add focused Playwright coverage for a known polyphonic example (`累`).

---

## [v0.2.21]

- **HWXNet 英文解释按拼音 transition:** Add structured `英文解释按拼音` to `extracted_characters_hwxnet.json`, add `english_translations_by_pinyin` to the live `hwxnet_characters` table, and use the curated reading-level English gloss artifact as the provenance source for polyphonic buckets. Monophonic rows are wrapped mechanically from legacy `英文翻译`.
- **Conservative English consumer migration:** Runtime consumers now prefer the new structured HWXNet English field internally while preserving current flat behavior through a shared flatten utility. Legacy flat `英文翻译` remains compatibility data during the migration.
- **Verification / tooling:** Added transition builder + merge scripts, DB backfill support, focused backend regression tests for English bucket normalization/flattening, and live DB verification coverage for the new column.

---

## [v0.2.20]

- **Search words grouped by pinyin:** The Feng `词组` row on the Search page now renders `WordsByPinyin` buckets directly instead of flattening them into a single comma-separated line, so polyphonic characters clearly separate phrases by reading. Added focused Playwright coverage for a known polyphonic example (`参`) to lock in the grouped UI behavior.
- **Polyphonic reading coverage cleanup:** Reviewed all uncovered HWXNet polyphonic readings under a stricter sample-word coverage rule, removed `506` low-value readings, added `23` manual sample words into `常用词组按拼音`, synced the updated JSON into Supabase, and verified that both local JSON and live DB now have `0` uncovered polyphonic readings. See `data/2026-03-27-polyphonic-reading-review.md`, `data/CHARACTERS_CHANGELOG.md`, and `data/CHARACTERS_ARCHITECTURE.md` for the full data-layer record.

---

## [v0.2.19]

- **HWXNet 常用词组按拼音 transition:** Add structured `常用词组按拼音` to `extracted_characters_hwxnet.json`, add `common_phrases_by_pinyin` to the live `hwxnet_characters` table, and keep `extracted_hwxnet_common_phrase_character_readings.reviewed.json` in git as the provenance artifact. Polyphonic buckets are derived from the reviewed phrase-reading artifact; monophonic rows are wrapped mechanically from legacy `常用词组`.
- **Conservative consumer migration:** Runtime and utility consumers now prefer the structured HWXNet field while conservatively flattening it back into legacy phrase order when reading-aware handling is not yet needed. This rollout updates Pinyin Recall stem selection plus supporting debug/report scripts without changing the flat-field fallback contract.
- **Test coverage:** Added focused backend regression coverage for HWXNet flattening and stem-word preference/fallback behavior in `backend/tests/test_words_by_pinyin_transition.py`.

---

## [v0.2.18]

- **Feng WordsByPinyin transition:** Add structured `WordsByPinyin` to Feng data in `characters.json` and add `words_by_pinyin` to the `feng_characters` table. Polyphonic buckets are derived from the completed reviewed Feng word-reading artifact; monophonic rows are wrapped mechanically. Current consumers now prefer the structured field internally while preserving the existing flat behavior and legacy `Words` remains temporarily for backward compatibility. Added transition scripts plus focused backend test coverage for normalization, flattening, validation, and data invariants.

---

## [v0.2.17]

- **Pinyin search resilience:** Fix HWXNet pinyin search when `searchable_pinyin` rows are stale or malformed in Supabase. Backend now recomputes normalized keys from the stored `pinyin` column at query time as a safety net, and the `add_searchable_pinyin_column.py` backfill script remains the canonical repair path for the indexed DB data. Added regression coverage for legacy accented-key rows (for example `zhèng`/`dāng` stored instead of `zheng4`/`dang1`).

---

## [v0.2.16]

- **Pinyin Recall (#30):** Make multi‑pinyin handling consistent across correct-answer, wrong-answer, and review screens. Backend `missed_item` now includes `all_pinyin` and `is_polyphonic`, and the frontend reuses a shared display so polyphonic characters (e.g. 占, 中) always show all readings with the primary one highlighted.

---

## [v0.2.15]

- **Pinyin Recall queue: Total Load + 巩固 slot reserve:** Replace Active Load with **Total Load** (count(难字) + count(普通在学字) + 0.3×count(普通已学字)) for mode selection, so users with large 普通已学字 backlogs transition to Consolidation/Rescue earlier. In Expansion and Consolidation modes, reserve 4–6 slots for 巩固 (普通已学字 + 掌握字) before allocating to 在学字, so 巩固 is never crowded out. See [PROPOSAL_Queue_巩固_Slot_Reserve_And_Total_Load](archive/proposals/PROPOSAL_Queue_巩固_Slot_Reserve_And_Total_Load.md).

---

## [v0.2.14]

- **HWXNet 常用词组 + stem words:** Extract 常用词组 (common phrases) from HWXNet into `extracted_characters_hwxnet.json`, add a `common_phrases` jsonb column to the `hwxnet_characters` table, and backfill it from JSON. Pinyin recall stem-word selection now uses HWXNet 常用词组 plus a deprioritized list, so stems better reflect real usage for each character.
- **例词 segmentation + 均读轻声 cleanup (#28, #29):** Update the HWXNet extractor to (a) strip all parentheticals from 例词 text, (b) split by sentence and comma with character-anchored grouping so phrases always contain the character, and (c) remove meta-comments like “均读轻声” from example phrases. Re-extract and merge 基本字义解释 for 417 affected characters into the main HWXNet JSON and backfill `basic_meanings` in Supabase so DB and JSON stay aligned. See `data/CHARACTERS_ARCHITECTURE.md` and `data/CHARACTERS_CHANGELOG.md` for details.

---

## [v0.2.13]

- **Pinyin Recall (#25):** Display a 多音字 (polyphonic character) tag next to the category tag (新字/巩固/重测) in the pinyin recall question header when the character has multiple pronunciations. Backend adds `is_polyphonic` to session items; frontend shows a distinct pill-style tag (purple) for 多音字.

---

## [v0.2.12]

- **Pinyin Recall (#24):** Show 基本解释 (Chinese meaning) on wrong-answer and final-review screens so both English meaning and 基本解释 appear when available, matching the correct-answer screen. Backend now always includes 基本解释 in `missed_item` when present in HWXNet (previously it was only sent when English meanings were missing).

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
