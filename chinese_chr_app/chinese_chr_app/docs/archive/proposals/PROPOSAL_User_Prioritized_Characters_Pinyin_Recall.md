# Proposal: User-prioritized characters for Pinyin Recall (新字 selection)

**Status:** Implemented  
**Date:** 2026-04-02  
**Implemented in:** v0.3.2  
**Context:** Learners (e.g. school dictation lists) benefit when the game surfaces **specific characters soon**, not only a global `zibiao_index` pool. [Emma’s P4 听写 category (ii) analysis](../../../../ai_study_buddy/docs/notes/p4_4a_dictation_2026_category_ii.md) now shows **176 / 548** category (ii) characters **not yet** in `pinyin_recall_unit_bank` at the character level, and **181 / 553** missing `character + reading` pairs at the reading-unit level. Since the source material is now available at both levels, this proposal uses a **hybrid priority model**: rows always target a **character**, and may optionally target a specific **reading/unit** when the curriculum source or operator import provides that precision.

**References:**

- [P4 4A 听写 / 默写 · category (ii) · 2026](../../../../ai_study_buddy/docs/notes/p4_4a_dictation_2026_category_ii.md) — full 字表, reading-level artifact, HWXNet / 字表 index breakdown, Emma Pinyin Recall 字库 cross (**176 / 548** characters missing; **181 / 553** `character + reading` pairs missing), refresh notes
- `backend/pinyin_recall.py` — `build_session_queue` (candidate pool, `new_items`, `new_queue`, Expansion / Consolidation / Rescue)
- `docs/archive/proposals/PROPOSAL_Queue_By_Five_Score_Categories.md` — batch modes, Active Load, 新字 caps
- `backend/database.py` — `pinyin_recall_unit_bank`, `PROFILE_*` score bands
- `docs/ARCHITECTURE.md` — reading units (`unit_id`), HWXNet/Feng sources
- `frontend/src/pages/PinyinRecall.jsx` — session item tags (`category` 新字/巩固/重测, `is_polyphonic` → 多音字)

---

## 1. Problem

1. **Curriculum gap:** Classroom materials (听写、词语表) define a **time-bound** set of characters. The game’s **新字** draw is largely **pool + shuffle** (`new_items` shuffled, then first-come until `n_new_slots`). That does not bias toward “what’s due for school this week.”
2. **No first-party hook:** There is no table or API for “this user should see these characters **as 新字** before others,” aside from implicit `zibiao_index` ordering (then shuffle).
3. **Measurable need:** Cross-referencing external lists with `pinyin_recall_unit_bank` is already useful documentation; **productizing** that link reduces manual alignment work and improves perceived relevance.

---

## 2. Goals

1. Store a **per-user, ordered list of prioritized characters**, with optional **reading-level specificity** and optional metadata (source, expiry).
2. When building **新字** slots in `build_session_queue`, **prefer** reading units whose **character** appears in that list, and honor a row’s optional reading constraint when present. Prioritized rows may also **override the normal candidate window** so targeted items remain truly prioritized, subject to safety constraints (`recall_enabled`, no existing bank row for that **unit**, not already placed in the batch).
3. When building **due / review** portions of the queue (**难字、普通在学字、普通已学字**等已入库且 `next_due` 已到期的项), give **extra weight** to units whose **character** is on the priority list and whose **score is weak** (e.g. `score < PROFILE_PROFICIENCY_MIN_SCORE` / 10), with reading-specific rows matching only that reading.
4. Keep **Rescue / Consolidation / Expansion** **slot counts** and **Active Load** mode selection; change **ordering** (and 新字 pick) to respect priorities, not the total recipe arithmetic.
5. Remain **backward compatible**: users with **no** priority rows behave exactly as today.
6. **In-game UX:** When an item is shown because the character is on the user’s priority list, the client displays a **short label** for *where* that priority comes from (e.g. **第二学期听写**), **alongside** the existing **新字 / 巩固 / 重测** and **多音字** chips.

**Non-goals (initial phase):**

- Replacing the entire candidate pool or changing `zibiao_min` / `zibiao_max_effective`.
- **Parent / settings UI** to edit lists in-app in v1 (use API + script first); the **in-game tag** is in scope.
- Guaranteeing **100%** of priority characters appear in one session (batch size and mode caps still apply).

**Implementation phasing (suggested):** Ship **新字** prioritization first (§3.2.1), then **due-queue boost** (§3.2.3) and the in-game labeling path (§3.3.1) - or both in one release if low risk. Behavior is specified in one proposal so queue logic stays coherent.

---

## 3. Design

### 3.1 Data model
#### 3.1.1 Hybrid priority model
The feature uses a **hybrid priority model**:

- Priorities are scoped to **`user_id`** only.
- A priority target may be either **character-wide** or **reading-specific**.
- Character-wide rows are the default import shape for school lists.
- Reading-specific rows are available when the source material or operator workflow provides `character + reading` precision.

This keeps the product simple for ordinary curriculum imports while still matching the app’s reading-unit storage model when polyphonic precision matters.

#### 3.1.2 Matching semantics
Pinyin Recall state is stored per `unit_id`, so the design uses these matching rules:

- `reading = NULL` means a row applies to any eligible reading for that character.
- `reading IS NOT NULL` means a row applies only to that exact reading/unit.
- If both a character-wide row and a reading-specific row match the same unit, the reading-specific row wins for ordering and label/source resolution.
- For character-wide rows on polyphonic characters, the fallback pick order is `reading_rank`.

### 3.2 Backend changes
#### 3.2.1 New-item queue behavior
Priority affects **新字** selection in three ways:

- prioritized targets should surface earlier than non-priority items
- explicit prioritized targets may override the normal candidate window
- existing 新字 slot counts remain unchanged

The queue should load the user’s priority rows, combine normal `new_items` with any eligible priority overrides, dedupe by `unit_id`, and then fill the batch from prioritized items before the non-priority remainder.
See the concrete `build_session_queue` logic in **§4.2.2.1**.

#### 3.2.2 Candidate-window override and pacing
Priority is intentionally strong enough to pull an explicit 新字 target in even when it sits outside the normal `[zibiao_min, zibiao_max_effective]` window. Otherwise, priority would only mean “prefer within the current pool,” which is too weak for school-driven lists.

Guardrails:

- override applies only to explicit priority targets, not their neighboring non-priority units
- the same safety checks still apply, such as `recall_enabled` and no existing bank row for that unit
- the existing 新字 budget does not increase
- the normal zibiao window still governs the non-priority population
See the candidate-window override implementation in **§4.2.2.2**.

#### 3.2.3 Due / review behavior
Weak banked items that also match a priority row should rank earlier within the existing due buckets:

- prioritized weak items review sooner
- mastered items are not boosted in v1
- reading-specific matches outrank character-wide matches when both apply
- the current due-pool slot counts remain unchanged
See the due-pool boosted ordering implementation in **§4.2.2.4**.

### 3.3 Frontend changes
#### 3.3.1 UX and signaling
The learner should be able to tell *why* an item is being emphasized without the feature overwhelming the session:

- prioritized items can carry a short human label such as `第二学期听写`
- that label appears beside the existing 新字/巩固/重测 and 多音字 chips
- queued items may also carry optional machine-facing fields such as `priority_source`

The implementation details for ingestion, API, migration, and tests are specified in §4.

---

## 4. Implementation

### 4.1 Data model

#### Table: `user_prioritized_characters`

| Column | Type | Notes |
|--------|------|--------|
| `id` | `bigint` or `uuid` PRIMARY KEY | Surrogate key for stable row identity. |
| `user_id` | `text` NOT NULL | Supabase auth user id (same as `pinyin_recall_unit_bank.user_id`). |
| `character` | `text` NOT NULL | Single simplified character; normalize NFC; length 1 enforced in app. |
| `reading` | `text` NULL | Optional accented Pinyin / bank-aligned reading. `NULL` means “any reading for this character”; non-NULL means this row only targets that `character + reading` unit. |
| `priority` | `integer` NOT NULL DEFAULT 0 | Lower = higher priority. |
| `label` | `text` | Human-readable UI tag such as `第二学期听写`. |
| `source` | `text` | Optional machine / analytics source tag. |
| `note` | `text` | Optional internal note; not shown in game. |
| `active` | `boolean` NOT NULL DEFAULT true | Soft-disable without delete. |
| `expires_at` | `timestamptz` NULL | If set and expired, row is ignored. |
| `created_at` | `timestamptz` NOT NULL DEFAULT `now()` | |
| `updated_at` | `timestamptz` NOT NULL DEFAULT `now()` | |

**Uniqueness rule:** one priority row per user per target, enforced with **`UNIQUE NULLS NOT DISTINCT (user_id, character, reading)`** so `reading = NULL` behaves as a single character-wide fallback row per character per user.

**Indexes:**

- `(user_id, active)` WHERE `active`
- Optional: `(user_id, character, reading)` WHERE `active`
- Optional: `(user_id, priority)`

**RLS:** same policy pattern as `pinyin_recall_unit_bank`: users may only read/write rows where `user_id = auth.uid()` (or service role for admin scripts).

### 4.2 Backend changes

#### 4.2.1 Population paths (Emma / operators)

Priority rows are populated in v1 by **backend scripts only**. There is no UI or write API path in scope.

#### Input sources

The script should accept either of these operator-managed inputs:

- a **character-level list**, such as the corrected `176` missing characters from [p4_4a_dictation_2026_category_ii.md](../../../../ai_study_buddy/docs/notes/p4_4a_dictation_2026_category_ii.md)
- a **reading-level list**, such as the missing `character + reading` pairs derived from [p4_4a_dictation_2026_category_ii_readings.json](../../../../ai_study_buddy/docs/notes/p4_4a_dictation_2026_category_ii_readings.json)

The normalized ingest shape should be:

- `character`
- optional `reading`
- `priority`
- optional `label`
- optional `source`
- optional `expires_at`
- optional `active`

#### Script behavior

Recommended script shape: `upsert_user_prioritized_characters.py`

Required arguments:

- `--user-id`
- exactly one input source, such as `--json-file <path>` or `--items-file <path>`
- exactly one write mode: `--merge` or `--replace`

Optional arguments:

- `--label`
- `--source`
- `--priority-start`
- `--expires-at`
- `--dry-run`

The script should:

1. load and normalize the input rows into `character` plus optional `reading`
2. validate that each `character` is length 1
3. validate any provided `reading` against the character bank for that character
4. assign deterministic priority ordering if the source file does not already provide one
5. apply optional defaults such as shared `label` / `source`
6. write rows transactionally
7. print a concise summary of inserted, updated, skipped, and invalid rows

#### Merge and replace semantics

- **Merge:** upsert on `(user_id, character, reading)`, with `reading = NULL` treated as a real dedupe target. Rows not mentioned by the input remain unchanged.
- **Replace:** delete all rows for the target user, then insert the normalized input in one transaction.

#### Expected operator workflows

- **Character-first workflow:** generate a missing-character list from the category (ii) note, then import it as character-wide priorities.
- **Reading-aware workflow:** generate missing `character + reading` pairs from the reading-level artifact, then import them as reading-specific priorities where polyphonic precision matters.

**Future UI** remains out of scope for v1.

#### 4.2.2 Queue implementation (`build_session_queue`)

#### 4.2.2.1 New-item flow (`build_session_queue`)

1. Load `prioritized_characters` for the `user_id`.
2. Build the normal `new_items` as today.
3. Build a **priority override set** of eligible prioritized units that are not already in `new_items`.
4. Combine them into `new_items_effective`, deduped by `unit_id`.
5. Split into:
   - `new_items_priority`
   - `new_items_rest`
6. Shuffle `new_items_rest` only.
7. Fill `new_queue` from `new_items_priority + new_items_rest`.

#### 4.2.2.2 Candidate-window override

Priority is allowed to override the normal `[zibiao_min, zibiao_max_effective]` window for explicit 新字 targets. An out-of-window target may still enter the override set if it:

- is `recall_enabled`
- has no existing bank row for that unit
- is not already placed in the current batch
- is not duplicated by another matching priority row

This override applies only to the explicit targets, not to neighboring non-priority units.

#### 4.2.2.3 Caps and fairness

- `n_new_slots` does not increase.
- Override items compete within the existing 新字 budget.
- Rescue / Consolidation / Expansion recipes remain unchanged.
- An optional guard such as `max_priority_new_per_batch` can be added later if repetition becomes an issue.

#### 4.2.2.4 Due / 巩固 / 重测 ordering boost

Weak banked items should rank earlier within the existing due pools when they also match a priority row:

- eligibility: active priority row match plus weak score, initially `score < PROFILE_PROFICIENCY_MIN_SCORE`
- mastered items are not boosted in v1
- ordering uses a composite key that prefers:
  - boosted over non-boosted
  - lower priority rank over higher
  - reading-specific match over character-wide match
  - then the current pool-specific secondary sort

This changes ordering only; it does not create extra review slots.

#### 4.2.3 Session payload, label resolution, and logging

Queued items may carry:

- `priority_label` (string | null)
- optional `priority_source`
- analytics flags such as `from_user_priority`

`priority_label` is resolved at session-build time by matching the queued unit’s `character` (and, when present, `reading`) against the user’s **active** `user_prioritized_characters` rows. If both a character-wide row and a reading-specific row match the same unit, the reading-specific row supplies the label/source.

---

### 4.3 Frontend changes

#### 4.3.1 UI chip for “where priority came from” (`priority_label`)

- When `item.priority_label` is a non-empty string, render a chip next to the existing category tag (新字 / 巩固 / 重测) and the 多音字 (polyphonic) chip.
- Styling: render as a secondary/neutral badge so the learning-state tag stays visually primary.
- Security: treat the label as plain text (no HTML injection).

---

### 4.4 Testing plan

**Goals:** (a) **Regression** — empty priority list, feature flag off, or missing table path behaves like **today** (same slot counts, same item multiset modulo shuffle where applicable). (b) **Correctness** — ordering, labels, and session payload semantics match §4.2.2–§4.2.3. (c) **Safety** — no cross-user data in session or script-driven workflows.

**1. `build_session_queue` (unit tests, `backend/tests/`)**

Prefer **deterministic** fixtures: fix RNG seed where the implementation shuffles `new_items_rest`, or stub shuffle, so order assertions are stable.

| Area | What to assert |
|------|----------------|
| **Baseline** | `prioritized_characters=[]` (or `None`) → item order / categories match pre-change golden tests; extend `test_reading_unit_contract.py` or add `test_pinyin_recall_user_priority_queue.py`. |
| **新字 front-load (§4.2.2.1)** | Given several 新字 candidates and a priority list `[A, B]`, the **first** `n_new_slots` 新字 drawn from the combined eligible set should list **all eligible priority targets before** non-priority characters (respecting per-character-row at-most-one-unit v1 rule for character-wide rows). |
| **Priority order** | Lower `priority` integer appears **before** higher among 新字 that are all priority-eligible. |
| **`reading_rank` (polyphonic)** | For one character-wide priority row with multiple units in `new_items`, the unit chosen matches documented v1 rule (first by `reading_rank`). |
| **Reading-specific override** | For one reading-specific row (e.g. `乐 + yuè`) and one character-wide row (`乐 + NULL`), the reading-specific row matches only that unit and wins for ordering / label resolution on that unit. |
| **Rescue / small `n_new_slots`** | With `n_new_slots=1` or `2`, if multiple priorities are eligible, only the **front** of the priority-ordered list can appear; no extra 新字 slots. |
| **Priority override outside pool** | Priority target **outside** zibiao band can still appear as 新字 via the override path if it passes safety checks; no duplicate `unit_id`; slot counts unchanged. |
| **Already banked** | Priority character with **existing** bank row for that unit must **not** appear in 新字 queue; may appear in **due** portion only. |
| **Inactive / expired** | Rows with `active=false` or `expires_at < now` (as loaded by `get_user_prioritized_characters`) are **ignored** for ordering and `priority_label`. |
| **`priority_label` (§4.2.3)** | For each emitted item whose unit matches an active priority row with non-empty `label`, `item["priority_label"]` equals trimmed `label`; null or omitted when no row, empty label, or non-priority item. |
| **掌握 / strong due** | Due item with `score ≥ 20` is **not** given priority **boost** (§4.2.2.4); order among mastered peers unchanged by boost key. |
| **Weak + prioritized due (§4.2.2.4)** | In `due_hard` (and each boosted pool you implement), construct two units with **same score** (or same tie-breaking key); the one whose character is prioritized sorts **before** the other. Secondary sort (e.g. score asc, `next_due`) preserved **within** boost vs non-boost buckets. |
| **Slot counts** | Total counts per batch mode (Expansion / Consolidation / Rescue) unchanged vs baseline for the same inputs except priority ordering. |

**2. Data layer & ingestion script**

| Area | What to assert |
|------|----------------|
| **`get_user_prioritized_characters`** | Returns rows ordered by `priority ASC, created_at ASC`; filters `active` and expiry as specified; preserves `reading = NULL` vs explicit reading. |
| **Script merge** | Upsert updates `label`/`source`/etc.; rows **not** in payload **unchanged**; wrong `user_id` never updated. |
| **Script replace** | All rows for user deleted then inserted; **transaction** — simulated failure leaves prior state (if you add a test hook or use a test DB). |
| **Validation** | Reject non–length-1 `character`, overlong `label`, control characters, and invalid `reading` values not found in the character bank for that character; script errors should be deterministic and easy to diagnose. |
| **RLS** | Integration or SQL test: user A cannot read/write user B’s rows (mirror `pinyin_recall_unit_bank` tests if present). |

**3. Session HTTP (`/api/games/pinyin-recall/session`, `next-batch`)**

| Area | What to assert |
|------|----------------|
| **JSON contract** | Every item in the response includes `priority_label` key when implemented (value `null` or string); frontend does not break on `null`. |
| **Auth** | Unauthenticated / wrong user: no leak of another user’s priorities in items (session built only for authenticated self). |
| **Dev bypass** | If `PINYIN_RECALL_DEV_USER` is used in tests, priority load uses the same `user_id` as bank rows. |

**4. Frontend (`PinyinRecall.jsx`)**

| Area | What to assert |
|------|----------------|
| **Chip visibility** | When `priority_label` is a non-empty string, chip renders **after** category and 多音字 chips; when `null`/missing, no extra chip. |
| **Escaping** | Label text rendered as **text**, not HTML (no XSS if label contained markup — should be rejected at API, but defense in depth in UI). |
| **Layout** | Small viewport: chips wrap or scroll without overlapping the prompt (smoke via Playwright if E2E exists). |

**5. Logging / analytics (optional in v1)**

- `pinyin_recall_item_presented` now carries serve-time `from_user_priority`, `priority_label`, and `priority_source`; keep a regression test or migration check that the insert path preserves those values when the presented item had them.

**6. Manual QA checklist (pre-release)**

- [ ] User with **no** priority rows: game indistinguishable from production today.  
- [ ] User with list: 新字 batch shows prioritized characters earlier; chip shows 第二学期听写 (or test label).  
- [ ] Polyphonic prioritized character: only one unit per batch (v1).  
- [ ] Merge then replace: list matches expected after each operation.

**Feature flag (optional):** `PINYIN_RECALL_PRIORITY_ENABLED=1` for safe rollout — add tests for **flag off** (loader returns empty list or `build_session_queue` skips priority branches).

---

## 5. Success metrics

- **Coverage:** % of active priority characters that receive a **first** `pinyin_recall_unit_bank` row within N days of being added.
- **Engagement:** session completion rate when priority list non-empty vs empty (holdout).
- **School alignment:** user-reported or measured dictation performance (long-term; optional).

---

## 6. Risks and mitigations

| Risk | Mitigation |
|------|------------|
| Priority list huge → boring or repetitive 新字 | Cap per batch; expiry; semester `source` rotation; consider limiting out-of-window override count per batch if needed. |
| Polyphonic: character-wide row may still train the “wrong” reading first | Reading-specific rows are now supported; character-wide rows fall back to `reading_rank` only when no reading-specific target is supplied. |
| Priority override bypasses normal pacing too aggressively | Override only explicit priority targets, keep existing 新字 slot caps, and monitor usage / completion metrics. |
| Stale lists | `expires_at`; UI “clear list” later. |
| Due boost over-tilts session | Only **reorder** within existing slot budgets; optional cap on “boosted” items per batch later if needed. |

---

## 7. Resolved decisions & remaining open items

| # | Topic | Decision |
|---|--------|----------|
| 1 | **Merge vs replace** on bulk import | **Both** supported: **merge** = upsert payload only; **replace** = delete all rows for user then insert payload (transaction). Backend scripts support the same modes (§4.2). |
| 2 | **Per-family vs `user_id`** | **`user_id` only.** Each signed-in learner has their own list (e.g. Emma vs Winston). No shared family-level table in v1. |
| 3 | **Integration with AI Study Buddy** or GoodNotes exports (automatic list refresh) | **Not yet** — no integration in this proposal; lists are populated manually, via script, or via future API. Revisit when cross-product flows are defined. |
| 4 | **巩固 / due-queue boost** for prioritized characters that **already have** a bank row but are **weak** (e.g. `score < 10`) | **Yes** — give them **earlier placement** within the same due pools (**难字 / 普通在学字 / optionally 普通已学字**), without changing slot counts. Details in §3.2.3 / §4.2.2.4. |
| 5 | **In-game tag for “where priority came from”** | **Yes** — store human **`label`** per row (e.g. 第二学期听写); session JSON exposes **`priority_label`**; UI shows a chip **next to** 新字/巩固/重测 and 多音字 (`PinyinRecall.jsx`, §3.3.1 / §4.3.1). |

---

## 8. Summary

Adding **`user_prioritized_characters`** personalizes Pinyin Recall in three ways: new-item emphasis, earlier review of weak prioritized units, and clearer in-game signaling for why an item is being surfaced. The model is hybrid: priorities are still scoped to `user_id`, but each row may be either character-wide or reading-specific. Active Load and per-mode slot totals stay unchanged aside from ordering / pick. Writes support merge and replace through backend scripts. AI Study Buddy / GoodNotes auto-import remains not yet (§7). Deliverables: table with optional `reading` and `label`, queue integration, frontend chip, tests, and script support.
