---
name: primary-pinyin-update
description: Standardizes the HWXNet primary pinyin update procedure for the Chinese chr app. Use when the user asks to set or change primary pinyin for a character (e.g. "primary pinyin should be tun2", "fix pinyin for 囤"), or to run the primary pinyin update protocol.
---

# Primary pinyin update (Chinese chr app)

When changing which pinyin reading is "primary" for a character (so Pinyin Recall and search treat it as the main answer), follow this protocol in order.

## 1. Update the JSON

- **File:** `chinese_chr_app/data/extracted_characters_hwxnet.json`
- **Change:** Find the character entry (key = single Hanzi). Set `"拼音"` to an array with the **desired primary reading first**, then other readings. Use accented pinyin (e.g. `tún`, `zhàn`).
- Example: for 囤 with primary tún, use `["tún", "dùn"]` (not `["dùn", "tún"]`).

## 2. Update Supabase

- **Table:** `hwxnet_characters`. The row for that character must have `pinyin` and `searchable_pinyin` match the JSON.
- **Script:** Run the reusable script from backend with the character (single Hanzi):  
  `python3 scripts/characters/update_hwxnet_primary_pinyin.py <character>`  
  Example: `python3 scripts/characters/update_hwxnet_primary_pinyin.py 囤`
- The script reads that character’s `"拼音"` from `extracted_characters_hwxnet.json`, recomputes `searchable_pinyin`, and updates the `hwxnet_characters` row. Edit the JSON first (step 1), then run this script.

## 3. Update CHARACTERS_CHANGELOG.md

- **File:** `chinese_chr_app/data/CHARACTERS_CHANGELOG.md`
- **Where:** New entry at the top, directly under the first `---` (reverse chronological order).
- **Format:**
  - Heading: `## YYYY-MM-DD — 字 primary pinyin fix`
  - **What:** For 字, set learner-oriented primary pinyin to X (e.g. tún / tun2). In `extracted_characters_hwxnet.json`, reordered `"拼音"` to `["primary", "other", ...]` and briefly say which reading/sense is first and which remains.
  - **Why:** One line (e.g. user report from 报错, or learner-frequency rationale).
- **Do not** add a **DB:** bullet in the changelog.

## 4. Verify

- **JSON:** In `extracted_characters_hwxnet.json`, confirm the character’s `"拼音"` array has the **intended primary reading first**. If not, fix it and re-run the update script (step 2).
- **Supabase:** Run the verification script from backend:  
  `python3 scripts/characters/verify_hwxnet_pinyin.py <character>`  
  Example: `python3 scripts/characters/verify_hwxnet_pinyin.py 囤`  
  It recomputes expected `pinyin` and `searchable_pinyin` from the JSON and compares to `hwxnet_characters`. Exit 0 means in sync; exit 1 prints mismatches. If it fails, fix the JSON and re-run the update script (step 2), then verify again.
- **Changelog:** Confirm the new entry is at the top of `CHARACTERS_CHANGELOG.md` (directly under the first `---`) and correctly names the character and primary pinyin.

## Reference

- Update script: `chinese_chr_app/chinese_chr_app/backend/scripts/characters/update_hwxnet_primary_pinyin.py`
- Verify script: `chinese_chr_app/chinese_chr_app/backend/scripts/characters/verify_hwxnet_pinyin.py` (optional `--all` to verify every character in the JSON).
- Searchable pinyin logic: `add_searchable_pinyin_column.compute_searchable_pinyin_for_row` (used by the update and verify scripts and the backfill).
