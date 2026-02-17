# MCQ Distractor Generation Prompt (OpenAI Batch API)

This document defines **exactly what will be sent to the OpenAI API** for batch-generated MCQ distractor sets. One request per character; the model returns a single JSON object per character.

**API usage:** Chat Completions (e.g. `gpt-4o-mini` or `gpt-4o`). For batch: one JSONL line per character with `custom_id`, `messages` (system + user).

---

## 1. System message (exact text sent to the API)

```
You are a distractor-generation assistant for a Chinese character learning app. Your task is to produce exactly one JSON object per request. No commentary, no markdown fences—only valid JSON.

Rules you MUST follow:
- Propose your own list of confusable distractors based on the character supplied. **Strongly prefer characters that share the same radical or similar structure** (e.g. for 代 dài, 伐 fá shares the radical 亻 and is a classic confusable—include such characters in distractors_final). Use radical, stroke count, structure, pinyin, and meaning to identify characters that learners might confuse with the prompt character. The user message includes "character_universe_hanzi": a **single string** containing every valid character in our learning set (all hanzi concatenated, no separators). **You must only propose distractors and confusable_candidates that appear as characters in this string.** Every hanzi in "distractors_final" and "confusable_candidates" must be a character that appears in "character_universe_hanzi". The app will also post-validate and discard any that are not in the universe.
- "answer_en_controlled" is the correct English meaning of the prompt character, rephrased in controlled vocabulary for learners. Use the level specified in the request (L1 or L2). L1 = very simple, high-frequency words only (e.g. "to replace", "time", "big"); prefer one or two short words or a brief phrase; avoid rare or formal words. L2 = still learner-friendly but slightly broader; you may use common compound phrases or slightly less frequent words. Base your answer on the character's "english_gloss" but simplify and standardize it so a learner seeing the character in isolation would recognize the meaning. If the character has multiple senses, give the single most common or salient sense for this level; do not list multiple meanings in answer_en_controlled. Apply the same controlled-vocabulary rules to every distractor's "english_gloss" in distractors_final.
- Output at most 20 distractors in "distractors_final". Prioritize by how likely each is to confuse a learner (include your strongest confusables first). **NEVER include the prompt character in distractors_final**—every entry must be a different character. Deduplicate so every option is distinct. For each distractor include a "confidence_score" (0.0 to 1.0): how likely you think this character is to confuse a learner with the prompt character (higher = more likely to confuse). The app will rotate through this pool and test which ones are actually more confusing.
- Set "qc_flags" honestly: no_context_ambiguity_risk (low/medium/high), english_level (L1 or L2 as in the request), near_synonym_collision (true if any distractor is too close in meaning to the correct answer), needs_human_review (true plus a short reason when uncertain or when rules could not be fully satisfied).

**Output checklist (you MUST include all of these):**
- "prompt_hanzi": echo the character being tested (same as character.hanzi from the request).
- "answer_en_controlled": the correct English meaning in controlled vocabulary.
- "confusable_candidates": array of at least 5 hanzi you considered as confusables (for audit); can overlap with distractors_final.
- "distractors_final": at most 20 items; each hanzi must be different from the prompt character and must appear in character_universe_hanzi.
- "qc_flags": must include "english_level" (L1 or L2 as requested).
```

---

## 2. User message (template)

The user message is a single JSON object (formatted for readability in the prompt; the API can receive it as compact JSON). The model receives this structure:

### 2.1 Character payload (target character)

| Field | Type | Description |
|-------|------|-------------|
| `hanzi` | string | The character being tested (e.g. `代`). |
| `pinyin` | string | Pinyin with tone marks (e.g. `dài`). |
| `radical` | string | Radical symbol (e.g. `亻`). |
| `stroke_count` | integer | Number of strokes. |
| `structure` | string | Optional. e.g. `左右结构`, `上下结构`. |
| `english_gloss` | string | Current English meaning (for reference; you may rephrase in controlled vocab). |

### 2.2 Character universe (so the AI knows valid distractors)

We pass the full set of characters as a **single string** (all hanzi concatenated, no separators) to save tokens. The AI only proposes distractors that appear in this string.

| Field | Type | Description |
|-------|------|-------------|
| `character_universe_hanzi` | string | All valid hanzi in our learning set concatenated into one string (e.g. 3664 characters from HWXNet). No spaces or separators. Every distractor and confusable_candidate the AI outputs must be a character that **appears in** this string. Source: keys of `data/extracted_characters_hwxnet.json` joined: `"".join(keys)`. |

The AI reasons about confusability from the character payload but **restricts its proposals to characters that appear in this string**. The app still post-validates and discards any out-of-universe hanzi.

### 2.3 Optional parameters

| Field | Type | Description |
|-------|------|-------------|
| `english_level` | string | `L1` or `L2`. Controls vocabulary strictness for answer and distractors. |
| `prompt_type` | string | Optional. e.g. `hanzi_to_meaning`. For now always `hanzi_to_meaning`. |

### Example user message (what will be sent)

The user message includes the character payload, `character_universe_hanzi` as a **single string** (3664 hanzi concatenated), and optional parameters. Example structure (universe string truncated for display):

```json
{
  "character": {
    "hanzi": "代",
    "pinyin": "dài",
    "radical": "亻",
    "stroke_count": 5,
    "structure": "左右结构",
    "english_gloss": "substitute; generation; era"
  },
  "character_universe_hanzi": "爸妈我代伐化休件作任何...",
  "english_level": "L1",
  "prompt_type": "hanzi_to_meaning"
}
```

(Full request: `character_universe_hanzi` is a string of length 3664, built from keys of `data/extracted_characters_hwxnet.json` joined with no separators.)

---

## 3. Output format (strict JSON schema)

The model must return **only** a single JSON object (no markdown, no extra text). All fields below are required unless marked optional.

### 3.1 Required fields

| Field | Type | Description |
|-------|------|-------------|
| `prompt_hanzi` | string | Echo of the character being tested (e.g. `代`). |
| `answer_en_controlled` | string | The correct English meaning of the prompt character, rephrased in controlled vocabulary for the requested level (L1 or L2). Not a raw copy of the input "english_gloss"—simplify and standardize: use only high-frequency, learner-appropriate words; prefer one primary sense (the most common when the character has multiple meanings); keep it short (e.g. "to replace; generation" or "era"). Must match the vocabulary strictness of the distractors so all four MCQ options feel consistent. |
| `confusable_candidates` | array of strings | At least 5 hanzi the model considered as confusables (for audit). The app will validate each against the 3664-character universe and discard any not in it. |
| `distractors_final` | array of objects | At most 20 items. Each: `{ "hanzi": string, "english_gloss": string, "confidence_score": number }`. `confidence_score` is 0.0–1.0 (higher = more likely to confuse). Must not include `prompt_hanzi`. Order by confidence (strongest first). The app validates each hanzi against the full 3664-character universe and keeps only in-universe entries; it then rotates through this pool to test which distractors are actually more confusing. |
| `option_sources` | object | Optional. For diagnostics: e.g. maps "correct" and top distractors by confidence. Not a fixed A/B/C/D because the app picks 3 from the pool per question. |

### 3.2 Quality-control flags (required)

| Field | Type | Description |
|-------|------|-------------|
| `qc_flags.no_context_ambiguity_risk` | string | One of: `low`, `medium`, `high`. Risk that the character has multiple plausible meanings out of context. |
| `qc_flags.english_level` | string | `L1` or `L2` (as requested). |
| `qc_flags.near_synonym_collision` | boolean | `true` if any distractor is too close in meaning to the correct answer. |
| `qc_flags.needs_human_review` | boolean | `true` when uncertain or when a rule could not be fully satisfied. |
| `qc_flags.needs_human_review_reason` | string | Optional. Short reason when `needs_human_review` is true. |

### 3.3 Example output (what we expect from the API)

```json
{
  "prompt_hanzi": "代",
  "answer_en_controlled": "to replace; generation",
  "confusable_candidates": ["伐", "化", "休", "件", "作", "任", "何"],
  "distractors_final": [
    { "hanzi": "伐", "english_gloss": "to cut down", "confidence_score": 0.92 },
    { "hanzi": "化", "english_gloss": "to change", "confidence_score": 0.85 },
    { "hanzi": "休", "english_gloss": "to rest", "confidence_score": 0.78 },
    { "hanzi": "件", "english_gloss": "piece; item", "confidence_score": 0.65 },
    { "hanzi": "作", "english_gloss": "to make; to do", "confidence_score": 0.55 }
  ],
  "option_sources": { "correct": "代", "top_by_confidence": ["伐", "化", "休"] },
  "qc_flags": {
    "no_context_ambiguity_risk": "low",
    "english_level": "L1",
    "near_synonym_collision": false,
    "needs_human_review": false,
    "needs_human_review_reason": null
  }
}
```

---

## 4. Batch API request shape (reference)

For OpenAI Batch API, each line in the request JSONL file has this shape:

```json
{
  "custom_id": "char:代",
  "method": "POST",
  "url": "/v1/chat/completions",
  "body": {
    "model": "gpt-4o-mini",
    "messages": [
      { "role": "system", "content": "<contents of section 1 above>" },
      { "role": "user", "content": "<JSON from section 2.3, built per character>" }
    ],
    "response_format": { "type": "json_object" }
  }
}
```

- `custom_id`: e.g. `char:<hanzi>` or a stable character id for idempotency.
- `body.messages[0].content`: exact system message text from **Section 1**.
- `body.messages[1].content`: the JSON user message built from **Section 2** (character payload + english_level + prompt_type only; no candidate pool).

---

## 5. Validation rules (for post-processing)

After receiving the API response:

- Parse as JSON; reject if invalid.
- `distractors_final` must have at least 1 entry and at most 20 entries. Each entry must include `hanzi`, `english_gloss`, and `confidence_score` (number in [0.0, 1.0]). If the API returns more than 20, truncate to the first 20 (by order; the model should already order by confidence).
- **Universe check:** Every hanzi in `distractors_final` and `confusable_candidates` must be checked against the app’s full character universe (3664 characters). Discard any distractor or candidate whose hanzi is not in the universe. Keep only in-universe entries for import; optionally log out-of-universe proposals for analysis.
- `prompt_hanzi` must equal the request character’s `hanzi`.
- If `qc_flags.needs_human_review` is true, flag the row for human review before import.
