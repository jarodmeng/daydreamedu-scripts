# Proposal: 精通项 band and Deep Consolidation mode

**Status:** Implemented (v0.4.0)
**Date:** 2026-06-02
**Author:** (agent draft)
**Context:** Emma is the first learner to finish **all 未学字** — every enabled reading-unit in the corpus now has a row in `pinyin_recall_unit_bank`. With no 新字 left to introduce, the queue's three load-based modes (Expansion / Consolidation / Rescue) no longer fit her situation: they are all designed around a steady drip of 新字 plus draining the 在学 backlog. Emma is entering a new phase — **elevating her 掌握项 into a deeper, longer-retained tier (精通项)** — and the app needs a mode that supports it.

This proposal:

1. Adds a new score band **精通项** (score ≥ 40) above 掌握项, splitting today's 掌握项 (score ≥ 20) into **掌握项 (20–39)** and **精通项 (≥ 40)**.
2. Adds a fourth queue mode **Deep Consolidation**, triggered when a user has **no 未学项 left** (no 新字 to serve) and is **not in Rescue** (Rescue still takes precedence for heavy backlogs). Its recipe front-loads 掌握项 to push them into 精通项, while still maintaining 精通项 and draining any residual 在学 debt.
3. Threads the new band through scoring, cooling, queue construction, profile counts/trend, category drill-down pages, logging, and documentation.

**References:**
- [`docs/ARCHITECTURE.md`](../../ARCHITECTURE.md) — §8 Pinyin Recall (modes, bands, cooling); §5 API endpoints
- [PROPOSAL_Queue_By_Five_Score_Categories.md](PROPOSAL_Queue_By_Five_Score_Categories.md) — five-band model, Active Load, Expansion/Consolidation/Rescue
- [PROPOSAL_Queue_巩固_Slot_Reserve_And_Total_Load.md](PROPOSAL_Queue_巩固_Slot_Reserve_And_Total_Load.md) — Total Load, 巩固 slot reserve
- [PROPOSAL_Profile_Three_Categories.md](PROPOSAL_Profile_Three_Categories.md) — 未学/在学/已学 profile split
- `backend/pinyin_recall.py` — `build_session_queue()`, `_score_band()`, `_batch_category_for_character()`
- `backend/database.py` — `get_pinyin_recall_category_counts()`, `get_pinyin_recall_characters_by_category()`, `get_pinyin_recall_category_daily_trend()`, `_cooling_days_for_score()`, `_profile_sub_band_for_score()`, `record_pinyin_recall_answer` (score/next_due write path)
- `backend/app.py` — `/api/profile/progress`, `/api/profile/progress/category/<category>`, `/api/games/pinyin-recall/session`, `/api/games/pinyin-recall/next-batch`
- `frontend/src/pages/Profile.jsx`, `frontend/src/pages/ProfileCategory.jsx`, `frontend/src/pages/Profile.css`

---

## 1. Motivation

The learning state is per-(user, reading-unit) and identified by `unit_id` (e.g. `行|xing2`) in `pinyin_recall_unit_bank`. Score range is **−50 … 100**; correct = +10, wrong/我不知道 = −10.

Today's terminal band is **掌握项** (score ≥ 20). Once a unit reaches 20 it stays "mastered" through 80 more points of head-room (up to 100) with no further differentiation. For a learner who has tested everything, this is too coarse:

- We cannot distinguish "just crossed 20" (fragile mastery) from "answered correctly many times, deeply retained".
- The queue has no reason to keep pushing a 掌握项 unit — Rescue is the only mode that even *seeds* 掌握项 (4 per batch, as a confidence warm-up), and it is gated on a high Total Load that Emma may not have once the 在学 backlog drains.
- With **no 新字**, the existing modes degrade poorly: Expansion/Consolidation budget 10/5 新字 slots that can never be filled; their review allocation was never designed for an all-review world.

We introduce **精通项** as a "deeply retained" tier and a **Deep Consolidation** mode whose explicit goal is to *manufacture* 精通项 from 掌握项 while maintaining the tiers below and above.

---

## 2. The 精通项 band

### 2.1 Definition

| Band (proposed) | Chinese | Score range | Notes |
|---|---|---|---|
| 未学项 | not tested | no bank row | unchanged |
| 难项 | hard | score ≤ −20 | unchanged |
| 普通在学项 | learning, normal | −20 < score < 10 | **unified** — queue boundary moved 0 → 10 (§2.3) |
| 普通已学项 | learned, normal | 10 ≤ score < 20 | **unified** — queue boundary moved 0 → 10 (§2.3) |
| **掌握项** | mastered | **20 ≤ score < 40** | **narrowed** (was ≥ 20) |
| **精通项** | memorized / deeply retained | **score ≥ 40** | **new** |

- **Threshold:** `精通项 = score ≥ 40`. A unit reaches 精通项 only after **two** more correct answers past 掌握项 (20 → 30 → 40). This is deliberate: pinyin recall is 4-option MCQ, so a single correct answer carries a ~25% guess probability; requiring two correct retrievals drops guess-survival to ~6%. Crucially, because a unit at score 30 is still 掌握项 with the 掌握项 cooling (22 days), those two corrects are **naturally spaced ~22 days apart** — two well-spaced successful retrievals beyond mastery are strong evidence of durable retention, which is what "精通" should mean. (Threshold 30 vs 40 was debated; 40 was chosen — see Open Questions §12.1.)
- **Elevation engine stays busy:** a higher threshold means 掌握项 units linger across two review cycles (20→30→40) instead of graduating on the first correct, so Deep Consolidation's "elevation" slots have sustained real work rather than draining the 掌握项 pool in one pass.
- **已学项 invariant preserved:** 已学项 (score ≥ 10) now decomposes into **普通已学项 + 掌握项 + 精通项**. The sum 未学项 + 在学项 + 已学项 = total enabled units is unchanged.
- **No new column / no schema change.** 精通项 is derived from the existing `score` column exactly like every other band.

### 2.2 New constants

`pinyin_recall.py` (queue):
```python
MASTERED_MIN_SCORE = 20    # existing: 掌握项 lower bound
MEMORIZED_MIN_SCORE = 40   # new: 精通项 lower bound
```

`database.py` (profile / cooling):
```python
PROFILE_LEARNED_MASTERED_MIN_SCORE = 20   # existing
PROFILE_LEARNED_MEMORIZED_MIN_SCORE = 40  # new
```

> **Naming (decided, Open Questions §12.7):** the **Chinese display label is 精通项**. Internal English/code identifiers stay `memorized` / `learned_memorized` / `MEMORIZED_MIN_SCORE` etc. — these are intentionally non-literal (matching the existing pattern where 掌握项 → `learned_mastered`) and avoid colliding with the existing `PROFICIENCY_MIN_SCORE` / `PROFILE_PROFICIENCY_MIN_SCORE` names. The band was called 牢记项 in an earlier draft; everywhere it now reads **精通项**.

### 2.3 Reconcile the queue 0-split with the profile 10-split (in scope)

There is a pre-existing inconsistency between the queue and the profile, and **this proposal fixes it** (decided per Open Questions §12.6) so the new band sits on a coherent ladder:

- The queue's `_score_band()` splits 在学/已学 at **score 0** (`learning_normal` = `score ≤ 0`, `learned_normal` = `0 < score < 20`).
- The profile's `_profile_sub_band_for_score()` / `get_pinyin_recall_category_counts()` split at **score 10** (`PROFICIENCY_MIN_SCORE`): 普通在学项 = `−20 < score < 10`, 普通已学项 = `10 ≤ score < 20`.

The profile's 10 boundary is the documented, user-facing one ("得分 ≥ 10 为已学项"). The queue's 0 boundary is a latent bug: units at **score 1–9** are scheduled by the queue as if "learned" — they get the 5-day 普通已学 cooling and only a `0.3×` Total-Load weight — even though the learner has not reached the 已学 threshold. Net effect: weak-positive units cool too long, and Total Load is under-counted so learners linger in Expansion past the point they should shift to Consolidation/Rescue.

**Fix:** move the queue's 在学/已学 boundary from 0 to `PROFICIENCY_MIN_SCORE` (10), matching the profile. Three call sites:

1. **`_score_band()`** (`pinyin_recall.py`): `learning_normal` becomes `score < PROFICIENCY_MIN_SCORE` (i.e. `−20 < score < 10`); `learned_normal` becomes `PROFICIENCY_MIN_SCORE ≤ score < MASTERED_MIN_SCORE` (`10 ≤ score < 20`).
2. **Total Load loop** in `build_session_queue()`: count `active_load` for `score < PROFICIENCY_MIN_SCORE` (hard + 普通在学项) and `n_learned_normal_bank` for `PROFICIENCY_MIN_SCORE ≤ score < MASTERED_MIN_SCORE`.
3. **`_cooling_days_for_score()`** (`database.py`): the 1-day branch becomes `score < PROFILE_PROFICIENCY_MIN_SCORE` (was `score ≤ 0`); the 5-day branch then covers `10 ≤ score < 20`.

After the fix, queue and profile agree on all band edges (−20 / 10 / 20 / 40), and Deep Consolidation's "普通已学项 push" pool (`due_learned_normal`) is exactly the profile's 普通已学项 (10–19). Both `_score_band()` and `_profile_sub_band_for_score()` also gain a 精通项 branch (`MEMORIZED_MIN_SCORE` / `PROFILE_LEARNED_MEMORIZED_MIN_SCORE`).

**Intended behavior change (call out in review/CHANGELOG):** score 1–9 units move from 普通已学项 → 普通在学项 in the queue, so their cooling drops 5 d → 1 d and Total Load rises (they now count 1.0 instead of 0.3). This is the correction, not a regression; verify with a before/after Total-Load check for an affected user.

### 2.4 Cooling interval — scales with score inside the band

Add a longer cooling for 精通项 so deeply-retained units recur on a wide spacing (Ebbinghaus: each success buys a longer interval). **Within the 精通项 band the cooling scales with score** (decided per Open Questions §12.2): the more proven a unit is, the wider its spacing, up to a cap. The 掌握项 cooling stays a flat 22 days.

`database.py`:
```python
PINYIN_RECALL_COOLING_DAYS_HARD = 0
PINYIN_RECALL_COOLING_DAYS_LEARNING_NORMAL = 1
PINYIN_RECALL_COOLING_DAYS_LEARNED_NORMAL = 5
PINYIN_RECALL_COOLING_DAYS_MASTERED = 22
# 精通项 (score >= 40): scales with score, capped.
PINYIN_RECALL_COOLING_DAYS_MEMORIZED_BASE = 60   # at score 40
PINYIN_RECALL_COOLING_DAYS_MEMORIZED_STEP = 30   # +30 days per +20 score above 40
PINYIN_RECALL_COOLING_DAYS_MEMORIZED_MAX = 120   # cap
```

`_cooling_days_for_score()` gains a branch (checked **before** the 掌握项 branch): for `score ≥ PROFILE_LEARNED_MEMORIZED_MIN_SCORE (40)`,

```python
days = min(
    PINYIN_RECALL_COOLING_DAYS_MEMORIZED_BASE
        + PINYIN_RECALL_COOLING_DAYS_MEMORIZED_STEP * ((score - 40) // 20),
    PINYIN_RECALL_COOLING_DAYS_MEMORIZED_MAX,
)
```

**The 60-day floor must track the 精通项 threshold (40), not 30.** A unit at score 30 is still 掌握项 and keeps the 22-day cooling; only at score ≥ 40 does it become 精通项. The resulting ladder:

| Band | Score | Cooling |
|---|---|---|
| 难项 | ≤ −20 | 0 days |
| 普通在学项 | −20 < score < 10 | 1 day |
| 普通已学项 | 10 ≤ score < 20 | 5 days |
| 掌握项 | 20 ≤ score < 40 | 22 days |
| **精通项** | **40 ≤ score < 60** | **60 days** |
| **精通项** | **60 ≤ score < 80** | **90 days** |
| **精通项** | **80 ≤ score ≤ 100** | **120 days (cap)** |

The 22-day 掌握项 cooling holding through score 39 is what produces the ~22-day spacing between the two corrects that elevate a unit from 掌握项 (20) → 30 → 精通项 (40). The mirror table `STAGE_INTERVAL_DAYS` / `PINYIN_RECALL_STAGE_INTERVAL_DAYS` already tops out at 30 days and is only used for the legacy `stage` analytics column; the authoritative scheduler is `_cooling_days_for_score`, so the scaled 精通项 cooling is added there. (Stage→analytics mapping is unaffected; 精通项 maps to the same top stage as 掌握项.)

---

## 3. Deep Consolidation mode

### 3.1 Trigger

Deep Consolidation is selected when the user has **no eligible 未学项 anywhere in the enabled pool** — i.e. there are no 新字 that could ever be served this batch — **and is not already in Rescue**. This is **evaluated per batch** (not sticky): if new units later appear (corpus growth, newly enabled units), or the backlog falls out of Rescue range, the user reverts to the appropriate mode automatically.

**Rescue takes precedence** (decided per Open Questions §12.4): a learner who has finished all 未学项 but still carries a large 难项/在学项 backlog (Total Load > 250) needs the Rescue recipe's heavier debt draining first. Rescue already redistributes its 2 新字 slots when no 新字 are available, so it works with an empty 新字 pool. Deep Consolidation slots in **below** Rescue and **above** Expansion/Consolidation:

```
if total_load > 250:              mode = "rescue"             # even when no 新字
elif no_new_available_anywhere:   mode = "deep_consolidation"
elif total_load <= 99:            mode = "expansion"
else:                             mode = "consolidation"
```

**Detecting "no 新字 anywhere" robustly (decided per Open Questions §12.5).** Add an optional `not_tested_count: Optional[int] = None` parameter to `build_session_queue`:

- **When the caller passes it** (production: `app.py` already computes `get_pinyin_recall_category_counts(...)["not_tested"]` over the authoritative enabled-unit pool), use `not_tested_count == 0` as the trigger. This is the cheapest and most authoritative signal, and it makes the queue trigger **exactly** match the profile's 未学项 = 0 condition.
- **When it is `None`** (e.g. direct unit-test calls), fall back to self-contained detection: if `n_new_avail == 0` within the window and `zibiao_max_effective >= max_zibiao_in_corpus`, treat as no-新字; if the window is smaller than the corpus, widen the effective window to `max_zibiao_in_corpus`, recompute `new_items`, and re-check before declaring Deep Consolidation.

`app.py` should pass `not_tested_count` from the same `category_counts` it can fetch for the user, avoiding a second full-corpus candidate rebuild on the hot session path.

### 3.2 Recipe (20 items, 0 新字)

The phase goal is **掌握项 → 精通项 elevation**, so 掌握项 gets the largest share. We still maintain the band above (精通项) and drain any residual debt below.

| Count | Source band | Role | Constant |
|---|---|---|---|
| **6** | 在学项 (难项 first, then 普通在学项) | **Debt collector** — drain residual backlog; 难项 first (score asc), no cap | `DEEP_CONSOLIDATION_LEARNING = 6` |
| **4** | 普通已学项 (10–19) | **Mastery push** — move toward 掌握项 (≥ 20), refilling the elevation pool | `DEEP_CONSOLIDATION_LEARNED_NORMAL = 4` |
| **8** | 掌握项 (20–39) | **Elevation** (primary) — push toward 精通项 (≥ 40) | `DEEP_CONSOLIDATION_MASTERED = 8` |
| **2** | 精通项 (≥ 40) | **Retention maintenance** — keep deeply-retained units from decaying | `DEEP_CONSOLIDATION_MEMORIZED = 2` |
| **0** | 未学项 | none available | `DEEP_CONSOLIDATION_NEW = 0` |

**Total:** 6 + 4 + 8 + 2 = 20.

Only **due** items are eligible (bank row + `next_due_utc <= now`, or null). Because 精通项 cools for 60+ days (60/90/120 by score, §2.4), on most days far fewer than 2 精通项 are due — that is intended; the spare flows to elevation.

### 3.3 Spare-slot redistribution

When a band has fewer **due** candidates than its target, reallocate the spare in priority order (elevation-first), capping at each band's available due count:

1. **掌握项** (the elevation engine) — absorb spare first.
2. **普通已学项** (refill the elevation pool).
3. **精通项** (extra maintenance).
4. **在学项** (extra debt draining).

Steady-state behavior: as 掌握项 units get elevated to 精通项, the 掌握项 pool shrinks and 普通已学项 / 精通项 / 在学项 naturally take the slots — the mode self-balances without code changes.

### 3.4 Ordering within the batch (confidence-first)

Following Rescue's confidence-first principle, order the batch easiest → hardest so the session opens with wins:

```
精通项 → 掌握项 → 普通已学项 → 在学项 (难项 first, then 普通在学项)
```

Within each band: 在学项 by score ascending (weakest first); 普通已学项 / 掌握项 / 精通项 by `next_due_utc` ascending (most overdue first). Priority-aware ordering (`user_prioritized_characters`) continues to apply within the due pools exactly as today.

### 3.5 Interaction with existing modes

- **`_score_band()`** gains a `memorized` return (`score ≥ 40`); `mastered` becomes `20 ≤ score < 40`. The per-batch logging band `_batch_category_for_character()` therefore emits a new `memorized` value.
- **Expansion / Consolidation / Rescue must not silently drop 精通项.** In those three modes the maintenance/巩固 pool currently uses `due_mastered`. To preserve their behavior (which historically treated everything ≥ 20 as one "mastered" pool), build a combined pool `due_mastered + due_memorized` (ordered by `next_due_utc`) wherever those modes consume "mastered" candidates. Deep Consolidation is the only mode that treats the two as distinct.
- **Display category (新字 / 巩固 / 重测)** is unchanged: 精通项 is `score ≥ 10` and all-correct → 巩固. No new display label is required in-session (a future enhancement could add a 精通 chip, see Open Questions §12.3).

---

## 4. Score & scheduler write path

`record_pinyin_recall_answer` (in `database.py`) already computes `score_after` and calls `_cooling_days_for_score(score_after)`. With the new branch:

- A 掌握项 unit at score 20 answered correctly → score 30 → still 掌握项 → cooled **22 days**; ~22 days later, answered correctly again → score 40 → now 精通项 → next due in **60 days**. (Two spaced corrects, by design.)
- A 精通项 unit answered wrong → score −10 (to 30) → drops back to 掌握项, `next_due_utc = None`, `stage = 0` (immediately due), and it re-climbs as usual.

No change to the +10 / −10 deltas, the −50/100 clamps, or the `stage` analytics mapping (精通项 shares the top stage with 掌握项).

---

## 5. Profile counts (`/api/profile/progress`)

`get_pinyin_recall_category_counts()` must split the `learned_mastered` filter:

- `learned_mastered`: `score >= 20 AND score < 40` (narrowed)
- `learned_memorized`: `score >= 40` (new)

The returned dict gains `learned_memorized`; `learned` (≥ 10), `learning`, `not_tested`, `learning_hard`, `learning_normal`, `learned_normal` are unchanged. The `/api/profile/progress` `proficiency` object gains `learned_memorized` alongside the existing sub-band fields.

Backward compatibility: the frontend treats a missing `learned_memorized` as 0 (so an older backend keeps working), and a missing field never changes the 已学项 total because the bar is driven by `learned_count`.

---

## 6. Daily trend chart (`category_trend`)

`get_pinyin_recall_category_daily_trend()` replays `pinyin_recall_item_answered.score_after` into end-of-day band snapshots.

- `_profile_sub_band_for_score()` gains a 精通字 branch (`score ≥ 40`); 掌握字 becomes `20 ≤ score < 40`.
- The internal `band_keys` list and the per-day snapshot dict gain `精通字`.
- `_category_trend_point_from_counts()` emits a new `memorized` key (from `counts["learned_memorized"]`) and narrows `mastered` to the new `learned_mastered`.
- Each trend point now has five series: `hard`, `learning_normal`, `learned_normal`, `mastered`, `memorized`.

`_sync_category_trend_with_live_counts()` keeps the latest UTC day aligned with the live table; it picks up the new key automatically once `_category_trend_point_from_counts` includes it.

---

## 7. Category drill-down (`/api/profile/progress/category/<category>`)

- `get_pinyin_recall_characters_by_category()` gains a `learned_memorized` branch (`score >= 40`) and narrows the existing `learned_mastered` branch to `score >= 20 AND score < 40`.
- Add the constant `PROFILE_CATEGORY_LEARNED_MEMORIZED = "learned_memorized"`.
- The route's `allowed` set in `app.py` gains `learned_memorized`.

---

## 8. Frontend

### 8.1 `Profile.jsx`
- Read `proficiency.learned_memorized` (default 0).
- Under the **已学项** row, show three sub-links instead of two: **精通项** (`/profile/category/learned_memorized`), **掌握项** (`/profile/category/learned_mastered`), **普通** (`/profile/category/learned_normal`), each with count and percentage. 掌握项 now reflects the narrowed 20–39 band.
- Add a fifth stacked `Area` to the 掌握度每日趋势 chart: `dataKey="memorized"`, `name="精通项"`, with the deepest-green stroke/fill (place it as the top of the stack, above 掌握项).
- Update the hint copy to mention 精通项 (e.g. "… 得分 ≥ 40 为精通项，20–39 为掌握项 …") — keep it concise.

### 8.2 `ProfileCategory.jsx`
- Add `learned_memorized: '精通项'` to `CATEGORY_TITLES` (this automatically makes the route valid and renders the unit grid; no other change needed).

### 8.3 `Profile.css`
- Add a color class for the 精通项 sub-band / a chart color (deep green, e.g. stroke `#1b5e20`, fill `#66bb6a`) distinct from 掌握项's `#2e7d32` / `#a5d6a7`.

---

## 9. Logging & analytics

- `batch_mode = "deep_consolidation"` is logged into `pinyin_recall_item_presented.batch_mode` (no schema change — free-text column).
- `batch_character_category` gains the value `memorized` for 精通项 items.
- The diagnostic/analytics helpers `backend/scripts/utils/diagnose_pinyin_recall_mastered_growth.py` and `backend/scripts/pinyin_recall/user_daily_category_counts.py` reference `PROFILE_LEARNED_MASTERED_MIN_SCORE`; they should be updated to also surface 精通项 (or at least not misreport 掌握项 now that it is capped at 40). This is analytics-only and can ship in the same change or as a fast-follow.

---

## 10. Data model / schema

**No schema change.** All bands derive from the existing `score` column in `pinyin_recall_unit_bank`. `batch_mode` and `batch_character_category` are existing free-text columns in `pinyin_recall_item_presented`. The trend is replayed at runtime from `pinyin_recall_item_answered`.

---

## 11. Backward compatibility

- **Existing users (still have 新字):** Deep Consolidation never triggers for them, and 掌握项 + 精通项 are merged back into one maintenance pool in the Total-Load modes (§3.5). **One intended change does reach them:** the 0→10 boundary fix (§2.3) reclassifies score 1–9 units from 普通已学项 → 普通在学项, so those units cool 1 day instead of 5 and Total Load rises slightly — a correction that may move some users from Expansion to Consolidation sooner. Expected and desirable; flag in CHANGELOG.
- **Cooling:** existing 掌握项 units that climb to ≥ 40 get a 60-day cooling on their *next* correct answer; nothing is retroactively rescheduled. Units already at score 30–39 are simply re-labeled 掌握项 (no longer "mastered + everything above") and keep the 22-day cooling.
- **Old frontend + new backend:** the extra `learned_memorized` field and `memorized` trend key are ignored; the chart simply omits the 精通项 area and 掌握项 appears smaller (now 20–39). Acceptable.
- **New frontend + old backend:** `learned_memorized` is undefined → treated as 0; 精通项 row shows 0 and the chart's 精通项 area is flat. Acceptable.

---

## 12. Open Questions

1. **精通项 threshold (40) — DECIDED.** Considered 30 (one correct past 掌握项) vs 40 (two correct). **Chose 40**: pinyin recall is 4-option MCQ, so one correct has ~25% guess survival vs ~6% for two; and the intermediate score-30 step keeps the unit in 掌握项 long enough (22-day cooling) that the two corrects are well spaced. *Remaining sub-question (deferred):* should we eventually require *consecutive* corrects (a streak field) rather than a raw score cutoff, which is more robust against an occasional miss that drops the score back? Not in v1.
2. **精通项 cooling — DECIDED: scales with score.** Within the band, cooling = 60 days (40–59) → 90 days (60–79) → 120 days (80–100, cap). See §2.4 for the formula/constants. Rationale: the more proven a unit is, the wider its spacing.
3. **In-session 精通项 surfacing — DECIDED: keep 巩固 for v1.** No new in-session chip; a 精通项 unit still shows the 巩固 label. A dedicated chip can be a future enhancement.
4. **Deep Consolidation vs residual Rescue — DECIDED: Rescue takes precedence.** When Total Load > 250, use Rescue even if there are no 新字 (Rescue redistributes its 2 新字 slots). Deep Consolidation applies only when not in Rescue range. See §3.1 decision order.
5. **Trigger detection — DECIDED: authoritative `not_tested_count`.** `build_session_queue` takes an optional `not_tested_count`; production callers pass the value from `get_pinyin_recall_category_counts` (matches the profile's 未学项 = 0 exactly). When absent (unit tests), fall back to the self-contained widen-window check. See §3.1.
6. **Reconcile queue 0-split vs profile 10-split — DECIDED: fix it in this proposal.** Confirmed a real latent bug (not cosmetic): `_score_band()` treats `0 < score < 20` as `learned_normal`, so the queue gives score 1–9 units the 5-day 普通已学 cooling and only a 0.3× Total-Load weight, even though the documented proficiency threshold and profile UI classify `score < 10` as 在学项 (`PROFICIENCY_MIN_SCORE = 10`). The fix moves the queue's 在学/已学 boundary from 0 → 10 at all three call sites (`_score_band`, the Total Load loop, `_cooling_days_for_score`). Folded into §2.3 and Phase 1; the intended behavior change (1–9 units: cooling 5 d → 1 d, Total-Load weight 0.3 → 1.0) is called out for review/CHANGELOG and before/after verification.
7. **Naming — DECIDED: 精通项.** The Chinese label is **精通项** (chosen over the earlier draft name 牢记项 and other candidates 熟记项 / 牢固项). Used in UI, trend legend, and category page title. *Internal English/code identifiers stay `memorized` / `learned_memorized` / `MEMORIZED_MIN_SCORE`* — consistent with the codebase's existing non-literal keys (e.g. 掌握项 → `learned_mastered`), to avoid colliding with the existing `PROFICIENCY_MIN_SCORE` / `PROFILE_PROFICIENCY_MIN_SCORE` ("proficiency") names.

---

## 13. Implementation plan

Each phase lists **Todo**, **Tests**, and **Success / handoff criteria**. Phases are ordered so backend lands before frontend, and so existing modes are never broken in between. A **final sweep** (Phase 6) checks completeness, accuracy, and consistency before sign-off.

### Phase 1 — Score band, threshold, cooling, and 0→10 boundary fix (foundation)

**Todo**
- [ ] Add `MEMORIZED_MIN_SCORE = 40` to `pinyin_recall.py`. Update `_score_band()`: `learning_normal` = `score < PROFICIENCY_MIN_SCORE` (10) — **boundary moved 0 → 10, §2.3/§12.6**; `learned_normal` = `10 ≤ score < MASTERED_MIN_SCORE`; `mastered` = `20 ≤ score < 40`; new `memorized` = `score >= 40` (checked before `mastered`).
- [ ] Update the **Total Load loop** in `build_session_queue()`: `active_load` counts `score < PROFICIENCY_MIN_SCORE`; `n_learned_normal_bank` counts `PROFICIENCY_MIN_SCORE ≤ score < MASTERED_MIN_SCORE`.
- [ ] Add `PROFILE_LEARNED_MEMORIZED_MIN_SCORE = 40` and the scaled-cooling constants (`PINYIN_RECALL_COOLING_DAYS_MEMORIZED_BASE = 60`, `_STEP = 30`, `_MAX = 120`) to `database.py`.
- [ ] Update `_cooling_days_for_score()`: 1-day branch becomes `score < PROFILE_PROFICIENCY_MIN_SCORE` (**moved from `score ≤ 0`**); 5-day branch covers `10 ≤ score < 20`; add 精通项 branch (before the 掌握项 case): `score >= 40` → `min(60 + 30*((score-40)//20), 120)`; score 30–39 still returns the 掌握项 22-day cooling.
- [ ] Confirm `_batch_category_for_character()` now emits `memorized` (it delegates to `_score_band`).

**Tests**
- [ ] Unit test `_score_band`: −30→hard, −5→learning_normal, **5→learning_normal** (boundary moved), **9→learning_normal, 10→learned_normal**, 15→learned_normal, 25→mastered, 35→mastered, 45→memorized (boundary: 39→mastered, 40→memorized).
- [ ] Unit test `_cooling_days_for_score`: −30→0, −5→1, **5→1** (boundary moved), **9→1, 10→5**, 15→5, 25→22, 35→22, 40→60, 55→60, 60→90, 80→120, 100→120.
- [ ] Total Load test: a user with N units at score 1–9 now has those counted at weight 1.0 (active_load) instead of 0.3 (learned_normal) → Total Load increases; confirm the mode can shift Expansion→Consolidation at the documented threshold.
- [ ] Regression: existing pinyin_recall queue tests still pass; update any that encoded the old 0-boundary expectation (they should now expect the 10-boundary).

**Success / handoff**
- Band + cooling helpers return the new tier; queue and profile agree on all band edges (−20 / 10 / 20 / 40). The only intended behavior change is score 1–9 reclassified 普通已学项 → 普通在学项 (cooling 5 d → 1 d, Total-Load weight 0.3 → 1.0). Backend tests green.

### Phase 2 — Deep Consolidation queue mode

**Todo**
- [ ] Add `DEEP_CONSOLIDATION_LEARNING/LEARNED_NORMAL/MASTERED/MEMORIZED/NEW = 6/4/8/2/0` constants to `pinyin_recall.py`.
- [ ] In `build_session_queue`, split the due pool into `due_mastered` (20–39) and `due_memorized` (≥ 40); sort `due_memorized` by `next_due_utc`.
- [ ] Add optional `not_tested_count: Optional[int] = None` to `build_session_queue`; implement the **no-new-anywhere** trigger (§3.1): when provided, use `not_tested_count == 0`; else fall back to the widen-window check (`max_zibiao_in_corpus`). Have `app.py` pass `not_tested_count` from `get_pinyin_recall_category_counts`.
- [ ] Implement the mode decision order with **Rescue precedence** (§3.1): `total_load > 250` → rescue (even with 0 新字); else no-新字 → deep_consolidation; else expansion/consolidation.
- [ ] Implement the Deep Consolidation allocator (fixed recipe + spare redistribution §3.3) and confidence-first ordering (§3.4).
- [ ] For Expansion/Consolidation/Rescue, feed a combined `due_mastered + due_memorized` pool into their maintenance/巩固 allocation so 精通项 is never dropped (§3.5).
- [ ] Ensure `build_session_queue` returns `mode = "deep_consolidation"` so `app.py` logs it as `batch_mode`.

**Tests**
- [ ] Queue test: user with 0 未学项, mixed bands → mode `deep_consolidation`, ≤20 items, 0 新字, 掌握项 gets the largest realized share when supply allows.
- [ ] Spare redistribution: few due 精通项 → spare flows to 掌握项 then 普通已学项.
- [ ] Trigger: `not_tested_count == 0` passed in → `deep_consolidation`; `not_tested_count > 0` → not deep_consolidation. With `not_tested_count=None`, the widen-window fallback still detects a fully-tested corpus.
- [ ] Edge: window smaller than corpus but corpus fully tested (no `not_tested_count` passed) → still detects `deep_consolidation` (not Expansion).
- [ ] **Rescue precedence:** user with 0 未学项 **and** Total Load > 250 → mode `rescue` (not `deep_consolidation`); Rescue redistributes its 2 新字 slots cleanly with 0 新字 available.
- [ ] Edge: user with 未学项 remaining → mode stays Expansion/Consolidation/Rescue and 精通项 units still appear in maintenance slots (not dropped).
- [ ] Ordering: batch is 精通项 → 掌握项 → 普通已学项 → 在学项 (难项 first).

**Success / handoff**
- A no-新字 learner gets a 掌握项-heavy, 0-新字 batch; load-mode learners are byte-for-byte unaffected except band logging. Queue tests green.

### Phase 3 — Profile counts, trend, and category API

**Todo**
- [ ] `get_pinyin_recall_category_counts()`: narrow `learned_mastered` to `[20,40)` and add `learned_memorized` (`≥ 40`) to SQL + returned dict.
- [ ] `app.py` `/api/profile/progress`: add `proficiency.learned_memorized`.
- [ ] `_profile_sub_band_for_score()`: add 精通字 branch; narrow 掌握字.
- [ ] `get_pinyin_recall_category_daily_trend()`: add `精通字` to `band_keys`/snapshots; emit `memorized` in output rows.
- [ ] `_category_trend_point_from_counts()`: add `memorized`; narrow `mastered`.
- [ ] Add `PROFILE_CATEGORY_LEARNED_MEMORIZED`; extend `get_pinyin_recall_characters_by_category()` (new `learned_memorized` branch; narrow `learned_mastered`).
- [ ] `app.py` `/api/profile/progress/category/<category>`: add `learned_memorized` to `allowed`.

**Tests**
- [ ] `test_profile_unit_progress_api.py`: extend to assert `learned_memorized` count and that `learned_mastered` excludes ≥ 40.
- [ ] Trend test: a unit crossing 40 moves from `mastered` to `memorized` in the daily snapshot; `_sync_category_trend_with_live_counts` carries the new key.
- [ ] Category endpoint: `learned_memorized` returns only ≥ 40 units; `learned_mastered` returns only 20–39.

**Success / handoff**
- API exposes 精通项 everywhere counts/trends/lists are produced; sums still reconcile (普通已学 + 掌握 + 精通 = 已学). Backend tests green.

### Phase 4 — Frontend (Profile, ProfileCategory, CSS)

**Todo**
- [ ] `Profile.jsx`: read `learned_memorized`; render 精通项 / 掌握项 / 普通 sub-links under 已学项; add the 精通项 `Area` to the trend chart; update the hint copy.
- [ ] `ProfileCategory.jsx`: add `learned_memorized: '精通项'`.
- [ ] `Profile.css`: add 精通项 color(s).
- [ ] Verify graceful fallback when `learned_memorized` is absent (older backend → 0).

**Tests**
- [ ] `npm run build` (Vite) succeeds (primary FE quality gate per AGENTS.md).
- [ ] Playwright: Profile renders the 精通项 row and `/profile/category/learned_memorized` shows the unit grid (use dev auth bypass + dev user per AGENTS.md).
- [ ] Manual: chart shows five stacked bands; 掌握项 now reflects 20–39.

**Success / handoff**
- 我的 page shows 精通项 count, link, and trend area; category page lists 精通项 units. Build + E2E green.

### Phase 5 — Analytics scripts (fast-follow, optional in same PR)

**Todo**
- [ ] Update `scripts/utils/diagnose_pinyin_recall_mastered_growth.py` and `scripts/pinyin_recall/user_daily_category_counts.py` to surface 精通项 and respect the narrowed 掌握项 bound.

**Tests**
- [ ] Run each script against a dev user; confirm band totals reconcile with `/api/profile/progress`.

**Success / handoff**
- Analytics no longer conflate 精通项 into 掌握项.

### Phase 6 — Documentation and final sweep

**Todo**
- [ ] `docs/ARCHITECTURE.md` §8.1: add **Deep Consolidation** to the mode list (trigger: no 未学项 **and not in Rescue** — Rescue takes precedence; recipe: 6 在学项 + 4 普通已学项 + 8 掌握项 + 2 精通项). §8.2: **fix band edges to −20 / 10 / 20 / 40** (普通在学项 −20 < score < 10, 普通已学项 10 ≤ score < 20) and add 精通项 (≥ 40), narrowing 掌握项 (20–39). §8.3: 精通项 cooling scales 60/90/120 by score; the 1-day/5-day boundary is now 10 (was 0) and the 22-day boundary ends at 39.
- [ ] `backend/DATABASE.md`: update the "Queue construction" paragraph (four modes incl. Deep Consolidation + Rescue precedence, five bands with the corrected 10-boundary, scaled 精通项 cooling) and the `get_pinyin_recall_category_daily_trend` row to mention five bands incl. 精通项.
- [ ] `docs/CHANGELOG.md`: add a version entry (e.g. **v0.4.0** given the new mode + band) describing 精通项 + Deep Consolidation **and the queue 在学/已学 boundary fix (0 → 10) with its behavior change for score 1–9 units**.
- [ ] `README.md`: bump the **Current version** line to match the new CHANGELOG entry (per AGENTS.md versioning housekeeping).
- [ ] Flip this proposal's **Status** to *Implemented* with the commit/date.
- [ ] **TODO.md check:** this proposal lives in the `chinese_chr_app` project and does not complete an `ai_study_buddy/TODO.md` bullet, so no TODO checkbox toggle is required. (P1-1 governs the *standard* this proposal follows; it is not closed by this work.)
- [ ] **Final sweep:** re-read every touched file and the three docs above for completeness (all bands/thresholds/cooling consistent across `pinyin_recall.py`, `database.py`, `app.py`, FE), accuracy (numbers match: band edges −20 / 10 / 20 / 40, 精通项 ≥ 40, 掌握项 20–39, cooling 1d/5d boundary at 10 and 22d/60d boundary at 40, recipe 6-4-8-2), and consistency (band names identical in code, API, UI, docs); confirm tests + build pass and the app is ready to ship.

**Tests**
- [ ] Docs link-check / visual read; confirm ARCHITECTURE §8 mode count is now four and bands list 精通项.
- [ ] Confirm `README.md` version == top `CHANGELOG.md` version.

**Success / handoff**
- All code, API, UI, and docs agree on band edges −20 / 10 / 20 / 40 (queue == profile), 精通项 (≥ 40), 掌握项 (20–39), Deep Consolidation (no-新字 trigger, Rescue precedence, fixed recipe). Version bumped. Proposal marked Implemented.

---

## 14. Files to touch

| Layer | File(s) | Change |
|---|---|---|
| Queue | `backend/pinyin_recall.py` | `MEMORIZED_MIN_SCORE`; `_score_band` memorized **+ 在学/已学 boundary 0→10**; Total Load loop boundary 0→10; optional `not_tested_count` param; Deep Consolidation constants, trigger (Rescue precedence), allocator, ordering; combine mastered+memorized for legacy modes |
| DB | `backend/database.py` | `PROFILE_LEARNED_MEMORIZED_MIN_SCORE`, scaled-cooling constants (`PINYIN_RECALL_COOLING_DAYS_MEMORIZED_BASE/_STEP/_MAX`), `_cooling_days_for_score`, `_profile_sub_band_for_score`, `get_pinyin_recall_category_counts`, `_category_trend_point_from_counts`, `get_pinyin_recall_category_daily_trend`, `get_pinyin_recall_characters_by_category`, `PROFILE_CATEGORY_LEARNED_MEMORIZED` |
| API | `backend/app.py` | `proficiency.learned_memorized`; `allowed` set in category route; pass `not_tested_count` into `build_session_queue`; (Deep Consolidation mode flows through `build_session_queue` return) |
| Frontend | `frontend/src/pages/Profile.jsx`, `ProfileCategory.jsx`, `Profile.css` | 精通项 row + link + trend area + colors + hint |
| Analytics | `backend/scripts/utils/diagnose_pinyin_recall_mastered_growth.py`, `backend/scripts/pinyin_recall/user_daily_category_counts.py` | surface 精通项 |
| Tests | `backend/tests/test_profile_unit_progress_api.py`, pinyin-recall queue tests | new band + Deep Consolidation coverage |
| Docs | `docs/ARCHITECTURE.md`, `backend/DATABASE.md`, `docs/CHANGELOG.md`, `README.md` | bands, mode, cooling, version |

---

## 15. Summary

- **New band 精通项 (score ≥ 40)** splits today's 掌握项 (≥ 20) into **掌握项 (20–39)** + **精通项 (≥ 40)**; 精通项 cooling **scales 60 → 90 → 120 days** by score (22-day 掌握项 cooling holds through score 39, so the two corrects that elevate 20→30→40 are naturally spaced). No schema change.
- **Band-edge fix (0 → 10):** the queue's 在学/已学 boundary is moved from score 0 to `PROFICIENCY_MIN_SCORE` (10) so it matches the profile. Queue and profile now agree on all edges (−20 / 10 / 20 / 40). One intended behavior change: score 1–9 units become 普通在学项 (cooling 5 d → 1 d, Total-Load weight 0.3 → 1.0).
- **New mode Deep Consolidation**, triggered when a learner has **no 未学项 anywhere** (no 新字 to serve) **and is not in Rescue** (Rescue keeps precedence for heavy backlogs). Recipe (20, 0 新字): **6 在学项 (难项 first) + 4 普通已学项 + 8 掌握项 (elevation) + 2 精通项**, confidence-first order, with spare slots flowing to elevation.
- **Existing modes** keep treating ≥ 20 as one maintenance pool and never enter Deep Consolidation while 新字 remain; the only change reaching them is the 0→10 boundary correction above.
- Threaded through scoring/cooling, queue, profile counts + trend (five bands), category drill-down, in-session logging (`batch_mode="deep_consolidation"`, `batch_character_category="memorized"`), frontend, analytics scripts, and docs, with a versioned CHANGELOG/README bump and a final consistency sweep.
