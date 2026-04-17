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
  and 4`, **`gpt-5.4`** + prompt v5, answer pages `1–68`): default OpenAI
  reasoning (`none`) is **`12/75` exact** vs adjudicated registry; the same
  setup with **`reasoning.effort=medium`** reaches **`71/75` exact** (see Arms
  Summary table).
- **Benchmark Test 04** (`Model Drawing Made Easy and Inspiring for P5 and P6`,
  **`gpt-5.4`** + prompt v5 + **`reasoning.effort=medium`**, answer pages
  `1–138`): vs Gemini-derived pilot JSON, **`83/110` exact**, **`86/110`**
  range-only, **`27`** mismatches; ~**`430k`** total tokens per batch line.
- **Conclusion (four benchmark tests to date):** **`models/gemini-2.5-pro`**
  remains the **best-performing default route** for this continuation +
  assembly workload: strong on the pilot and English registry baseline, best or
  reference-defining scores on the large worked-solutions books in this log
  (registry adjudication on P3/P4; pilot anchor on P5/P6), and **reliable Batch
  completion** here (unlike Flash / Flash-lite). **`gpt-5.4`** with
  **`reasoning.effort=medium`** is the **most credible OpenAI alternative**
  (e.g. **`42/42`** on English with prompt v5; **`71/75`** vs adjudicated truth on
  P3/P4), but it is **not uniformly safer** on every book (e.g. P5/P6
  **`83/110`**, including long **phase-error** chains after a single missed
  same-page heading).

## Cost assumptions

Estimated **USD** values in the **Arms Summary** tables below are **rough**
order-of-magnitude checks from logged token usage:

- **OpenAI:** list prices for **`gpt-5.4`** / **`gpt-5.4-mini`**, then assume
  **Batch API 50%** discount. **Input is priced at the standard Batch input rate
  with no cache discount** (ignore `cached_tokens`) so cross-run rows stay
  comparable. Output rate applies to **all** billed output tokens (including
  **reasoning** tokens when present).
- **Gemini 2.5 Pro (Developer API, ≤200k prompt tier):** assume **Batch-mode 50%
  discount** on the public list rates; billable “output” for cost estimation is
  **`candidatesTokenCount + thoughtsTokenCount`**.
- Excludes tax, credits, regional uplifts, tools, and any future rate changes.
  Re-check [OpenAI](https://openai.com/api/pricing/) and
  [Gemini](https://ai.google.dev/gemini-api/docs/pricing) when precision matters.

## Benchmark Test 01 - Pilot (Small Book)

**Date:** 2026-04-16  
**Scope:** `Science Revision Guide Primary 4` (small-book pilot)  
**Goal:** initial cross-model benchmarking baseline before larger-book runs

### Setup

- Prompt baseline used in successful Gemini test: prompt v2.
- Policy update after pilot: prompt v4 clarifies trailing blank-page handling
  (exclude trailing fully blank pages from effective end-range).
- This policy is used to interpret the OpenAI pilot result.

### Arms Summary

| Arm | Model | Prompt | Reasoning | Quality vs truth | Ops | Est. cost (USD) |
|---|---|---|---|---|---|---|
| Test 01-A | `models/gemini-2.5-pro` | v2 | Gemini thinking (default builder) | **`8/8`** exact on pilot sample | Completed | ~$0.0248 |
| Test 01-B | `gpt-5.4-mini` | v4 | OpenAI default (`none`) | **`8/8`** exact under prompt v4 trailing-blank policy | Completed | ~$0.0158 |
| Test 01-C | `models/gemini-2.5-flash` | v2 | Gemini Batch | No score (job stalled) | Cancelled (`PENDING`) | N/A |
| Test 01-D | `models/gemini-2.5-flash-lite` | v2 | Gemini Batch | No score (job stalled) | Cancelled (`PENDING`) | N/A |

Token sources: `science_revision_guide_primary_4.v01` / `science_revision_guide_primary_4.v012_openai_gpt54mini` run blocks in `RUN_LOGS.md` (`usageMetadata` / `batch.usage`). Costs use [Cost assumptions](#cost-assumptions).

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

### Arms Summary

Compare target for OpenAI arms: **`book_answer_mappings`** (truth **`42`**
units), except **Test 02-Base** which is a **registry self-anchor** for the
Gemini run that produced / backs the imported mappings (`*`).

| Arm | Model | Prompt | Reasoning | Exact | Range-only | Mism. | Pred | Est. cost (USD) |
|---|---|---|---|---:|---:|---:|---:|---|
| Test 02-Base | `models/gemini-2.5-pro` | v3 | Gemini thinking | `42/42`* | `42/42`* | `0`* | `42`* | ~$0.0487 |
| Test 02-A | `gpt-5.4-mini` | v4 | `none` | `20/42` | `34/42` | `22` | `41` | ~$0.0194 |
| Test 02-B | `gpt-5.4` | v4 | `none` | `38/42` | `40/42` | `4` | `42` | ~$0.0634 |
| Test 02-C | `gpt-5.4` | v5 | `none` | `42/42` | `42/42` | `0` | `42` | ~$0.0651 |
| Test 02-D | `gpt-5.4-mini` | v5 | `none` | `21/42` | `34/42` | `21` | `41` | ~$0.0196 |

\*Self-agreement with the imported registry baseline for that Gemini run, not
an independent adjudication proof.

Metrics from `batch_artifacts/english_weekly_revision_primary_1.v*_*.compare.json`; tokens from `RUN_LOGS.md`. Costs: [Cost assumptions](#cost-assumptions).

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

### Arms Summary

Compare target: **`book_answer_mappings`** for this book (truth **`75`**
units), after manual adjudication on a small set of boundary rows (notably
units **43–44**) where the registry was taken as authoritative.

| Arm | Model | Prompt | Reasoning | Exact | Range-only | Mism. | Pred | Est. cost (USD) |
|---|---|---|---|---:|---:|---:|---:|---|
| Test 03-Base | `models/gemini-2.5-pro` | v1 (utility v0.1.0) | Gemini thinking | `73/75` | `74/75` | `2` | `75` | ~$0.1172 |
| Test 03-A | `gpt-5.4` | v5 | `none` | `12/75` | `13/75` | `63` | `75` | ~$0.3050 |
| Test 03-B | `gpt-5.4` | v5 | `medium` | `71/75` | `72/75` | `4` | `75` | ~$0.3600 |

**Test 03-Base** is **`math_model_drawing_p3_p4.v01`** assembled output scored
against the **current adjudicated registry** (so it is **not** `75/75` against
that truth). **Test 03-A/B** metrics come from
`math_model_drawing_p3_p4.v02_openai_gpt5_4.compare.json` and
`math_model_drawing_p3_p4.v03_openai_gpt5_4_reason_medium.compare.json`. Tokens
from `RUN_LOGS.md` / job `batch.usage`. Costs: [Cost assumptions](#cost-assumptions).

### Results

- Batch **completed** in this environment (~minutes); no Flash-tier queue
  issue.
- Ground-truth compare vs **`book_answer_mappings`** (truth **`75`** units):
  - Predicted unit count: **`75`** (no missing unit in assembled output).
  - **Exact:** `12/75`; **range-only (ignore split flags):** `13/75`;
    **mismatches incl. flags:** `63`.
- Token usage (`batch.usage`): input **`218,097`**, output **`4,316`**, total
  **`222,413`** (reasoning `0`).
- **Follow-up (`math_model_drawing_p3_p4.v03_openai_gpt5_4_reason_medium`):** same
  book/pages/prompt v5, but **`reasoning.effort=medium`**. Compare vs adjudicated
  registry: **`71/75` exact**, **`72/75` range-only**, **`4`** mismatches,
  predicted **`75`**. `batch.usage`: input **`218,097`**, output **`11,643`**
  (reasoning **`7,838`**), total **`229,740`** (cached input reported on the job;
  cost row in the table uses **no-cache** pricing for comparability).

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
- **Reasoning depth matters here:** Test **03-A** vs **03-B** is mostly the same
  dollars-per-input story, but **`reasoning.effort=medium`** moves quality from
  unusable (**`12/75`**) to near-registry (**`71/75`**) on this PDF class.

## Benchmark Test 04 - Model Drawing P5/P6 (full worked solutions vs Gemini-derived anchor)

**Date:** 2026-04-17  
**Scope:** `Model Drawing Made Easy and Inspiring for P5 and P6` — **110**
manifest units, answer pages **`1–138`** on `_c_Math Model P5 and P6 Worked
Solutions.pdf`.  
**Goal:** compare **`gpt-5.4`** + prompt v5 + **`reasoning.effort=medium`**
(OpenAI Batch) against the in-repo **Gemini-derived** compare anchor
`pilot_ground_truth/model_drawing_made_easy_p5_p6_ground_truth.json` (same
provenance style as other pilot ground-truth files).

### Setup

- OpenAI Batch `/v1/responses`, strict JSON schema, rendered JPEGs (build
  reported ~`57.8` MiB batch input).
- Prompt **v5**.
- Run id / artifacts: `math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium`
  (batch `batch_69e18a49d3c08190b774598ee50fdd84`).

### Arms Summary

Compare target: **`pilot_ground_truth/model_drawing_made_easy_p5_p6_ground_truth.json`**
(Gemini-derived anchor, **110** manifest units).

| Arm | Model | Prompt | Reasoning | Exact | Range-only | Mism. | Pred | Est. cost (USD) |
|---|---|---|---|---:|---:|---:|---:|---|
| Test 04-Base | `models/gemini-2.5-pro` | continuation schema (Attempt 24 → pilot JSON) | Gemini thinking | `110/110`* | `110/110`* | `0`* | `110`* | TBD |
| Test 04-A | `gpt-5.4` | v5 | `medium` | `83/110` | `86/110` | `27` | `110` | ~$0.64 |

- **Test 04-Base:** **`110/110`** is **self-consistency** only — the pilot JSON
  is the serialized **Gemini 2.5 Pro** **Attempt 24** run (`batch_job` in file
  header: `batches/bf3a6mwxnc62zvoxi2dz6lrwwtbwhyjjznge`), not a second
  independent audit. **Test 04-A** is the only arm scored **against** that
  anchor. Attempt **24** token usage is **not** in `RUN_LOGS.md` here → cost
  **TBD**. OpenAI cost method: [Cost assumptions](#cost-assumptions).

### Results

- Batch **completed** (`request_counts`: `total=1`, `completed=1`, `failed=0`).
- Compare vs **`pilot_ground_truth/model_drawing_made_easy_p5_p6_ground_truth.json`**
  (truth **`110`** units):
  - Predicted unit count: **`110`**.
  - **Exact** (range + `starts_mid_page` / `ends_mid_page`): **`83/110`**.
  - **Range-only** (ignore split flags): **`86/110`**.
  - **Mismatches** including split flags: **`27`** (see
    `batch_artifacts/math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium.compare.json`).
- Token usage (`batch.usage`): input **`413,252`**, output **`16,397`**, reasoning
  **`10,026`**, total **`429,649`** (cached input **`0`**).
- **Estimated cost (USD, rough):** ~**`$0.64`** using OpenAI Batch **50%** rate
  card and **no cache discount** on input (input × `$1.25`/M + output ×
  `$7.50`/M, output includes reasoning tokens as billed).

### Diagnosis: chain error (do not treat as 27 independent bugs)

A **mistaken reading** of the **`27`** mismatch count is that the model made
**many unrelated** segmentation mistakes across the book. For **`math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium`**, a large share of the delta is
instead a **single propagated chain** tied to one boundary:

- **Human-confirmed fact:** **“Practice 4.1”** (registry unit **59**, file
  `…_059_Unit 4 - 01 - 4.1.pdf`) **starts on answer page `57`** in the PDF.
- **Model trace (`…processed.json`):** on page **`57`**, the model kept
  **`continued_unit_index: 58`** (Review 9) with **empty**
  `visible_heading_labels`; it first listed **`"Practice 4.1"`** and
  **`visible_unit_indices: [59]`** on page **`58`** only.
- **Assembler consequence:** **unit `58`** spans **`55–58`** vs truth **`55–57`**
  (`…assembled.json`), and **unit `59`** spans **`58–59`** vs truth **`57–58`**.
  From there, for much of **Unit 4**, assembled ranges track truth with a
  **phase-locked `+1` page on both `answer_page_start` and `answer_page_end`**
  (e.g. units **`59–69`**, **`71–76`** vs `model_drawing_made_easy_p5_p6_ground_truth.json`), i.e. one missed same-page handoff, not fresh errors per unit.
- **Where the chain frays / re-syncs:** small deviations (**`70`**, **`77–78`**),
  then **`79`** matches truth again—so **`58–78`** is best read as **one causal
  incident with local wobble**, not **`21`** independent Unit‑4 failures.

**Implication for benchmarking:** headline **exact-match rate** on this book
understates “true” model quality **unless** you separate **anchor / cascade**
mismatches (one root boundary) from **scattered** disagreements elsewhere (e.g.
other units still worth individual review in `…compare.json`).

### Takeaways

- At **~2×** the answer-page span of Benchmark Test 03 (`138` vs `68` pages),
  **reasoning-enabled `gpt-5.4`** reaches **`83/110` ≈ 75.5%** exact against this
  Gemini-derived anchor (vs **`71/75` ≈ 94.7%** exact on P3/P4 after
  adjudication — different book/length, so compare trends not raw rates). In
  both cases the remaining mass is **boundary / split-flag** disagreements, not
  missing units (`110/110` and `75/75` predicted counts).
- **Cost/scale:** ~**`430k`** tokens per single batch line item for this book;
  budget accordingly for full-book OpenAI + reasoning runs.
- The pilot JSON is a **strong but not infallible** reference (same caveat as
  Test 03); spot-review `…compare.json` before treating disagreements as
  model-only errors.

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
