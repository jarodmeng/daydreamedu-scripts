# Unit-to-answer-page mapping run log

For each **end-to-end** run of the continuation page-segments pipeline (`build` → `submit` → `poll` → `process` → `assemble`, and optional ground-truth compare), prepend one row to the [Run index](#run-index) and add one matching `### N.` block under **`## Runs`** (see convention below). Keeps enough context to reproduce, debug, or correlate with `pdf_file_manager` book groups.

**Convention:** Stable **`#`**: **1** = oldest run, **higher = newer** (never renumber past rows). Both the [Run index](#run-index) table and **`## Runs`** **display newest first**: the **top** row is the highest `#`; the **bottom** row is `#1`. When you add a run, insert **one new row** at the **top** of the index table (next `#`) and insert **one** `### N.` block **immediately under `## Runs`** (above older blocks)—**`### N` matches index `#N`**. Same-day tie-break when *ordering*: **later** batch time closer to the top (`batch_artifacts/<run id>.job.json`: **OpenAI** `batch.created_at`; **Gemini** `job.end_time` or `job.create_time`).

---

## Run index

Stable **`#`**: **1** = oldest, **higher = newer** (never renumber). Rows are **newest first** (highest `#` at the top). When you add a run, insert **one row** here as the **first data row** (next `#`), and add **one** `### N.` block at the **top** of `## Runs` (directly under the heading).

| # | Run id | Run name |
|---|--------|----------|
| 15 | `grammar-practice-primary-1.v01` | Grammar Practice Primary 1 (Gemini 2.5 Pro, answer p1–4) |
| 14 | `conquer_exam_terry_chew_p5_lessons_p1_37.v01` | Conquer Exam Standard Mathematics Problem Sums with Terry Chew Primary 5 (lessons only, answer p1–37, Gemini 2.5 Pro) |
| 13 | `math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium` | Model Drawing Made Easy and Inspiring for P5 and P6 (OpenAI gpt-5.4, reasoning medium) |
| 12 | `math_model_drawing_p3_p4.v02_openai_gpt5_4` | Math Model Drawing P3/P4 (Benchmark Test 03, OpenAI) |
| 11 | `english_weekly_revision_primary_1.v5_openai_gpt54mini` | English Weekly Revision Primary 1 (prompt v5 + gpt-5.4-mini) |
| 10 | `english_weekly_revision_primary_1.v5_openai_gpt5_4` | English Weekly Revision Primary 1 (prompt v5 + gpt-5.4) |
| 9 | `english_weekly_revision_primary_1.v4_openai_gpt5_4` | English Weekly Revision Primary 1 (Benchmark Test 02 follow-up) |
| 8 | `english_weekly_revision_primary_1.v4_openai_gpt54mini` | English Weekly Revision Primary 1 (Benchmark Test 02) |
| 7 | `science_revision_guide_primary_4.v012_openai_gpt54mini` | Science Revision Guide Primary 4 |
| 6 | `science_revision_guide_primary_4.v011_thoughts_benchmark` | Science Revision Guide Primary 4 (benchmarking observation) |
| 5 | `english_weekly_revision_primary_1.v02` | English Weekly Revision Primary 1 |
| 4 | `english_weekly_revision_primary_1.v01` | English Weekly Revision Primary 1 |
| 3 | `science_thematic_tests_and_exam_practice_primary_4.v01` | Science Thematic Tests and Exam Practice Primary 4 |
| 2 | `science_revision_guide_primary_4.v01` | Science Revision Guide Primary 4 |
| 1 | `math_model_drawing_p3_p4.v01` | Math Model Drawing Made Easy and Inspiring Primary 3 and 4 |

---

## Runs

### 15. grammar-practice-primary-1.v01 — Grammar Practice Primary 1 (Gemini)

| Field | Value |
|--------|--------|
| **Run id** | `grammar-practice-primary-1.v01` |
| **Logged** | 2026-04-19 |
| **Pipeline** | split_book_answer_by_unit_using_ai (Gemini Batch, continuation page-segments) |
| **Registry book label** | `Grammar Practice Primary 1` |
| **Model** | `models/gemini-2.5-pro` |
| **Batch request key** | `book:grammar_practice_primary_1:page_segments_continuation_gemini:p1_4` |
| **Answer pages in batch** | 1–4 |
| **Units in manifest (build)** | 23 (includes `00 Preface + Contents`; answer key segments **Chapters 1–22** only) |
| **Assembled mapping rows** | 22 |
| **Gemini batch job** | `batches/8z47yt77rj4263h6x6lownl4essztz7gy6yq` |
| **Uploaded JSONL (API)** | `files/c4ldpiunl0am` |
| **Status** | completed (`JOB_STATE_SUCCEEDED`; `job.end_time` `2026-04-19T05:16:32.590565+00:00`). |

**Token usage** (from `response.usageMetadata` in `grammar-practice-primary-1.v01.output.jsonl`)

| Field | Value |
|--------|--------|
| **Prompt tokens** | 4,694 |
| **Thoughts tokens** | 2,331 |
| **Candidates tokens** | 926 |
| **Total tokens** | 7,951 |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|--------|
| Batch input JSONL | `batch_artifacts/grammar-practice-primary-1.v01.jsonl` |
| Job metadata | `batch_artifacts/grammar-practice-primary-1.v01.job.json` |
| Job name (one line) | `batch_artifacts/grammar-practice-primary-1.v01.job_name.txt` |
| Raw batch output | `batch_artifacts/grammar-practice-primary-1.v01.output.jsonl` |
| Processed JSON | `batch_artifacts/grammar-practice-primary-1.v01.processed.json` |
| Assembled mappings | `batch_artifacts/grammar-practice-primary-1.v01.assembled.json` |
| Ground-truth JSON | `pilot_ground_truth/grammar_practice_primary_1_ground_truth.json` |
| Ground-truth table | `pilot_ground_truth/grammar_practice_primary_1_ground_truth_table.md` |

**Notes**

- **Import:** `PdfFileManager.import_book_answer_mappings_from_json` with source `ground_truth_grammar_practice_primary_1_v01` — **22** rows imported; `list_book_answer_mappings(book_group_id=…)` shows **22** mappings for this book group.
- **Human validation:** Pending — spot-check split-page flags and chapter boundaries on the four answer pages if anything looks off in the UI.

### 14. conquer_exam_terry_chew_p5_lessons_p1_37.v01 — Conquer Exam Standard Mathematics Problem Sums with Terry Chew Primary 5 (lessons, Gemini)

| Field | Value |
|--------|--------|
| **Run id** | `conquer_exam_terry_chew_p5_lessons_p1_37.v01` |
| **Logged** | 2026-04-17 |
| **Pipeline** | split_book_answer_by_unit_using_ai **prompt v5** (Gemini Batch, continuation page-segments) |
| **Registry book label** | `Conquer Exam Standard Mathematics Problem Sums with Terry Chew Primary 5` |
| **Pre-run registry fix** | Removed **7** duplicate book-group members: student-mirror `_c_` lesson PDFs under `winston.ry.meng@gmail.com/.../P5/Book/...` (kept general `…/Singapore Primary Math/P5/Book/...` template rows). |
| **Manifest filters** | `--unit-include-substring Lesson` and `--unit-exclude-substring Story` (**28** units). |
| **Model** | `models/gemini-2.5-pro` |
| **Batch request key** | `book:conquer_exam_standard_mathematics_problem_sums_with_terry_chew_primary_5:page_segments_continuation_gemini:p1_37` |
| **Answer pages in batch** | 1–37 |
| **Units in manifest** | 28 |
| **Gemini batch job** | `batches/y1zp7nmih580v541g0l7sceatsxyzvr3zol1` |
| **Uploaded JSONL (API)** | `files/j60238k61bic` |
| **Status** | completed (`JOB_STATE_SUCCEEDED`; `job.end_time` `2026-04-17T04:50:02.969492+00:00`). |

**Token usage** (from `response.usageMetadata` in `…v01.output.jsonl`)

| Field | Value |
|--------|--------|
| **Prompt tokens** | 14,511 |
| **Thoughts tokens** | 5,312 |
| **Candidates tokens** | 3,320 |
| **Total tokens** | 23,143 |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|--------|
| Batch input JSONL | `batch_artifacts/conquer_exam_terry_chew_p5_lessons_p1_37.v01.jsonl` |
| Job metadata | `batch_artifacts/conquer_exam_terry_chew_p5_lessons_p1_37.v01.job.json` |
| Job name (one line) | `batch_artifacts/conquer_exam_terry_chew_p5_lessons_p1_37.v01.job_name.txt` |
| Raw batch output | `batch_artifacts/conquer_exam_terry_chew_p5_lessons_p1_37.v01.output.jsonl` |
| Processed JSON | `batch_artifacts/conquer_exam_terry_chew_p5_lessons_p1_37.v01.processed.json` |
| Assembled mappings | `batch_artifacts/conquer_exam_terry_chew_p5_lessons_p1_37.v01.assembled.json` |
| Ground-truth JSON | `pilot_ground_truth/conquer_exam_terry_chew_p5_lessons_ground_truth.json` |
| Ground-truth table | `pilot_ground_truth/conquer_exam_terry_chew_p5_lessons_ground_truth_table.md` |

**Notes**

- **Import:** `PdfFileManager.import_book_answer_mappings_from_json` with source `ground_truth_conquer_exam_terry_chew_p5_lessons_p1_37_v01` — **28** rows imported; `list_book_answer_mappings(book_group_id=…)` shows **28** mappings for this book group.
- **Human validation (2026-04-17):** Manual review of all **28** lesson mappings (answer pages 1–37, split-page flags) — **confirmed correct** end-to-end.

### 13. math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium — Model Drawing Made Easy and Inspiring for P5 and P6 (OpenAI)

| Field | Value |
|--------|--------|
| **Run id** | `math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium` |
| **Logged** | 2026-04-17 |
| **Pipeline** | split_book_answer_by_unit_using_ai **prompt v5** (OpenAI batch variant, `reasoning.effort=medium`) |
| **Registry book label** | `Model Drawing Made Easy and Inspiring for P5 and P6` |
| **Model** | `gpt-5.4` (job `model`: `gpt-5.4-2026-03-05`) |
| **Batch request key** | `book:model_drawing_made_easy_and_inspiring_for_p5_and_p6:page_segments_continuation_openai:p1_138` |
| **Answer pages in batch** | 1–138 |
| **Units in manifest** | 110 |
| **OpenAI batch job** | `batch_69e18a49d3c08190b774598ee50fdd84` |
| **Uploaded JSONL (API)** | `file-H4LpfNgjSC5hCxxQPqRu1G` |
| **Status** | completed (`status: completed`; request_counts: `total=1, completed=1, failed=0`). |

**Token usage**

| Field | Value |
|--------|--------|
| **Input tokens** | 413,252 (`usage.input_tokens`) |
| **Cached input tokens** | 0 (`usage.input_tokens_details.cached_tokens`) |
| **Output tokens** | 16,397 (`usage.output_tokens`) |
| **Reasoning tokens** | 10,026 (`usage.output_tokens_details.reasoning_tokens`) |
| **Total tokens** | 429,649 (`usage.total_tokens`) |
| **Source** | `batch.usage` in `batch_artifacts/math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium.job.json` |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|--------|
| Batch input JSONL | `batch_artifacts/math_model_drawing_p5_p6.v01_openai_gpt5_4_reason_medium.jsonl` (reused for v02 submit) |
| Job metadata | `batch_artifacts/math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium.job.json` |
| Job id (one line) | `batch_artifacts/math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium.job_id.txt` |
| Raw batch output | `batch_artifacts/math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium.output.jsonl` |
| Processed JSON | `batch_artifacts/math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium.processed.json` |
| Assembled mappings | `batch_artifacts/math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium.assembled.json` |
| Pilot ground-truth compare | `batch_artifacts/math_model_drawing_p5_p6.v02_openai_gpt5_4_reason_medium.compare.json` |

**Notes**

- **Benchmark Test 04:** compare target is `pilot_ground_truth/model_drawing_made_easy_p5_p6_ground_truth.json` (**Gemini-derived** anchor, **110** units; same shape as other pilot compares).
- Assembled vs pilot ground truth: **`83/110` exact** (range + split flags), **`86/110` range-only**, **`27`** mismatches incl. flags; predicted unit count **`110`** (no dropped index). See `…compare.json` for per-unit deltas.
- Build for this book was ~`57.8` MiB batch input (138 answer pages as JPEGs).

### 12. math_model_drawing_p3_p4.v02_openai_gpt5_4 — Math Model Drawing Made Easy and Inspiring Primary 3 and 4 (Benchmark Test 03)

| Field | Value |
|--------|--------|
| **Run id** | `math_model_drawing_p3_p4.v02_openai_gpt5_4` |
| **Logged** | 2026-04-16 |
| **Pipeline** | split_book_answer_by_unit_using_ai **prompt v5** (OpenAI batch variant) |
| **Registry book label** | `Math Model Drawing Made Easy and Inspiring Primary 3 and 4` |
| **Model** | `gpt-5.4` (job `model`: `gpt-5.4-2026-03-05`) |
| **Batch request key** | `book:math_model_drawing_made_easy_and_inspiring_primary_3_and_4:page_segments_continuation_openai:p1_68` |
| **Answer pages in batch** | 1–68 |
| **Units in manifest** | 75 |
| **OpenAI batch job** | `batch_69e06be462f4819095176c6cb9351e10` |
| **Uploaded JSONL (API)** | `file-LFLvgQ4F6XUrxybnM5NKxt` |
| **Status** | completed (`status: completed`; request_counts: `total=1, completed=1, failed=0`). |

**Token usage**

| Field | Value |
|--------|--------|
| **Input tokens** | 218,097 (`usage.input_tokens`) |
| **Output tokens** | 4,316 (`usage.output_tokens`) |
| **Reasoning tokens** | 0 (`usage.output_tokens_details.reasoning_tokens`) |
| **Total tokens** | 222,413 (`usage.total_tokens`) |
| **Source** | `batch.usage` in `batch_artifacts/math_model_drawing_p3_p4.v02_openai_gpt5_4.job.json` |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|------|
| Batch input JSONL | `batch_artifacts/math_model_drawing_p3_p4.v02_openai_gpt5_4.jsonl` |
| Job metadata | `batch_artifacts/math_model_drawing_p3_p4.v02_openai_gpt5_4.job.json` |
| Job id (one line) | `batch_artifacts/math_model_drawing_p3_p4.v02_openai_gpt5_4.job_id.txt` |
| Raw batch output | `batch_artifacts/math_model_drawing_p3_p4.v02_openai_gpt5_4.output.jsonl` |
| Processed JSON | `batch_artifacts/math_model_drawing_p3_p4.v02_openai_gpt5_4.processed.json` |
| Assembled mappings | `batch_artifacts/math_model_drawing_p3_p4.v02_openai_gpt5_4.assembled.json` |
| Ground-truth compare | `batch_artifacts/math_model_drawing_p3_p4.v02_openai_gpt5_4.compare.json` |

**Notes**

- **Benchmark Test 03:** first large worked-solutions book in the OpenAI + prompt v5 track; compare against `book_answer_mappings` sourced from human-reviewed Gemini output (`math_model_drawing_p3_p4.v01`, imported as `ground_truth_math_model_drawing_p3_p4_v01`).
- Batch input size ~`29.76` MiB rendered JPEGs for 68 answer pages + front matter (see build stdout for `math_model_drawing_p3_p4.v02_openai_gpt5_4.jsonl`).
- Ground-truth compare (vs registry): **`12/75` exact**, **`13/75` range-only**, **`63`** mismatches including split flags; **`75/75`** predicted units (no dropped index). Many disagreements look like **systematic page alignment / heading detection** drift vs the imported mapping (spot-check mismatches in `…compare.json`).
- Assembler validation: no missing units in span, no continuation violations in the structured diagnostics for this assembled JSON.

### 11. english_weekly_revision_primary_1.v5_openai_gpt54mini — English Weekly Revision Primary 1 (prompt v5 + gpt-5.4-mini)

| Field | Value |
|--------|--------|
| **Run id** | `english_weekly_revision_primary_1.v5_openai_gpt54mini` |
| **Logged** | 2026-04-16 |
| **Pipeline** | split_book_answer_by_unit_using_ai **prompt v5** (OpenAI batch variant) |
| **Registry book label** | `English Weekly Revision Primary 1` |
| **Model** | `gpt-5.4-mini` (job `model`: `gpt-5.4-mini-2026-03-17`) |
| **Batch request key** | `book:english_weekly_revision_primary_1:page_segments_continuation_openai:p1_10` |
| **Answer pages in batch** | 1-10 |
| **Units in manifest** | 42 |
| **OpenAI batch job** | `batch_69e068a9db3c81909de2703309143775` |
| **Uploaded JSONL (API)** | `file-KWxMKFqwywz7aHsJUTRbNE` |
| **Status** | completed (`status: completed`; request_counts: `total=1, completed=1, failed=0`). |

**Token usage**

| Field | Value |
|--------|--------|
| **Input tokens** | 45,557 (`usage.input_tokens`) |
| **Output tokens** | 1,123 (`usage.output_tokens`) |
| **Reasoning tokens** | 0 (`usage.output_tokens_details.reasoning_tokens`) |
| **Total tokens** | 46,680 (`usage.total_tokens`) |
| **Source** | `batch.usage` in `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt54mini.job.json` |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|------|
| Batch input JSONL | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt54mini.jsonl` |
| Job metadata | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt54mini.job.json` |
| Job id (one line) | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt54mini.job_id.txt` |
| Raw batch output | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt54mini.output.jsonl` |
| Processed JSON | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt54mini.processed.json` |
| Assembled mappings | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt54mini.assembled.json` |
| Ground-truth compare | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt54mini.compare.json` |

**Notes**

- Same book and page window as `english_weekly_revision_primary_1.v5_openai_gpt5_4`; **same prompt v5**; model tier **`gpt-5.4-mini`**.
- Ground-truth compare (vs `book_answer_mappings`): predicted **`41`** units; **`21/42` exact**; **`34/42` range-only**; **`21`** mismatches (vs **`20/42` exact**, **`22`** mismatches under prompt v4 + mini on `english_weekly_revision_primary_1.v4_openai_gpt54mini` — marginal delta, still not production-quality on this sample).
- Still missing one assembled unit vs manifest span (same failure class as the v4 mini run).

### 10. english_weekly_revision_primary_1.v5_openai_gpt5_4 — English Weekly Revision Primary 1 (prompt v5 + gpt-5.4)

| Field | Value |
|--------|--------|
| **Run id** | `english_weekly_revision_primary_1.v5_openai_gpt5_4` |
| **Logged** | 2026-04-16 |
| **Pipeline** | split_book_answer_by_unit_using_ai **prompt v5** (OpenAI batch variant) |
| **Registry book label** | `English Weekly Revision Primary 1` |
| **Model** | `gpt-5.4` (job `model`: `gpt-5.4-2026-03-05`) |
| **Batch request key** | `book:english_weekly_revision_primary_1:page_segments_continuation_openai:p1_10` |
| **Answer pages in batch** | 1-10 |
| **Units in manifest** | 42 |
| **OpenAI batch job** | `batch_69e0662236fc81909ed06c5492456265` |
| **Uploaded JSONL (API)** | `file-XbfdrqBK8QNN5KLhYGNMan` |
| **Status** | completed (`status: completed`; request_counts: `total=1, completed=1, failed=0`). |

**Token usage**

| Field | Value |
|--------|--------|
| **Input tokens** | 45,557 (`usage.input_tokens`) |
| **Output tokens** | 1,084 (`usage.output_tokens`) |
| **Reasoning tokens** | 0 (`usage.output_tokens_details.reasoning_tokens`) |
| **Total tokens** | 46,641 (`usage.total_tokens`) |
| **Source** | `batch.usage` in `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt5_4.job.json` |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|------|
| Batch input JSONL | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt5_4.jsonl` |
| Job metadata | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt5_4.job.json` |
| Job id (one line) | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt5_4.job_id.txt` |
| Raw batch output | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt5_4.output.jsonl` |
| Processed JSON | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt5_4.processed.json` |
| Assembled mappings | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt5_4.assembled.json` |
| Ground-truth compare | `batch_artifacts/english_weekly_revision_primary_1.v5_openai_gpt5_4.compare.json` |

**Notes**

- Same book and page window as `english_weekly_revision_primary_1.v4_openai_gpt5_4`; **prompt v5** replaces v4 (operational top-of-page vs continuation rules).
- Ground-truth compare (vs `book_answer_mappings`): **`42/42` exact** (range and split flags); `0` mismatches.
- Input token count is slightly higher than the v4 prompt run on the same pages (`45,557` vs `45,082`) because the system prompt text grew.

### 9. english_weekly_revision_primary_1.v4_openai_gpt5_4 — English Weekly Revision Primary 1 (Benchmark Test 02 follow-up)

| Field | Value |
|--------|--------|
| **Run id** | `english_weekly_revision_primary_1.v4_openai_gpt5_4` |
| **Logged** | 2026-04-16 |
| **Pipeline** | split_book_answer_by_unit_using_ai prompt v4 (OpenAI batch variant) |
| **Registry book label** | `English Weekly Revision Primary 1` |
| **Model** | `gpt-5.4` (job `model`: `gpt-5.4-2026-03-05`) |
| **Batch request key** | `book:english_weekly_revision_primary_1:page_segments_continuation_openai:p1_10` |
| **Answer pages in batch** | 1-10 |
| **Units in manifest** | 42 |
| **OpenAI batch job** | `batch_69e05f8c8218819089e97dc3f27a9965` |
| **Uploaded JSONL (API)** | `file-6xSQSzsZKWXZ2f86rMBGMs` |
| **Status** | completed (`status: completed`; request_counts: `total=1, completed=1, failed=0`). Output downloaded; `process_openai_batch_output.py` + `assemble_ranges_from_page_segments_continuation.py` run locally. |

**Token usage**

| Field | Value |
|--------|--------|
| **Input tokens** | 45,082 (`usage.input_tokens`) |
| **Output tokens** | 942 (`usage.output_tokens`) |
| **Reasoning tokens** | 0 (`usage.output_tokens_details.reasoning_tokens`) |
| **Total tokens** | 46,024 (`usage.total_tokens`) |
| **Source** | `batch.usage` in `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt5_4.job.json` (mirrors per-line `response.body.usage` on the output row) |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|------|
| Batch input JSONL | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt5_4.jsonl` |
| Job metadata | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt5_4.job.json` |
| Job id (one line) | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt5_4.job_id.txt` |
| Raw batch output | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt5_4.output.jsonl` |
| Processed JSON | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt5_4.processed.json` |
| Assembled mappings | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt5_4.assembled.json` |
| Ground-truth compare | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt5_4.compare.json` |

**Notes**

- Same bounded page window and prompt v4 as `english_weekly_revision_primary_1.v4_openai_gpt54mini`; only the OpenAI model tier changed (`gpt-5.4` instead of `gpt-5.4-mini`).
- Ground-truth compare summary (vs `book_answer_mappings`): `42` predicted units; `38/42` exact; `40/42` range-only; `4` mismatches (split-flag / adjacent-unit boundary pairing on units `15`–`16` and `32`–`33`).
- New helper scripts used for this run: `scripts/check_openai_batch_status.py`, `scripts/process_openai_batch_output.py`.

### 8. english_weekly_revision_primary_1.v4_openai_gpt54mini — English Weekly Revision Primary 1 (Benchmark Test 02)

| Field | Value |
|--------|--------|
| **Run id** | `english_weekly_revision_primary_1.v4_openai_gpt54mini` |
| **Logged** | 2026-04-16 |
| **Pipeline** | split_book_answer_by_unit_using_ai prompt v4 (OpenAI batch variant) |
| **Registry book label** | `English Weekly Revision Primary 1` |
| **Model** | `gpt-5.4-mini` (`gpt-5.4-mini-2026-03-17`) |
| **Batch request key** | `book:english_weekly_revision_primary_1:page_segments_continuation_openai:p1_10` |
| **Answer pages in batch** | 1-10 |
| **Units in manifest** | 42 |
| **OpenAI batch job** | `batch_69e057ff2ac881909e77302adb3095bd` |
| **Uploaded JSONL (API)** | `file-7bHPh3ba7EARtWT45FJjbu` |
| **Status** | completed (`status: completed`; request_counts: `total=1, completed=1, failed=0`). Output downloaded and normalized to existing processed/assemble shape. |

**Token usage**

| Field | Value |
|--------|--------|
| **Input tokens** | 45,082 (`usage.input_tokens`) |
| **Output tokens** | 1,129 (`usage.output_tokens`) |
| **Reasoning tokens** | 0 (`usage.output_tokens_details.reasoning_tokens`) |
| **Total tokens** | 46,211 (`usage.total_tokens`) |
| **Source** | `response.body.usage` in `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt54mini.output.jsonl` |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|------|
| Batch input JSONL | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt54mini.jsonl` |
| Job metadata | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt54mini.job.json` |
| Job id (one line) | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt54mini.job_id.txt` |
| Raw batch output | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt54mini.output.jsonl` |
| Processed JSON | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt54mini.processed.json` |
| Assembled mappings | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt54mini.assembled.json` |
| Ground-truth compare | `batch_artifacts/english_weekly_revision_primary_1.v4_openai_gpt54mini.compare.json` |

**Notes**

- Benchmarking context: this is Benchmark Test 02 (see `docs/learnings/benchmarking_learnings.md`).
- Ground-truth compare summary (vs `book_answer_mappings`): truth `42` units; predicted `41` units; `20/42` exact; `34/42` range-only matches; `22` mismatches when including split flags.
- Compared to the prior human-reviewed Gemini Pro run for this book (`english_weekly_revision_primary_1.v02`, prompt v3), this OpenAI prompt v4 run is materially weaker on split-boundary flags and misses an assembled unit boundary.

### 7. science_revision_guide_primary_4.v012_openai_gpt54mini — Science Revision Guide Primary 4

| Field | Value |
|--------|--------|
| **Run id** | `science_revision_guide_primary_4.v012_openai_gpt54mini` |
| **Logged** | 2026-04-16 |
| **Pipeline** | split_book_answer_by_unit_using_ai prompt v3 (OpenAI batch variant) |
| **Registry book label** | `Science Revision Guide Primary 4` |
| **Model** | `gpt-5.4-mini` (`gpt-5.4-mini-2026-03-17`) |
| **Batch request key** | `book:science_revision_guide_primary_4:page_segments_continuation_openai:p1_8` |
| **Answer pages in batch** | 1-8 |
| **Units in manifest** | 11 |
| **OpenAI batch job** | `batch_69e04efeac8c8190b2999a6714ac37d8` |
| **Uploaded JSONL (API)** | `file-X5udW7jkT8tLbSpg463kfr` |
| **Status** | completed (`status: completed`; request_counts: `total=1, completed=1, failed=0`). Output downloaded and normalized to existing processed/assemble shape. |

**Token usage**

| Field | Value |
|--------|--------|
| **Input tokens** | 37,103 (`usage.input_tokens`) |
| **Output tokens** | 852 (`usage.output_tokens`) |
| **Reasoning tokens** | 0 (`usage.output_tokens_details.reasoning_tokens`) |
| **Total tokens** | 37,955 (`usage.total_tokens`) |
| **Source** | `response.body.usage` in `batch_artifacts/science_revision_guide_primary_4.v012_openai_gpt54mini.output.jsonl` |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|------|
| Batch input JSONL | `batch_artifacts/science_revision_guide_primary_4.v012_openai_gpt54mini.jsonl` |
| Job metadata | `batch_artifacts/science_revision_guide_primary_4.v012_openai_gpt54mini.job.json` |
| Job id (one line) | `batch_artifacts/science_revision_guide_primary_4.v012_openai_gpt54mini.job_id.txt` |
| Raw batch output | `batch_artifacts/science_revision_guide_primary_4.v012_openai_gpt54mini.output.jsonl` |
| Processed JSON | `batch_artifacts/science_revision_guide_primary_4.v012_openai_gpt54mini.processed.json` |
| Assembled mappings | `batch_artifacts/science_revision_guide_primary_4.v012_openai_gpt54mini.assembled.json` |
| Ground-truth compare | local compare script output: `7/8` exact, `7/8` range (policy-normalized to `8/8` exact under prompt v4 trailing-blank-page rule) |

**Notes**

- This OpenAI run was prepared to be as close as possible to the successful Gemini sample: same book, same page window (1-8), same rendered image inputs, and same continuation JSON schema contract.
- Ground-truth mismatch observed on unit `10`: predicted `4-8` vs truth `4-7`.
- Re-interpretation after prompt v4 trailing-blank-page policy update: page `8` in `_c_Science Revision Guide Primary 4 - 13 - Answers.pdf` is blank, so content-based normalization treats both `4-7` and `4-8` as equivalent for this sample; policy-normalized outcome is `8/8`.

### 6. science_revision_guide_primary_4.v011_thoughts_benchmark — Science Revision Guide Primary 4 (benchmarking observation)

| Field | Value |
|--------|--------|
| **Run id** | `science_revision_guide_primary_4.v011_thoughts_benchmark` |
| **Logged** | 2026-04-16 |
| **Pipeline** | split_book_answer_by_unit_using_ai prompt v2 benchmark run |
| **Registry book label** | `Science Revision Guide Primary 4` |
| **Models tested** | `models/gemini-2.5-pro`, `models/gemini-2.5-flash`, `models/gemini-2.5-flash-lite` |
| **Pro batch job** | `batches/vmshh0z9z5liaefrurcrocc46nmmg3m2415p` (`JOB_STATE_SUCCEEDED`) |
| **Flash batch job** | `batches/3kbtzl1o9azfaxirffu1574pg2494mjchgas` (`JOB_STATE_CANCELLED` after prolonged `PENDING`) |
| **Flash-Lite batch job** | `batches/eo6r3pyln56y9o3wuonfpe8hvpxkfz4jp97t` (`JOB_STATE_CANCELLED` after prolonged `PENDING`) |
| **Status** | benchmark partially completed; Pro processed successfully, Flash tiers cancelled due to operational queue latency |

**Notes**

- Pro (prompt v2 with thoughts included) processed cleanly and matched ground truth (`8/8` exact on this sample book).
- Flash and Flash-Lite remained in `JOB_STATE_PENDING` for many hours (including resubmission attempts) and were cancelled.
- Operational conclusion for this benchmark: Flash-tier Gemini Batch jobs were not practically usable in this environment due to queue latency, regardless of potential model quality/cost.

### 5. english_weekly_revision_primary_1.v02 — English Weekly Revision Primary 1

| Field | Value |
|--------|--------|
| **Run id** | `english_weekly_revision_primary_1.v02` |
| **Logged** | 2026-04-15 |
| **Pipeline** | split_book_answer_by_unit_using_ai v0.1.3 |
| **Registry book label** | `English Weekly Revision Primary 1` |
| **Gemini model** | `models/gemini-2.5-pro` |
| **Batch request key** | `book:english_weekly_revision_primary_1:page_segments_continuation_gemini:p1_10` |
| **Answer pages in batch** | 1-10 |
| **Units in manifest** | 42 |
| **Gemini batch job** | `batches/xswdcwwi3uufdicoymay9m5p2nxamghl3xya` |
| **Uploaded JSONL (API)** | `files/4bdu6p96blzt` |
| **Status** | completed (`JOB_STATE_SUCCEEDED`). Output downloaded and processed with local `process_gemini_batch_output.py` + `assemble_ranges_from_page_segments_continuation.py`. |

**Token usage**

| Field | Value |
|--------|--------|
| **Input (prompt) tokens** | 8,308 (`promptTokenCount`; breakdown: 4,696 TEXT + 3,612 IMAGE) |
| **Output (candidates) tokens** | 1,630 (`candidatesTokenCount`) |
| **Thinking tokens** | 7,069 (`thoughtsTokenCount`) |
| **Total tokens** | 17,007 (`totalTokenCount`) |
| **Source** | `response.usageMetadata` on the single line in `batch_artifacts/english_weekly_revision_primary_1.v02.output.jsonl` |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|------|
| Batch input JSONL | `batch_artifacts/english_weekly_revision_primary_1.v02.jsonl` |
| Job metadata | `batch_artifacts/english_weekly_revision_primary_1.v02.job.json` |
| Job name (one line) | `batch_artifacts/english_weekly_revision_primary_1.v02.job_name.txt` |
| Raw batch output | `batch_artifacts/english_weekly_revision_primary_1.v02.output.jsonl` |
| Processed JSON | `batch_artifacts/english_weekly_revision_primary_1.v02.processed.json` |
| Assembled mappings | `batch_artifacts/english_weekly_revision_primary_1.v02.assembled.json` |
| Ground truth JSON | `pilot_ground_truth/english_weekly_revision_primary_1_ground_truth.json` |
| Ground truth table | `pilot_ground_truth/english_weekly_revision_primary_1_ground_truth_table.md` |

**Notes**

- Page 5 index alignment corrected: `visible_unit_indices` includes `[21, 22, 23]` for `Assessment 1`, `Practice 21`, `Practice 22`.
- Validation is clean: no missing unit indices within detected span; assembled mapping count is 42.
- Imported to `pdf_file_manager`: 42 mappings imported with source `ground_truth_english_weekly_revision_primary_1_v02` (v01 source fully replaced).

### 4. english_weekly_revision_primary_1.v01 — English Weekly Revision Primary 1

| Field | Value |
|--------|--------|
| **Run id** | `english_weekly_revision_primary_1.v01` |
| **Logged** | 2026-04-15 |
| **Pipeline** | split_book_answer_by_unit_using_ai v0.1.2 |
| **Registry book label** | `English Weekly Revision Primary 1` |
| **Gemini model** | `models/gemini-2.5-pro` |
| **Batch request key** | `book:english_weekly_revision_primary_1:page_segments_continuation_gemini:p1_10` |
| **Answer pages in batch** | 1-10 |
| **Units in manifest** | 42 |
| **Gemini batch job** | `batches/dmilmvxzstraztchbeshxopi4h3teol1o9ku` |
| **Uploaded JSONL (API)** | `files/cllckp9cpalj` |
| **Status** | completed (`JOB_STATE_SUCCEEDED`). Output downloaded and processed with local `process_gemini_batch_output.py` + `assemble_ranges_from_page_segments_continuation.py`. |

**Token usage**

| Field | Value |
|--------|--------|
| **Input (prompt) tokens** | 7,995 (`promptTokenCount`; breakdown: 4,383 TEXT + 3,612 IMAGE) |
| **Output (candidates) tokens** | 1,755 (`candidatesTokenCount`) |
| **Thinking tokens** | 4,545 (`thoughtsTokenCount`) |
| **Total tokens** | 14,295 (`totalTokenCount`) |
| **Source** | `response.usageMetadata` on the single line in `batch_artifacts/english_weekly_revision_primary_1.v01.output.jsonl` |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|------|
| Batch input JSONL | `batch_artifacts/english_weekly_revision_primary_1.v01.jsonl` |
| Job metadata | `batch_artifacts/english_weekly_revision_primary_1.v01.job.json` |
| Job name (one line) | `batch_artifacts/english_weekly_revision_primary_1.v01.job_name.txt` |
| Raw batch output | `batch_artifacts/english_weekly_revision_primary_1.v01.output.jsonl` |
| Processed JSON | `batch_artifacts/english_weekly_revision_primary_1.v01.processed.json` |
| Assembled mappings | `batch_artifacts/english_weekly_revision_primary_1.v01.assembled.json` |
| Ground truth JSON | `pilot_ground_truth/english_weekly_revision_primary_1_ground_truth.json` |
| Ground truth table | `pilot_ground_truth/english_weekly_revision_primary_1_ground_truth_table.md` |

**Notes**

- Build completed with `unit_count: 42`, answer pages `1-10`, and request size `6.87 MB`.
- Assembled mapping count is 41; validation reports missing unit index `41` within detected span.
- Imported to `pdf_file_manager`: 41 mappings imported with source `ground_truth_english_weekly_revision_primary_1_v01`.

### 3. science_thematic_tests_and_exam_practice_primary_4.v01 — Science Thematic Tests and Exam Practice Primary 4

| Field | Value |
|--------|--------|
| **Run id** | `science_thematic_tests_and_exam_practice_primary_4.v01` |
| **Logged** | 2026-04-14 |
| **Pipeline** | split_book_answer_by_unit_using_ai v0.1.0 (MVP) |
| **Registry book label** | `Science Thematic Tests and Exam Practice Primary 4` |
| **Gemini model** | `models/gemini-2.5-pro` |
| **Batch request key** | `book:science_thematic_tests_and_exam_practice_primary_4:page_segments_continuation_gemini:p1_20` |
| **Answer pages in batch** | 1-20 |
| **Units in manifest** | 11 |
| **Gemini batch job** | `batches/mcpaw95raiwzl0eab1lpcpkte6hclvn6lgyz` |
| **Uploaded JSONL (API)** | `files/k882fm3d2mv2` |
| **Status** | completed (`JOB_STATE_SUCCEEDED`). Output downloaded and processed with local `process_gemini_batch_output.py` + `assemble_ranges_from_page_segments_continuation.py`. |

**Token usage**

| Field | Value |
|--------|--------|
| **Input (prompt) tokens** | 7,530 (`promptTokenCount`; breakdown: 1,854 TEXT + 5,676 IMAGE) |
| **Output (candidates) tokens** | 2,173 (`candidatesTokenCount`) |
| **Thinking tokens** | 5,502 (`thoughtsTokenCount`) |
| **Total tokens** | 15,205 (`totalTokenCount`) |
| **Source** | `response.usageMetadata` on the single line in `batch_artifacts/science_thematic_tests_and_exam_practice_primary_4.v01.output.jsonl` |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|------|
| Batch input JSONL | `batch_artifacts/science_thematic_tests_and_exam_practice_primary_4.v01.jsonl` |
| Job metadata | `batch_artifacts/science_thematic_tests_and_exam_practice_primary_4.v01.job.json` |
| Job name (one line) | `batch_artifacts/science_thematic_tests_and_exam_practice_primary_4.v01.job_name.txt` |
| Raw batch output | `batch_artifacts/science_thematic_tests_and_exam_practice_primary_4.v01.output.jsonl` |
| Processed JSON | `batch_artifacts/science_thematic_tests_and_exam_practice_primary_4.v01.processed.json` |
| Assembled mappings | `batch_artifacts/science_thematic_tests_and_exam_practice_primary_4.v01.assembled.json` |

**Notes**

- Book group resolved uniquely by exact label.
- Group members reviewed; single answer file identified as `_c_Science Thematic Tests and Exam Practice Primary 4 - 12 Answers.pdf`.
- Batch input built successfully (`size_mb: 15.99`) and job submitted.
- Ground truth created: `pilot_ground_truth/science_thematic_tests_and_exam_practice_primary_4_ground_truth.json`.
- Human-readable table created: `pilot_ground_truth/science_thematic_tests_and_exam_practice_primary_4_ground_truth_table.md`.
- Imported to `pdf_file_manager`: 11 mappings imported with source `ground_truth_science_thematic_tests_and_exam_practice_primary_4_v01`.

### 2. science_revision_guide_primary_4.v01 — Science Revision Guide Primary 4

| Field | Value |
|--------|--------|
| **Run id** | `science_revision_guide_primary_4.v01` |
| **Logged** | 2026-04-14 |
| **Pipeline** | split_book_answer_by_unit_using_ai v0.1.0 (MVP) |
| **Registry book label** | `Science Revision Guide Primary 4` |
| **Gemini model** | `models/gemini-2.5-pro` |
| **Batch request key** | `book:science_revision_guide_primary_4:page_segments_continuation_gemini:p1_8` |
| **Answer pages in batch** | 1-8 |
| **Units in manifest** | 11 |
| **Gemini batch job** | `batches/dzpj5rrxewqjcmh05omty2dyvsj4m7tflacb` |
| **Uploaded JSONL (API)** | `files/2yr3769isq7k` |
| **Status** | completed (`JOB_STATE_SUCCEEDED`; batch `end_time` 2026-04-14T08:43:37Z). `process_gemini_batch_output.py` + `assemble_ranges_from_page_segments_continuation.py` run locally. |

**Token usage**

| Field | Value |
|--------|--------|
| **Input (prompt) tokens** | 4,884 (`promptTokenCount`; breakdown: 1,788 TEXT + 3,096 IMAGE) |
| **Output (candidates) tokens** | 924 (`candidatesTokenCount`) |
| **Thinking tokens** | 3,417 (`thoughtsTokenCount`) |
| **Total tokens** | 9,225 (`totalTokenCount`) |
| **Source** | `response.usageMetadata` on the single line in `batch_artifacts/science_revision_guide_primary_4.v01.output.jsonl` |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|------|
| Batch input JSONL | `batch_artifacts/science_revision_guide_primary_4.v01.jsonl` |
| Job metadata | `batch_artifacts/science_revision_guide_primary_4.v01.job.json` |
| Job name (one line) | `batch_artifacts/science_revision_guide_primary_4.v01.job_name.txt` |
| Raw batch output | `batch_artifacts/science_revision_guide_primary_4.v01.output.jsonl` |
| Processed JSON | `batch_artifacts/science_revision_guide_primary_4.v01.processed.json` |
| Assembled mappings | `batch_artifacts/science_revision_guide_primary_4.v01.assembled.json` |

**Notes**

- Build command completed and produced one request row (`size_mb: 7.32`).
- Book group members verified before run; answer file identified as `_c_Science Revision Guide Primary 4 - 13 - Answers.pdf`.
- Ground truth created: `pilot_ground_truth/science_revision_guide_primary_4_ground_truth.json`.
- Human-readable table created: `pilot_ground_truth/science_revision_guide_primary_4_ground_truth_table.md`.
- Imported to `pdf_file_manager`: 8 mappings imported with source `ground_truth_science_revision_guide_primary_4_v01`.
- Validation caveat: assembled output includes 8 mappings (manifest has 11 units); missing index `9` within detected span and continuation rule violation at answer page `4`.

### 1. math_model_drawing_p3_p4.v01 — Math Model Drawing Made Easy and Inspiring Primary 3 and 4

| Field | Value |
|--------|--------|
| **Run id** | `math_model_drawing_p3_p4.v01` |
| **Logged** | 2026-04-14 |
| **Pipeline** | split_book_answer_by_unit_using_ai v0.1.0 (MVP) |
| **Registry book label** | `Math Model Drawing Made Easy and Inspiring Primary 3 and 4` |
| **Gemini model** | `models/gemini-2.5-pro` |
| **Batch request key** | `book:math_model_drawing_made_easy_and_inspiring_primary_3_and_4:page_segments_continuation_gemini:p1_68` |
| **Answer pages in batch** | 1–68 |
| **Units in manifest** | 75 (front matter: Preface/TOC excluded from units; answer file excluded) |
| **Gemini batch job** | `batches/c9swcdyjkec19057gf5xwtvxy9hzqfbfjaq6` |
| **Uploaded JSONL (API)** | `files/0uy77owi0ard` |
| **Status** | completed (`JOB_STATE_SUCCEEDED`; batch `end_time` 2026-04-14T04:46:56Z). `process_gemini_batch_output.py` + `assemble_ranges_from_page_segments_continuation.py` run locally. |

**Token usage**

| Field | Value |
|--------|--------|
| **Input (prompt) tokens** | 26,201 (`promptTokenCount`; breakdown: 7,625 TEXT + 18,576 IMAGE) |
| **Output (candidates) tokens** | 6,704 (`candidatesTokenCount`) |
| **Thinking tokens** | 13,466 (`thoughtsTokenCount`) |
| **Total tokens** | 46,371 (`totalTokenCount`) |
| **Source** | `response.usageMetadata` on the single line in `batch_artifacts/math_model_drawing_p3_p4.v01.output.jsonl` |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|------|
| Batch input JSONL | `batch_artifacts/math_model_drawing_p3_p4.v01.jsonl` |
| Job metadata | `batch_artifacts/math_model_drawing_p3_p4.v01.job.json` |
| Job name (one line) | `batch_artifacts/math_model_drawing_p3_p4.v01.job_name.txt` |
| Raw batch output | `batch_artifacts/math_model_drawing_p3_p4.v01.output.jsonl` |
| Processed JSON | `batch_artifacts/math_model_drawing_p3_p4.v01.processed.json` |
| Assembled mappings | `batch_artifacts/math_model_drawing_p3_p4.v01.assembled.json` |

**Notes**

- Build: `build_gemini_page_segments_continuation_batch_input.py --book-label "Math Model Drawing Made Easy and Inspiring Primary 3 and 4"`.
- Answer PDF: registered unit `_c_Math Model Drawing Made Easy and Inspiring Primary 3 and 4 - 77 - Worked Solutions.pdf`.
- `book_context.identify_front_matter` extended for “Preface and Table of Contents” (see `scripts/book_context.py`).
- Assembled output: 75 unit mappings (`unit_index` 2–76 in manifest order; preface is front matter only). Next step: review and import into `pdf_file_manager` `book_answer_mappings` if acceptable.
- Human validation: spot-checked unit-to-answer-page ranges; sampled mappings look correct.
- Imported to `pdf_file_manager`: 75 mappings imported with source `ground_truth_math_model_drawing_p3_p4_v01`.

---

## Template (copy below the line)

```
### <N>. <short slug> — <book group label>

Use **N** = the run’s index in the **Run index** table (stable: **oldest is 1**; new runs get the **next** `#`—insert the index row at the **top** of the table as the first data row, then paste this block at the **top** of `## Runs`, directly under the `## Runs` heading).

| Field | Value |
|--------|--------|
| **Run id** | `<artifact basename stem, e.g. science_practice_primary_5_and_6.v02>` |
| **Logged** | YYYY-MM-DD |
| **Pipeline** | split_book_answer_by_unit_using_ai (see `README.md` version) |
| **Registry book label** | Exact `file_groups.label` in `PdfFileManager` |
| **Gemini model** | e.g. `models/gemini-2.5-pro` |
| **Batch request key** | From build stdout: `key: book:...` |
| **Answer pages in batch** | e.g. `1–68` (inclusive) |
| **Units in manifest** | Count from build stdout (`unit_count`) |
| **Gemini batch job** | e.g. `batches/...` (from `submit_gemini_batch.py` or `*.job.json`) |
| **Uploaded JSONL (API)** | e.g. `files/...` (from job JSON `uploaded_file.name`) |
| **Status** | `batch built` / `submitted` / `completed` / `failed` (+ short note) |

**Token usage** (fill after the batch finishes; source is often the job in Google AI Studio / Gemini API `completion_stats`, or usage metadata on the batch result)

| Field | Value |
|--------|--------|
| **Input (prompt) tokens** | |
| **Output (candidates) tokens** | |
| **Thinking tokens** | (if reported; else `—`) |
| **Total tokens** | (if API gives a single total; else sum or `—`) |
| **Source** | e.g. `*.job.json` after completion, API response, or console export |

**Artifacts (repo-relative)**

| Stage | Path |
|--------|------|
| Batch input JSONL | `batch_artifacts/<run id>.jsonl` |
| Job metadata | `batch_artifacts/<run id>.job.json` |
| Job name (one line) | `batch_artifacts/<run id>.job_name.txt` |
| Raw batch output | `batch_artifacts/<run id>.output.jsonl` |
| Processed JSON | `batch_artifacts/<run id>.processed.json` |
| Assembled mappings | `batch_artifacts/<run id>.assembled.json` |
| Ground-truth compare | (optional) command + result summary |

**Notes**

- Anything that matters later: prompt edits, `--omit-front-matter`, partial page window, registry fixes, import into `book_answer_mappings`, etc.
- When adding a run: insert a row at the **top** of the **Run index** table with the next `#`, set **N** to that same number, and paste this block at the **top** of `## Runs` (directly under the heading).
```
