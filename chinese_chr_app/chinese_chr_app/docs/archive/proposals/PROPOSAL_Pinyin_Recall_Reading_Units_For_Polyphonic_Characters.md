# Proposal: Reading-Level Units for Polyphonic Characters in Pinyin Recall

**Status:** Implemented  
**Date:** 2026-03-24  
**Revisited:** 2026-03-27  
**Issue:** #32 — `[Chinese character app] Polyphonic characters should be split into multiple "characters"`

> Update (2026-03-27): Since this proposal was drafted, the source data has gained
> structured per-reading buckets for the main pinyin-recall content sources:
> Feng `WordsByPinyin`, HWXNet `常用词组按拼音` / `common_phrases_by_pinyin`,
> and HWXNet `英文解释按拼音` / `english_translations_by_pinyin`.
> That means the main prerequisite data modeling is now complete. The remaining
> gap is mostly in the pinyin-recall runtime model, which still treats the
> learning unit as `character` and still flattens those structured fields back
> into character-level prompts and feedback.

---

## 1. Problem

Today the pinyin-recall game uses **written character** as the atomic unit.

- The per-user learning state is keyed by `character` in `pinyin_recall_character_bank`.
- The answer key is `get_correct_pinyin(hwxnet_entry)`, which currently means **"use the first pinyin in HWXNet"**.
- Stem words are built by `get_stem_words(...)`, which currently pulls from Feng words plus HWXNet examples/common phrases across the character as a whole.

That works for monophonic characters, but it creates a real mismatch for polyphonic characters:

- the **question is scored against one reading only** (usually the first one), while
- the **context words can come from a different reading**.

This is not just a theoretical edge case. It is visible in live data.

### Real examples from the live database

#### `和`

- Current correct choice: `hé`
- Current generic stems from the live DB: `和了`, `暖和`, `和谐`, `和泥`, `和平`

Those stems span multiple readings:

- `和|hé` -> `和谐`, `和平`
- `和|hú` -> `和了`
- `和|huó` -> `暖和`
- `和|huó` / `和|huò` -> `和泥`

So the current single-unit model can ask for `hé` while showing stems that point
to `hú`, `huó`, or `huò`.

#### `行`

- Current correct choice: `xíng`
- Current generic stems from the live DB: `爬行`, `进行`, `品行`, `横行`, `行业`

Those stems are not one reading:

- `行|xíng` -> `爬行`, `进行`, `品行`
- `行|xíng` -> `横行`
- `行|háng` -> `行业`

So the learner is being tested on one pronunciation while seeing hints from another.

#### `累`

- Current correct choice: `lèi`
- Current generic stems from the live DB: `积累`, `累计`, `受累`, `劳累`, `累赘`

Those stems span different readings:

- `累|lěi` -> `积累`, `累计`
- `累|lèi` -> `受累`, `劳累`
- `累|léi` -> `累赘`

The current model collapses all three into one score and one schedule.

#### `参`

- Current correct choice: `cān`
- Current generic stems from the live DB: `党参`, `参照`, `参观`, `参加`, `人参`

Those stems span different readings:

- `参|cān` -> `参照`, `参观`, `参加`
- `参|shēn` -> `党参`, `人参`

So the current model can ask for `cān` while still showing stems that point to
the herbal / noun reading `shēn`.

---

## 2. Live DB Findings

Stats below were queried from the real Supabase/Postgres database on
**2026-03-27** using:

- `backend/scripts/utils/query_polyphonic_character_stats.py`

### 2.1 Character-pool impact

- Total HWXNet characters: **3664**
- Polyphonic characters (>1 distinct pinyin): **424** (**11.57%** of the pool)
- Polyphonic characters also in the Feng set: **366** (**86.32%** of polyphonic chars)
- Reading-level units for those 424 characters: **904**
- Extra learning units vs current character-only model: **480**

If we fully split all polyphonic characters into reading-level units, the pinyin-recall pool would grow from:

- **3664 character units** -> **4144 reading units**

That is a **13.10%** increase in total learnable units.

### 2.2 Distribution by number of readings

- 2 readings: **377** characters
- 3 readings: **39**
- 4 readings: **7**
- 5 readings: **1**

Average readings per polyphonic character: **2.13**

### 2.3 Current learner-data impact

Current `pinyin_recall_character_bank` rows on polyphonic characters:

- Bank rows: **572**
- Users affected: **9**
- Distinct polyphonic characters already seen by learners: **305**
- Expanded bank rows if split by reading: **1211**
- Extra bank rows if split by reading: **639** (**+111.71%** vs current polyphonic bank rows)

Current `pinyin_recall_item_answered` rows on polyphonic characters:

- Answer rows: **2375**
- Users affected: **9**
- Distinct polyphonic characters answered: **305**

So issue #32 is not only about future data quality. The current learner history already contains a large amount of polyphonic-character activity.

### 2.4 Coverage and remaining edge cases

Here, **coverage** means **sample phrase coverage** for a `character + reading`
unit. `basic_meanings` is a narrower question: whether that reading is
explicitly represented in HWXNet `basic_meanings`.

Among the 424 polyphonic characters:

- **373** already have **>1 reading** explicitly represented in `basic_meanings`
- **50** have only **1 reading** tagged in `basic_meanings`
- **1** has **0** reading-tagged senses

This is now a secondary caution, not the main blocker. The important change
since the original draft is that the reading-specific source buckets now exist:
Feng `WordsByPinyin`, HWXNet `common_phrases_by_pinyin`, and HWXNet
`english_translations_by_pinyin`.

So the remaining work is mostly runtime modeling, not source-data invention:

- keep the target unit as `character + reading`
- consume the existing reading-specific buckets directly
- use a small override / curation layer for incomplete or non-recall-ready cases

In short: sample phrase coverage is mostly in place, while `basic_meanings`
representation still needs cleanup around the edges.

---

## 3. Recommendation

For **pinyin recall only**, change the atomic unit from:

- **current:** `character`

to:

- **proposed:** `character + normalized_pinyin`

Important scope boundary:

- **Do change** the learning-unit model used by pinyin recall, scheduling, and logging.
- **Do not change** the app's main dictionary/search model. Search, radicals, stroke counts, and character detail pages should remain character-centric.

In other words:

- `hwxnet_characters` and `feng_characters` remain the source-of-truth content tables.
- pinyin recall gets a **derived reading-unit layer** on top of them.

This solves the actual issue without forcing the entire app to pretend that `行|xíng` and `行|háng` are separate dictionary characters.

### 3.1 Recommended first implementation slice

This is the short version of the rollout sequencing described later in
Section 7. To reduce risk, the first implementation should focus on
**content correctness** before full learner-history migration:

1. Build one derived reading-unit helper layer from the current content tables.
   This can start in-memory / in-code before we commit to a physical derived
   table.
2. Use that helper to produce merged reading-specific prompt payloads using:
   `WordsByPinyin` -> `common_phrases_by_pinyin` -> reading-matched
   `basic_meanings`, plus `english_translations_by_pinyin` for feedback glosses.
3. Validate those payloads on real characters and confirm the runtime no longer
   leaks cross-reading stems or glosses.
4. Only after that content layer is stable, add new unit-keyed bank / answer
   tables and migrate learner progress and reporting.

In rollout-plan terms, this means:

- first complete the contract/content/runtime work in Phases 0-2
- then do persistence and reporting migration in Phases 3-4

This keeps the first milestone narrow:

- correct unit identity
- correct answer key
- correct stem selection
- reading-specific English gloss selection
- explicit `recall_enabled` handling for fringe readings

---

## 4. Proposed Recall-Unit Contract

This section defines the **target recall-unit shape** that pinyin recall should
consume once the atomic item becomes `character + reading`.

Important clarification:

- this is the logical contract that runtime behavior, stored learner state, and
  reporting should agree on
- it does **not** require a physical `pinyin_recall_reading_units` table on day 1
- we can first derive these units in code / memory, then decide later whether a
  dedicated derived table is worth materializing

### 4.1 Target derived unit shape

If we do materialize the unit layer, a natural table name would be
`pinyin_recall_reading_units`. But even before that, the runtime should behave
as if this structure exists.

Suggested fields:

| Column | Purpose |
|--------|---------|
| `unit_id` | Stable PK, e.g. `行|xing2` |
| `character` | Hanzi, e.g. `行` |
| `reading_display` | Tone-mark pinyin for UI, e.g. `xíng` |
| `reading_key` | Normalized pinyin key, e.g. `xing2` |
| `reading_rank` | Stable per-character reading order, usually from HWXNet `拼音` order unless overridden for curation |
| `is_primary` | Whether this unit is the character's designated default reading for migration / continuity purposes; initially this will usually be the `reading_rank = 1` unit |
| `recall_enabled` | Whether this reading should appear in pinyin recall |
| `enable_reason` | `auto`, `manual_override`, `disabled_rare`, `disabled_incomplete`, etc. |
| `basic_meanings` | Reading-specific meanings only |
| `english_translations` | Reading-specific English glosses only |
| `example_words` | Reading-specific stems/examples only |
| `source_character_index` | Optional Feng index / linkage back to source character |

In other words, this section is specifying the shape of one recall unit, not
yet mandating how aggressively it must be persisted physically.

Optional tooling note:

- CC-CEDICT may still be useful as an offline curation aid for unresolved
  readings, but it should not be treated as a core runtime dependency for this
  proposal now that the app already has a curated structured English field.

### 4.2 Why a derived unit layer is better than duplicating character rows

We should **not** duplicate `hwxnet_characters` or `feng_characters` into multiple physical "characters".

That would make dictionary/search semantics messy and would over-couple the learning model to the rest of the app.

Instead, we should introduce a derived recall-unit layer:

- keep character tables as they are
- derive recall units for learning
- store only recall-specific, reading-specific fields in the new table

That derived layer may initially live:

- in backend helper code
- in unit-aware session payloads
- in new unit-keyed bank/log tables

and only later, if useful, in a dedicated `pinyin_recall_reading_units` table

This keeps the data model honest:

- search/dictionary = character-centric
- pinyin recall = reading-centric

### 4.3 Normalize IDs, not display strings

The primary key should use a normalized numeric form, not raw tone marks:

- `和|he2`
- `行|xing2`
- `行|hang2`
- `累|lei3`

Display should still use the tone-mark form from the source data.

This avoids Unicode-key issues and matches the existing pinyin-normalization logic already used elsewhere.

### 4.4 Existing learner state and event logs must also move to the reading unit

Changing the prompt unit from `character` to `character + reading` is not only a
content-model change. It also changes the identity of the item being scheduled,
scored, and logged.

Required contract:

- learner state must be keyed by `(user_id, unit_id)`, not `(user_id, character)`
- presented and answered events must be attributable to exactly one `unit_id`
- reporting and analytics must treat `unit_id` as the authoritative recall-item
  identity after cutover
- `character` may still be stored alongside `unit_id` for UI and reporting, but
  it is no longer the learning-state key

The migration strategy, schema changes, and historical backfill rules belong in
the rollout plan in Section 7.

---

## 5. Risks and Trade-offs

### 5.1 More units means more surface area

Splitting 424 characters into 904 reading units increases content and scheduling complexity.

Mitigation:

- `recall_enabled`
- override layer
- phased rollout

### 5.2 Not every source reading should become a recall unit automatically

The current source data is much stronger than when this proposal was first
drafted, but that does not mean every raw reading in `拼音` should immediately
become a learner-facing recall unit.

Some readings will still be weaker on one or more dimensions:

- stem coverage is thin or overly marginal
- `basic_meanings` support is incomplete
- the reading is real but low-value for recall
- the reading exists in source data but needs explicit curation before it becomes
  a good prompt

Mitigation:

- keep source tables unchanged
- use a derived recall-unit layer with manual overrides
- do not require every raw reading to be recall-enabled on day 1

### 5.3 Historical continuity is imperfect

Old character-level history cannot be split perfectly by reading.

Mitigation:

- migrate polyphonic history only to the primary unit
- keep old tables for legacy analytics / audit

---

## 6. Prompt Construction Rules

Once the unit becomes `character + reading`, the prompt builder should follow these rules.

### 6.1 Correct answer

Correct answer should be:

- `reading_display` for the selected reading unit

not:

- `first pinyin in hwxnet_characters`

### 6.2 Stem-word selection

Stem words must be reading-specific.

Recommended priority:

1. Feng `WordsByPinyin` phrases matching this reading
2. HWXNet `常用词组按拼音` / `common_phrases_by_pinyin` phrases matching this reading
3. Reading-tagged HWXNet `例词` from `basic_meanings` matching this reading
4. Reading-tagged override words for incomplete entries
5. No stems at all

Preferred generation logic:

1. Start with the reading's Feng `WordsByPinyin` bucket, if present.
2. Append the matching HWXNet `常用词组按拼音` bucket.
3. Append reading-matched HWXNet `basic_meanings` `例词`.
4. De-duplicate while preserving first-seen order.
5. For the actual recall prompt, show the first **3** words from the merged list
   (matching the current `get_stem_words(..., max_words=3)` behavior).

Rule:

- **Never show a stem that points to another reading of the same character.**

This is more important than always having 3 example words.

Source policy:

- if a phrase is already bucketed in `WordsByPinyin`, use that structured mapping directly
- then append any additional phrases from the matching
  `common_phrases_by_pinyin` bucket
- then append any additional phrases tied to the reading in HWXNet
  `basic_meanings`
- if a remaining source phrase is not covered by any of those paths, keep it
  out of recall prompts until curated

### 6.3 Distractors

Distractors should continue to exclude other readings of the same character from the wrong choices.

The learner should be asked:

- "For this reading-context of `行`, which pinyin is correct?"

not:

- "Pick between `xíng` and another valid reading of the same character."

### 6.4 Feedback screen

On answer feedback:

- highlight the tested reading first
- show only the English glosses for that tested reading
- optionally show "other readings" as secondary information

For example:

- `行`
- **This question's reading:** `háng`
- Other readings: `xíng`

That teaches the distinction without collapsing the score/state again.

English-gloss rule:

- do not show a character-level mixed English list on a reading-specific result
  card
- if the tested reading lacks curated English glosses, prefer no English gloss
  over a wrong cross-reading gloss

### 6.5 Worked examples

All examples below use the same stem-generation rule:

- `WordsByPinyin`
- then `常用词组按拼音` / `common_phrases_by_pinyin`
- then reading-matched `basic_meanings`
- de-duplicate in first-seen order
- show the first `3` merged items in the current recall UI

| Character | Reading unit | New prompt stems | Notes |
|--------|--------|--------|--------|
| `和` | `和|he2` (`hé`) | `和平`, `和谐`, `和解` | Separates the common `hé` reading from sibling readings that currently leak into the prompt. |
| `和` | `和|he4` (`hè`) | `一唱一和`, `曲高和寡`, `和诗` | Shows a distinct literary reading that should not be merged into `hé`. |
| `和` | `和|huo2` (`huó`) | `和面`, `和泥`, `暖和` | Keeps the verb/adjectival reading-specific evidence together. |
| `和` | `和|huo4` (`huò`) | `和弄`, `和药`, `奶里和点儿糖` | Another distinct prompt unit, even if not all such readings are recall-enabled on day 1. |
| `和` | `和|hu2` (`hú`) | `和了`, `和牌` | Good example of a domain-specific reading that the model can represent separately. |
| `行` | `行|xing2` (`xíng`) | `行动`, `行走`, `进行` | Fixes the current problem where `银行` can appear under the `xíng` question. |
| `行` | `行|hang2` (`háng`) | `行列`, `行业`, `银行` | Keeps trade/row/profession evidence out of the `xíng` unit. |
| `乐` | `乐|le4` (`lè`) | `乐观`, `快乐`, `欢乐` | Clean split between the “happy” reading and the music reading. |
| `乐` | `乐|yue4` (`yuè`) | `乐队`, `音乐`, `乐曲` | Should not leak into the `lè` prompt. |
| `累` | `累|lei4` (`lèi`) | `劳累`, `受累`, `累死累活` | Keeps the “tired” reading distinct. |
| `累` | `累|lei2` (`léi`) | `累赘`, `果实累累`, `累臣` | Keeps the “cumbersome / piled up” reading distinct. |
| `累` | `累|lei3` (`lěi`) | `积累`, `累计`, `日积月累` | Keeps the “accumulate” reading distinct. |
| `参` | `参|can1` (`cān`) | `参照`, `参加`, `参与` | High-frequency school usage should be separated from the noun and literary readings. |
| `参` | `参|shen1` (`shēn`) | `人参`, `党参`, `参商` | Distinct noun/medicine reading. |
| `参` | `参|cen1` (`cēn`) | `参差不齐`, `参差`, `参错` | Good example of a reading that may need explicit `recall_enabled` judgment. |
| `琢` | `琢|zhuo2` (`zhuó`) | `琢磨`, `琢石`, `雕琢` | Shows that a phrase can legitimately belong to more than one reading bucket. |
| `琢` | `琢|zuo2` (`zuó`) | `琢磨` | The same phrase may appear here too without being considered a bug. |
| `啊` | `啊|a1` (`ā`) | `啊呀`, `啊哟`, `啊哈` | Demonstrates discourse-particle readings rather than lexical senses. |
| `啊` | `啊|a2` (`á`) | `啊，你说什么？` | Sentence snippets may be the best reading-specific cues. |
| `啊` | `啊|a3` (`ǎ`) | `啊，这事怎么了？`, `啊，这是怎么回事？` | Another discourse reading that likely needs product judgment before enablement. |
| `啊` | `啊|a4` (`à`) | `啊，亲爱的祖国！`, `啊，好吧！`, `啊，我这才明白过来！` | Example of why source cleanliness alone does not decide recall usefulness. |

---

## 7. Detailed Rollout Plan

This change touches four coupled surfaces:

- recall-unit content derivation
- pinyin-recall session/runtime payloads
- persistent learner state and logs
- profile/progress reporting and category UI

So the implementation should be staged deliberately rather than merged as one
large switch.

### 7.1 Phase 0: Freeze the unit contract

Before changing runtime behavior, define the reading-unit contract clearly.

Required outputs for each recall-enabled unit:

- `unit_id`
- `character`
- `reading_key`
- `reading_display`
- `reading_rank`
- `is_primary`
- `recall_enabled`
- `enable_reason`
- reading-specific `stem_words`
- reading-specific `english_translations`
- reading-specific `basic_meanings`

Field clarifications:

- `reading_rank` is a stable ordering field within one character's readings. It
  should usually follow HWXNet `拼音` order, unless an explicit override layer
  changes that order for curation reasons. Its main jobs are deterministic unit
  generation, deterministic UI ordering, and giving migration logic a stable
  fallback order.
- `is_primary` marks the one reading unit that should act as the character's
  default / continuity target when legacy character-level learner state must map
  to exactly one unit. On the first implementation pass, this will usually mean
  the same unit as `reading_rank = 1`, but it is defined separately so we can
  preserve source order while still overriding the migration/default target if
  needed later.

Required product invariant:

- every pinyin-recall question, answer update, and progress count must be
  attributable to exactly one `unit_id`

Definition-of-done for this phase:

- a single backend helper can build a stable reading-unit payload for any HWXNet
  character
- that helper is the canonical contract source for later runtime / persistence /
  profile work, so downstream phases do not redefine unit fields independently
- the helper returns a deterministic payload shape with at least:
  `unit_id`, `character`, `reading_key`, `reading_display`, `reading_rank`,
  `is_primary`, `recall_enabled`, `enable_reason`, `stem_words`,
  `english_translations`, and `basic_meanings`
- the helper uses structured per-reading sources first and does not flatten them
  back to character-level prompts
- a small gold-set verification fixture covers real polyphonic examples such as
  `和`, `行`, `乐`, `长`, or `累`, and confirms:
  stable `unit_id` ordering, no cross-reading stem leakage, and reading-specific
  gloss/basic-meaning selection
- if two engineers implement Phase 1 or Phase 2 against the helper, they should
  get the same unit identity and payload shape without separately debating field
  semantics

### 7.2 Phase 1: Build the reading-unit content layer

Implement a backend helper or builder that derives recall units from current
source tables / JSON. The content it produces should follow the prompt
construction rules defined in Section 6, especially the stem-selection and
English-gloss rules.

Input sources:

- HWXNet `拼音`
- HWXNet `basic_meanings`
- HWXNet `common_phrases_by_pinyin`
- HWXNet `english_translations_by_pinyin`
- Feng `WordsByPinyin`
- manual override / curation config for `recall_enabled`

Expected behavior:

- monophonic characters yield one unit
- polyphonic characters yield one unit per enabled reading
- stems are merged per reading
- glosses are selected per reading
- disabled readings remain visible in debug/admin output but are excluded from
  the recall pool

Suggested verification work:

- snapshot real examples like `和`, `行`, `乐`, `长`, `累`
- verify that no unit leaks stems from a sibling reading
- verify that glosses match the tested reading only
- verify that `unit_id` is stable across rebuilds

Definition-of-done for this phase:

- the backend can produce a full in-memory pool of recall-enabled reading units
- the total enabled unit count is known and can be exposed for reporting

### 7.3 Phase 2: Make the pinyin-recall session API unit-aware

Change queue building and prompt construction to operate on units instead of
characters. This phase is where the runtime should fully adopt the prompt
construction rules in Section 6.

Backend changes:

- replace character-based candidate selection with unit-based candidate selection
- build distractors against the tested reading unit
- exclude sibling readings of the same character from distractors
- emit session items keyed by `unit_id`

Session payload should include:

- `unit_id`
- `character`
- `correct_pinyin`
- `all_pinyin` or `other_readings`
- reading-specific `stem_words`
- reading-specific `meanings`
- `is_polyphonic`
- existing category/batch metadata

Frontend pinyin-recall changes:

- treat the session item as a reading unit even if the main visual headline is
  still the Hanzi
- show the tested reading on result screens as the primary answer identity
- keep other readings secondary
- update the correct-answer and incorrect-answer screens to consume
  reading-specific English meanings for the tested unit, rather than the
  current flattened character-level meaning list
- preserve the current "多音字" affordance, but make the card explicitly about
  one tested reading

Definition-of-done for this phase:

- a live session can ask `行|háng` and `行|xíng` as two different questions
- correct-answer and incorrect-answer screens show only the tested reading's
  English meaning / gloss content
- feedback screens are internally consistent for the tested reading

Practical verification checklist:

- the session API emits unit-aware items with `unit_id`, reading-specific
  `correct_pinyin`, reading-specific `stem_words`, and reading-specific
  `meanings`
- for a polyphonic character such as `行`, the runtime can emit both `行|xíng`
  and `行|háng` as separate items
- the `xíng` item never shows `银行`, and the `háng` item never shows `行动`
- wrong-answer feedback is built from the tested unit, not from the
  character-level first reading
- sibling readings of the same character are excluded from distractors
- the frontend can submit `unit_id` back to the answer endpoint and render the
  tested reading as the primary answer identity on feedback screens

### 7.4 Phase 3: Introduce unit-keyed persistence

Add new persistence structures for reading-unit learning state and logs.

Recommended target changes:

- new bank table keyed by `(user_id, unit_id)`
- presented log stores both `character` and `unit_id`
- answered log stores both `character` and `unit_id`
- report-error log stores nullable `unit_id`

Minimal required columns for the new bank table:

- `user_id`
- `unit_id`
- `character`
- `reading_key`
- `reading_display`
- `score`
- `stage`
- `next_due_utc`
- `first_seen_at`
- `last_answered_at`
- `total_correct`
- `total_wrong`
- `total_i_dont_know`

Migration tasks:

1. Create the new unit-keyed bank/log tables.
2. Backfill legacy character-bank rows to unit rows using a `primary_only`
   strategy: monophonic characters map to their sole unit, and polyphonic
   characters map only to the legacy-tested primary reading unit.
3. Backfill legacy `item_presented` rows with inferred `unit_id`, `reading_key`,
   and `reading_display` using `character + correct_choice`, with fallback to
   the current primary reading when the historical target reading no longer
   exists in the current unit builder.
4. Backfill legacy `item_answered` rows with inferred `unit_id`, `reading_key`,
   and `reading_display` by joining to the latest preceding
   `item_presented` row in the same `(user_id, session_id, character)`.
5. Switch all runtime writes to the new tables.
6. Stop reading from the old character-keyed bank in queue building.

Operational safety:

- create timestamped backup copies of every persistence table before any schema
  change or backfill write; this is a required migration step, not an optional
  precaution
- run dual-read or verification scripts during rollout
- do not delete legacy tables immediately after cutover

Definition-of-done for this phase:

- answering a question updates only one unit row
- no scoring or scheduling code still depends on `(user_id, character)` for
  recall state

### 7.5 Phase 4: Migrate profile/progress reporting to the unit denominator

After the game runtime is unit-aware, the Profile page and related analytics
must also move to the same denominator.

Current behavior:

- progress is reported against total character count
- category counts are grouped by character
- trend replay groups answer history per `(user_id, character)`

Target behavior:

- progress is reported against total enabled recall-unit count
- learned / learning / not-tested are counts of units
- category lists show unit-level entries
- daily trend replays unit history, not character history

Backend work:

- replace total character constant with total enabled unit count
- replace category-count queries with unit-based versions
- replace daily trend replay with unit-based grouping
- replace "characters by category" queries with unit-aware results

Frontend/Profile work:

- remove hardcoded `3664` fallback
- render `total_units` or equivalent backend-provided denominator
- update copy so the user understands that some polyphonic readings count
  separately
- category pages should render entries like `行（xíng）` and `行（háng）`, not
  one collapsed `行`

Recommended product copy adjustment:

- avoid saying only "汉字掌握度" if the denominator is now partly reading-based
- the implemented UI direction uses `读音掌握度` / `项` wording

Definition-of-done for this phase:

- Profile and pinyin-recall use the same denominator and the same unit identity
- a user's progress percentage changes only because the underlying pool changed,
  not because one screen is still character-based

Queue / scheduling note:

- if all eligible polyphonic readings become recall units, the effective pool
  grows by about **13.10%**
- queue and progression constants may need retuning later:
  batch new-count caps, Total Load thresholds, and zibiao/pool expansion heuristics
- do **not** bundle those retunings into the first implementation of issue #32;
  first ship correct unit identity, stems, answer keys, logging, and reporting,
  then measure whether queue pressure justifies new thresholds

### 7.6 Phase 5: Cutover and validation

Roll the change out behind a controlled cutover.

Recommended order:

1. Land reading-unit builder and verification scripts.
2. Land new unit-keyed tables and migration scripts.
3. Backfill legacy learner state.
4. Deploy runtime reads/writes against the unit model.
5. Deploy profile/progress changes.
6. Compare old vs new counts for a sample of users.
7. Keep legacy tables read-only for a safety window.
8. Confirm the Profile page, category pages, and trend charts now use the
   enabled reading-unit denominator while search/dictionary drill-down remains
   intentionally character-centric.

Validation checklist:

- sample users retain expected progress on old primary readings
- non-primary readings start as new units
- profile category counts sum to the total enabled unit denominator
- daily trend charts remain monotonic / plausible after replay migration
- pinyin-recall session mixes new units and due units correctly
- correct and incorrect answer pages no longer render flattened
  character-level English meanings for polyphonic units
- no frontend screen still assumes "one Hanzi = one recall item"
- post-cutover presented / answered / report-error rows all carry `unit_id`
- legacy presented / answered rows were backfilled successfully, with zero
  remaining null `unit_id` rows in those two tables
- runtime writes no longer depend on `pinyin_recall_character_bank`
- category pages list one tile per unit, while click-through remains
  character-centric by design

### 7.7 Final Implementation Decisions

Resolved implementation choices:

1. The user-facing denominator is `recall_enabled` units only.
2. The unit layer stays derived in code; no physical
   `pinyin_recall_reading_units` table was introduced in this rollout.
3. Category pages list one tile per unit, with the reading shown on the tile.
   Clicking still opens the character search/detail flow.
4. Legacy presented/answered logs were backfilled with inferred `unit_id`.
   `item_presented` used `character + correct_choice` with primary-reading
   fallback for pruned historical readings; `item_answered` used the latest
   preceding `item_presented` row in the same session and character.
5. The Profile UI now uses `读音掌握度` / `项` wording instead of presenting the
   denominator as purely character-based.

### 7.8 Final State Summary

After rollout, the shipped behavior is:

- pinyin recall runtime is keyed by `unit_id`
- learner state is stored in `pinyin_recall_unit_bank`
- `item_presented` and `item_answered` rows are fully backfilled with
  `unit_id`, `reading_key`, and `reading_display`
- profile/progress uses the enabled reading-unit denominator
- search and character detail remain intentionally character-centric

---
