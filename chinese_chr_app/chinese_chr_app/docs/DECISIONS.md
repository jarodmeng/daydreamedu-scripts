# Architecture Decision Records (ADRs)

This document records the technical rationale behind the current state of the Chinese learning app. Each entry is backfilled from archived proposals; the implemented behavior is described in [ARCHITECTURE.md](ARCHITECTURE.md) and [backend/database.py](../backend/database.py).

**Source materials:** [archive/proposals/](archive/proposals/), [archive/plans/](archive/plans/), [archive/research/](archive/research/).

Entries are numbered and ordered chronologically by the archive file dates of the source proposals.

---

## ADR-001: Profile Three Categories (未学字 / 在学字 / 已学字)

**Context:** The 我的 (Profile) page originally showed only **已学字** (learned) in the “汉字掌握度” section. We needed a clear, MECE view of the learner’s progress across the full HWXNet pool (3664 characters) so users could see not only what they’ve learned but what they’re still learning and what they haven’t yet encountered.

**Decision:** Extend 汉字掌握度 to show three categories:

| Category   | Definition                          | Source |
|-----------|--------------------------------------|--------|
| **未学字** | Not tested yet                      | 3664 − (number of rows in bank for user) |
| **在学字** | Tested, still learning (score &lt; 10) | Count in bank with `score < 10` |
| **已学字** | Tested, learned (score ≥ 10)        | Count in bank with `score >= 10` |

Backend: one DB function returning (learned, learning, not_tested); API: extend `GET /api/profile/progress` with `learning_count` and `not_tested_count`. Frontend: show all three (e.g. stacked bar + three count lines).

**Rationale:** A single “learned” bar hid the distinction between “never seen” and “in progress.” Showing 未学字 / 在学字 / 已学字 gives learners a clear picture of progress and aligns the Profile with the same score threshold (≥10) used for pinyin recall 巩固 vs 重测. Chosen over keeping a single bar to improve interpretability and motivation.

**Source:** [archive/proposals/PROPOSAL_Profile_Three_Categories.md](archive/proposals/PROPOSAL_Profile_Three_Categories.md)

**Status:** Accepted

---

## ADR-002: Pinyin Recall Negative Score Floor (−50)

**Context:** With a floor at 0, repeated wrongs at the floor carried no signal: a character with many consecutive wrongs (from 0) was indistinguishable from one never practiced. We needed to preserve repeated-failure information for queue prioritization and future analytics (e.g. backoff, adaptive scheduling).

**Decision:** Introduce a **negative score floor at −50**. Correct: +10 (cap 100). Wrong or 我不知道: −10 (floor −50). Scores can range from −50 to 100. Proficiency threshold remains `score ≥ 10`; all negative scores are “not learned.”

**Rationale:** Preserving failure signal allows the queue to prioritize 难字 (e.g. score ≤ −20) and order by score ascending (weakest first). A shallow floor (−50) avoids unbounded negativity while giving enough headroom (5 wrongs from 0) to distinguish “repeatedly failed” from “one wrong.” Chosen over keeping floor at 0 to support 难字-through-repetition and Rescue-mode logic without schema change (integer column already supports negatives).

**Source:** [archive/proposals/PROPOSAL_Pinyin_Recall_Negative_Score_Floor.md](archive/proposals/PROPOSAL_Pinyin_Recall_Negative_Score_Floor.md)

**Status:** Accepted

---

## ADR-003: Symmetric Scoring (+10 / −10)

**Context:** The original scheme used correct +10 and wrong/我不知道 −15 (asymmetric: one wrong cancelled 1.5 corrects). We wanted a simpler, more interpretable scoring model that still respected the proficiency threshold (score ≥ 10 = 已学字) and 巩固 vs 重测 behavior.

**Decision:** Use **symmetric deltas**: correct +10 (cap 100), wrong or 我不知道 −10 (floor −50). One wrong cancels one correct.

**Rationale:** Interpretability: “each answer moves score by ±10” is easier to explain and reason about. At the critical threshold (10), 10−10=0 vs 10−15=0 — same “one wrong drops learned” behavior. Above threshold (e.g. 20), symmetric scoring is slightly more forgiving (20−10=10 keeps “learned”; 20−15=5 would not). Chosen over −15 to reduce cognitive load and marginal complexity with little downside; if too lenient, future options include +8/−10 rather than reverting to −15.

**Source:** [archive/proposals/PROPOSAL_Pinyin_Recall_Symmetric_Scoring.md](archive/proposals/PROPOSAL_Pinyin_Recall_Symmetric_Scoring.md)

**Status:** Accepted

---

## ADR-004: Queue by Five Score Categories and Adaptive Batch Mode

**Context:** The character bank can be partitioned into five categories by score. We needed queue construction to align with learning goals and research principles (retrieval-first, spacing, avoid learning-debt spiral, 难字 through repetition) while keeping batch size fixed at 20.

**Decision:** Build each batch of 20 using **five score-based categories** and an **adaptive valve** by Active Load:

- **Five categories (MECE):** 未学字 (no row), 难字 (score ≤ −20), 普通在学字 (−20 &lt; score ≤ 0), 普通已学字 (0 &lt; score &lt; 20), 掌握字 (score ≥ 20).
- **Active Load** = count(难字) + count(普通在学字). **Batch mode:**
  - **Expansion** (Active Load &lt; 100): 10 新字 + 10 review.
  - **Consolidation** (100 ≤ Active Load ≤ 250): 5 新字 + 15 review.
  - **Rescue** (Active Load &gt; 250): 4 掌握字 + 8 普通已学字 + 6 在学字 (难字 first, then 普通在学字) + 2 新字.
- Within 在学字 slots: **难字 first** (score ascending), no cap — repetition turns 难字 into 普通在学字.
- **Display categories** (three) kept for UI/logs: 新字, 重测, 巩固.

**Rationale:** Balancing “Rescue” (when the learner is overloaded) with “Expansion” (discovery): when Active Load is high, reducing 新字 per batch prevents the learning-debt spiral and protects motivation. Rescue mode’s confidence-first ordering (掌握字 then 普通已学字 then 在学字 then 新字) gives easy wins first. Prioritizing 难字 within 在学字 slots, with no cap, ensures repeated exposure and corrective feedback. Chosen over a single fixed recipe to adapt to learner state while keeping implementation tractable (no schema change; cooling and band constants in code).

**Source:** [archive/proposals/PROPOSAL_Queue_By_Five_Score_Categories.md](archive/proposals/PROPOSAL_Queue_By_Five_Score_Categories.md). Research context: [archive/research/Learning_Functions_Research_and_Brainstorming.md](archive/research/Learning_Functions_Research_and_Brainstorming.md), [archive/research/Chinese_Character_Learning_Algorithm_Design.md](archive/research/Chinese_Character_Learning_Algorithm_Design.md).

**Status:** Accepted

---

## ADR-005: Queue Total Load and 巩固 Slot Reserve

**Context:** User data showed accumulated 普通已学字 with no 巩固 tests for consecutive days, and excessive 新字 despite learning debt. Root cause: (1) Active Load excluded 普通已学字, so users with many 已学字 but fewer 在学字 stayed in Expansion; (2) in Expansion/Consolidation, 在学字 took all review slots first, crowding out 巩固.

**Decision:** Extend the queue logic (ADR-004) with two changes:

- **Total Load** replaces Active Load for mode selection: Total Load = count(难字) + count(普通在学字) + 0.3×count(普通已学字). Same thresholds (Expansion &lt; 100, Consolidation 100–250, Rescue &gt; 250). Users with large 普通已学字 backlogs transition to Consolidation/Rescue earlier.
- **Consolidation slot reserve:** In Expansion and Consolidation, reserve 4 or 6 slots for 巩固 (普通已学字 + 掌握字) **before** allocating to 在学字. Expansion: 4 reserved; Consolidation: 6 reserved. Remaining review slots go to 在学字.

**Rationale:** Including 普通已学字 in load prevents the case where a user accumulates hundreds of 已学字 but stays in Expansion (10 新字/batch) because 在学字 count is low. Reserving 巩固 slots ensures maintenance reviews are never crowded out when many 在学字 are due.

**Source:** [archive/proposals/PROPOSAL_Queue_巩固_Slot_Reserve_And_Total_Load.md](archive/proposals/PROPOSAL_Queue_巩固_Slot_Reserve_And_Total_Load.md)

**Status:** Accepted
