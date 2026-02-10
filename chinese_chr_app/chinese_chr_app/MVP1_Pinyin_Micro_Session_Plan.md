# MVP 1 Plan: Daily Micro-Session (Pinyin Recall)

Date: 2026-02-08  
Related doc: `Learning Functions Research & Brainstorming.md` (MVP notes + learning principles)  
Follow-up: **MVP 2** (Meaning in Context) — see `MVP2_Daily_Micro_Session_Plan.md`

---

## Goal (week 1)

Ship the first working version of **MVP 1: Pinyin Recall Micro-Session**:

- A short, repeatable session that **builds a personalized queue** of characters
- Runs **guided retrieval** of **pinyin + tone** with immediate feedback
- Updates a **spaced schedule** per character, per user
- **After the session ends**, gives the user an **opportunity to learn** the characters they answered wrong or chose 我不知道 for
- Logs enough events to measure pronunciation recall and iterate

### Success criteria (v0)

- Users can complete a 5–8 minute session with 10–12 items (or play open-ended; see below)
- Accuracy improves on repeated characters across days
- Confusions show up clearly in logs (tone vs syllable vs distractor type)

---

## Open-ended game format

The game uses an **open-ended session** so the user can play continuously until they choose to stop.

### Flow

1. **Start:** User clicks 开始练习. Backend returns the **first batch of 20 characters** (due items first, then new items, same queue logic as before).
2. **Play:** User answers one question at a time (4 pinyin choices + 我不知道). Immediate feedback (correct/wrong, then next).
3. **After 20:** When the user finishes the 20th item, the frontend requests the **next batch of 20** from the backend. The backend builds another queue of 20 (same logic: due + new, up to 20) and returns it. The game continues with no “session complete” screen—the next 20 questions are shown.
4. **End session:** The user can **end the session** at any time (e.g. an “结束本局” or “End session” control). When they do:
   - If there are any wrong or 我不知道 items from the session, show the **post-session learning** step (all missed items accumulated during the session).
   - Then show the **session-complete** screen (e.g. total practiced, number added for review).

### Design details

- **Batch size:** 20 characters per batch. When one batch is finished, the next 20 are fetched and displayed; no pause or “batch complete” screen unless desired.
- **Scheduler:** Unchanged. Wrong/我不知道 → item stays due (stage 0). Correct → stage advances, next_due set. “Due” and “new” items are computed the same way when building each batch.
- **Missed items:** Accumulated in the frontend for the whole session. When the user ends the session, the learn step shows all missed items from the entire run (all batches).
- **Logging:** When `USE_DATABASE=true`, events are written to Supabase: `item_presented` → `pinyin_recall_item_presented`, `item_answered` → `pinyin_recall_item_answered` (two-table design). When `USE_DATABASE=false`, events are written to `pinyin_recall.log`. Batches can be correlated by session_id.

### Backend API (open-ended)

- **GET /api/games/pinyin-recall/session** — Returns first batch: `{ session_id, items }` with **20 items** (was 12).
- **POST /api/games/pinyin-recall/next-batch** — Body: optional `{ session_id }`. Returns **next batch:** `{ items }` (up to 20 items). Same auth and queue logic as session; used when the user finishes the current 20 so the game can continue.
- **POST /api/games/pinyin-recall/answer** — Unchanged.

If the backend has fewer than 20 due+new items available, it returns as many as it can. The frontend continues with that many; when the user finishes them and requests next-batch, it may get 0 items and can then show “no more items” and offer to end the session.

---

## Scope boundary (MVP 1, week 1)

### In scope

- Web app micro-session UI + backend APIs
- **Character items only** in v0
- **Login-aware personalization** (Supabase Auth)
- **Deterministic v0 scheduler** (simple stage-based intervals)
- **Pinyin-focused distractors** (tone + syllable confusions)
- **Debug endpoints** and "why was this chosen?" payloads
- **Post-session learning**: after session ends, offer a learn step for characters the user got wrong or chose 我不知道 (see [Post-session learning](#post-session-learning))

### Explicitly out of scope

- Meaning/definition testing
- Word/sentence comprehension
- Tone ear training (audio discrimination)
- Handwriting scoring
- Parent/teacher dashboards, streak economy
- "Optimal" SRS tuning (start simple, measure first)

---

## Key technical constraints / existing system integration

Shared with MVP 2: auth, data sources, logging. Reuse the data model, APIs, and queue construction with new prompt types and distractor rules. See `MVP2_Daily_Micro_Session_Plan.md` for the same scaffolding.

---

## Item representation (MVP 1)

Scheduled unit is a **character**. We need:

- `hanzi`
- `pinyin` (with tone marks)
- `pinyin_no_tone` (for syllable grouping)
- `tone` (1–5; 5 = neutral)
- **words/phrases (词组)** for stem context (primary source for MVP 1):
  - from Feng `characters.json` / `feng_characters.Words`
  - from HWXNet `extracted_characters_hwxnet.json` / `hwxnet_characters.基本字义解释[].释义[].例词`
- optional example sentence (only if words are insufficient)

### Stem content (MVP 1)

In the question stem, show:

- the target **character**
- **1–3 common words/phrases** that include the character

This makes the pinyin task less abstract and helps avoid misleading "character-only" meaning cues.

### Word selection rules (MVP 1)

- Prefer **Feng Words** first (kid-facing), then HWXNet 例词 to fill gaps
- Dedupe identical strings across sources
- Cap to 3 words (shortest first if more than 3)

### Stem generation reference

Use the script `chinese_chr_app/chinese_chr_app/backend/scripts/generate_stem.py` as the reference implementation for how stems should be constructed in MVP 1.

### Polyphonic characters (MVP 1 rule)

Because the stem already includes **1–3 words**, we can use that context to disambiguate pronunciation.

Rules:

- Allow polyphonic characters **only if** the stem includes a word/phrase that clearly fixes the reading.
- If no disambiguating word is available, exclude the character from MVP 1 (treat as single-pronunciation-only).
- **Correct answer**: For characters with multiple pronunciations, use the **first** entry in the `拼音` (pinyin) field from `extracted_characters_hwxnet.json` as the correct answer. Other pronunciations of the same character must **not** appear as distractors (see Distractor generation).

  **Examples:** 和 — correct answer hé (he2); hè (he4) must not be in distractors. 好 — correct answer hǎo (hao3); hào (hao4) must not be in distractors.

---

## Algorithm 1: scheduling (v0 stage ladder)

Deterministic ladder (shared with MVP 2):

- stage 0 → verify again same session (optional immediate confirm)
- stage 1 → +1 day
- stage 2 → +3 days
- stage 3 → +7 days
- stage 4 → +14 days
- stage 5 → +30 days

Update rule unchanged.

---

## Algorithm 2: build a personalized session queue (v0)

Same queue logic as MVP 2 (due items + small number of new items). **Candidate pool filters** for MVP 1: exclude polyphonic characters unless we implement context.

### New item selection (MVP 1)

- Build `seen_set` from `learning_item_state`
- Build candidate pool:
  - characters with `zibiao_index` in **[1..500]**
  - **single-pronunciation only** (MVP 1 Option A)
- Deterministic random sample (seeded by `user_id` + date)

---

## Character bank and per-character score (MVP 1 — implemented when USE_DATABASE=true)

**Current status:** Implemented when `USE_DATABASE=true`. The app has:

- **Character bank:** Table `pinyin_recall_character_bank` stores per (user_id, character): score (0–100), stage, next_due_utc, first_seen_at, last_answered_at, total_correct, total_wrong, total_i_dont_know. Used for queue building and persistence across restarts.
- **Event log:** Two tables: `pinyin_recall_item_presented` (when a character is shown) and `pinyin_recall_item_answered` (when the user submits; includes score_before, score_after). When `USE_DATABASE=false`, events go to `pinyin_recall.log` and learning state is in-memory only.

The design below describes the **character bank** and **score** semantics (now implemented).

### Goals

1. **Track each user's character bank:** For each (user, character) we persist a record that the user has "seen" that character in the game and we maintain a **score** reflecting current understanding.
2. **Score semantics:** Higher score = better understanding. Score is updated on every answer (correct / wrong / 我不知道) and optionally latency or streak.
3. **Queue logic uses score:** When building the session queue, prefer or prioritize characters with **lower** scores (need more practice) and/or **due** by schedule; score can also gate "new" vs "learning" vs "mastered" bands.

### Proposed: character bank (persistent store)

- **Scope:** One row (or document) per (user_id, character).
- **Persisted:** In a **database table** (e.g. `pinyin_recall_character_bank` or `learning_item_state`) so it survives restarts and can be queried for queue building and analytics. Optionally keep a write-through to the existing `pinyin_recall.log` for raw events.
- **Fields (per user–character):**
  - `user_id`, `character` (primary key)
  - **score** (numeric, see below)
  - **stage** (0–5), **next_due_utc** (existing scheduler semantics, can stay as-is or be derived from score)
  - **first_seen_at**, **last_answered_at** (timestamps)
  - Optional: **total_correct**, **total_wrong**, **total_i_dont_know**, **streak_correct** (for richer score or analytics)

### Proposed: score definition and update rule

- **Score scale:** e.g. 0–100 or 0–N; higher = better understanding.
- **Initial score:** When a character first enters the user's bank (first time presented in a session), assign a default (e.g. 0 or a low value so it is prioritized).
- **Update on answer:**
  - **Correct:** Increase score (e.g. +X); cap at max. Optionally: larger increase for fast answers or after a streak.
  - **Wrong:** Decrease score (e.g. −Y) and/or set to a floor (e.g. 0). Wrong strongly signals "need more practice."
  - **我不知道:** Decrease score (e.g. same as wrong or slightly more) and set floor. Same as wrong for queue purposes.
- **Optional:** Decay over time (e.g. score drifts down if not seen for a long time) — can be MVP 2.

Concrete numbers (e.g. +10 correct, −15 wrong) and caps are tuning; the important part is that **every answer updates the stored score** for that (user, character).

### Proposed: queue logic using score

- **Due items:** Keep current rule: `next_due_utc <= now` (or null) ⇒ due. Optionally **order due items by score ascending** so lowest-score (weakest) characters appear first in the batch.
- **New items:** Unchanged: characters not yet in the user's bank (or never answered). When selecting **which** new items to add, optional: prefer characters that are "neighbors" of low-score characters (e.g. same syllable) for later iterations; for MVP 1, keep deterministic random from candidate pool.
- **Cap / bands:** Optionally treat "score ≥ threshold" as "mastered" and show less often or only in maintenance reviews; "score in middle" as "learning"; "score low" as "priority." For MVP 1, "due first, then new" plus **within due, sort by score ascending** is enough.

So: **queue = due items (sorted by score ascending) + new items (random sample), up to batch size.**

### Logging and idempotency (implemented)

- **Event log:** When `USE_DATABASE=true`, `item_presented` → `pinyin_recall_item_presented`, `item_answered` → `pinyin_recall_item_answered` (two-table design). `item_answered` includes **score_before** and **score_after**. When `USE_DATABASE=false`, events go to `pinyin_recall.log`.
- **Idempotency:** One write per answer to the character bank and one event row per presented/answered.

### Summary (implemented when USE_DATABASE=true)

| Piece | Purpose |
|-------|--------|
| **Character bank table** | `pinyin_recall_character_bank`: user_id, character, score, stage, next_due_utc, timestamps, counts |
| **Score update** | On every answer: correct +10 (cap 100), wrong/我不知道 −15 (floor 0) |
| **Queue build** | Due first (ordered by score ascending), then new |
| **Logging** | Two tables: `pinyin_recall_item_presented`, `pinyin_recall_item_answered`; item_answered includes score_before, score_after |

---

## Algorithm 3: prompt types + distractor generation (MVP 1)

### Prompt types (v0)

For each scheduled character:

1) **hanzi → pinyin-with-tone** (MCQ)

(If we need extra variety in week 2: add `pinyin → hanzi` recognition.)

Stem rendering:

- show the **character** plus **1–3 words/phrases** containing it

**"我不知道" (I don't know) option:** Always offer an explicit **我不知道** choice so the user can indicate they truly don't know the character. Without it, users must guess to advance; a correct guess does not reflect learning and sends a wrong signal to the scheduler (item may be delayed when it should be retried soon). See [I don't know — behavior and scheduling](#i-dont-know--behavior-and-scheduling) below.

### Distractor generation (MCQ)

We need 3 distractors for each correct pinyin. Heuristic pool:

- **Same syllable, different tone** (primary)
- **Same tone, different syllable** (secondary)
- **Common tone confusions** (2↔3, 1↔4) if we want a small bias
- **Fallback**: random from same difficulty band

Rules:

- Always dedupe
- Avoid including the correct answer
- Avoid distractors that are *too close* (exact same pinyin)
- **Polyphonic characters**: Do not include any of the character’s other pronunciations as distractors. Only the first pronunciation in the `拼音` field is the correct answer; all other entries in that field for the same character must be excluded from the distractor pool. (e.g. 和: correct hé/he2 → exclude hè/he4; 好: correct hǎo/hao3 → exclude hào/hao4.)

### Logging for analysis

- `item_presented`: prompt_type, correct_choice, choices, distractor_sources
- `item_answered`: selected_choice, correct, latency_ms, hint_level, **i_dont_know** (true when user chose 我不知道)

### "I don't know" — behavior and scheduling

- **Rationale:** If the user has no clue, forcing a guess is bad for learning and for the algorithm: a lucky correct guess is treated as recall and can delay the next review.
- **UI:** Offer **我不知道** as a distinct option (e.g. separate button or clearly labeled 5th choice) so users can advance without guessing.
- **Scheduling:** Treat a selection of 我不知道 the same as an **incorrect** answer: do not advance the item’s stage; schedule it for early review (e.g. same session or next day) so the user sees it again soon.
- **Logging:** Record `i_dont_know: true` (or equivalent) in `item_answered` so analytics can separate "wrong pinyin" from "no attempt" and the scheduler uses the correct signal.

---

## Backend API design (MVP 1)

- **GET /api/games/pinyin-recall/session** — First batch of 20 items; returns `{ session_id, items }`.
- **POST /api/games/pinyin-recall/next-batch** — Next batch of 20 items (optional body `session_id` for logging); returns `{ items }`.
- **POST /api/games/pinyin-recall/answer** — Submit one answer; returns `{ correct, i_dont_know, missed_item? }`.

Reuse the same endpoint shape as MVP 2 for answer. Only difference is `prompt_type` and `choices` content.

---

## Frontend UI plan (MVP 1)

- **Open-ended play:** Start with 20 items; when the user finishes 20, fetch the next 20 and continue. User ends the session explicitly (e.g. “结束本局” / “End session”).
- One question at a time, large tap targets
- Show **pinyin with tone marks** as choices (4 options: 1 correct + 3 distractors)
- Always show a **我不知道** (I don't know) option so the user can advance without guessing
- **End session** control (e.g. link or button) so the user can stop at any time
- Immediate feedback:
  - show correct pinyin
  - optionally show a short example word/sentence
- **When user ends session**: offer a **post-session learning** step for all wrong and 我不知道 items from the session (see below)
- **Wrong vs correct feedback:** When the user answers **correctly**, show a brief confirmation (✓ 正确, character, pinyin, phrases) and move on. When the user answers **wrongly** or clicks **我不知道**, show a dedicated **learning moment** page (see below) before "下一题".

### Wrong-answer / I don't know — learning moment (design, not yet implemented)

When the user selects a wrong pinyin or **我不知道**, they are either confused about the character or do not know it. The feedback screen should act as a short **learn this character** card using existing character data, so the wrong answer becomes a clear learning opportunity. The correct-answer screen stays minimal; the wrong-answer screen is expanded and structured for learning.

**Audience note:** For **English-speaking primary school students**, showing the **English meaning** of the character (e.g. from 英文翻译) is especially useful—it helps them attach the sound and form to a meaning they already know and supports vocabulary building. The learning screen should prioritize English meaning when available for this audience.

**Goal:** Maximize learning effect in the moment (meaning, form, and sound) without overwhelming the user. Use only data we already have (HWXNet + Feng).

**Data available (per character):**

- **HWXNet** (`extracted_characters_hwxnet.json`): 拼音, 部首, 总笔画, 基本字义解释 (释义 with 解释 + 例词), 英文翻译.
- **Feng** (`characters.json`): Pinyin, Radical, Strokes, Structure (e.g. 左右结构), Sentence, Words.

**Proposed content for the wrong-answer / 我不知道 learning screen (in order):**

1. **Outcome line**  
   - "答错了" (red, bold).  
   - If wrong pinyin: "你选了：{selected}" (e.g. 你选了：gàng).  
   - If 我不知道: "你选了：我不知道".

2. **Correct sound and form**  
   - Large **character** in KaiTi.  
   - **Correct pinyin** (with tone mark) prominently below the character.

3. **Meaning**  
   - One short meaning so sound connects to sense. For English-speaking learners (e.g. primary school), **always show English meaning when available**: use **英文翻译** from HWXNet (e.g. "father", "mother") as the primary meaning; if missing, fall back to first **解释** from 基本字义解释 (e.g. "称呼父亲。").  
   - Label e.g. "Meaning：" (or "意思：" when showing Chinese 解释) so it’s clear.

4. **Form cues (decomposition)**  
   - **部首 · 笔画** (e.g. "部首：父 · 8 画") from HWXNet or Feng.  
   - **结构** (e.g. "左右结构") from Feng when available.  
   - Helps users chunk and remember the character shape.

5. **常见词组**  
   - Same 1–3 phrases as in the stem, with the **tested character bolded** in each phrase.  
   - Optional: show pinyin for each phrase (e.g. below or above) to reinforce sound–word link.  
   - Section clearly labeled (e.g. "常见词组：") and visually distinct (e.g. light background, left border as on question screen).

6. **Example sentence**  
   - Feng **Sentence** when available (e.g. "爸爸每天早晨都和我去散步。").  
   - Tested character **bolded** in the sentence.  
   - Optional: translation or pinyin for the sentence in a later iteration.

7. **Optional later / v1**  
   - "查看笔顺" (View stroke order) linking to existing stroke animation (HanziWriter / strokes API) so users can see stroke order without cluttering the wrong-answer screen in v0.

**Layout and UX:**

- Single scrollable card or a short sequence of sections; no quiz, no extra clicks to see the correct answer.  
- Primary action: **下一题** at the bottom. Secondary: **结束本局**.  
- Typography: character in KaiTi; labels (意思, 部首, 常见词组, etc.) slightly emphasized so the page scans clearly.

**Correct-answer screen (unchanged in spirit):**

- "✓ 正确", character (KaiTi), pinyin, optional short phrase list.  
- No meaning, radical, structure, or sentence—keep it brief so correct answers stay fast.

**Backend / API:**

- The answer endpoint already returns `missed_item` with `character`, `stem_words`, `correct_pinyin`.  
- To support the learning screen, the backend should optionally return for wrong/我不知道: **meaning** (one string), **radical**, **strokes**, **structure**, **sentence** (and optionally phrase pinyin).  
- Either extend `missed_item` with these fields when available, or add a small "character learning info" payload that the frontend requests only after a wrong/我不知道 (to keep answer response small). Design choice: extend `missed_item` in the same response so the learning screen can render without an extra round-trip.

**Summary:**

- **Correct:** Short confirmation (character + pinyin + phrases).  
- **Wrong / 我不知道:** Dedicated learning moment with correct pinyin, meaning, radical·strokes, structure, 常见词组 (character bolded), and example sentence (character bolded), using HWXNet + Feng. Design is documented here; implementation to follow after review.

---

### Post-session learning

When the session ends, if the user had any **wrong** or **我不知道** answers:

- Show an opportunity to **learn** those characters (no quiz—study only).
- For each such character, display: **character**, **pinyin (with tone)**, and **1–3 example words/phrases** (same stem content as in the session).
- User can step through the list at their own pace (e.g. tap to see next); optionally allow "Done" / skip to exit.
- If there were no wrong or 我不知道 items, skip this step and show the normal session-complete state.

---

## Testing + debugging plan (MVP 1)

Same testing approach as MVP 2, with extra coverage:

- Distractor builder returns **tone and syllable**-based distractors
- Polyphonic filter excludes ambiguous items (if Option A)

---

## MVP 1 open questions

- Which dataset fields definitively indicate **single vs multiple pinyin**?
- Whether we should include **neutral tone** (5) early or delay it
- If we should bias new-item sampling to **high-frequency syllables** first
