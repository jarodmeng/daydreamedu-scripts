# Proposal: `英文解释按拼音` Transition Field

**Status:** Proposed  
**Date:** 2026-03-27  
**Related:** `WordsByPinyin`, `常用词组按拼音`, reading-level English gloss batch artifact

---

## 1. Summary

Introduce a new structured transition field:

- JSON: `英文解释按拼音`
- DB: `english_translations_by_pinyin`

This field would sit alongside the current flat character-level English field:

- JSON: `英文翻译`
- DB: `english_translations`

The purpose is the same as the earlier `WordsByPinyin` and `常用词组按拼音`
transitions:

- preserve existing flat compatibility data for current consumers
- add a structured reading-aware field for polyphonic characters
- let consumers migrate gradually toward the structured field

In short:

- `英文翻译` remains temporary compatibility data
- `英文解释按拼音` becomes the preferred source for any reading-aware consumer

---

## 2. Problem

Today the app’s English field is character-centric:

- one character
- one flat English list

That is workable for monophonic characters, but it breaks down for polyphonic
characters because the flat list often mixes senses from multiple readings.

Examples:

- `乐`
  - current flat English may mix `happy` and `music`
  - but `乐|lè` and `乐|yuè` should not share the same learner-facing gloss bucket
- `参`
  - current flat English may mix `participate`, `ginseng`, and `uneven`
  - but those belong to `cān`, `shēn`, and `cēn` respectively
- `累`
  - current flat English may mix `tired`, `accumulate`, and `burdensome`
  - but those belong to different readings

We already solved the analogous phrase problem with:

- Feng `WordsByPinyin`
- HWXNet `常用词组按拼音`

English glosses now have the same structural need.

---

## 3. Why a transition field is the right pattern

This should follow the same transition approach we used before:

- keep the legacy flat field
- add the structured reading-aware field
- migrate consumers conservatively

Why this is better than replacing `英文翻译` immediately:

- many existing app surfaces still expect a flat character-level English list
- the current runtime still contains character-centric consumers
- we want to land reading-aware English without forcing an all-at-once migration
- we want provenance and auditability while the new field matures

So this proposal intentionally mirrors:

- `Words` -> `WordsByPinyin`
- `常用词组` -> `常用词组按拼音`

---

## 4. Proposed field shape

Use the same ordered bucket pattern as the other reading-aware transition fields:

```json
[
  {
    "Pinyin": "lèi",
    "Glosses": ["tired", "to tire"]
  },
  {
    "Pinyin": "léi",
    "Glosses": ["burden", "numerous", "cumbersome"]
  },
  {
    "Pinyin": "lěi",
    "Glosses": ["accumulate", "successive", "involve"]
  }
]
```

Recommended rules:

- bucket order should match the row’s `拼音` order
- keep one bucket per reading in the row’s `拼音` list, even for fringe readings
  that currently have only a thin reviewed gloss set
- monophonic rows should also use the same shape
- `Glosses` should be an ordered array of short learner-facing gloss strings
- bucket contents should be reading-specific only

Suggested mappings:

- JSON: `英文解释按拼音`
- DB column: `english_translations_by_pinyin`

### 4.1 Before vs. after examples

#### Example: `乐`

Current flat field:

```json
{
  "英文翻译": ["happy", "joyful", "music", "musical"]
}
```

Problem:

- `happy` / `joyful` belong to `乐|lè`
- `music` / `musical` belong to `乐|yuè`
- the flat field mixes both readings into one bucket

Proposed structured field:

```json
{
  "英文解释按拼音": [
    { "Pinyin": "lè", "Glosses": ["happy", "joyful"] },
    { "Pinyin": "yuè", "Glosses": ["music", "musical"] }
  ]
}
```

#### Example: `参`

Current flat field:

```json
{
  "英文翻译": ["participate", "mix", "consult", "explore", "visit", "impeach"]
}
```

Problem:

- the current flat field only reflects the `cān` cluster
- it does not cleanly represent `参|shēn` (`ginseng`, constellation name)
- it does not cleanly represent `参|cēn` (`uneven`, `irregular`)

Proposed structured field:

```json
{
  "英文解释按拼音": [
    { "Pinyin": "cān", "Glosses": ["participate", "consult", "explore", "visit", "impeach"] },
    { "Pinyin": "shēn", "Glosses": ["ginseng", "one of the 28 constellations"] },
    { "Pinyin": "cēn", "Glosses": ["uneven", "irregular"] }
  ]
}
```

#### Example: `累`

Current flat field:

```json
{
  "英文翻译": ["tired", "accumulate", "burden"]
}
```

Problem:

- `tired` belongs to `累|lèi`
- `accumulate` belongs mainly to `累|lěi`
- `burden` / `cumbersome` belongs to `累|léi`
- the flat field compresses three readings into one ambiguous list

Proposed structured field:

```json
{
  "英文解释按拼音": [
    { "Pinyin": "lèi", "Glosses": ["tired", "to tire"] },
    { "Pinyin": "léi", "Glosses": ["burden", "numerous", "cumbersome"] },
    { "Pinyin": "lěi", "Glosses": ["accumulate", "successive", "involve"] }
  ]
}
```

---

## 5. Source of truth

For polyphonic rows, `英文解释按拼音` should be derived from the reviewed
reading-level English-gloss artifact, not guessed mechanically from the flat
character-level `英文翻译`.

Recommended source priority:

1. reviewed reading-level English gloss artifact keyed by `unit_id`
2. upstream manual override / review decisions that produced that reviewed artifact
3. reading-specific Chinese evidence from `基本字义解释`
4. Feng `WordsByPinyin`
5. HWXNet `常用词组按拼音`
6. CC-CEDICT candidate entries for the same `character + reading`

Important rule:

- do **not** try to split the old flat `英文翻译` list into buckets mechanically

That old field may still be useful as compatibility data or as a weak hint, but
it should not be treated as the authoritative input for the new structured field.

---

## 6. Compatibility behavior

During the transition:

- keep `英文翻译` unchanged as compatibility data
- add `英文解释按拼音` alongside it
- migrate consumers toward `英文解释按拼音` as the preferred source
- preserve current behavior during migration by flattening the structured field
  through a middleware utility where a flat list is still expected

Flattening rule:

- the shared flatten utility should return a deterministic flat English list from
  `英文解释按拼音`
- it should preserve bucket order from `拼音`
- within each bucket, it should preserve gloss order and de-duplicate by
  first-seen value

Consumer guidance:

- character-centric surfaces should move to reading from `英文解释按拼音`
  through a shared flatten utility rather than reading legacy flat `英文翻译`
  directly
- reading-aware surfaces should prefer `英文解释按拼音` directly
- legacy flat `英文翻译` remains compatibility data during the migration, not the
  preferred consumer target

Example:

- Search / dictionary page can remain behaviorally character-centric for now,
  while sourcing its English list from flattened `英文解释按拼音`
- future reading-aware pinyin-recall units should read from
  `英文解释按拼音` directly

---

## 7. Migration plan

### Phase 1: Land the transition field in JSON

- add `英文解释按拼音` to `extracted_characters_hwxnet.json`
- monophonic rows are wrapped mechanically into one bucket
- polyphonic rows are filled from the reviewed reading-level English artifact

### Phase 2: Add DB support

- add `english_translations_by_pinyin` to `hwxnet_characters`
- backfill it from `extracted_characters_hwxnet.json`
- keep existing `english_translations` unchanged

### Phase 3: Conservative consumer migration

- add a shared flatten utility for `英文解释按拼音` -> flat English list
- migrate existing consumers to read from `英文解释按拼音` through that flatten
  utility where they still need flat behavior
- let reading-aware consumers adopt `英文解释按拼音` directly
- keep legacy flat `英文翻译` available as compatibility data during the migration
- do not change UI behavior in this phase; this is a data-source migration first

### Phase 4: Review and tighten

- spot-check reviewed / edited fringe readings
- confirm no polyphonic reading buckets are leaking cross-reading glosses
- decide later whether flat `英文翻译` should eventually become derived
  compatibility data from the structured buckets

---

## 8. Benefits

- aligns English gloss structure with the app’s reading-aware phrase structure
- removes a major source of cross-reading leakage for polyphonic characters
- supports future reading-level pinyin-recall units cleanly
- keeps rollout low-risk by preserving current compatibility fields
- makes provenance and review much clearer for fringe readings

---

## 9. Risks

### 9.1 Some reading buckets are still fringe or weakly supported

This is already true in the reviewed reading-level artifact.

Mitigation:

- keep the reviewed decision layer
- preserve `needs_human_review` / reviewed overrides in the source pipeline
- do not force every source reading to become a polished learner-facing bucket immediately

### 9.2 Flat and structured English fields can drift

During transition, two English fields will coexist.

Mitigation:

- make the reviewed reading-level artifact the provenance source for the
  structured field
- document clearly which consumers should use which field
- avoid hand-editing both fields independently

---

## 10. Recommendation

Proceed with a new transition field:

- `英文解释按拼音`

and treat it as the English analogue of:

- `WordsByPinyin`
- `常用词组按拼音`

This keeps the data model honest:

- character-level English remains available for legacy consumers
- reading-level English becomes available for reading-aware consumers

That is the cleanest path from today’s flat `英文翻译` world to a future
reading-aware runtime.

---

## 11. Implementation Checklist

- [ ] Before overwriting `extracted_characters_hwxnet.json`, create a timestamped JSON backup in `chinese_chr_app/data/backups/` using the same naming style as earlier character-bank transitions, e.g. `extracted_characters_hwxnet.YYYYMMDD-english-glosses-by-pinyin-backup.json`.
- [ ] Add `英文解释按拼音` to `extracted_characters_hwxnet.json` as the new structured transition field.
- [ ] Use HWXNet rows only as the content scope for this rollout; do not add a Feng-side English transition field.
- [ ] For monophonic rows, wrap the reviewed final English glosses mechanically into a single bucket.
- [ ] For polyphonic rows, populate buckets from the reviewed reading-level English gloss artifact keyed by `unit_id`.
- [ ] Keep fringe / weakly supported reviewed readings in `英文解释按拼音` rather than dropping them from the field.
- [ ] Store only the reviewed final glosses in `英文解释按拼音`; do not embed batch confidence, review status, or other provenance metadata inside the transition field itself.
- [ ] Add a new DB column `english_translations_by_pinyin` to `hwxnet_characters`.
- [ ] Update the HWXNet table creation / upsert script so the new JSON field is written into `english_translations_by_pinyin`.
- [ ] Before the live DB backfill / upsert, create a timestamped Supabase backup table using the existing naming convention, e.g. `hwxnet_characters_backup_YYYYMMDD_HHMMSS`.
- [ ] Backfill the live `hwxnet_characters` table from the updated JSON.
- [ ] Update backend lookup serialization so `english_translations_by_pinyin` is exposed to Python consumers in the same style as `WordsByPinyin` / `common_phrases_by_pinyin`.
- [ ] Add a shared flatten utility that converts `英文解释按拼音` into the current flat English-list behavior.
- [ ] Migrate existing consumers to read from `英文解释按拼音` through that flatten utility where flat behavior is still expected.
- [ ] Keep current UI/runtime behavior the same during this migration, even though the data source shifts to the new structured field.
- [ ] Add one or more verification scripts / checks to confirm every monophonic row has exactly one English bucket.
- [ ] Add one or more verification scripts / checks to confirm every polyphonic row’s bucket order matches `拼音`.
- [ ] Add one or more verification scripts / checks to confirm every reading in `拼音` has a corresponding bucket in `英文解释按拼音`.
- [ ] Add one or more verification scripts / checks to confirm every bucket contains only reviewed final gloss strings.
- [ ] Add one or more verification scripts / checks to confirm DB and JSON stay in sync for the new field.
- [ ] Record the rollout in `data/CHARACTERS_CHANGELOG.md`.
- [ ] In `data/CHARACTERS_CHANGELOG.md`, record the exact `chinese_chr_app/data/backups/extracted_characters_hwxnet.*-english-glosses-by-pinyin-backup.json` filename.
- [ ] In `data/CHARACTERS_CHANGELOG.md`, record the exact `hwxnet_characters_backup_YYYYMMDD_HHMMSS` table name.
- [ ] Record the app/data-layer transition in `docs/CHANGELOG.md` and, if accepted as an architectural decision, `docs/DECISIONS.md`.
