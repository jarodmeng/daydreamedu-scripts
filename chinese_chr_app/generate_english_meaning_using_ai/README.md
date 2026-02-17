# Proposal: AI-Generated English Gloss via OpenAI Batch API

## Summary

Use OpenAI's Batch API to generate or improve English gloss (translations) for each of the 3,664 characters in `extracted_characters_hwxnet.json`. The current `英文翻译` (English translation) values are often inaccurate, overly literal, or inconsistent across the corpus. This proposal outlines how to leverage the Batch API for cost-effective bulk generation with 50% savings and higher rate limits.

---

## 1. Problem Statement

Characters in `chinese_chr_app/data/extracted_characters_hwxnet.json` have an `英文翻译` field (array of English strings). Issues with current glosses include:

- **Inaccuracy**: Some glosses are direct dictionary translations that don't convey the character's *meaning in isolation* when learners encounter it.
- **Inconsistency**: Similar characters may use different gloss styles (e.g., "father" vs " dad" vs "papa").
- **Poor fit for MCQ**: The distractor-generation pipeline (`generate_distractors_using_ai`) relies on `english_gloss`. Suboptimal glosses degrade MCQ quality and controlled-vocabulary alignment.

---

## 2. Approach: OpenAI Batch API

Use the **Batch API** instead of synchronous Chat Completions because:

| Benefit | Details |
|---------|---------|
| **50% cost discount** | Batch API pricing is ~half of synchronous API |
| **Higher rate limits** | Separate pool; no blocking during processing |
| **Async processing** | ~24 hour completion window; no immediate response needed |
| **Same quality** | Same Chat Completions endpoint; only execution mode differs |

**Workflow:**

1. Build a JSONL file (one line per character) with Chat Completions requests.
2. Upload the file via Files API (`purpose="batch"`).
3. Create a batch job (`/v1/batches`).
4. Poll for status until `completed` (or handle `failed` / `expired`).
5. Download output file via `output_file_id`.
6. Merge results back into the character JSON (update `英文翻译` / equivalent field).

---

## 3. Prompt Design

### 3.1 System Message

The model acts as a **lexicographer** for learner-oriented Chinese character glosses:

- **Primary sense**: For characters with multiple meanings, prioritize the most common/learner-salient sense.
- **Learner-friendly**: Use high-frequency, clear English. Avoid obscure or formal terms unless necessary.
- **Consistency**: Align style with existing good glosses (simple words, short phrases, semicolon-separated for multiple senses).
- **Structured output**: Return only valid JSON; no markdown or commentary.

### 3.2 User Message (per character)

Each request includes a JSON object with:

| Field | Type | Source | Description |
|-------|------|--------|-------------|
| `hanzi` | string | `character` | The character (e.g. `代`) |
| `pinyin` | array/string | `拼音` | Pinyin readings with tone marks |
| `radical` | string | `部首` | Radical |
| `stroke_count` | integer | `总笔画` | Total strokes |
| `basic_meanings` | array | `基本字义解释` | Chinese definitions and example words |
| `current_english_gloss` | array | `英文翻译` | Existing English translation (for reference; may be inaccurate) |

The model uses `basic_meanings` (Chinese definitions) as the primary semantic source. It may consider `current_english_gloss` as a hint but should correct or replace it when it is wrong or inconsistent.

### 3.3 Output Format (JSON schema)

```json
{
  "hanzi": "代",
  "english_gloss": "substitute; generation; era",
  "primary_sense": "substitute; to replace",
  "alternative_senses": ["generation; era"],
  "confidence_score": 0.92,
  "qc_flags": {
    "multi_sense": true,
    "needs_human_review": false,
    "review_reason": null
  }
}
```

- `english_gloss`: Main output—concise, semicolon-separated for multiple senses; used to update `英文翻译`.
- `primary_sense`: Single most common sense (optional; for MCQ alignment).
- `confidence_score`: 0.0–1.0 for downstream QC.
- `qc_flags.needs_human_review`: Set `true` when uncertain or when rules conflict.

---

## 4. Batch API Request Shape

Each line in the input JSONL:

```json
{
  "custom_id": "char:代",
  "method": "POST",
  "url": "/v1/chat/completions",
  "body": {
    "model": "gpt-4o-mini",
    "messages": [
      { "role": "system", "content": "<system message from 3.1>" },
      { "role": "user", "content": "<JSON payload from 3.2>" }
    ],
    "response_format": { "type": "json_object" },
    "max_tokens": 256
  }
}
```

- `custom_id`: `char:<hanzi>` for idempotent mapping when merging results.
- `model`: `gpt-4o-mini` recommended for cost; `gpt-4o` if higher accuracy is required.

---

## 5. Implementation Plan

### Phase 1: Prompt & Script Setup

1. **Create `english_gloss_generation_prompt.md`**  
   - Full system message and user-message template.
   - Example inputs/outputs and validation rules.

2. **Create `build_batch_input.py`**  
   - Load `extracted_characters_hwxnet.json`.
   - For each character: build user message JSON.
   - Write JSONL to `batch_input.jsonl` (or similar).
   - Support `--pilot N` with stratified sampling (see 5.1) or `--limit N` for first-N-only.

3. **Create `run_single_gloss_prompt.py`**  
   - Test one character synchronously (like `run_single_distractor_prompt.py`).
   - Validate output schema; log any parse errors.

### 5.1 Pilot Sampling Strategy

For pilot runs (e.g. 50 characters), use stratified sampling instead of first-N-only to get representative coverage.

**Recommended: Stratified sampling**

| Stratum | Target | Rationale |
|---------|--------|-----------|
| 常用字 (`分类`) | ~25 | High-frequency; most learner exposure |
| 通用字 (`分类`) | ~15 | Standard characters |
| Other 分类 | ~10 | Less common; edge cases |
| Stroke count low (≤5) | ~15 | Simple characters |
| Stroke count mid (6–12) | ~20 | Typical complexity |
| Stroke count high (13+) | ~15 | Complex characters |
| Multiple senses (multiple 释义/读音) | ~10–15 | Polysemous characters; harder cases |

Within each stratum, use random sampling (with fixed seed for reproducibility). Strata can overlap (e.g. a 常用字 may also have multiple senses).

**Alternative options**

- **First N by index**: `--limit 50` on ordered list. Simple, reproducible, but may over-represent high-frequency characters.
- **Uniform random**: 50 random characters. Unbiased but may miss edge cases.
- **Targeted selection**: Manually pick characters with known bad glosses. Best for validating known problem cases; requires prior review.

**Implementation**: `build_batch_input.py` supports `--pilot 50 --stratify` (and optionally `--seed 42` for reproducibility).

### Phase 2: Batch Execution

4. **Create `submit_batch.py`**  
   - Upload JSONL via `files.create(purpose="batch")`.
   - Create batch via `batches.create(input_file_id=..., endpoint="/v1/chat/completions", completion_window="24h")`.
   - Persist `batch_id` for status checks.

5. **Create `check_batch_status.py`**  
   - Poll `batches.retrieve(batch_id)` until `status == "completed"` or `"failed"` / `"expired"` / `"cancelled"`.
   - On completion: download output via `files.content(output_file_id)`.
   - On failure: fetch and log `error_file_id` contents.

### Phase 3: Result Merging

6. **Create `merge_gloss_results.py`**  
   - Parse output JSONL; each line has `custom_id` and `response.body.choices[0].message.content`.
   - Map `custom_id` → `hanzi` (parse from `char:代`).
   - Update character records: set `英文翻译` from parsed `english_gloss` (split by `;` into array if desired).
   - Write to new file (e.g. `extracted_characters_hwxnet.gloss_updated.json`) to avoid overwriting source.
   - Optionally add `english_gloss_ai` / `gloss_confidence` as separate fields for A/B comparison.

### Phase 4: Validation & QC

7. **Validation**  
   - Parse every response as JSON; reject malformed lines.
   - Ensure `hanzi` in output matches `custom_id`.
   - Flag rows where `qc_flags.needs_human_review` is true for manual review.

8. **Spot checks**  
   - Use the same stratified sample (5.1) as the pilot for consistency.
   - Compare old vs. new gloss; document improvements and regressions.

---

## 6. Cost Estimation

- **Per-request tokens (rough)**  
  - System: ~300–500 tokens  
  - User: ~200–600 tokens (varies with `基本字义解释` length)  
  - Output: ~50–150 tokens  
  - Total per character: ~600–1,200 tokens

- **Batch API pricing**  
  - ~50% of standard Chat Completions (check [OpenAI Pricing](https://openai.com/pricing) for current rates).
  - Example: 3,664 chars × ~800 tokens avg ≈ 2.9M input + ~400K output.
  - At typical batch rates (~$0.09/1M input, ~$0.36/1M output): on the order of **~$0.50–2.00** for full corpus (order-of-magnitude).

- **Pilot run**  
  - First 50–100 characters: negligible cost; validate prompt and pipeline.

---

## 7. Risks & Mitigations

| Risk | Mitigation |
|------|-------------|
| Batch expires or fails | Poll status; retry failed subset with new batch; keep `custom_id` for idempotency |
| Some responses invalid JSON | Log and skip; run a follow-up batch for failed `custom_id`s only |
| Gloss quality varies | Use `confidence_score` and `needs_human_review` to prioritize manual review |
| Overwriting good glosses | Merge script writes to new file; keep backup; diff before replacing |

---

## 8. Alignment with `generate_distractors_using_ai`

The distractor-generation pipeline expects `english_gloss` per character. After this proposal is implemented:

- Updated `英文翻译` (or a derived `english_gloss` field) will feed into the distractor prompt.
- Better glosses → better `answer_en_controlled` and distractor quality.
- Both pipelines share the same Batch API pattern and can reuse `submit_batch.py` / `check_batch_status.py` utilities (parameterized by input file and endpoint).

---

## 9. Files to Create (Summary)

| File | Purpose |
|------|---------|
| `prompts/english_gloss_generation_prompt.md` | System/user message spec, output schema, examples |
| `scripts/build_batch_input.py` | Generate JSONL from character data |
| `scripts/run_single_gloss_prompt.py` | Single-character test (sync API) |
| `scripts/submit_batch.py` | Upload JSONL, create batch, save batch_id |
| `scripts/check_batch_status.py` | Poll status, download output/error files |
| `scripts/process_batch_output.py` | Parse batch output JSONL → gloss JSON |
| `scripts/merge_glosses_into_hwxnet.py` | Merge AI glosses into character JSON |

## 10. Folder Layout

```
generate_english_meaning_using_ai/
├── README.md
├── prompts/
│   └── english_gloss_generation_prompt.md   # Prompt spec
├── scripts/
│   ├── build_batch_input.py                 # Build JSONL for batch
│   ├── submit_batch.py                      # Upload and create batch
│   ├── check_batch_status.py                # Poll and download results
│   ├── process_batch_output.py              # JSONL → gloss JSON
│   ├── merge_glosses_into_hwxnet.py         # Merge into hwxnet data
│   ├── estimate_batch_cost.py               # Cost estimation
│   └── run_single_gloss_prompt.py           # Single-char test
└── batch_artifacts/                         # Batch inputs, outputs, glosses
    ├── batch_id*.txt
    ├── batch_*input*.jsonl
    ├── batch_*output*.jsonl
    └── *_glosses.json
```

Run scripts from `scripts/` with `python3 script.py` or from the repo root with `python3 scripts/script.py`.

---

## 11. Next Steps (When Ready to Execute)

1. Implement Phase 1 (prompt + build script).
2. Run pilot on 50 characters with `build_batch_input.py --pilot 50 --stratify` (see 5.1); test a few with `run_single_gloss_prompt.py`.
3. Review pilot outputs; refine prompt if needed.
4. Submit full batch; merge results after completion.
5. Spot-check and optionally backfill failed/flagged characters.
