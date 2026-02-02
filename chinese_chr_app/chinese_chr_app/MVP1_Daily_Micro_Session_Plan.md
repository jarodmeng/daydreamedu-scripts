# MVP 1 Plan: Daily Micro-Session (5–8 minutes)

Date: 2026-02-01  
Related doc: `chinese_chr_app/chinese_chr_app/Learning Functions Research & Brainstorming.md` (MVP 1 section)

## Goal (this week)

Ship the first working version of **MVP 1: Daily Micro-Session**:

- A short, repeatable session that **builds a personalized queue** of items
- Runs **guided retrieval** with immediate feedback
- Updates a **spaced schedule** per item, per user
- Logs enough events to measure retention, debug scheduling, and iterate

This doc is intentionally implementation-oriented: data model, algorithms, APIs, logging, and test/debug strategy.

---

## Scope boundary (for week 1)

### In scope

- **Web app** micro-session UI (frontend) + backend APIs
- **Character items only** in v0 (words/sentences can be “surface forms” attached to character items, but the scheduled unit is a character)
- **Login-aware personalization** (use Supabase Auth JWT; per-user state stored in Postgres/Supabase)
- **Deterministic v0 scheduler** (simple stage-based intervals)
- **Confusion-set distractors** (pinyin/radical/strokes heuristics)
- **Debug endpoints** and a “why was this chosen?” payload for queue transparency

### Explicitly out of scope (this week)

- Full “story corpus” / graded micro-stories
- Tone ear training (D)
- Full handwriting scoring (we can reuse stroke animation + optional tracing later)
- Parent/teacher dashboards, social features, streak economy
- “Optimal” SRS tuning (we’ll build observability first)

---

## Key technical constraints / existing system integration

### Auth

- Backend already supports Supabase JWT verification via `backend/auth.py` (`verify_bearer_token`).
- Frontend already uses Supabase (`frontend/src/supabaseClient.js` and `AuthContext.jsx`).

### Data sources

- Characters live in:
  - JSON (`data/characters.json`, `data/extracted_characters_hwxnet.json`) OR
  - DB (`feng_characters`, `hwxnet_characters`) when `USE_DATABASE=true` (see `backend/database.py`)

### Existing logging primitive

- There is already DB logging for character views: `database.log_character_view(user_id, character, display_name)`
- This can become a useful signal later (implicit interest), but v0 micro-session should not depend on it.

---

## Data model (new tables)

We need two things:

1) **Per-user per-item scheduling state**  
2) **Event log** (append-only) for analytics + debugging

### 1) `learning_item_state` (per-user per-character)

Proposed columns (Postgres):

- `user_id TEXT NOT NULL`
- `item_id TEXT NOT NULL`  
  - v0: `char:<汉字>` (e.g., `char:学`)
- `item_type TEXT NOT NULL`  
  - v0 always `character`
- `stage INTEGER NOT NULL DEFAULT 0`  
  - stage \(0..5\)
- `next_due_at TIMESTAMPTZ NULL`
- `last_seen_at TIMESTAMPTZ NULL`
- `introduced_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `last_result BOOLEAN NULL` (last attempt correct?)
- `correct_streak INTEGER NOT NULL DEFAULT 0`
- `total_attempts INTEGER NOT NULL DEFAULT 0`
- `total_correct INTEGER NOT NULL DEFAULT 0`
- `last_latency_ms INTEGER NULL`
- `last_hint_level INTEGER NOT NULL DEFAULT 0`  
  - 0 = none, 1 = light hint, 2 = heavy hint (or “revealed”)
- `created_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `updated_at TIMESTAMPTZ NOT NULL DEFAULT now()`

Constraints / indexes:

- Primary key: `(user_id, item_id)`
- Indexes:
  - `(user_id, next_due_at)`
  - `(user_id, updated_at)`

### 2) `learning_events` (append-only)

Proposed columns:

- `id BIGSERIAL PRIMARY KEY`
- `user_id TEXT NOT NULL`
- `session_id TEXT NOT NULL` (UUID v4)
- `event_name TEXT NOT NULL`
- `occurred_at TIMESTAMPTZ NOT NULL DEFAULT now()`
- `payload JSONB NOT NULL DEFAULT '{}'::jsonb`

Indexes:

- `(user_id, occurred_at)`
- `(session_id, occurred_at)`
- `(event_name, occurred_at)`

Event names (v0):

- `learning_session_started`
- `learning_session_completed`
- `queue_built`
- `item_presented`
- `item_answered`
- `item_scheduled`

---

## Item representation (v0)

The scheduled unit is a **character**; we fetch metadata to render prompts:

- `hanzi`
- `pinyin` (with tone marks) — from Feng/HWXNet
- `radical`
- `stroke_count`
- `english_gloss` (from HWXNet english translations)
- optional examples:
  - Feng “Words” list (词组)
  - Feng “Sentence” (例句)
  - HWXNet example words (例词) if/when we parse them

---

## Algorithm 1: scheduling (v0 stage ladder)

### Inputs needed

- `user_id`
- `item_id`
- `now`
- `was_correct` (boolean)
- `hint_level` (0/1/2)

### Stage ladder

- stage 0 → verify again same session (optional immediate confirm)
- stage 1 → +1 day
- stage 2 → +3 days
- stage 3 → +7 days
- stage 4 → +14 days
- stage 5 → +30 days

### Update rule

Treat heavy hints as not-correct (or partially correct):

- If `was_correct=true` AND `hint_level==0`:
  - `stage = min(stage + 1, 5)`
  - `correct_streak += 1`
- Else:
  - `stage = max(stage - 1, 0)`
  - `correct_streak = 0`

Then compute `next_due_at` from the stage ladder.

### Why this is the right v0

- Deterministic and explainable (“you got it right, next in 3 days”)
- Easy to test
- Generates clean event streams so we can later tune intervals empirically

---

## Algorithm 2: build a personalized session queue (v0)

### What the queue must accomplish

Within ~5–8 minutes, we want a mix of:

- **Due reviews** (spaced items)
- **A small number of new items**
- **Confusables** (interleaving for discrimination) as distractors, not necessarily scheduled items

### Inputs needed

- `user_id`
- `now`
- Item universe:
  - from HWXNet set (preferred) plus Feng subset (has richer kid-facing examples)
- User state:
  - rows from `learning_item_state`
- Optional signals (later):
  - recently searched/viewed characters (already logged in `character_views`)

### Session parameters (v0 constants)

- `TARGET_ITEM_COUNT = 12` (adjustable)
- `MAX_NEW_ITEMS = 2`
- `DUE_LOOKAHEAD = 24h` (include items due within next day to reduce “empty sessions”)
- `MAX_REINTRODUCE_STAGE0 = 1` (avoid infinite loops)

### Queue construction steps (v0)

1) **Fetch due items**

- Query `learning_item_state` where:
  - `user_id = ?`
  - `next_due_at <= now + DUE_LOOKAHEAD`
- Sort by:
  - `next_due_at ASC NULLS FIRST`
  - then `stage ASC` (prioritize fragile items)

2) **Take up to N due items**

- `due = take_first(min(TARGET_ITEM_COUNT - MAX_NEW_ITEMS, len(due_items)))`

3) **Pick new items (if needed)**

We need a deterministic, debuggable rule.

**Verified source of `zibiao_index`:** it is loaded from the `data/level-*.json` lists (see `extract_character_from_wxnet/batch_extract_hwxnet.py`), and described in `chinese_chr_app/chinese_chr_app/README.md` as “the character’s index in the `level-*.json` lists.” These level files are a Zìbiǎo-style ordering (earlier index = more common), which is a reasonable proxy for “easiness” for English-dominant primary learners.

New item selection algorithm (v0, per your preference):

**Goal**: draw new items from a pool that is *not too hard but not too easy*.

- Build `seen_set = { item_id from learning_item_state }`
- Build a **candidate pool**:
  - all characters with `zibiao_index` in **[1..500]**
  - convert to item ids: `char:<汉字>`
  - exclude anything already in `seen_set`
- Select `MAX_NEW_ITEMS` characters by **deterministic random sampling**:
  - define a reproducible RNG seed, e.g. `seed = sha256(user_id + ":" + yyyy-mm-dd)`
  - sample without replacement from the candidate pool
  - if pool is too small:
    - expand window to `zibiao_index <= 1000`, then `<= 2000` as needed (log the window used)

**Why deterministic random?**

- You get variety (not always “same next easiest”)
- You can reproduce/debug a user’s queue exactly given `user_id` and date


4) **Merge and order**

- Primary ordering:
  - interleave due and new items roughly as: `due, due, new, due, due, new, ...`
- Log a `queue_built` event with:
  - selected item_ids
  - counts: due/new
  - reason for each item: `due`, `new_seed`, etc.

### Output of queue builder (API shape)

For each queue entry:

- `item_id`
- `item_type`
- `prompt_type` (see next section)
- `metadata` (hanzi/pinyin/radical/strokes/english)
- `due_info`: stage, next_due_at, last_seen_at
- `selection_reason`: `due` | `new_seed`

---

## Algorithm 3: prompt types + distractor generation (v0)

We want multiple prompt types for the same underlying character item.

### Prompt types (v0)

For each scheduled character:

1) **hanzi → meaning** (MCQ)
2) **meaning → hanzi** (MCQ)
3) **hanzi → pinyin-with-tone** (MCQ)

We can rotate prompt types by stage:

Locked for week 1 (Option 1: keep it simple/gentle):

- stage 0–1: **only** `hanzi → meaning` (recognition)
- stage 2–3: introduce `meaning → hanzi` at low frequency (start recall gradually)
- stage 4–5: mix all; include `hanzi → pinyin-with-tone` more often

### Distractor generation (MCQ)

We need 3 distractors for each correct choice. Inputs:

- target character metadata (pinyin, radical, strokes)
- global lookup tables from hwxnet/feng

Heuristic pool builders:

- **Pinyin-tone confusions**:
  - same syllable, different tone (if available)
- **Radical match**:
  - characters with same radical (from hwxnet)
- **Stroke proximity**:
  - stroke count within ±2 (from hwxnet)
- **Fallback**:
  - random from same “band” (e.g., similar zibiao_index range) to avoid always-easy distractors

Rules:

- Always dedupe
- Avoid including the correct answer
- Cap “very rare/unfriendly” characters (v0 can ignore; later we can filter by classification)

### Logging for analysis/debug

When presenting a question:

- log `item_presented` with payload:
  - `prompt_type`
  - `correct_choice`
  - `choices` (list)
  - `distractor_sources` (e.g., `["radical", "pinyin", "stroke"]`)

When answered:

- log `item_answered` with:
  - `selected_choice`
  - `correct` boolean
  - `latency_ms`
  - `hint_level`

This is what makes confusions measurable.

---

## Backend API design (v0)

All endpoints require `Authorization: Bearer <supabase_access_token>` in v0.

### `POST /api/learning/session/start`

Response:

- `session_id`
- `queue` (list of items/questions for the session)

Also inserts:

- `learning_session_started`
- `queue_built`

### `POST /api/learning/session/answer`

Request:

- `session_id`
- `item_id`
- `prompt_type`
- `selected_choice`
- `correct`
- `latency_ms`
- `hint_level`

Response:

- `updated_state` (stage, next_due_at, etc.)
- optionally `next_question` (or let frontend drive from queue)

Also:

- upsert `learning_item_state`
- insert `item_answered`
- insert `item_scheduled`

### `POST /api/learning/session/complete`

Request:

- `session_id`
- summary: counts correct/incorrect, duration

Response:

- `ok: true`

Also inserts:

- `learning_session_completed`

### Debug endpoints (strongly recommended)

#### `GET /api/learning/debug/item-state?item_id=char:学`

Return:

- raw `learning_item_state` row
- recent events from `learning_events` for that item

#### `GET /api/learning/debug/queue?dry_run=1`

Return:

- the same queue build output as `/session/start`
- plus “why” explanations for each selection and each distractor choice

---

## Frontend UI plan (v0)

### Entry points

- Add a top-level nav item: **Learn** (or a button on Search page)
- The Learn page:
  - “Start today’s session” CTA
  - shows last completion time and a simple streak (optional, non-blocking)

### Session UI

- One question at a time, large tap targets
- Progress indicator (e.g., 3/12)
- Immediate feedback:
  - highlight correct answer
  - brief explanation:
    - show pinyin + English gloss
    - optionally show radical cue (light C integration) on some items

### Failure / recovery

- If not logged in: show “Sign in to save progress”
- If queue empty (should be rare): show 2 seed items and log `queue_empty_fallback`

---

## Testing + debugging plan

### Unit tests (backend)

1) **Scheduler tests** (pure function):

- Given `(stage, correct, hint_level)` outputs correct `(new_stage, next_due_delta)`
- Covers boundaries (0 and 5)

2) **Queue builder tests** (with fixed fixtures):

- With no prior state → returns 2 new seed items + remainder (if any) from fallback
- With due items present → due items appear and are ordered deterministically

3) **Distractor builder tests**:

- Never includes correct answer as distractor
- Always returns 4 unique choices when enough candidates exist
- When candidates insufficient, falls back gracefully

### Integration tests (manual + scripted)

- Start session, answer first 3 questions, verify:
  - DB rows created in `learning_item_state`
  - events appended in `learning_events`
- Force time (or mock) to simulate due items

### Debugging “reasoning” surfaces

Make it easy to answer: “why did the app show this?”

- Queue payload includes `selection_reason`
- Choice payload includes `distractor_sources`
- Debug endpoint returns a full trace

### Minimal analytics checks (week 1)

- Count sessions started/completed
- Count items introduced
- Stage distribution histogram
- Incorrect answer top confusions (most chosen distractors)

---

## Risks and mitigations (week 1)

- **DB schema friction**: migrations in Supabase can be tedious  
  → Keep tables small; add columns later.
- **Cold start** (no user state) produces boring sessions  
  → Seed deck (Option A/B) and introduce 1–2 new items every session.
- **Over-hard items** for English-dominant learners  
  → Start with recognition prompts; add recall gradually by stage.

---

## Open questions (to lock scope for this week)

Locked decisions for this week:

1) **Require sign-in** (no guest mode).
2) **v0 is character-only** for scheduled items.
3) **New-item seeding**: deterministic random sample from the first **500** `zibiao_index` characters.
4) **Defer stroke-order tracing**; focus on **meaning + pinyin** prompts.

Remaining open question (small but important):

- **Exact prompt mix**: locked for week 1 as Option 1 (see Algorithm 3).

