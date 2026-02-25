# Proposal: Symmetric Scoring (+10 / −10) for Pinyin Recall

**Status:** Implemented (2026-02-21)

---

## 1. Current Scheme

| Answer | Delta | Notes |
|--------|-------|-------|
| Correct | +10 | Cap 100 |
| Wrong / 我不知道 | −15 | Floor 0 |

Asymmetric: one wrong cancels 1.5 corrects.

---

## 2. Proposed Scheme

| Answer | Delta | Notes |
|--------|-------|-------|
| Correct | +10 | Cap 100 |
| Wrong / 我不知道 | −10 | Floor 0 |

Symmetric: one wrong cancels one correct.

---

## 3. Rationale

| Concern | Current (+10/−15) | Proposed (+10/−10) |
|---------|-------------------|---------------------|
| **Interpretability** | Harder to explain; users must track two deltas | Simple: “each answer moves score by ±10” |
| **Marginal benefit of asymmetry** | Slightly stricter, adds complexity | Clear mental model with little downside |
| **Proficiency threshold (≥10)** | 10−15 → 0; one wrong from 10 drops learned | 10−10 → 0; same critical behavior |

---

## 4. Behavioral Impact

- **Score at 10:** 10−10=0 vs 10−15=0 → unchanged for the threshold.
- **Score at 20:** 20−10=10 vs 20−15=5 → with −10, one wrong keeps score 10 (still learned); with −15, drops to 5 (not learned).

Overall: slightly more forgiving near the “learned” threshold.

---

## 5. Implementation Scope (Code)

1. **`database.py`** — Change `PINYIN_RECALL_SCORE_WRONG_DELTA` from `15` to `10`.
2. **`pinyin_recall.py`** — Update in-memory scoring if used standalone.
3. **Documentation** — Update `backend/DATABASE.md` and `docs/plans/MVP1_Pinyin_Micro_Session_Plan.md` to describe +10/−10.

---

## 6. Backfill Plan

### 6.1 Overview

Recompute existing scores using the new +10/−10 scheme and persist them, so historical data matches the new scoring semantics.

**Source of truth:** `pinyin_recall_item_answered` — each row has `user_id`, `character`, `correct`, `i_dont_know`, `created_at`. Score depends on answer *order*, so replay from the log is required.

### 6.2 What to Backfill

1. **`pinyin_recall_character_bank.score`** — Per (user_id, character), overwrite with score recomputed from the log.
2. **`pinyin_recall_item_answered.score_before`** and **`score_after`** — Per row, overwrite with the values that would have been stored under the new scheme.

### 6.3 Algorithm

**Replay logic:**

```
For each (user_id, character):
  score = 0
  answers = rows from item_answered ordered by (created_at, id)
  for each row in answers:
    score_before = score
    if correct:
      score = min(score + 10, 100)
    else:
      score = max(score - 10, 0)
    score_after = score
    record (row.id, score_before, score_after) for update
```

**Updates:**

1. `UPDATE pinyin_recall_character_bank SET score = ? WHERE user_id = ? AND character = ?` — final score per (user_id, character).
2. `UPDATE pinyin_recall_item_answered SET score_before = ?, score_after = ? WHERE id = ?` — one update per row.

### 6.4 Coverage

| Scenario | Action |
|----------|--------|
| Bank row has log history | Replay and update bank + all item_answered rows for that (user_id, character). |
| Bank row has no log rows | Cannot recompute; leave bank score unchanged. |
| Log has (user_id, character) not in bank | Optional: replay and upsert bank row (score only; other fields would need default/derived values). |

### 6.5 Script Design

- **Input:** `pinyin_recall_item_answered`
- **Output:** Updates to `pinyin_recall_character_bank` and `pinyin_recall_item_answered`
- **Pattern:** Similar to `backfill_pinyin_recall_category.py` and `backfill_pinyin_recall_batch_id.py`
- **Backup:** Before overwriting, the script must create backup copies of both tables (e.g. `pinyin_recall_character_bank_backup_YYYYMMDD_HHMMSS` and `pinyin_recall_item_answered_backup_YYYYMMDD_HHMMSS`). No updates to live tables until backups exist. Support `--no-backup` to skip (use with caution).
- **Safety:** Support `--dry-run` to report old vs new scores without writing.
- **Determinism:** `ORDER BY user_id, character, created_at, id` to handle ties in `created_at`.

### 6.6 Execution Order

1. Change `PINYIN_RECALL_SCORE_WRONG_DELTA` in code.
2. Run the backfill script (bank + item_answered).
3. Verify: spot-check scores and compare old vs new in dry-run output.

---

## 7. Risk / Trade-off

The new scheme is more forgiving near the learned threshold. If that proves too lenient, future options include smaller deltas (e.g. +8/−10) rather than reverting to −15.
