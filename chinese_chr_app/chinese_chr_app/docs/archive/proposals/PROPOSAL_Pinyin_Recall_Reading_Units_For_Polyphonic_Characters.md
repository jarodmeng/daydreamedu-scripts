# Proposal: Reading-Level Units for Polyphonic Characters in Pinyin Recall

**Status:** Proposed  
**Date:** 2026-03-24  
**Revisited:** 2026-03-27  
**Issue:** #32 — `[Chinese character app] Polyphonic characters should be split into multiple "characters"`

> Update (2026-03-27): Since this proposal was drafted, the source data has gained
> structured per-reading phrase buckets for both major stem sources:
> Feng `WordsByPinyin` and HWXNet `常用词组按拼音` / `common_phrases_by_pinyin`.
> That means a substantial part of the old "reading-tagging" prerequisite is now
> complete at the data layer. The remaining gap is mainly in the pinyin-recall
> runtime model, which still treats the learning unit as `character` and still
> flattens those structured fields back into character-level stem lists.

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
- `和|huo` -> `暖和`
- `和|huó` / `和|huò` -> `和泥`

So the current single-unit model can ask for `hé` while showing stems that point
to `hú`, `huo`, or `huó` / `huò`.

#### `行`

- Current correct choice: `xíng`
- Current generic stems from the live DB: `爬行`, `进行`, `品行`, `横行`, `行业`

Those stems are not one reading:

- `行|xíng` -> `爬行`, `进行`, `品行`
- `行|héng` -> `横行`
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

### 2.4 Data-quality nuance: source coverage is much better, but runtime still uses character-level behavior

Among the 424 polyphonic characters:

- **373** already have **>1 reading** explicitly represented in `basic_meanings`
- **50** have only **1 reading** tagged in `basic_meanings`
- **1** has **0** reading-tagged senses

This still matters for implementation, but the situation has improved since the
original draft:

- Feng words now exist in a structured transition field: `WordsByPinyin`
- HWXNet common phrases now exist in a structured transition field:
  `常用词组按拼音` / `common_phrases_by_pinyin`

So the remaining caution is no longer "we must first invent reading-aware phrase
tagging for our main stem sources." Instead, it is:

- a reading-level model is still the right target, and
- we should now consume the existing structured buckets rather than flattening
  them back into character-level phrase lists.

We still need a small **override / curation layer** for incomplete cases,
especially where `basic_meanings` does not yet cover all readings cleanly or
where a raw source reading should not be recall-enabled yet.

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

1. Generate derived reading-unit rows from the current content tables.
2. Build one backend helper that produces merged reading-specific stems using:
   `WordsByPinyin` -> `common_phrases_by_pinyin` -> `basic_meanings`.
3. Use that helper to build reading-specific prompt payloads and validate them on
   real characters.
4. Only after that content layer is stable, add new unit-keyed bank / answer
   tables and migrate learner progress.

This keeps the first milestone narrow:

- correct unit identity
- correct answer key
- correct stem selection
- reading-specific English gloss selection
- explicit `recall_enabled` handling for fringe readings

---

## 4. Proposed Data Model

### 4.1 New derived table: `pinyin_recall_reading_units`

Create a new derived table specifically for pinyin recall.

Suggested columns:

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

### 4.1.1 English meanings must also split by reading

The proposal should treat `english_translations` the same way it treats stems
and `basic_meanings`: for polyphonic recall units, the English glosses should be
bucketed by reading, not copied wholesale from the character row.

Why this matters:

- a single character-level English list often mixes senses from multiple readings
- if we keep inherited mixed glosses, the feedback screen and future review UI
  will still leak cross-reading hints
- the reading-unit layer should stay internally consistent: one reading, one
  answer key, one stem set, one meaning/gloss bucket

Recommended derivation rule:

1. Prefer reading-specific glosses derived from the matching HWXNet
   `basic_meanings` bucket.
2. Use CC-CEDICT as a candidate source for `character + reading` English glosses,
   especially when the current app gloss exists only at the whole-character level.
3. If the source English translations were previously merged at the whole-character
   level, map or curate them into per-reading buckets during reading-unit build.
4. If a reading cannot yet be assigned a trustworthy English gloss bucket, leave
   `english_translations` empty for that unit and rely on the Hanzi + pinyin +
   stems until curated.

So for polyphonic characters, "inherited translations" should only mean
"inherited after per-reading assignment," not "copy the full character-level
English list into every reading unit."

Recommended source priority for reading-level English:

1. HWXNet reading-specific `basic_meanings`
2. CC-CEDICT entries matching the same `character + reading`
3. Existing app-level `英文翻译` as a weak compatibility hint only
4. Manual override / curation for unresolved cases

Important caution:

- CC-CEDICT should be treated as a **candidate source**, not a blind final source
- it is useful because it is already reading-aware
- but its glosses still need filtering or rewriting for learner-friendly
  character-level use

### 4.2 Why a derived table is better than duplicating character rows

We should **not** duplicate `hwxnet_characters` or `feng_characters` into multiple physical "characters".

That would make dictionary/search semantics messy and would over-couple the learning model to the rest of the app.

Instead:

- keep character tables as they are
- derive recall units for learning
- store only recall-specific, reading-specific fields in the new table

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

---

## 5. Prompt Construction Rules

Once the unit becomes `character + reading`, the prompt builder should follow these rules.

### 5.1 Correct answer

Correct answer should be:

- `reading_display` for the selected reading unit

not:

- `first pinyin in hwxnet_characters`

### 5.2 Stem-word selection

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

### 5.3 Distractors

Distractors should continue to exclude other readings of the same character from the wrong choices.

The learner should be asked:

- "For this reading-context of `行`, which pinyin is correct?"

not:

- "Pick between `xíng` and another valid reading of the same character."

### 5.4 Feedback screen

On answer feedback:

- highlight the tested reading first
- show only the English glosses for that tested reading
- optionally show "other readings" as secondary information

For example:

- `行`
- **This question's reading:** `háng`
- Other readings: `xíng`, `hàng`, `xìng`, `héng`

That teaches the distinction without collapsing the score/state again.

English-gloss rule:

- do not show a character-level mixed English list on a reading-specific result
  card
- if the tested reading lacks curated English glosses, prefer no English gloss
  over a wrong cross-reading gloss

---

## 6. How This Would Work for Real Characters

All examples below use the same stem-generation rule:

- `WordsByPinyin`
- then `常用词组按拼音` / `common_phrases_by_pinyin`
- then reading-matched `basic_meanings`
- de-duplicate in first-seen order
- show the first `3` merged items in the current recall UI

### 6.1 `和`

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

So issue #32 does **not** need to mean "ask 8 separate `和` questions immediately."
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

### 6.2 `行`

Current live behavior:

- correct answer = `xíng`
- current stems include `银行`, which points to `háng`

Proposed reading units:

- `行|xing2` (`xíng`) -> `行走`, `爬行`, `进行`
- `行|hang2` (`háng`) -> `银行`, `行业`, `行列`

Additional readings like `hàng`, `xìng`, `héng` can be:

- recall-disabled initially, or
- enabled only after manual review

This is a good example of why we need `recall_enabled` and `enable_reason`, not just "split every pinyin string blindly."

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

### 6.3 `乐`

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

### 6.4 `累`

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

### 6.5 `参`

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

### 6.6 `琢`

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

### 6.7 `啊`

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
- the raw HWXNet pinyin list also includes a tone-less `a`, which likely should
  stay recall-disabled unless we have a strong pedagogical reason to surface it

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

### 6.8 Example: English meaning split by reading

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

---

## 7. Reading-Aware Stem Data Status and Remaining Gaps

To make the reading-level model work well in practice, we should not stop at
splitting the answer key.

The important update is that the two biggest whole-character stem sources now
already have reading-aware transition fields:

- Feng card `WordsByPinyin`
- HWXNet `常用词组按拼音` / `common_phrases_by_pinyin`

So the remaining mismatch is now mainly in the runtime consumer:

- learning state is still character-level, and
- the current pinyin-recall stem builder still flattens structured phrase buckets
  back into character-level lists, which can leak the wrong reading into the prompt.

### 7.1 What is already present

The data layer already contains the key transition outputs this proposal wanted:

- Feng JSON / DB: `WordsByPinyin` / `words_by_pinyin`
- HWXNet JSON / DB: `常用词组按拼音` / `common_phrases_by_pinyin`

Those fields can feed directly into a derived reading-unit table, or they can be
joined on demand while generating recall items.

### 7.2 What still needs to happen

For each polyphonic character:

1. Start with the reading list from HWXNet.
2. Collect candidate phrases from:
   - Feng `WordsByPinyin`
   - HWXNet `例词`
   - HWXNet `常用词组按拼音`
3. Use those structured buckets directly where present.
4. Use HWXNet `basic_meanings` `例词` directly where the reading is explicit.
5. For still-uncovered cases, fall back to a small review/override layer rather
   than flattening across readings.

### 7.3 Review / override layer

The manual layer should be small and focused:

- readings present in raw `拼音` but not mature enough to be recall-enabled
- characters whose `basic_meanings` coverage is incomplete or uneven
- cases where all structured buckets are empty and no safe reading-specific stems exist
- phrases whose assignment looks suspicious in spot checks

### 7.4 Recommended bridge for reading-level English glosses

The biggest remaining gap on the English side is that the current app glosses
were generated at the **character** level, not the **character + reading** level.

The best bridge strategy is:

1. keep the current character-level `英文翻译` as compatibility data
2. build a new derived reading-level English artifact keyed by `unit_id`
3. bootstrap that artifact from:
   - HWXNet reading-specific `basic_meanings`
   - CC-CEDICT entries matching the same `character + reading`
4. use AI to rewrite or rank those candidates into a short learner-facing gloss
   bucket
5. keep a small manual override layer for cases where CC-CEDICT or AI output is
   too broad, too word-oriented, or pedagogically weak

This is preferable to trying to split the existing app `英文翻译` list
mechanically after the fact.

The reviewed decision should then be persisted as the source of truth so the same phrase does not need to be re-adjudicated repeatedly.

### 7.5 Practical rule

For polyphonic characters:

- a Feng phrase should come from the matching `WordsByPinyin` bucket to be
  eligible for the final stem list
- a HWXNet common phrase should come from the matching
  `常用词组按拼音` / `common_phrases_by_pinyin` bucket to be eligible for the
  final stem list
- a HWXNet `例词` should only be used when its reading is explicit in
  `basic_meanings`

They can still exist in the source tables, but pinyin recall should only consume
the reading-specific versions.

### 7.6 Why this matters

This preserves one of the current app's strengths:

- Feng `Words` are often very child-friendly and curriculum-aligned
- 常用词组 often give more natural usage than dictionary 例词 alone

So the right solution is not to drop them. The right solution is to **reading-tag them** and keep them in the pipeline safely.

---

## 8. Rollout Strategy

### Phase 1: Add reading-unit infrastructure

1. Create `pinyin_recall_reading_units`
2. Build a generation script from `hwxnet_characters` and the existing
   structured stem fields
3. Add a small override file/table for:
   - disabling fringe readings
   - supplying missing reading-specific stems/examples
   - correcting incomplete source data
4. Make the pinyin-recall prompt builder consume:
   - Feng `WordsByPinyin`
   - HWXNet reading-tagged `例词`
   - HWXNet `常用词组按拼音` / `common_phrases_by_pinyin`
5. Keep uncovered or low-confidence cases behind a manual override / disable path

### Phase 2: Switch pinyin recall to unit-based scheduling

Add new learning-state tables keyed by `unit_id` rather than `character`:

- `pinyin_recall_unit_bank`
- `pinyin_recall_unit_presented`
- `pinyin_recall_unit_answered`
- optionally `pinyin_recall_unit_report_error`

I recommend **new tables**, not in-place mutation of the current ones.

Reason:

- old tables contain character-level history
- new tables contain reading-level history
- mixing both semantics in one table will make analytics and migrations fragile

### Phase 3: Migrate existing learner progress conservatively

Migration rule:

- **Monophonic characters:** migrate 1:1 to their only unit
- **Polyphonic characters:** migrate existing bank/history to the **primary reading unit only**
- all non-primary reading units start as unseen

Why this conservative rule is better:

- current history does not tell us which reading the learner actually mastered
- some historical prompts already mixed readings in the stem
- pretending we can split that history precisely would create fake data

Primary-unit migration preserves most learner progress without inventing certainty we do not have.

### Phase 4: Revisit profile aggregation

The profile page currently uses a 3664-character denominator.

If pinyin recall moves to 4144 possible reading units, we should **not** automatically replace the profile denominator with 4144.

Recommended short-term approach:

- keep the existing character-centric profile
- add a separate reading-level metric later if useful

Possible future metric:

- `多音字读音掌握` or similar

That keeps issue #32 focused on fixing the learning model without unexpectedly redefining the entire profile UI.

---

## 9. Queue / Scheduling Implications

If all polyphonic readings become eligible units, the effective recall pool grows by **13.10%**.

That means the current queue and progression constants may need retuning later:

- batch new-count caps
- Total Load thresholds
- zibiao/pool expansion heuristics
- profile thresholds if they ever become reading-based

I do **not** recommend bundling those retunings into the first implementation of issue #32.

The first milestone should be:

- correct unit identity
- correct stems
- correct answer key
- correct logging

Then measure whether queue pressure changes enough to justify new thresholds.

---

## 10. Risks and Trade-offs

### 9.1 More units means more surface area

Splitting 424 characters into 904 reading units increases content and scheduling complexity.

Mitigation:

- `recall_enabled`
- override layer
- phased rollout

### 9.2 Source data is not uniformly complete

`行` is a good warning example: it has 5 readings in the live DB, but the reading-tagged sense coverage is not equally complete.

Mitigation:

- keep source tables unchanged
- use a derived table with manual overrides
- do not require every raw reading to be recall-enabled on day 1

### 9.3 Historical continuity is imperfect

Old character-level history cannot be split perfectly by reading.

Mitigation:

- migrate polyphonic history only to the primary unit
- keep old tables for legacy analytics / audit

---

## 11. Recommendation Summary

Issue #32 should be solved by introducing a **reading-level learning model** for pinyin recall:

- keep dictionary/search character-centric
- make pinyin recall unit = `character + normalized_pinyin`
- derive reading-specific stems/meanings per unit
- consume the existing reading-aware source fields first:
  `WordsByPinyin` and `常用词组按拼音` / `common_phrases_by_pinyin`
- use HWXNet-explicit `basic_meanings` mappings where available
- add an override layer for incomplete source data
- use new unit-keyed bank/event tables
- migrate historical polyphonic progress conservatively to primary units only

This is the smallest solution that is both:

- **correct enough for real characters like `和`, `行`, `乐`, `累`**, and
- **honest about the limits of the current data**.
