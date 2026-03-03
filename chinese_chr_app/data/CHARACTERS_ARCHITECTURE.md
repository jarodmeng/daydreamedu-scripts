# Character bank architecture

This document describes how the Chinese character app’s character bank is produced and how it relates to HWXNet, the JSON file, and the database. The pipeline evolved over time and is not fully recorded elsewhere; this file is the single place to reason about it.

---

## 1. Source of truth

- **HWXNet** (zd.hwxnet.com) is the external dictionary we scrape for character data.
- **`extracted_characters_hwxnet.json`** (in this folder) is our local mirror of that data. When we run the batch extract script (see below), this file is updated to match what we extract from HWXNet. **Note:** After a one-time restore (2026-03-02), the current file is a *hybrid*: all fields except 常用词组 were restored from a backup that still had the AI-merged 英文翻译 and 拼音; 常用词组 comes from the post–batch-extract file. So for the current state, 英文翻译 and 拼音 do *not* reflect a raw HWXNet re-fetch—they reflect the pre-restore backup. See CHARACTERS_CHANGELOG.md for the restore entry.
- **Supabase table `hwxnet_characters`** is populated *from* the JSON file. It is the runtime source for the app (search, character cards, pinyin recall). The JSON is the source of truth for *content*; the DB is the deployed copy.

---

## 2. Character list (what is in the bank)

The character set is the **union** of:

1. **Feng list** — `characters.json` in this folder (~3000 characters).
2. **Level-1 (字表)** — `level-1.json` in this folder (additional characters; union gives 3664 total).

The batch extract script can load this full set via `--full` (see `extract_character_from_wxnet/batch_extract_hwxnet.py`, `load_characters_full()`). So the “base” character bank is exactly the set we get by uniting these two lists and then fetching each character’s page from HWXNet.

---

## 3. Pipeline overview

Rough order of operations (historical and current):

```
Character lists (characters.json + level-1.json)
    → Batch extract from HWXNet (extract_character_from_wxnet/)
    → extracted_characters_hwxnet.json  (HWXNet mirror)

Optional: AI gloss merge (generate_english_meaning_using_ai/)
    → Updates 英文翻译 and 拼音 order in the same JSON

Load to DB (backend/scripts/characters/create_hwxnet_characters_table.py)
    → hwxnet_characters table (character, pinyin, english_translations, etc.)

Backfill searchable_pinyin (backend/scripts/characters/add_searchable_pinyin_column.py)
    → Must run after pinyin in the DB is final (see §5)
```

Important: **`searchable_pinyin` is derived from the `pinyin` column in the DB.** It is not stored in the JSON. The backfill script reads `pinyin` and writes `searchable_pinyin`. So if `pinyin` is updated later (e.g. after an AI gloss merge that reorders or changes 拼音), `searchable_pinyin` must be recomputed; otherwise search will use stale keys (e.g. [issue #23](https://github.com/jarodmeng/daydreamedu-scripts/issues/23)).

---

## 4. Post–HWXNet changes (AI gloss and pinyin order)

After extraction, we sometimes modify the JSON (and then reload into the DB) using scripts under **`chinese_chr_app/generate_english_meaning_using_ai/`**:

- **`英文翻译` (English translations)**  
  HWXNet’s 英文翻译 can be inaccurate or inconsistent. We use the Batch API to generate better primary (and alternative) English glosses. The merge script (`merge_glosses_into_hwxnet.py`) overwrites `英文翻译` with AI-generated `[primary_sense, ...alternative_senses]`. So **differences in 英文翻译 between a “raw” HWXNet extract and the current JSON are expected** for characters that went through this merge.

- **`拼音` order (primary pinyin first)**  
  For polyphonic characters, the first reading in the list is treated as the “primary” one in the app. We use the same AI pipeline to set a learner-oriented primary pinyin. The merge script reorders `拼音` so that `primary_pinyin` is first (and adds it if missing). So **differences in 拼音 order** (and occasionally in the set of readings, if the AI output differed from HWXNet) between a raw extract and the current JSON are expected for merged characters.

These two steps explain why a **backup** of `extracted_characters_hwxnet.json` from *before* the AI merge can differ from the **current** file in 英文翻译 and 拼音, even though both ultimately came from the same HWXNet base.

---

## 5. searchable_pinyin and issue #23

Pinyin search uses the **`searchable_pinyin`** column in `hwxnet_characters`. That column is **not** part of the JSON; it is backfilled by `add_searchable_pinyin_column.py` from the **`pinyin`** column in the DB.

- **Correct order:**  
  1. Populate or update `hwxnet_characters` from `extracted_characters_hwxnet.json` (so `pinyin` in the DB is final).  
  2. Run `add_searchable_pinyin_column.py` so that `searchable_pinyin` is computed from the current `pinyin`.

- **What went wrong (root cause of [issue #23](https://github.com/jarodmeng/daydreamedu-scripts/issues/23)):**  
  `searchable_pinyin` was backfilled **before** the pinyin list was updated by the AI gloss merge. So for characters like **识** and **褒**, the DB had updated `pinyin` (e.g. 识: primary reading changed; 褒: one reading removed) but **searchable_pinyin** was still computed from the old pinyin. As a result, queries like `shi2` did not match 识 because `shí` was no longer in the stored `pinyin` list and therefore not in `searchable_pinyin`. **Fix:** Re-run `add_searchable_pinyin_column.py` after any update to `pinyin` (e.g. after re-loading the JSON that has been through the AI merge), and do **not** use `--skip-filled` if you need to refresh all rows.

---

## 6. Files and scripts (quick reference)

| What | Where |
|------|--------|
| Character lists | `data/characters.json` (Feng), `data/level-1.json` |
| HWXNet mirror | `data/extracted_characters_hwxnet.json` |
| Batch extract | `extract_character_from_wxnet/batch_extract_hwxnet.py` (uses `--full` for 3664 chars) |
| Single-char extract | `extract_character_from_wxnet/extract_character_hwxnet.py` |
| AI gloss merge | `generate_english_meaning_using_ai/scripts/merge_glosses_into_hwxnet.py` |
| Load JSON → DB | `chinese_chr_app/backend/scripts/characters/create_hwxnet_characters_table.py` |
| Backfill searchable_pinyin | `chinese_chr_app/backend/scripts/characters/add_searchable_pinyin_column.py` |
| DB schema / scripts | `chinese_chr_app/backend/DATABASE.md` |

---

## 7. JSON fields vs DB columns

The JSON keys (e.g. 分类, 拼音, 部首, 总笔画, 基本字义解释, 英文翻译, 常用词组) are mapped to DB columns by `create_hwxnet_characters_table.py`. As of this writing:

- **常用词组** exists in the JSON (from the batch extract) but is **not** yet stored in `hwxnet_characters`. Adding it to the DB and using it for stem words (e.g. in pinyin recall) is tracked in [issue #26](https://github.com/jarodmeng/daydreamedu-scripts/issues/26).

For changelog of what changed and when, see **`CHARACTERS_CHANGELOG.md`** in this folder.

---

## 8. 例词 segmentation and 均读轻声 handling

The **例词** we store come from HWXNet’s `基本字义解释` bullets, not from the separate 常用词组 section. The extractor:

- **Strips all parentheticals** `（…）` / `(...)` from the 例词 text before further processing (this removes meta-comments like `“人”均读轻声`).
- **Splits by sentence (`。`) and comma (`，`)**, but only keeps segments that **contain the target character**. When a sentence has multiple comma-separated clauses, it uses a character-anchored grouping rule so we do not split phrases in ways that drop the character.
  - Example (郭): `城郭, 爷娘闻女来, 出郭相扶将` → `["城郭", "爷娘闻女来，出郭相扶将"]`.
- **Never stores `均读轻声` as a standalone 例词** and removes trailing `，…均读轻声` suffixes as part of the parenthetical stripping and segmentation rules.

For a detailed history of the resegmentation pass that corrected 例词 for 417 characters (and the one-off merge script used), see **`CHARACTERS_CHANGELOG.md`** (entry “2026-03-02 — 例词 resegmentation and 均读轻声 cleanup”).
