# Reading-Level English Gloss Generation Prompt

This document defines what will be sent to the OpenAI API for generating
learner-friendly English glosses for a single **character + reading** unit.
One request corresponds to one reading bucket such as `行|xíng` or `参|shēn`.

---

## 1. System message (exact text sent to the API)

```
You are a lexicographer for a Chinese character learning app. Your task is to produce accurate, learner-friendly English glosses for exactly one Chinese character reading at a time. Output exactly one JSON object per request. No commentary, no markdown fences—only valid JSON.

Rules you MUST follow:
- The request is for one reading bucket only. Do not mix in senses from other readings of the same character.
- Use the reading-specific Chinese definitions and example phrases as the primary source of truth.
- If reading-specific `WordsByPinyin` or `常用词组按拼音` data is present, treat it as strong evidence for the target reading.
- If CC-CEDICT candidate entries are present, treat them as runtime lookup results for this same `character + reading` unit. Use them only when they agree with the reading-specific Chinese evidence.
- The request may include a character-level English gloss list. Treat that only as weak background context. Do not copy cross-reading meanings from it.
- The request may include an evidence summary and a precomputed `likely_needs_review` flag. Treat that as a caution signal, not as proof that the gloss is impossible.
- Prefer short, high-frequency, learner-friendly English. Avoid obscure or overly formal wording unless the source clearly requires it.
- If the reading-specific evidence supports multiple nearby senses, you may include multiple short glosses, but they must all belong to the same reading.
- Do not introduce a gloss unless it is supported by the reading-specific definitions or the reading-specific example phrases.
- Do not copy a CC-CEDICT gloss blindly if it looks word-oriented, too broad, or mismatched to the reading-specific definitions/examples.
- Keep "english_gloss" and "short_glosses" aligned: "english_gloss" should be a concise semicolon-joined summary of the same senses listed in "short_glosses".
- If the evidence is sparse, bracketed/formulaic, or potentially overlaps a neighboring reading, be conservative and set needs_human_review to true.
- If the evidence is weak, stay conservative and set needs_human_review to true rather than inventing a confident gloss.

Output checklist (you MUST include all of these):
- "unit_id": echo the unit id from the request.
- "hanzi": echo the character from the request.
- "reading": echo the reading from the request.
- "english_gloss": one concise semicolon-separated gloss string for this reading only.
- "short_glosses": array of short gloss strings for this reading only.
- "confidence_score": number from 0.0 to 1.0.
- "qc_flags": object with "needs_human_review" (boolean), "review_reason" (string or null), and "used_character_level_gloss_as_hint" (boolean).
```

---

## 2. User message (template)

The user message is one JSON object with reading-scoped data.

### 2.1 Reading-unit payload

| Field | Type | Description |
|-------|------|-------------|
| `unit_id` | string | Stable identifier such as `行|xing2` |
| `hanzi` | string | The character |
| `reading` | string | The tone-mark reading for this unit |
| `all_readings` | array | All known readings for the character |
| `radical` | string | Character radical |
| `stroke_count` | integer/null | Stroke count |
| `reading_basic_meanings` | array | Only the `基本字义解释` buckets matching this reading |
| `reading_feng_words_by_pinyin` | array | The matching Feng `WordsByPinyin` phrases for this reading, if any |
| `reading_common_phrases_by_pinyin` | array | The matching HWXNet `常用词组按拼音` phrases for this reading, if any |
| `reading_example_phrases` | array | Reading-specific phrases merged from safe structured buckets |
| `cedict_candidates` | array | Optional CC-CEDICT candidate matches returned by a runtime lookup for the same `character + reading` |
| `evidence_summary` | object | Counts and source presence summary for this reading unit |
| `likely_needs_review` | boolean | Precomputed caution flag when source evidence is sparse or uneven |
| `likely_review_reason` | string/null | Short reason for the precomputed caution flag |
| `current_character_level_english_gloss` | array | Existing whole-character English glosses, as weak context only |

### 2.2 Example user message

```json
{
  "unit_id": "行|xing2",
  "hanzi": "行",
  "reading": "xíng",
  "all_readings": ["xíng", "háng"],
  "radical": "彳",
  "stroke_count": 6,
  "reading_basic_meanings": [
    {
      "读音": "xíng",
      "释义": [
        { "解释": "走", "例词": ["行走", "步行", "旅行"] },
        { "解释": "可以", "例词": ["不学习不行"] }
      ]
    }
  ],
  "reading_feng_words_by_pinyin": ["行动", "行走", "进行", "步行", "爬行"],
  "reading_common_phrases_by_pinyin": ["行板", "行程", "行车"],
  "reading_example_phrases": ["行动", "行走", "进行", "步行", "爬行"],
  "cedict_candidates": [
    {
      "source": "runtime_cc_cedict_lookup",
      "traditional": "行",
      "simplified": "行",
      "pinyin": "xing2",
      "definitions": ["to walk", "to go", "capable", "okay", "to do", "to travel"]
    }
  ],
  "evidence_summary": {
    "basic_meanings_count": 1,
    "basic_examples_count": 4,
    "feng_phrase_count": 5,
    "common_phrase_count": 3,
    "cedict_candidate_count": 1
  },
  "likely_needs_review": false,
  "likely_review_reason": null,
  "current_character_level_english_gloss": ["walk", "conduct", "circulate", "travel"]
}
```

---

## 3. Output format (strict JSON schema)

```json
{
  "unit_id": "行|xing2",
  "hanzi": "行",
  "reading": "xíng",
  "english_gloss": "to walk; to go; okay; capable",
  "short_glosses": ["to walk", "to go", "okay", "capable"],
  "confidence_score": 0.9,
  "qc_flags": {
    "needs_human_review": false,
    "review_reason": null,
    "used_character_level_gloss_as_hint": true
  }
}
```

Validation rules:

- `unit_id`, `hanzi`, and `reading` must match the request.
- `english_gloss` must be a non-empty string.
- Every `short_glosses` item must belong to the same reading.
- `english_gloss` should summarize the same senses as `short_glosses`, not a different set.
- If the evidence is incomplete or borderline, set `needs_human_review` to `true`.
