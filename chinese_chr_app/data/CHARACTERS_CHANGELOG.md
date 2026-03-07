# Character bank changelog

This file records changes to the character bank (character set, source data, and processing steps). When you change how `extracted_characters_hwxnet.json` is produced or how it is loaded into `hwxnet_characters`, add an entry below in reverse chronological order.

**Format:** Start each entry with a short heading and date (YYYY-MM-DD) if known. Include what changed, which files/scripts were involved, and any follow-up required (e.g. re-run backfill, update DB). Newest entries go directly below this section.

---

## 2026-03-08 — 胆 English translation fix

- **What:** In `extracted_characters_hwxnet.json`, updated 胆’s `"英文翻译"` from "gall" to "gallbladder" for the organ sense (胆囊). Synced to `hwxnet_characters` via one-off script `_update_dan_english_translations.py`.
- **Why:** "Gallbladder" is the precise name for the organ; "gall" alone usually refers to the bile.

---

## 2026-03-08 — 呵 pinyin prune

- **What:** For 呵, pruned to single reading: in `extracted_characters_hwxnet.json`, set `"拼音"` to `["hē"]` only (removed kē, ā, á, ǎ, à, a). List was pruned to the single learner-oriented reading hē (he1).
- **Why:** Prune to only he1; 呵 as exclamation/breath (呵气, 呵责) is the primary reading for learners.

---

## 2026-03-08 — 拙 pinyin prune

- **What:** For 拙, pruned incorrect reading: in `extracted_characters_hwxnet.json`, set `"拼音"` to `["zhuō"]` only (removed zhuó). List was pruned to the single correct reading zhuō (zhuo1).
- **Why:** Remove incorrect reading zhuó; 拙 is only read zhuō in standard usage.

---

## 2026-03-06 — 耙 primary pinyin fix

- **What:** For 耙, set learner-oriented primary pinyin to pá (pa2). In `extracted_characters_hwxnet.json`, reordered `"拼音"` to `["pá", "bà"]` so the “rake / gather” reading (耙子, 钉耙) comes first; the “harrow” reading bà remains as secondary.
- **Why:** Primary pinyin should be pa2 for learners (耙 as rake/gather is more common than the bà “harrow” sense).

---

## 2026-03-06 — 囤 primary pinyin fix

- **What:** For 囤, set learner-oriented primary pinyin to tún (tun2):
  - In `extracted_characters_hwxnet.json`, reordered `"拼音"` to `["tún", "dùn"]` so the “store / hoard” reading (囤积, 囤聚) comes first, while keeping the “granary” reading dùn (粮囤).
- **Why:** User report from Pinyin Recall (报错 on 囤) indicated the app was treating dùn as primary; learners more often encounter 囤 as tún in 囤积, 囤积居奇, etc.

---

## 2026-03-05 — Feng Words 180-character re-extraction

- **What:** Tightened the Feng `Words` (词组) data for 180 characters in `characters.json` so that every sample word/phrase either contains the character or is a full idiom anchored on it (no split halves). Re-extracted those 180 cards from the original PNGs using the improved prompt (`extract_characters_using_ai/chinese_character_extraction_prompt.md`) that enforces:
  - Every `Words` item must contain the `Character` somewhere in the string.
  - Multi-part idioms printed with spaces/commas are kept as a single item (e.g. 冬 → 秋收冬藏, 寒冬腊月; 藏 → 暗藏杀机; 彩 → 缤纷多彩, 张灯结彩; 秀 → 山清水秀; 朗 → 吊儿郎当 as the one allowed association that does not contain 朗).
  - 180-character batch was run via the Responses Batch API, with a direct follow-up call for 蒸 (1324) after one batch request failed with a server error. The merged results live in `/tmp/improved_180_results.json`.
- **Data:** Updated `data/characters.json` by overwriting **only** the `Words` field for these 180 indices, except for two indices whose batch outputs had wrong-character contamination in an earlier run:
  - 0656 非
  - 2328 谴  
  For those two, `Words` remain the hand-curated originals from git.
- **DB:** Ran a one-off Supabase update so `feng_characters.words` stays in sync with `characters.json` for this set: for the same 180 indices (skipping 0656/2328), `words` in `feng_characters` was updated from `/tmp/improved_180_results.json` while leaving all other columns untouched. Before the update, the full table was backed up to JSON via a temporary helper script. That helper and its local backups were intentionally removed afterwards; this entry is the long-term record of the change.
- **Why:** Pinyin Recall and the character search view were surfacing fragmented or misleading words (e.g. 光明 without 大, 冰清 / 玉洁 without 洁, halves of idioms like 来日 / 方长). This pass re-aligns Feng sample words with the source cards and the invariant that words shown in the app are complete phrases that (almost always) contain the teaching character.

---

## 2026-03-04 — 占 primary pinyin fix

- **What:** For 占, set learner-oriented primary pinyin:
  - In `extracted_characters_hwxnet.json`, reordered `"拼音"` to `["zhàn", "zhān"]` so the high-frequency “occupy / take up” reading comes first, while still keeping the `zhān` (“divine; tell fortunes”) sense.
- **DB:** Added a one-off script `chinese_chr_app/backend/scripts/characters/_update_hwxnet_character_zhan_primary.py` that reads the 占 entry from `extracted_characters_hwxnet.json`, recomputes `searchable_pinyin` using a normalization compatible with `add_searchable_pinyin_column.py`, and updates the `hwxnet_characters` row (`pinyin`, `searchable_pinyin`) so Supabase stays in sync with the JSON.
- **Why:** User reports and in-app usage (e.g. example phrases like 占据, 霸占, 占优势) show that learners primarily encounter 占 as `zhàn` (“occupy / take”), not `zhān` (“divine”). Flipping the primary pinyin ensures pinyin recall treats zhàn as the main answer while still surfacing zhān as an additional reading.

---

## 2026-03-03 — 洁/姜 Feng words fix

- **What:** Corrected Feng `Words` lists for 洁 and 姜 so that all example phrases either contain the character or are full idioms as printed on the original cards:
  - 洁: `清洁, 整洁, 纯洁, 洁具, 洁癖, 廉洁, 洁白, 洁净, 冰清玉洁, 洁身自好` (previously had split `冰清`, `玉洁`, `洁身`, `自好`).
  - 姜: `姜汤, 生姜, 姜太公钓鱼，愿者上钩` (previously split the idiom into `姜太公钓鱼` and `愿者上钩`).
- **DB:** Added a one-off script `chinese_chr_app/backend/scripts/characters/_update_feng_words_jie_jiang.py` that reads the canonical `Words` from `data/characters.json` and updates the `feng_characters.words` column for 洁 and 姜 so Supabase stays in sync with the JSON.
- **Why:** Emma’s error reports exposed that some Pinyin Recall “常见词组” did not actually contain the target character (e.g. 冰清, 自好, 愿者上钩). This change realigns the app’s words with the Feng source cards and the intent that each example either includes the character or is a complete idiom anchored on it.

---

## 2026-03-03 — 挣 primary pinyin fix

- **What:** For 挣, set learner-oriented primary pinyin:
  - In `extracted_characters_hwxnet.json`, reordered `"拼音"` to `["zhēng", "zhèng"]` so the `挣扎` / `挣脱` reading comes first, while still keeping the `挣钱` (zhèng) sense.
- **DB:** Added a one-off script `chinese_chr_app/backend/scripts/characters/_update_hwxnet_character_zheng_primary.py` that reads the 挣 entry from `extracted_characters_hwxnet.json`, computes `searchable_pinyin` using the same normalization as `add_searchable_pinyin_column.py`, and updates the `hwxnet_characters` row (`pinyin`, `english_translations`, `searchable_pinyin`) so Supabase stays in sync with the JSON.
- **Why:** The AI gloss merge had set `primary_pinyin` to zhèng (“earn”), which made the app present zhèng as the only “correct” reading, even though both 挣扎 (zhēng) and 挣钱 (zhèng) are frequent in the teaching list. This change aligns primary pinyin with the Feng list and learner expectations.

---

## 2026-03-03 — 铛 primary pinyin and gloss fix

- **What:** For 铛, set learner-oriented primary pinyin and clarify the English gloss:
  - In `extracted_characters_hwxnet.json`, reordered `"拼音"` to `["dāng", "chēng"]` so the common 铃铛 / 铛铛 reading comes first.
  - Updated `"英文翻译"` to emphasize both the metal clanging / shackle sense and the utensil sense: `["metal clanging sound; shackle", "frying pan; warmed vessel; cooking utensil"]`.
- **DB:** Added a one-off script `chinese_chr_app/backend/scripts/characters/_update_hwxnet_character_dang_cheng.py` that reads the 铛 entry from `extracted_characters_hwxnet.json`, computes `searchable_pinyin` using the same normalization as `add_searchable_pinyin_column.py`, and updates the `hwxnet_characters` row (`pinyin`, `english_translations`, `searchable_pinyin`) so Supabase stays in sync with the JSON.
- **Why:** User-facing reports (e.g. from Emma) showed that the app treated the utensil reading `chēng` as primary, even though learners most often encounter 铛 as `dāng` in words like 铃铛 / 铛铛. This change keeps the utensil meaning but makes the high-frequency `dāng` reading primary for teaching and search.

---

## 2026-03-03 — 窄 polyphonic flag fix (#27)

- **What:** For 窄, removed the spurious secondary reading `zé` so the character is treated as monophonic:
  - In `extracted_characters_hwxnet.json`, updated `"拼音"` to `["zhǎi"]` to match the AI gloss primary pinyin and typical learner expectations.
- **DB:** Added a one-off script `chinese_chr_app/backend/scripts/characters/_update_hwxnet_character_zai_primary.py` that reads the 窄 entry from `extracted_characters_hwxnet.json`, recomputes `searchable_pinyin` using the same normalization as `add_searchable_pinyin_column.py`, and updates the `hwxnet_characters` row (`pinyin`, `searchable_pinyin`) so Supabase stays in sync with the JSON.
- **Why:** Issue [#27](https://github.com/jarodmeng/daydreamedu-scripts/issues/27) reported that 窄 was incorrectly marked as polyphonic in the app UI, despite the AI gloss data and real-world usage treating it as `zhǎi` only. Removing `zé` keeps the data consistent and avoids confusing learners.

---

## 2026-03-02 — 例词 resegmentation and 均读轻声 cleanup (#28, #29)

- **What:** Updated the HWXNet extractor's 例词 logic so that:
  - Example phrases are segmented using sentence + comma + **character-anchored grouping** (only segments containing the character are kept; e.g. 郭: `城郭, 爷娘闻女来, 出郭相扶将` → `["城郭", "爷娘闻女来，出郭相扶将"]`).
  - All parenthetical comments `（…）` / `(...)` are stripped from the 例词 text before segmentation.
  - Meta-comments like `均读轻声` are removed (no standalone `"均读轻声"` 例词, no trailing `，…均读轻声` suffixes in phrases).
- **Data:** Re-ran extraction for **417 affected characters** and wrote their updated `基本字义解释` (with cleaned 例词) to `extracted_characters_hwxnet.resegmented_affected.json`, then merged **only** `基本字义解释` for those characters back into `extracted_characters_hwxnet.json` via `extract_character_from_wxnet/merge_resegmented_into_main_hwxnet.py`.
- **Backup:** Before merging, backed up `extracted_characters_hwxnet.json` to `data/backups/` (timestamped). The resegmented subset file was then moved to `data/backups/extracted_characters_hwxnet.resegmented_affected.json` and is no longer tracked by git (kept only as a reproducibility artifact).
- **Result:** For the 417 characters, `基本字义解释` now has correctly segmented 例词 which always contain the character and no leaked `均读轻声` comments. Other fields and characters in the main JSON are unchanged.

---

## 2026-03-02 — Restore AI-merged fields, keep 常用词组

- **What:** The full batch re-run (2026-03-01) had overwritten **英文翻译** and **拼音** (and 分类, etc.) with raw HWXNet data, undoing the earlier AI gloss merge. We restored all fields **except 常用词组** from `backups/extracted_characters_hwxnet.20260301-184220.json` into `extracted_characters_hwxnet.json`, keeping **常用词组** from the current file (the new extraction).
- **Backup:** Current file was backed up to `backups/extracted_characters_hwxnet.20260302-024930.json` before the restore.
- **Result:** The JSON now has AI-merged 英文翻译 and 拼音 again, plus 常用词组 from the 2026-03-01 batch. See CHARACTERS_ARCHITECTURE.md §1 for the “hybrid” state.

---

## 2026-03-01 — 常用词组 added to extraction

- **What:** Batch extractor was updated to scrape the **常用词组** (common phrases) section from HWXNet in addition to existing fields. Full batch re-run with `--full` (union of Feng + level-1, 3664 characters) so that `extracted_characters_hwxnet.json` now includes a `常用词组` array per character (empty when the section is absent on HWXNet).
- **Scripts:** `extract_character_from_wxnet/extract_character_hwxnet.py` (`extract_common_phrases`), `batch_extract_hwxnet.py`.
- **Note:** 常用词组 is not yet in the `hwxnet_characters` table or used by the app; see [issue #26](https://github.com/jarodmeng/daydreamedu-scripts/issues/26).

---

## AI gloss and primary pinyin merge (before 2026-03)

- **What:** Scripts under `generate_english_meaning_using_ai/` were used to improve English glosses and to set a learner-oriented primary pinyin for polyphonic characters. `merge_glosses_into_hwxnet.py` was run to update `extracted_characters_hwxnet.json`: **英文翻译** was replaced with AI-generated primary + alternative senses; **拼音** was reordered (and occasionally the set of readings changed) so the primary reading is first.
- **Why:** HWXNet’s 英文翻译 was often inaccurate or inconsistent; the first pinyin in the list was not always the most commonly used reading.
- **Effect:** The current JSON therefore differs from a “raw” HWXNet-only extract in 英文翻译 and 拼音 (order and sometimes content) for characters that were in the merge. See CHARACTERS_ARCHITECTURE.md §4.

---

## searchable_pinyin backfill (before AI merge — caused issue #23)

- **What:** The `searchable_pinyin` column was added to `hwxnet_characters` and backfilled from the `pinyin` column via `add_searchable_pinyin_column.py`.
- **Problem:** This backfill was run **before** the pinyin list was updated by the AI gloss merge. So for characters whose 拼音 was later changed (e.g. **识** lost `shí`, **褒** lost `bǎo`), `searchable_pinyin` in the DB was never recomputed and still reflected the old pinyin. Result: pinyin search (e.g. `shi2` for 识) could miss characters ([issue #23](https://github.com/jarodmeng/daydreamedu-scripts/issues/23)).
- **Fix:** Re-run `add_searchable_pinyin_column.py` **after** loading the final JSON (with AI-merged pinyin) into the DB, and do not use `--skip-filled` when refreshing all rows. See CHARACTERS_ARCHITECTURE.md §5.

---

## Initial character bank (Feng + level-1)

- **What:** Character set defined as the union of `characters.json` (Feng list, ~3000) and `level-1.json` (字表 level-1). Batch extraction from HWXNet produced `extracted_characters_hwxnet.json` with 3664 characters. Table `hwxnet_characters` created and populated from this JSON.
- **Scripts:** `extract_character_from_wxnet/batch_extract_hwxnet.py`, `chinese_chr_app/backend/scripts/characters/create_hwxnet_characters_table.py`.
