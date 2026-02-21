# Proposal: 汉字掌握度 — show 未学字 / 在学字 / 已学字

**Date:** 2026-02-21  
**Context:** The 我的 (Profile) page currently shows only **已学字** (learned) in the “汉字掌握度” section. This proposal extends it to show all three character categories.

---

## Current behavior

- **API:** `GET /api/profile/progress` returns `proficiency: { learned_count, total_characters, description }`.
- **Source:** `learned_count` = count of rows in `pinyin_recall_character_bank` for the user with `score >= 10`. `total_characters` = 3664 (HWXNet pool).
- **UI:** One progress bar: “已学 273 / 3664 字 (7%)” and a hint that mastery is based on pinyin recall (score ≥ 10 = 已学).

---

## Target behavior

Show three categories in 汉字掌握度:

| Category   | Definition                          | Source |
|-----------|--------------------------------------|--------|
| **未学字** | Not tested yet                      | 3664 − (number of rows in bank for user) |
| **在学字** | Tested, still learning (score &lt; 10) | Count in bank with `score < 10` |
| **已学字** | Tested, learned (score ≥ 10)        | Count in bank with `score >= 10` (current `learned_count`) |

Sum: 未学字 + 在学字 + 已学字 = 3664.

---

## Implementation plan

### 1. Backend — database

**Add** a function that returns all three counts in one query (avoids three round-trips and keeps logic in one place):

- **Function (e.g. in `database.py`):** `get_pinyin_recall_category_counts(user_id: str) -> Dict[str, int]`
  - Query `pinyin_recall_character_bank` for the user:
    - `learned_count`: `COUNT(*) WHERE user_id = %s AND score >= 10`
    - `learning_count`: `COUNT(*) WHERE user_id = %s AND score < 10`
  - `tested_count` = learned_count + learning_count (or one query: `COUNT(*) WHERE user_id = %s`).
  - `not_tested_count` = `PROFILE_HWXNET_TOTAL - tested_count`.
  - Return e.g. `{ "learned": n, "learning": m, "not_tested": k }` with keys aligned to the frontend (or keep names 已学/在学/未学 in a comment only; API can use English keys for consistency with existing `learned_count`).

**Single-query option:**

```sql
SELECT
  COUNT(*) FILTER (WHERE score >= 10) AS learned,
  COUNT(*) FILTER (WHERE score < 10)  AS learning
FROM pinyin_recall_character_bank
WHERE user_id = %s
```

Then `not_tested = PROFILE_HWXNET_TOTAL - learned - learning`.

### 2. Backend — API

**Extend** `GET /api/profile/progress` response:

- Keep `proficiency.learned_count` and `proficiency.total_characters` for backward compatibility.
- Add to `proficiency`:
  - `learning_count` — 在学字 (score &lt; 10)
  - `not_tested_count` — 未学字 (not in bank)
- Optionally add `proficiency.by_category`: `{ "未学字": k, "在学字": m, "已学字": n }` for the frontend to use directly.

Call the new DB function from the profile progress handler and merge the result into the `proficiency` object.

### 3. Frontend — Profile.jsx

**Update** the 汉字掌握度 block:

- **Data:** Read `progress.proficiency.learned_count`, `progress.proficiency.learning_count`, `progress.proficiency.not_tested_count` (and fallback to 0 if absent so old API still works).
- **Layout options (pick one or combine):**
  - **Option A — Three rows:** For each of 未学字 / 在学字 / 已学字, show a label and “X / 3664 字” (and optional small bar or percentage). Compact and clear.
  - **Option B — Stacked bar:** One horizontal bar with three segments (e.g. gray = 未学, amber = 在学, green = 已学), plus a legend or labels below with counts. Visually shows proportion at a glance.
  - **Option C — One bar + list:** Keep the current single bar for 已学 (learned) and add two lines below: “在学字 X 字”, “未学字 Y 字”. Minimal change.

**Recommendation:** Option B (stacked bar) gives a clear visual of the three-way split; add three lines of text under it: “未学字 X / 3664 字”, “在学字 Y / 3664 字”, “已学字 Z / 3664 字” so numbers are explicit.

**Copy:** Keep or shorten the existing hint, e.g. “掌握度根据拼音记忆游戏计算（得分 ≥ 10 为已学字，&lt; 10 为在学字，未测试为未学字）”.

### 4. CSS

- Add classes for the three segments if using a stacked bar (e.g. `.profile-proficiency-segment-not-tested`, `.profile-proficiency-segment-learning`, `.profile-proficiency-segment-learned`).
- Reuse or extend existing `.profile-proficiency-bar` so the stacked bar is one container with three child divs whose widths are percentages of 3664.

### 5. Backward compatibility

- If the API does not return `learning_count` or `not_tested_count`, frontend can treat them as 0 and show only 已学字 (current behavior). So existing clients continue to work after backend deploy; frontend can ship after.

---

## Files to touch

| Layer   | File(s) |
|---------|---------|
| DB      | `chinese_chr_app/backend/database.py` — add `get_pinyin_recall_category_counts` |
| API     | `chinese_chr_app/backend/app.py` — in `get_profile_progress`, call new function and add fields to `proficiency` |
| Frontend| `chinese_chr_app/frontend/src/pages/Profile.jsx` — 汉字掌握度 section layout and copy |
| Styles  | `chinese_chr_app/frontend/src/pages/Profile.css` — stacked bar / three-category styles |

---

## Summary

- **Backend:** One new DB function returning (learned, learning, not_tested); extend `proficiency` in `/api/profile/progress` with `learning_count` and `not_tested_count`.
- **Frontend:** Show 未学字 / 在学字 / 已学字 (e.g. stacked bar + three count lines), with fallbacks when new fields are missing.

No schema changes; reuses existing `pinyin_recall_character_bank` and `PROFILE_HWXNET_TOTAL`.
