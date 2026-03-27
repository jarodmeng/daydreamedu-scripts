# Proposal: Reading-Level Units for Polyphonic Characters in Pinyin Recall

**Status:** Proposed  
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

### 2.4 Remaining data-quality edge cases: source coverage is much better, but runtime still uses character-level behavior

Among the 424 polyphonic characters:

- **373** already have **>1 reading** explicitly represented in `basic_meanings`
- **50** have only **1 reading** tagged in `basic_meanings`
- **1** has **0** reading-tagged senses

This still matters for implementation, but it is now a **secondary caution**
rather than the main blocker. The situation has improved since the original
draft:

- Feng words now exist in a structured transition field: `WordsByPinyin`
- HWXNet common phrases now exist in a structured transition field:
  `常用词组按拼音` / `common_phrases_by_pinyin`
- HWXNet English glosses now exist in a structured transition field:
  `英文解释按拼音` / `english_translations_by_pinyin`

So the remaining caution is no longer "we must first invent reading-aware source
structure." Instead, it is:

- a reading-level model is still the right target, and
- we should now consume the existing structured buckets rather than flattening
  them back into character-level phrase and gloss lists.

We still need a small **override / curation layer** for incomplete cases,
especially where `basic_meanings` does not yet cover all readings cleanly,
where a structured bucket exists but should not yet be recall-enabled, or where
the runtime needs a cleaner per-reading interpretation than the raw source row
currently provides.

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

To reduce risk, the first implementation should focus on **content correctness**
before full learner-history migration:

1. Build one derived reading-unit helper layer from the current content tables.
   This can start in-memory / in-code before we commit to a physical derived
   table.
2. Use that helper to produce merged reading-specific prompt payloads using:
   `WordsByPinyin` -> `common_phrases_by_pinyin` -> reading-matched
   `basic_meanings`, plus `english_translations_by_pinyin` for feedback glosses.
3. Validate those payloads on real characters and confirm the runtime no longer
   leaks cross-reading stems or glosses.
4. Only after that content layer is stable, add new unit-keyed bank / answer
   tables and migrate learner progress.

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

- this is the logical contract the runtime, persistence layer, and reporting
  should agree on
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
| `reading_rank` | Order from HWXNet / override |
| `is_primary` | Whether this is the current first reading |
| `recall_enabled` | Whether this reading should appear in pinyin recall |
| `enable_reason` | `auto`, `manual_override`, `disabled_rare`, `disabled_incomplete`, etc. |
| `basic_meanings` | Reading-specific meanings only |
| `english_translations` | Reading-specific English glosses only |
| `example_words` | Reading-specific stems/examples only |
| `source_character_index` | Optional Feng index / linkage back to source character |

In other words, this section is specifying the shape of one recall unit, not
yet mandating how aggressively it must be persisted physically.

### 4.1.1 English meanings must also split by reading

The proposal should treat `english_translations` the same way it treats stems
and `basic_meanings`: for polyphonic recall units, the English glosses should be
bucketed by reading, not copied wholesale from the character row.

Why this matters:

- a single character-level English list often mixes senses from multiple readings
- English meaning is shown on the current correct-answer and incorrect-answer
  pages, so a reading-specific testing unit also requires reading-specific
  feedback content
- if we keep inherited mixed glosses, the feedback screen and future review UI
  will still leak cross-reading hints
- the reading-unit layer should stay internally consistent: one reading, one
  answer key, one stem set, one meaning/gloss bucket

Recommended derivation rule:

1. Prefer HWXNet `英文解释按拼音` / `english_translations_by_pinyin` as the
   primary source of learner-facing reading-specific English glosses.
2. Fall back to reading-matched HWXNet `basic_meanings` only when the structured
   English bucket is absent or intentionally empty.
3. Use manual override / curation for unresolved readings that should still be
   recall-enabled.
4. If a reading cannot yet be assigned a trustworthy English gloss bucket, leave
   `english_translations` empty for that unit and rely on the Hanzi + pinyin +
   stems until curated.

So for polyphonic characters, "inherited translations" should mean
"inherit the already-curated per-reading bucket when available," not "copy the
full character-level English list into every reading unit."

Recommended source priority for reading-level English:

1. HWXNet `english_translations_by_pinyin`
2. HWXNet reading-specific `basic_meanings`
3. Manual override / curation for unresolved cases
4. Existing app-level `英文翻译` only as a weak compatibility hint while legacy
   consumers still exist

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

Today the pinyin-recall persistence layer is character-keyed:

- `pinyin_recall_character_bank` uses `(user_id, character)` as the learning-state key
- `pinyin_recall_item_presented` logs `character`
- `pinyin_recall_item_answered` logs `character`
- queue/category analytics replay history per `(user_id, character)`

Once recall becomes reading-specific, those tables can no longer treat `行`
as a single learnable item. They need to key against the recall unit instead.

Recommended target shape:

- learner-state table: key by `(user_id, unit_id)` where
  `unit_id = character|reading_key`
- presented log: keep `character`, but also store `unit_id`, `reading_key`,
  and `reading_display`
- answered log: keep `character`, but also store `unit_id`, `reading_key`,
  and the tested `correct_reading`
- error-report log: keep `character`, but also store nullable `unit_id` so
  report triage knows which reading-specific prompt was shown

Important schema note:

- for the event-log tables, this is mostly an **additive schema change**
- for the learner-state table, this is **not only additive**, because the
  logical identity and primary key change from `(user_id, character)` to
  `(user_id, unit_id)`

In practice, that means we should either:

- create a new unit-keyed learner-state table, or
- add the new columns and then replace the old PK / uniqueness contract

The first option is safer and easier to audit during rollout.

Why keep both `character` and `unit_id`:

- `character` remains useful for joins, UI, and broad reporting
- `unit_id` is the real learning identity for scheduling and correctness
- storing both makes migration/debugging much easier than trying to recover the
  Hanzi from `unit_id` everywhere

### 4.4.1 Do not clone old character-bank state onto every reading

The old bank rows should **not** be copied wholesale to all derived reading
units for a polyphonic character.

Example of what we should avoid:

- old row: `(user_id, 行)` score `20`
- bad migration: create both `(user_id, 行|xing2)` score `20` and
  `(user_id, 行|hang2)` score `20`

That would incorrectly mark unseen readings as already learned.

The conservative migration rule should be:

- monophonic characters: migrate state directly to their sole reading unit
- polyphonic characters: migrate existing bank/history only to the
  **legacy-tested primary reading unit**, not to every reading
- other enabled readings for that character should start with no bank row yet
  (or an explicit untouched/new state, if we want rows materialized eagerly)

Why mapping to the primary reading is the least-wrong interpretation:

- the old runtime always scored the character against `get_correct_pinyin(...)`,
  which means the first HWXNet reading
- so existing bank score/stage/due state represents learner exposure to the
  old **primary-reading question**, even if the stems were sometimes noisy
- it does **not** represent mastery of the character's other readings

### 4.4.2 Recommended migration strategy for existing tables

Use a staged migration, not an in-place reinterpretation of the old tables.

1. Create new unit-keyed learner-state tables and add unit columns to the
   event-log tables.
2. Backfill monophonic rows directly to their sole unit.
3. Backfill polyphonic bank rows only to the current primary reading unit.
4. Leave other polyphonic reading units uninitialized until the learner actually
   encounters them in the new runtime.
5. Switch queue building, answer updates, category counts, daily trend replay,
   and progress analytics to the unit-keyed tables / unit-aware log columns.
6. Keep the old character-keyed tables as backup / audit history until the new
   flow has been verified in production.

Recommended concrete mapping for the bank table:

- source key: `(user_id, character)`
- target key: `(user_id, unit_id)`
- monophonic: `unit_id = character|sole_reading`
- polyphonic: `unit_id = character|current_primary_reading`
- copy across: `score`, `stage`, `next_due_utc`, `first_seen_at`,
  `last_answered_at`, `total_correct`, `total_wrong`, `total_i_dont_know`
- add migration metadata such as `migration_source = 'legacy_character_bank'`
  and `migration_strategy = 'primary_only'`

Recommended concrete schema direction:

- existing `pinyin_recall_character_bank` should not remain logically keyed by
  `(user_id, character)` once the runtime is unit-based
- the new learner-state table should be keyed by `(user_id, unit_id)` and keep
  `character`, `reading_key`, and `reading_display` as explicit columns
- existing event-log tables can keep `character`, but should gain `unit_id`
  and reading columns so new rows are unit-identifiable

### 4.4.3 What to do with historical event rows

Historical event rows are useful, but they should not block the product change.

Recommended approach:

- new runtime writes reading-unit-aware presented/answered rows going forward
- old character-only rows remain preserved as legacy history
- any analytics that depend on exact item identity should read from the new
  unit-aware history after the cutover date

For optional backfill:

- `item_presented` rows can usually be mapped to a unit because the presented
  payload stores the old `correct_choice`, which corresponds to the legacy
  tested reading
- `item_answered` rows are weaker because they store the selected choice but not
  the full presented prompt context; if we backfill them, the safest rule is to
  map them to the same legacy primary-reading unit rather than pretending they
  contain fully reading-specific evidence

So the proposal should treat historical logs as:

- worth preserving
- useful for audit / broad trend context
- not trustworthy enough to synthesize per-reading mastery for non-primary
  readings

Subsequent table-usage change:

- after cutover, new runtime writes must treat `unit_id` as the item identity
- queue building must load learner state by `(user_id, unit_id)`, not by
  `(user_id, character)`
- score/category progression must update one unit row at a time
- daily trend replay and profile category counts must group answered history by
  `(user_id, unit_id)` for post-cutover rows
- any remaining character-level reporting should be treated as legacy or as a
  separate rollup view, not as the authoritative recall-state model

### 4.4.4 Product consequence for users

After migration, a learner who previously studied `行` under the old character
model should experience:

- their old progress continuing on `行|xíng` if `xíng` was the old tested reading
- `行|háng` appearing as a genuinely new unit later
- no fake "already learned" status for readings they were never explicitly tested on

That preserves user trust better than either:

- resetting all polyphonic progress to zero, or
- copying one character score onto multiple distinct readings

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

## 6. Detailed Rollout Plan

This change touches four coupled surfaces:

- recall-unit content derivation
- pinyin-recall session/runtime payloads
- persistent learner state and logs
- profile/progress reporting and category UI

So the implementation should be staged deliberately rather than merged as one
large switch.

### 6.1 Phase 0: Freeze the unit contract

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

Required product invariant:

- every pinyin-recall question, answer update, and progress count must be
  attributable to exactly one `unit_id`

Definition-of-done for this phase:

- a single backend helper can build a stable reading-unit payload for any HWXNet
  character
- the helper uses structured per-reading sources first and does not flatten them
  back to character-level prompts

### 6.2 Phase 1: Build the reading-unit content layer

Implement a backend helper or builder that derives recall units from current
source tables / JSON.

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

### 6.3 Phase 2: Make the pinyin-recall session API unit-aware

Change queue building and prompt construction to operate on units instead of
characters.

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

### 6.4 Phase 3: Introduce unit-keyed persistence

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
2. Backfill legacy character-bank rows to unit rows using the `primary_only`
   strategy described above.
3. Optionally backfill legacy event rows with inferred `unit_id` for audit
   continuity.
4. Switch all runtime writes to the new tables.
5. Stop reading from the old character-keyed bank in queue building.

Operational safety:

- keep backup copies of old tables before backfill
- run dual-read or verification scripts during rollout
- do not delete legacy tables immediately after cutover

Definition-of-done for this phase:

- answering a question updates only one unit row
- no scoring or scheduling code still depends on `(user_id, character)` for
  recall state

### 6.5 Phase 4: Migrate profile/progress reporting to the unit denominator

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
- preferred direction: explain that pinyin recall progress is based on
  "拼音记忆单元" or equivalent wording

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

### 6.6 Phase 5: Cutover and validation

Roll the change out behind a controlled cutover.

Recommended order:

1. Land reading-unit builder and verification scripts.
2. Land new unit-keyed tables and migration scripts.
3. Backfill legacy learner state.
4. Deploy runtime reads/writes against the unit model.
5. Deploy profile/progress changes.
6. Compare old vs new counts for a sample of users.
7. Keep legacy tables read-only for a safety window.

Validation checklist:

- sample users retain expected progress on old primary readings
- non-primary readings start as new units
- profile category counts sum to the total enabled unit denominator
- daily trend charts remain monotonic / plausible after replay migration
- pinyin-recall session mixes new units and due units correctly
- correct and incorrect answer pages no longer render flattened
  character-level English meanings for polyphonic units
- no frontend screen still assumes "one Hanzi = one recall item"

### 6.7 Open decisions to resolve before implementation

The proposal should call out a few choices explicitly:

1. Is the user-facing denominator all derived units or only `recall_enabled`
   units?
2. Do we introduce a physical `pinyin_recall_reading_units` table immediately,
   or keep the unit layer derived in code first?
3. Do category pages list one row per unit, or group by character with reading
   chips inside each row?
4. Do we backfill legacy presented/answered logs with inferred `unit_id`, or
   keep them as pre-cutover history only?
5. What exact user-facing label replaces or qualifies `汉字掌握度` once polyphonic
   readings count separately?

---

## 7. Prompt Construction Rules

Once the unit becomes `character + reading`, the prompt builder should follow these rules.

### 7.1 Correct answer

Correct answer should be:

- `reading_display` for the selected reading unit

not:

- `first pinyin in hwxnet_characters`

### 7.2 Stem-word selection

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

### 7.3 Distractors

Distractors should continue to exclude other readings of the same character from the wrong choices.

The learner should be asked:

- "For this reading-context of `行`, which pinyin is correct?"

not:

- "Pick between `xíng` and another valid reading of the same character."

### 7.4 Feedback screen

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

---

## 8. How This Would Work for Real Characters

All examples below use the same stem-generation rule:

- `WordsByPinyin`
- then `常用词组按拼音` / `common_phrases_by_pinyin`
- then reading-matched `basic_meanings`
- de-duplicate in first-seen order
- show the first `3` merged items in the current recall UI

### 8.1 `和`

Current live behavior:

- one bank row
- one score
- correct answer fixed to `hé`
- stems may include `和牌`, `和了`, `和面`, which belong to other readings

Proposed reading units:

- `和|he2` (`hé`) -> `和谐`, `和解`, `和睦`
- `和|he4` (`hè`) -> `和诗`, `曲高和寡`
- `和|huo2` (`huó`) -> `和面`, `和泥`
- `和|huo4` (`huò`) -> `和药`, `和稀泥`
- `和|hu2` (`hú`) -> Mahjong / card-game "和"

Likely rollout detail:

- not every raw HWXNet reading needs to be recall-enabled on day 1
- fringe readings such as tone-less or interjection-like variants can be disabled until curated

So issue #32 does **not** need to mean "ask 5 separate `和` questions immediately."
It means the model is capable of separating them correctly.

If we apply the preferred merge order:

- Feng `WordsByPinyin`
- then HWXNet `常用词组按拼音`
- then HWXNet `basic_meanings`

then the merged reading-specific word lists for the recall-enabled `和` units become:

- `和|he2` (`hé`) -> `和平`, `和谐`, `和解`, `和气`, `和蔼`, `和蔼可亲`,
  `和畅`, `和风`, `和风细雨`, `和服`, `和好`, `和缓`, `和会`, `和局`,
  `和乐`, `和美`, `和睦`, `和暖`, `和声`, `和合`, `和衷共济`, `温和`,
  `祥和`, `和悦`, `和煦`, `惠风和畅`, `讲和`, `和约`, `和议`, `和亲`,
  `二加二的和是四`, `和盘托出`, `和衣而卧`, `我和老师打球`,
  `我和老师请教`, `和文`, `大和民族`, `和棋`
- `和|he4` (`hè`) -> `一唱一和`, `曲高和寡`, `和诗`
- `和|huo2` (`huó`) -> `和面`, `和泥`, `暖和`
- `和|huo4` (`huò`) -> `和弄`, `和药`, `奶里和点儿糖`, `和稀泥`,
  `衣裳洗了三和水`
- `和|hu2` (`hú`) -> `和了`, `和牌`

And the actual prompt stems shown by the current 3-word recall UI would be:

- `和|he2` (`hé`) -> `和平`, `和谐`, `和解`
- `和|he4` (`hè`) -> `一唱一和`, `曲高和寡`, `和诗`
- `和|huo2` (`huó`) -> `和面`, `和泥`, `暖和`
- `和|huo4` (`huò`) -> `和弄`, `和药`, `奶里和点儿糖`
- `和|hu2` (`hú`) -> `和了`, `和牌`

### 8.2 `行`

Current live behavior:

- correct answer = `xíng`
- current stems include `银行`, which points to `háng`

Proposed reading units:

- `行|xing2` (`xíng`) -> `行走`, `爬行`, `进行`
- `行|hang2` (`háng`) -> `银行`, `行业`, `行列`

This is still a good example of why the model should be reading-specific even
when the current live row only has two active recall-ready readings.

If we apply the preferred merge order:

- Feng `WordsByPinyin`
- then HWXNet `常用词组按拼音`
- then HWXNet `basic_meanings`

then the merged reading-specific word lists for the recall-enabled `行` units become:

- `行|xing2` (`xíng`) -> `行动`, `行走`, `进行`, `步行`, `爬行`, `品行`,
  `横行`, `飞行`, `行尸走肉`, `行坐不安`, `行板`, `行卜`, `行步`,
  `行部`, `行车`, `行成`, `行程`, `行成于思`, `行船`, `行刺`, `行都`,
  `旅行`, `行踪`, `行百里者半九十`, `行云流水`, `行远自迩`, `行装`,
  `行箧`, `行李`, `行销`, `风行一时`, `行商`, `行营`, `行径`, `言行`,
  `操行`, `行礼`, `行医`, `行文`, `不学习不行`, `你真行`, `行将毕业`,
  `五行`, `长歌行`, `行书`
- `行|hang2` (`háng`) -> `行列`, `行业`, `银行`, `行帮`, `行辈`,
  `行当`, `行道`

And the actual prompt stems shown by the current 3-word recall UI would be:

- `行|xing2` (`xíng`) -> `行动`, `行走`, `进行`
- `行|hang2` (`háng`) -> `行列`, `行业`, `银行`

### 8.3 `乐`

Current live behavior:

- correct answer = `lè`
- stems may include `音乐`, `乐曲`, `乐谱`, which point to `yuè`

Proposed reading units:

- `乐|le4` (`lè`) -> `快乐`, `乐观`
- `乐|yue4` (`yuè`) -> `音乐`, `乐曲`, `乐谱`

This is the cleanest kind of polyphonic split and should be easy to support automatically.

If we apply the preferred merge order:

- Feng `WordsByPinyin`
- then HWXNet `常用词组按拼音`
- then HWXNet `basic_meanings`

then the merged reading-specific word lists for `乐` become:

- `乐|le4` (`lè`) -> `乐观`, `快乐`, `欢乐`, `乐园`, `安居乐业`,
  `乐于助人`, `乐不可极`, `乐不可言`, `乐不可支`, `乐道`, `乐得`,
  `乐呵呵`, `乐和`, `取乐`, `逗乐`, `乐此不疲`, `乐善好`,
  `这事太可乐了`
- `乐|yue4` (`yuè`) -> `乐队`, `音乐`, `乐曲`, `乐谱`, `乐池`, `乐府`,
  `乐感`, `乐歌`, `乐工`, `乐官`, `乐户`, `声乐`, `乐音`, `乐正`

And the actual prompt stems shown by the current 3-word recall UI would be:

- `乐|le4` (`lè`) -> `乐观`, `快乐`, `欢乐`
- `乐|yue4` (`yuè`) -> `乐队`, `音乐`, `乐曲`

### 8.4 `累`

Current live behavior:

- correct answer = `lèi`
- current stems include `积累`, `累计`, and `累赘`, which point to other readings

Proposed reading units:

- `累|lei4` (`lèi`) -> `劳累`, `受累`, `累乏`
- `累|lei2` (`léi`) -> `累赘`, `果实累累`, `乱石累累`
- `累|lei3` (`lěi`) -> `积累`, `累计`, `日积月累`

This is a good example of why a character-level answer key is not enough: the
current generic stem list can mix "tired" (`lèi`), "accumulate" (`lěi`), and
"cumbersome / piled up" (`léi`) evidence in the same prompt.

If we apply the preferred merge order:

- Feng `WordsByPinyin`
- then HWXNet `常用词组按拼音`
- then HWXNet `basic_meanings`

then the merged reading-specific word lists for `累` become:

- `累|lei4` (`lèi`) -> `劳累`, `受累`, `累死累活`, `累乏`,
  `病刚好，别再累着`
- `累|lei2` (`léi`) -> `累赘`, `果实累累`, `累臣`, `乱石累累`
- `累|lei3` (`lěi`) -> `积累`, `累计`, `日积月累`, `累次`, `累代`,
  `累罚`, `累积`, `累及`, `累见不鲜`, `累教不改`, `累进`,
  `罪行累累`, `累卵`, `累年`, `累日`, `累累`, `连篇累牍`,
  `累进税`, `牵累`, `拖累`

And the actual prompt stems shown by the current 3-word recall UI would be:

- `累|lei4` (`lèi`) -> `劳累`, `受累`, `累死累活`
- `累|lei2` (`léi`) -> `累赘`, `果实累累`, `累臣`
- `累|lei3` (`lěi`) -> `积累`, `累计`, `日积月累`

### 8.5 `参`

Current live behavior:

- correct answer = `cān`
- current stems include `党参` and `人参`, which point to `shēn`

Proposed reading units:

- `参|can1` (`cān`) -> `参加`, `参与`, `参政`, `参赛`, `参议`
- `参|shen1` (`shēn`) -> `人参`, `党参`, `参商`
- `参|cen1` (`cēn`) -> `参差` (enable only once curated / supported cleanly)

This is a useful example because it mixes:

- high-frequency school usage (`参加`, `参考`, `参观`)
- a clearly separate noun / medicine reading (`人参`, `党参`)
- and a rarer literary bucket (`参差`)

So `参` shows why a reading-unit model needs both:

- reading-specific stems, and
- `recall_enabled` / override control for fringe or low-priority readings.

If we apply the preferred merge order:

- Feng `WordsByPinyin`
- then HWXNet `常用词组按拼音`
- then HWXNet `basic_meanings`

then the full merged reading-specific word lists for `参` become:

- `参|can1` (`cān`) -> `参照`, `参加`, `参与`, `参观`, `参拜`, `参半`,
  `参劾`, `参见`, `参军`, `参看`, `参考`, `参考读物`, `参考书`, `参量`,
  `参政`, `参赛`, `参议`, `参杂`, `参省`, `参阅`, `参检`, `参悟`, `参透`,
  `参破`, `参禅`, `参奏`, `参革`
- `参|cen1` (`cēn`) -> `参差不齐`, `参差`, `参错`
- `参|shen1` (`shēn`) -> `人参`, `党参`, `参商`, `参辰卯酉`

And the actual prompt stems shown by the current 3-word recall UI would be:

- `参|can1` (`cān`) -> `参照`, `参加`, `参与`
- `参|cen1` (`cēn`) -> `参差不齐`, `参差`, `参错`
- `参|shen1` (`shēn`) -> `人参`, `党参`, `参商`

### 8.6 `琢`

Current live behavior:

- correct answer = `zhuó`
- current stems are all from the `zhuó` side: `琢磨`, `雕琢`, `琢刻`, `琢句`,
  `玉不琢，不成器`

Proposed reading units:

- `琢|zhuo2` (`zhuó`) -> `琢磨`, `雕琢`, `琢刻`
- `琢|zuo2` (`zuó`) -> `琢磨`

This is a useful example because it shows a true polyphonic phrase:

- `琢磨` legitimately belongs to both `zhuó` and `zuó`

So the reading-unit model should allow the same phrase to appear in more than
one reading bucket when that reflects real usage, instead of forcing a
one-phrase-one-reading rule.

If we apply the preferred merge order:

- Feng `WordsByPinyin`
- then HWXNet `常用词组按拼音`
- then HWXNet `basic_meanings`

then the merged reading-specific word lists for `琢` become:

- `琢|zhuo2` (`zhuó`) -> `琢磨`, `琢石`, `雕琢`, `琢刻`, `琢句`,
  `玉不琢，不成器`
- `琢|zuo2` (`zuó`) -> `琢磨`

And the actual prompt stems shown by the current 3-word recall UI would be:

- `琢|zhuo2` (`zhuó`) -> `琢磨`, `琢石`, `雕琢`
- `琢|zuo2` (`zuó`) -> `琢磨`

### 8.7 `啊`

Current live behavior:

- correct answer = `ā`
- current stems mix multiple discourse readings:
  `啊哟`, `啊呀`, `啊，你说什么？`, `啊，亲爱的祖国！`, `啊，这事怎么了？`

Proposed reading units:

- `啊|a1` (`ā`) -> `啊呀`, `啊哟`, `啊哈`
- `啊|a2` (`á`) -> `啊，你说什么？`
- `啊|a3` (`ǎ`) -> `啊，这是怎么回事？`
- `啊|a4` (`à`) -> `啊，好吧！`, `啊，我这才明白过来！`

This is a useful example because it shows a different kind of polyphonic split:

- the readings are all discourse particles rather than lexical senses
- the best "stem words" are often short exclamations or whole sentence snippets
- the best enabled reading set may still need product judgment even when the
  source row itself looks clean

So `啊` shows why the reading-unit model needs not only reading-specific stems,
but also a practical `recall_enabled` gate for variants that are technically
present in source data but may not be useful recall items.

If we apply the preferred merge order:

- Feng `WordsByPinyin`
- then HWXNet `常用词组按拼音`
- then HWXNet `basic_meanings`

then the merged reading-specific word lists for the recall-enabled `啊` units become:

- `啊|a1` (`ā`) -> `啊呀`, `啊哟`, `啊哈`, `啊唷`, `啊`,
  `这花真美呀！啊哈`
- `啊|a2` (`á`) -> `啊，你说什么？`
- `啊|a3` (`ǎ`) -> `啊，这事怎么了？`, `啊，这是怎么回事？`
- `啊|a4` (`à`) -> `啊，亲爱的祖国！`, `啊，好吧！`,
  `啊，我这才明白过来！`

And the actual prompt stems shown by the current 3-word recall UI would be:

- `啊|a1` (`ā`) -> `啊呀`, `啊哟`, `啊哈`
- `啊|a2` (`á`) -> `啊，你说什么？`
- `啊|a3` (`ǎ`) -> `啊，这事怎么了？`, `啊，这是怎么回事？`
- `啊|a4` (`à`) -> `啊，亲爱的祖国！`, `啊，好吧！`, `啊，我这才明白过来！`

### 8.8 Example: English meaning split by reading

The same separation should apply to English glosses.

Current problematic pattern:

- one character row has one merged English list
- that list is often a blend of multiple readings
- if we copy that full list into every reading unit, the reading split is only
  partial

#### Example: `乐`

Character-level mixed English list might look like:

- `happy; joyful; pleasure; enjoy`
- `music; musical`

That should not be copied into both reading units.

Proposed reading-level English buckets:

- `乐|le4` (`lè`) -> `happy; joyful`, `pleasure`, `to enjoy`
- `乐|yue4` (`yuè`) -> `music; musical`

So on a recall result for `乐|yue4`, the learner should see English like
`music; musical`, not a mixed gloss list that also includes `happy` or `enjoy`.

#### Example: `行`

Character-level mixed English list might look like:

- `to walk; to go; to do; capable`
- `row; line; profession; trade`

Proposed reading-level English buckets:

- `行|xing2` (`xíng`) -> `to walk`, `to go`, `to do`, `capable; okay`
- `行|hang2` (`háng`) -> `row; line`, `profession; trade`

That keeps the unit internally consistent:

- `行|xing2` should pair `行动 / 行走 / 进行` with `to walk / to go / to do`
- `行|hang2` should pair `行业 / 银行 / 行列` with `profession / trade / row`

#### Example: `累`

Character-level mixed English list might look like:

- `tired; fatigued`
- `to accumulate; repeated; cumulative`
- `cumbersome; bulky; piled up`

Proposed reading-level English buckets:

- `累|lei4` (`lèi`) -> `tired`, `fatigued`
- `累|lei3` (`lěi`) -> `to accumulate`, `cumulative`, `repeated`
- `累|lei2` (`léi`) -> `cumbersome; bulky`, `piled up`

This is a good example of why polyphonic English splitting is not only about
UI cleanliness. The English buckets also help keep the learning signal aligned:

- `累|lei4` should pair `劳累 / 受累` with `tired / fatigued`
- `累|lei3` should pair `积累 / 累计 / 日积月累` with `accumulate / cumulative`
- `累|lei2` should pair `累赘 / 果实累累 / 乱石累累` with `cumbersome / piled up`

#### Example: `参`

Character-level mixed English list might look like:

- `to take part in; to join; to consult; to compare`
- `ginseng; codonopsis`
- `uneven; irregular`

Proposed reading-level English buckets:

- `参|can1` (`cān`) -> `to take part in`, `to join`, `to consult`, `to compare`
- `参|shen1` (`shēn`) -> `ginseng`, `codonopsis`
- `参|cen1` (`cēn`) -> `uneven; irregular`

This is a useful curation-heavy case because the `cān` bucket itself may still
contain several nearby senses, while `shēn` and `cēn` are much narrower. Even
so, the important rule still holds: keep those three buckets separate rather
than inheriting one blended character-level English list into all three units.

#### Example: incomplete gloss coverage

Some readings may have good stem coverage before they have polished English
gloss coverage.

In those cases:

- keep the reading unit
- keep the reading-specific stems
- leave `english_translations` empty or minimal for that reading until curated

That is still better than showing an English gloss bucket that belongs to a
different reading.
