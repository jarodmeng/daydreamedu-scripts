# Proposal: Queue construction by five score-based categories

**Status:** Implemented (2026-02; commit 21372eb — queue by five score-based categories, batch logging; batch_mode/batch_character_category in pinyin_recall_item_presented)  
**Date:** 2026-02-21  
**Context:** The character bank can be partitioned into five categories by **master score**. This proposal rethinks how we build a batch of 20 characters so the queue aligns with learning goals and research principles.

**References:**  
- `docs/research/Learning_Functions_Research_and_Brainstorming.md` — retrieval practice, spacing, interleaving, diagnose→select→practice→feedback→schedule  
- `README.md` — app goals, data model (3664 HWXNet pool)  
- `docs/plans/MVP1_Pinyin_Micro_Session_Plan.md` — current queue: due first (stratified 巩固/重测), then new  
- `docs/research/Chinese_Character_Learning_Algorithm_Design.md` — adaptive valve by Active Load, Rescue/Consolidation/Expansion, cooling periods, confidence-first ordering

---

## 1. Five categories (MECE by score)

| # | Category       | Definition              | Score range   | Learning intent |
|---|----------------|-------------------------|---------------|------------------|
| 1 | **未学字**     | Not tested yet          | (no row)      | First encounter; limit exposure per batch. |
| 2 | **难字**       | Difficult               | score ≤ -20   | Repeated failures; need frequent re-encounters and corrective feedback. |
| 3 | **普通在学字** | Normal, still learning  | -20 < score ≤ 0 | On the way; practice until they climb. |
| 4 | **普通已学字** | Normal, learned         | 0 < score < 20 | Learned but not yet “mastered”; spaced maintenance. |
| 5 | **掌握字**     | Mastered                | score ≥ 20    | Strong retention; spaced maintenance so they are not forgotten. |

- **Total pool:** 3664 characters (HWXNet). Every character is in exactly one category per user.
- **Score semantics:** Correct +10 (cap 100), wrong/我不知道 −10 (floor −50). Thresholds −20 and 20 are configurable (e.g. `PROFILE_LEARNING_HARD_MAX_SCORE`, `PROFILE_LEARNED_MASTERED_MIN_SCORE`).

---

## 2. Principles from research (to keep in mind)

From *Learning Functions Research & Brainstorming* and MVP1:

1. **Retrieval as default** — Quizzing drives learning; the queue is a retrieval queue, not a “read more” list.
2. **Guided retrieval** — Avoid overload: don’t flood the batch with only 未学字 or only 难字; mix so the session is doable and discriminative.
3. **Spacing** — Use `next_due_utc` (and stage) so items are re-encountered over time; the queue should respect “due” vs “not due” within tested characters. **Cooling intervals** by band: 难字 0 days (immediate), 普通在学字 1 day, 普通已学字 3–7 days, 掌握字 14–30 days. Eligibility: character is due when `T_now - T_last_seen ≥ T_cool` for its band. This follows the **Ebbinghaus Forgetting Curve** idea: each successful review allows a longer cooling period before the next, so we show a character when memory is about to decay.
4. **Avoid learning-debt spiral** — When 在学字 (Active Load) is large, reduce 新字 per batch so the app “cleans house” before adding more; otherwise 在学字 grows faster than it drains and the learner feels overwhelmed.
5. **Relative share:** **在学字 > 新字 > 已学字** — When allocating the 20 slots, 在学字 should get the *largest* share, 新字 the next largest, 已学字 the next. So we aim for a **mix**: no category dominates the whole queue; all three are represented. 在学字 get more attention than 新字/已学字 so the 在学字 pool can drain, but 新字 and 已学字 still get meaningful slots every batch.
6. **Prioritize need** — Within 在学字, weakest first (难字 then 普通在学字 by score ascending). 已学字 ordered by spacing (most overdue first).
7. **难字 through repetition** — Do not cap 难字. Within the 在学字 slots, fill **难字 first** (score ascending), then 普通在学字. The goal is to turn 难字 into 普通在学字 through repeated exposure and corrective feedback.
8. **Interleave for discrimination** — A mix of categories in one batch can help (e.g. not 20 难字 in a row); ordering can interleave bands.
9. **Short sessions, low friction** — Batch size 20 is fixed; we only decide *which* 20 and in what order.
10. **Instrument everything** — Log category per item (answer-time) so we can measure by band and iterate.

---

## 3. Current queue logic (brief)

- **Due vs new:** Characters with a bank row and `next_due_utc <= now` (or null) are “due”; others in pool but not in bank are “new” (未学字).
- **Stratified due:** Among due, split into 重测 (score < 10) and 巩固 (score ≥ 10, all-correct so far). Reserve up to `due_confirm_min` (4) for 巩固, rest for 重测. 重测 ordered by score ascending (weakest first), 巩固 by most overdue.
- **New:** After filling up to `due_first` (8) with due items, fill remaining slots up to `new_count` (8) from 未学字, then up to `total_target` (20).
- **Result:** At most 8 新字 per batch; the rest are due 重测 + 巩固.

---

## 4. Proposed queue construction (20 per batch)

### 4.1 Relative share: 在学字 > 新字 > 已学字 (mix, not dominance)

When drawing the queue, **在学字 > 新字 > 已学字** means 在学字 get the *largest* share of the 20, 新字 the next largest, 已学字 the next — but **all three are in the mix**. 在学字 do not simply trump the others and fill the whole batch; we want a balanced session where 在学字 get more slots than the rest so that pool can shrink over time, while 新字 and 已学字 (maintenance) still get meaningful slots every time.

**One way to implement:** allocate the 20 slots by **target shares** (tunable), e.g.:

- **在学字 (due):** target ~8–10 slots (largest share). If fewer due 在学字 exist, use what we have and give the spare to 已学字 or 新字.
- **新字:** target ~5–8 slots (next largest).
- **已学字 (due):** target ~4–6 slots (maintenance). Fill remainder to 20.

So typical batch: ~8 在学字, ~6 新字, ~6 已学字 (example). When 在学字 due count is low, 已学字 and 新字 take more; when 在学字 is large, we still limit 在学字 to the target (e.g. 10) so 新字 and 已学字 are present. Exact targets can be constants or derived from due counts with weights (在学字 weight &gt; 新字 &gt; 已学字).

### 4.1b Batch mode by Active Load (adaptive valve)

**Active Load** = count(难字) + count(普通在学字) — the number of characters “in progress” (在学字). When Active Load is high, we reduce 新字 per batch so the app “cleans house” before adding more; this prevents the **learning-debt spiral** (在学字 growing faster than it drains) and protects motivation.

| Mode | Active Load | N_新字 (target) | N_在学字 + N_已学字 | Goal |
|------|-------------|------------------|----------------------|------|
| **Expansion** | &lt; 100 | 10 (50%) | 10 (50%) | Discovery; fast progress. |
| **Consolidation** | 100–250 | 5 (25%) | 15 (75%) | Stabilizing; shift to cleaning up. |
| **Rescue** | &gt; 250 | 0–2 (≈10%) | 18+ (≈90%) | Mastery; drain backlog, boost confidence. |

**Detailed Rescue batch recipe (20 characters)** — from “Detailed Batch Recipe” in the conversation. When in Rescue mode, build the batch as follows:

| Count | Source | Role | Why |
|-------|--------|------|-----|
| **4** | 掌握字 | **Confidence Foundation** | Start the session with easy wins; lowers cognitive load and builds momentum. |
| **8** | 普通已学字 | **Mastery Push** | Characters at score 1–19; testing them now pushes them toward 掌握字 (≥20). This is where the “progress bar” moves. |
| **6** | 在学字 (难字 + 普通在学字) | **Debt Collector / 难字 repetition** | Fill from 在学字 with **难字 first** (score ascending), then 普通在学字. Aim to turn 难字 into 普通在学字 through repetition; no cap on 难字. Also attacks the 普通在学字 backlog and prevents forgetting. |
| **2** | 新字 | **Slow Drip** | Only 2 new per batch; satisfies “something new” without adding much mental load. |

**Total:** 4 + 8 + 6 + 2 = 20. The 6 在学字 slots are filled by due 难字 first (weakest first), then due 普通在学字 — so 难字 get the repetition they need to climb out of the 难字 band.

**Expansion / Consolidation:** For Expansion use 10 新字 + 10 review (split between 在学字 and 已学字); for Consolidation 5 新字 + 15 review. Within 在学字 slots, 难字 are prioritized first (score asc) in all modes. Before allocating slots, compute Active Load and choose the mode; use that mode’s recipe for the current batch.

### 4.2 Build steps (high level)

1. **Active Load and mode** — Count 在学字 (难字 + 普通在学字) total → Active Load. Choose mode: Expansion (&lt; 100), Consolidation (100–250), Rescue (&gt; 250).
2. **Due counts** — From pool, count *due* (bank row + `next_due_utc <= now`) per band: 在学字 (难字 + 普通在学字), 已学字 (普通已学字 + 掌握字). 未学字 = candidates for 新字.
3. **Allocate slots** — Using the **mode’s** recipe (see §4.1b). **Rescue:** N_掌握字 = 4, N_普通已学字 = 8, N_在学字 = 6 (filled by 难字 first, then 普通在学字), N_新字 = 2. **Expansion:** 10 新字, 10 review (split 在学字 / 已学字). **Consolidation:** 5 新字, 15 review. If a band has fewer candidates than allocated, use actual count and assign spare slots to the others.
4. **Fill** — Draw from each band per allocation. **Within 在学字 slots (all modes):** 难字 first (score asc), then 普通在学字 (score asc) — no cap on 难字; repetition is how 难字 move toward 普通在学字. 已学字: next_due_utc asc. 新字: random. Combine into queue (see §4.4).

### 4.3 Ordering within each band

- **难字 / 普通在学字:** By score ascending (most negative first).
- **普通已学字 / 掌握字:** By `next_due_utc` ascending (most overdue first).
- **未学字:** Random (or zibiao-order then shuffle).

### 4.4 Order within batch and output

**Rescue order (confidence-first):** Per the Detailed Batch Recipe, put **Confidence Foundation first** — the 4 掌握字 at the start of the session so the user gets easy wins and builds momentum. Then Mastery Push (8 普通已学字), then Debt Collector (6 在学字: 难字 first, then 普通在学字), then Slow Drip (2 新字). So the batch order is: 掌握字 → 普通已学字 → 在学字 (难字 then 普通在学字) → 新字.

**Expansion / Consolidation:** Concatenate in band order (e.g. 已学字 → 在学字 → 新字, or 在学字 → 新字 → 已学字) or interleave. Output list of ≤20 items with `category` for logging (新字/重测/巩固 as in §5). Candidate pool and classification as today: HWXNet [zibiao_min, zibiao_max_effective], pool expansion by mastered count; due = bank row + `next_due_utc <= now`.

**Future refinements (optional):** (a) **Same-session reappearance:** if user answers a 难字 wrong, re-queue it later in the same batch (e.g. 10 items later). (b) **Retire at floor:** when score = −50, make character ineligible for 48 hours to avoid negative association.

---

## 5. Mapping to current display categories (新字 / 重测 / 巩固)

For **logging and UI**, we can keep the three answer-time labels:

- **新字** — Item is 未学字 (first time).
- **重测** — Item is 难字 or 普通在学字 (score ≤ 0; “retest” = needs practice).
- **巩固** — Item is 普通已学字 or 掌握字 (score > 0; maintenance).

So the **five categories** drive **queue selection and slot allocation**; the **three labels** stay for analytics and in-session display unless we later add finer labels (e.g. 难字 vs 普通 in UI).

---

## 6. Implementation outline

- **Backend (pinyin_recall.py):**
  - Replace or extend the “due → 重测/巩固 split” with a **five-band split** (难字, 普通在学字, 普通已学字, 掌握字) among due items; 未学字 = new.
  - **Adaptive valve:** Compute Active Load; choose mode. **Rescue:** use Detailed Recipe (4 掌握字, 8 普通已学字, 6 在学字 [难字 first, then 普通在学字], 2 新字). **Expansion/Consolidation:** 10 or 5 新字 + review. Within 在学字 slots in all modes: 难字 first (score asc), then 普通在学字 — no cap; goal is to turn 难字 into 普通在学字 through repetition.
  - **Relative share** within mode: 在学字 &gt; 新字 &gt; 已学字; fill each band up to its allocation. Optional: confidence-first ordering (start with a few 掌握字).
  - Keep `_category_for_character` for **display** (新字/重测/巩固); add an internal band for **selection** if useful.
  - **Spacing:** Set `next_due_utc` using cooling intervals (难字 0, 普通在学字 1 day, 普通已学字 3–7 days, 掌握字 14–30 days) so “due” reflects eligibility.
- **Database:** No schema change. Score and next_due_utc already exist. Optionally add a view or helper that returns counts per band for analytics.
- **API:** Same response shape; items still have `category` (新字|重测|巩固). Optionally add `score_band` (难字|普通在学字|普通已学字|掌握字) in the item payload for future UI.
- **Config:** Document the five categories, relative-share principle, **Active Load modes** (Expansion / Consolidation / Rescue) and thresholds (100, 250), cooling intervals, and target recipes (难字 prioritized within 在学字, no cap) in MVP1 plan and DATABASE.md.

---

## 7. Summary

- **Five categories by score** (未学字, 难字, 普通在学字, 普通已学字, 掌握字) give a clear, MECE partition of the 3664 pool.
- **Queue of 20:** **Adaptive by Active Load** — compute 在学字 count; choose Expansion, Consolidation, or Rescue. **Rescue (Detailed Recipe):** 4 掌握字 (Confidence Foundation) + 8 普通已学字 (Mastery Push) + 6 在学字 (Debt Collector: **难字 first**, then 普通在学字) + 2 新字 (Slow Drip) = 20. **No cap on 难字** — the 6 在学字 slots are filled with 难字 first (score asc), then 普通在学字, so repetition turns 难字 into 普通在学字. **Order:** 掌握字 first, then 普通已学字, 在学字 (难字 then 普通在学字), 新字. Expansion/Consolidation: 10 or 5 新字 + review; within 在学字 slots, 难字 first in all modes.
- **Spacing:** Cooling intervals (难字 0, 普通在学字 1 day, 普通已学字 3–7 days, 掌握字 14–30 days) drive when characters are “due”; implement via `next_due_utc`.
- **Principles preserved:** Retrieval-first, spacing, avoid learning-debt spiral (valve on 新字 when Active Load high), 难字 through repetition (prioritized within 在学字, no cap), instrumented (category/band in logs).
- **Backward compatibility:** Keep 新字/重测/巩固 for display and logs; five bands and mode logic used internally for selection.
