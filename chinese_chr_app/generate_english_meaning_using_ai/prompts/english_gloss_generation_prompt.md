# English Gloss Generation Prompt (OpenAI Batch API)

This document defines **exactly what will be sent to the OpenAI API** for batch-generated English glosses. One request per character; the model returns a single JSON object per character.

**API usage:** Chat Completions (e.g. `gpt-4o-mini` or `gpt-4o`). For batch: one JSONL line per character with `custom_id`, `messages` (system + user).

---

## 1. System message (exact text sent to the API)

```
You are a lexicographer for a Chinese character learning app. Your task is to produce accurate, learner-friendly English glosses. Output exactly one JSON object per request. No commentary, no markdown fences—only valid JSON.

Rules you MUST follow:
- **Primary sense first**: For characters with multiple meanings (多个释义), prioritize the most common or learner-salient sense. The Chinese definitions (基本字义解释) are your primary semantic source—translate them faithfully into clear English.
- **Learner-friendly**: Use high-frequency, clear English words. Avoid obscure or overly formal terms unless the character genuinely requires them (e.g. classical/archaic senses).
- **Consistency**: Use semicolons to separate multiple senses in english_gloss (e.g. "substitute; generation; era"). Prefer short phrases or single words. Align style with common learner dictionaries.
- **Current gloss (optional)**: The user message may include "current_english_gloss" (the existing translation). When present, use it as a hint only—if inaccurate, incomplete, or inconsistent, replace it entirely. When absent, derive the gloss purely from the Chinese definitions (基本字义解释); do not infer or assume prior translations.
- **Structured output**: Return only valid JSON matching the schema below. No extra text before or after.
- **Primary pinyin**: Always include "primary_pinyin"—the pinyin that corresponds to the primary_sense. When the character has multiple readings (多个读音), choose the reading that matches the primary sense (e.g. 仆: pú = servant, pū = fall → if primary_sense is "servant", set primary_pinyin to "pú"). When there is only one reading, set primary_pinyin to that reading.

**Output checklist (you MUST include all of these):**
- "hanzi": echo the character from the request.
- "english_gloss": main output—concise, semicolon-separated for multiple senses; used to update the character's 英文翻译.
- "primary_sense": (required) the single most common or learner-salient sense for MCQ alignment. Pick one even when multiple senses are common.
- "primary_pinyin": (required) the pinyin for the primary sense (e.g. "pú" for 仆 when primary_sense is "servant"). Use the sole reading when the character has only one.
- "alternative_senses": (optional) array of other senses if multi-sense.
- "confidence_score": 0.0–1.0 (1.0 = very confident).
- "qc_flags": must include "multi_sense" (boolean), "needs_human_review" (boolean), "review_reason" (string or null).
```

---

## 2. User message (template)

The user message is a single JSON object. The model receives this structure:

### 2.1 Character payload

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `hanzi` | string | `character` | The character (e.g. `代`) |
| `pinyin` | array | `拼音` | Pinyin readings with tone marks |
| `radical` | string | `部首` | Radical |
| `stroke_count` | integer | `总笔画` | Total strokes |
| `basic_meanings` | array | `基本字义解释` | Chinese definitions (see structure below) |
| `current_english_gloss` | array | `英文翻译` | Optional. Existing English translation (for reference; may be inaccurate). Omit when running in independent mode. |

`basic_meanings` structure (from 基本字义解释): each element has `读音` (pinyin) and `释义` (array of `{解释, 例词}`).

### 2.2 Example user message

```json
{
  "hanzi": "代",
  "pinyin": ["dài"],
  "radical": "亻",
  "stroke_count": 5,
  "basic_meanings": [
    {
      "读音": "dài",
      "释义": [
        { "解释": "代替。", "例词": ["代课", "代笔"] },
        { "解释": "辈分；世系的辈分。", "例词": ["世代", "下一代"] },
        { "解释": "历史上的时期。", "例词": ["朝代", "古代"] }
      ]
    }
  ],
  "current_english_gloss": ["substitute", "generation", "era"]
}
```

---

## 3. Output format (strict JSON schema)

The model must return **only** a single JSON object (no markdown, no extra text). All fields below are required unless marked optional.

### 3.1 Required fields

| Field | Type | Description |
|-------|------|-------------|
| `hanzi` | string | Echo of the character (e.g. `代`). |
| `english_gloss` | string | Main output. Concise, semicolon-separated for multiple senses. Used to update 英文翻译. |
| `primary_sense` | string | Single most common or learner-salient sense for MCQ alignment. Always pick one, even for multi-sense characters. |
| `primary_pinyin` | string | Pinyin for the primary sense (e.g. "pú" for 仆). Use the sole reading when character has only one. |
| `confidence_score` | number | 0.0–1.0. Higher = more confident in the gloss. |
| `qc_flags` | object | Must include `multi_sense`, `needs_human_review`, `review_reason`. |

### 3.2 Optional fields

| Field | Type | Description |
|-------|------|-------------|
| `alternative_senses` | array of strings | Other senses when character is polysemous. |

### 3.3 QC flags (required within qc_flags)

| Field | Type | Description |
|-------|------|-------------|
| `qc_flags.multi_sense` | boolean | `true` if character has multiple distinct meanings. |
| `qc_flags.needs_human_review` | boolean | `true` when uncertain or when rules conflict. |
| `qc_flags.review_reason` | string \| null | Short reason when `needs_human_review` is true; otherwise null. |

### 3.4 Example outputs

**Single pinyin (代):**
```json
{
  "hanzi": "代",
  "english_gloss": "substitute; generation; era",
  "primary_sense": "substitute",
  "primary_pinyin": "dài",
  "alternative_senses": ["generation", "era"],
  "confidence_score": 0.92,
  "qc_flags": {
    "multi_sense": true,
    "needs_human_review": false,
    "review_reason": null
  }
}
```

**Multiple pinyin (仆: pú = servant, pū = fall):**
```json
{
  "hanzi": "仆",
  "english_gloss": "servant; fall; prostrate; tumble",
  "primary_sense": "servant",
  "primary_pinyin": "pú",
  "alternative_senses": ["fall", "prostrate", "tumble"],
  "confidence_score": 0.9,
  "qc_flags": {
    "multi_sense": true,
    "needs_human_review": false,
    "review_reason": null
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
      { "role": "user", "content": "<JSON from section 2, built per character>" }
    ],
    "response_format": { "type": "json_object" },
    "max_tokens": 256
  }
}
```

- `custom_id`: `char:<hanzi>` for idempotent mapping when merging results.
- `body.messages[0].content`: exact system message text from **Section 1**.
- `body.messages[1].content`: the JSON user message built from **Section 2** (character payload from source data).

---

## 5. Validation rules (for post-processing)

After receiving the API response:

- Parse as JSON; reject if invalid.
- `hanzi` in output must match the request character (from `custom_id`).
- `english_gloss` must be a non-empty string.
- `confidence_score` must be a number in [0.0, 1.0]; clamp if out of range.
- If `qc_flags.needs_human_review` is true, flag the row for manual review before merging into the main dataset.
