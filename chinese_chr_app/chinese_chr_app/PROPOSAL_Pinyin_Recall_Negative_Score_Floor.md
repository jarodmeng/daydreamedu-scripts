# Proposal: Pinyin Recall Score Floor at −50

**Status:** Implemented (2026-02-21)

---

## 1. Current Scheme

| Bound | Value | Notes |
|-------|-------|-------|
| Cap | 100 | Correct +10, capped |
| Floor | 0 | Wrong −10, floored; repeated wrongs at 0 have no effect |

**Problem:** Repeated wrongs at the floor carry no signal. A character with 5 consecutive wrongs (from 0) is indistinguishable from one never practiced.

---

## 2. Proposed Scheme

| Bound | Value | Notes |
|-------|-------|-------|
| Cap | 100 | Unchanged |
| Floor | −50 | Wrong −10, floored at −50; up to 5 extra wrongs at 0 are recorded |

**Rationale:** Preserve repeated-failure information for queue prioritization and analytics. Characters with more recent wrongs sort lower (higher priority in 重测) and can be used for backoff or adaptive scheduling later.

---

## 3. Behavioral Impact

| Scenario | Current (floor 0) | Proposed (floor −50) |
|----------|-------------------|------------------------|
| 0 → wrong | 0 (no change) | −10 |
| −10 → wrong | 0 (floored) | −20 |
| −40 → wrong | 0 (floored) | −50 (capped) |
| −50 → wrong | N/A | −50 (no further drop) |
| Queue ordering | 0 = lowest priority | −50 < −40 < … < 0 < 10 |

**Proficiency threshold:** Still `score ≥ 10`. All negative scores remain "not learned."

---

## 4. Implementation Scope

### 4.1 Code Changes

| File | Change |
|------|--------|
| `database.py` | Set `PINYIN_RECALL_SCORE_MIN = -50` (from 0) |
| `database.py` | Update comments: "floor 0" → "floor −50" |

**No changes needed:**
- `pinyin_recall.py` — uses score from DB for queue ordering; `score >= 10` still correct for proficiency
- Queue logic — `revise_items.sort(key=score)` naturally orders negatives before 0
- `PROFILE_PROFICIENCY_MIN_SCORE` — remains 10; negatives are correctly "not learned"

### 4.2 Backfill Script

Update `backfill_pinyin_recall_score.py`:
- Set `SCORE_MIN = -50`.
- **Run backfill** to recompute all scores with the new floor.

**Why backfill:** Replay from `pinyin_recall_item_answered` will correctly apply the −50 floor. Characters that hit 0 and then had additional wrongs (currently stored as 0 due to floor) will get negative scores. Example: C,C,W,W,W,W → old replay: 0→10→20→10→0→0→0; new replay: 0→10→20→10→0→−10→−20.

**Procedure:** Same as symmetric scoring backfill — replay per (user_id, character), update bank and item_answered. Create backup tables first. Support `--dry-run`.

### 4.3 Schema

- `pinyin_recall_character_bank.score` — `integer` supports negatives; no migration.
- `pinyin_recall_item_answered.score_before`, `score_after` — same.

### 4.4 Documentation

- `DATABASE.md` — "Score: correct +10 (cap 100), wrong/我不知道 −10 (floor 0)" → "floor −50"
- `MVP1_Pinyin_Micro_Session_Plan.md` — update score range description if present

---

## 5. UI Considerations

- **Profile / 已学 count:** Uses `score >= 10`; no change.
- **Frontend:** Does not display raw score to users. No UI change.
- **Logs / analytics:** `score_before`, `score_after` may be negative; ensure any dashboards or exports handle negatives.

---

## 6. Backfill Plan

### 6.1 Overview

Replay `pinyin_recall_item_answered` per (user_id, character) in chronological order, recompute score with floor −50. Update `pinyin_recall_character_bank.score` and `item_answered.score_before` / `score_after`.

### 6.2 Algorithm

Same as existing `backfill_pinyin_recall_score.py`, with `SCORE_MIN = -50`:

```
For each (user_id, character):
  score = 0
  for each answer in order:
    score_before = score
    if correct: score = min(score + 10, 100)
    else:       score = max(score - 10, -50)
    score_after = score
    record updates
```

### 6.3 Backup

Create backup tables before modifying: `pinyin_recall_character_bank_backup_*`, `pinyin_recall_item_answered_backup_*`. Support `--dry-run`, `--no-backup`.

### 6.4 Expected Impact

Characters currently at 0 that had wrongs after hitting 0 will move to negative scores. All others unchanged.

---

## 7. Execution Order

1. Change `PINYIN_RECALL_SCORE_MIN` in `database.py`.
2. Update `backfill_pinyin_recall_score.py` with `SCORE_MIN = -50`.
3. Run backfill script (with backup, or `--dry-run` first).
4. Update documentation.
5. Deploy.

---

## 8. Future Options

- **Backoff:** Use negative score (e.g. &lt; −20) to temporarily reduce show rate.
- **Analytics:** Segment characters by score bands including negative ranges.
- **Adjust floor:** If −50 proves too shallow or deep, change the constant and redeploy.
