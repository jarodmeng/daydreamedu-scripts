# Benchmarking Learnings

This document is a running log of practical learnings from model benchmarking for
`split_book_answer_by_unit_using_ai`.

It is intentionally lightweight and organized by benchmark test. Add each new
test under a new titled section.

## Current Snapshot

- Pilot test on `Science Revision Guide Primary 4` shows strong quality from
  `models/gemini-2.5-pro` and acceptable quality from `gpt-5.4-mini` under the
  prompt v4 trailing-blank-page policy.
- On a larger book (`English Weekly Revision Primary 1`), `gpt-5.4-mini` under
  prompt v4 underperformed registry `book_answer_mappings`; **prompt v5 +
  `gpt-5.4-mini`** on the same pages moved the needle only slightly (`21/42`
  exact vs `20/42`). **`gpt-5.4`** under prompt v4 recovered most of the gap
  (`38/42` exact, `40/42` range-only). **Prompt v5 + `gpt-5.4`** on the same
  pages achieved **`42/42` exact** vs `book_answer_mappings` (Benchmark Test 02
  follow-ups).
- `models/gemini-2.5-flash` and `models/gemini-2.5-flash-lite` were not
  operationally usable in Batch due to prolonged queue `PENDING` states in this
  environment.
- **Benchmark Test 03** (`Math Model Drawing Made Easy and Inspiring Primary 3
  and 4`, **`gpt-5.4`** + prompt v5, answer pages `1–68`): registry compare vs
  mappings imported from human-reviewed Gemini (`v01`) is **`12/75` exact**,
  **`13/75` range-only** — a hard large-book stress test; do not extrapolate
  from English Weekly alone.

## Benchmark Test 01 - Pilot (Small Book)

**Date:** 2026-04-16  
**Scope:** `Science Revision Guide Primary 4` (small-book pilot)  
**Goal:** initial cross-model benchmarking baseline before larger-book runs

### Setup

- Prompt baseline used in successful Gemini test: prompt v2.
- Policy update after pilot: prompt v4 clarifies trailing blank-page handling
  (exclude trailing fully blank pages from effective end-range).
- This policy is used to interpret the OpenAI pilot result.

### Results

- `models/gemini-2.5-pro`
  - Batch completed successfully.
  - Quality on this sample matched ground truth (`8/8` exact).
- `gpt-5.4-mini` (OpenAI Batch)
  - Batch completed successfully.
  - Under prompt v4 trailing-blank-page policy, treated as matching this
    sample-book ground truth.
- `models/gemini-2.5-flash` and `models/gemini-2.5-flash-lite`
  - Batch jobs remained `PENDING` for many hours (including resubmission).
  - Jobs were cancelled due to queue latency.

### Takeaways

- Pilot confirms useful quality from both Gemini Pro and GPT-5.4-mini on a
  small benchmark book.
- Batch queue reliability is a first-class selection criterion, not only
  quality/cost.
- In this environment, Gemini Flash-tier Batch is currently not practical for
  time-sensitive benchmarking.

## Benchmark Test 02 - English Weekly Revision Primary 1 (OpenAI)

**Date:** 2026-04-16  
**Scope:** `English Weekly Revision Primary 1` (larger multi-unit book)  
**Goal:** compare `gpt-5.4-mini` (OpenAI Batch) under prompt v4 against the
existing human-reviewed Gemini Pro baseline from prompt v3

### Setup

- Prompt: v4 (includes trailing blank-page handling guidance).
- Model: `gpt-5.4-mini` (`gpt-5.4-mini-2026-03-17`) via OpenAI Batch on
  `/v1/responses`.
- Page window: answer pages `1-10` (same style of bounded continuation batch as
  the Gemini registry-backed runs).

### Results

- OpenAI Batch completed quickly in this environment (no queue stall like the
  Gemini Flash-tier runs).
- Ground-truth compare vs `book_answer_mappings` (truth `42` units):
  - Predicted unit count: `41` (missing one unit boundary in the assembled
    output).
  - Exact page-range matches: `20/42`.
  - Inclusive page-range matches (ignoring `starts_mid_page` /
    `ends_mid_page`): `34/42`.
  - Total mismatches when including split flags: `22`.
- Token usage (from `response.body.usage` in the batch output line):
  - Input: `45,082` tokens
  - Output: `1,129` tokens (reasoning tokens: `0`)
  - Total: `46,211` tokens

### Takeaways

- **Do not assume small-book parity generalizes:** `gpt-5.4-mini` looked fine on
  the Science Revision pilot, but regressed substantially on this larger book.
- **Split-boundary flags are a major failure mode** for `gpt-5.4-mini` here: many
  disagreements are not “off by a page”, but inconsistent `starts_mid_page` /
  `ends_mid_page` labeling on dense single-page units.
- **Missing units are high severity:** dropping a unit entirely is worse than a
  localized page drift; this run should not be treated as production-ready for
  this workload without stronger model settings or a different model tier.

### Follow-up (same book, prompt v4): `gpt-5.4` OpenAI Batch

**Date:** 2026-04-16  
**Scope:** Same as above — `English Weekly Revision Primary 1`, answer pages
`1-10`, same JSONL builder and assembler.

**Results** (vs `book_answer_mappings`, truth `42` units):

- Predicted unit count: `42` (no dropped unit).
- Exact matches: `38/42`; range-only matches: `40/42`; mismatches including split
  flags: `4`.
- Remaining disagreements are two localized cascades (units `15`–`16` and
  `32`–`33`): page-span vs `starts_mid_page` / `ends_mid_page` boundary pairing,
  not whole-book drift or missing indices.
- Batch job usage (`batch.usage`): input `45,082`, output `942`, total `46,024`
  tokens (reasoning `0`). Resolved model id on the job: `gpt-5.4-2026-03-05`.

**Takeaway:** For this workload, **`gpt-5.4-mini` vs `gpt-5.4` is not a small
delta** on dense multi-unit answer keys; the larger model is a better default
when cost allows.

### Follow-up (same book, same pages, **prompt v5**): `gpt-5.4` OpenAI Batch

**Date:** 2026-04-16  
**Scope:** `English Weekly Revision Primary 1`, answer pages `1-10`; same
assembler; **prompt v5** (top-of-page vs `continued_unit_index` operational
rules).

**Results** (vs `book_answer_mappings`, truth `42` units):

- **`42/42` exact** (including `starts_mid_page` / `ends_mid_page`); **`0`**
  mismatches.
- Batch `usage`: input `45,557`, output `1,084`, total `46,641` tokens (slightly
  more input than the prompt v4 + `gpt-5.4` run due to longer system text).

**Takeaway:** The four residual errors under prompt v4 + `gpt-5.4` (top-of-page
vs continuation on units `15`–`16` and `32`–`33`) are **consistent with prompt
ambiguity**; prompt v5’s explicit operational rules eliminated them on this
benchmark sample. Re-benchmark other books before treating v5 as universally
closed.

### Follow-up (same book, same pages, **prompt v5**): `gpt-5.4-mini` OpenAI Batch

**Date:** 2026-04-16  
**Scope:** `English Weekly Revision Primary 1`, answer pages `1-10`; **prompt
v5**; **`gpt-5.4-mini`**.

**Results** (vs `book_answer_mappings`, truth `42` units):

- Predicted unit count: **`41`** (still missing one unit in the assembled span).
- **`21/42` exact** (vs **`20/42`** under prompt v4 + mini on the same book).
- **`34/42` range-only** (unchanged vs prompt v4 + mini).
- **`21` mismatches** including split flags (vs **`22`** under prompt v4 + mini).

**Takeaway:** Prompt v5 **did not materially fix** `gpt-5.4-mini` on this sample;
the bottleneck is **model capability / structural coherence**, not only the
continuation wording gap that v5 closed for **`gpt-5.4`**.

## Benchmark Test 03 - Math Model Drawing P3/P4 (large worked solutions)

**Date:** 2026-04-16  
**Scope:** `Math Model Drawing Made Easy and Inspiring Primary 3 and 4` — **75**
manifest units, answer pages **`1–68`** on `_c_Math Model Drawing Made Easy and
Inspiring Primary 3 and 4 - 77 - Worked Solutions.pdf` (same window as Gemini
`math_model_drawing_p3_p4.v01`).  
**Goal:** stress-test **`gpt-5.4`** + **prompt v5** OpenAI Batch on a **large,
figure-heavy** worked-solutions PDF; truth = `book_answer_mappings` imported
from human-reviewed Gemini (`ground_truth_math_model_drawing_p3_p4_v01`).

### Setup

- OpenAI Batch `/v1/responses`, strict JSON schema, rendered JPEGs (build
  reported ~`29.76` MiB batch input).
- Prompt **v5** (includes v4 trailing-blank rule + operational continuation
  rules).

### Results

- Batch **completed** in this environment (~minutes); no Flash-tier queue
  issue.
- Ground-truth compare vs **`book_answer_mappings`** (truth **`75`** units):
  - Predicted unit count: **`75`** (no missing unit in assembled output).
  - **Exact:** `12/75`; **range-only (ignore split flags):** `13/75`;
    **mismatches incl. flags:** `63`.
- Token usage (`batch.usage`): input **`218,097`**, output **`4,316`**, total
  **`222,413`** (reasoning `0`).

### Takeaways

- **English Weekly parity does not transfer:** perfect **`42/42`** on dense
  English practices does **not** predict worked-solutions math layout quality on
  this book at the same model tier.
- **Ground truth provenance matters:** registry rows trace to a **different
  pipeline (Gemini + human review)**; large deltas may mix model error with
  defensible interpretation differences on diagram-first pages — use spot
  reviews on `batch_artifacts/math_model_drawing_p3_p4.v02_openai_gpt5_4.compare.json`
  before “fixing” the prompt only.
- **Cost/scale:** ~`222k` tokens for one batch line item sets expectations for
  multi-book OpenAI benchmarking budgets.

## Update Template

When adding a new benchmarking update, include:

- Benchmark test title (e.g. `Benchmark Test 02 - <label>`)
- Date
- Book/sample used
- Prompt version
- Models tested
- Job states and queue behavior
- Quality summary (exact/range vs ground truth)
- Cost/token notes
- Operational decision impact
