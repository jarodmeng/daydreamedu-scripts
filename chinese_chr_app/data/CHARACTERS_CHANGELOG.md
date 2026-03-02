# Character bank changelog

This file records changes to the character bank (character set, source data, and processing steps). When you change how `extracted_characters_hwxnet.json` is produced or how it is loaded into `hwxnet_characters`, add an entry below in reverse chronological order.

**Format:** Start each entry with a short heading and date (YYYY-MM-DD) if known. Include what changed, which files/scripts were involved, and any follow-up required (e.g. re-run backfill, update DB).

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
