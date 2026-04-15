# Unit-to-answer-page mapping run log

Append one block per **end-to-end** run of the continuation page-segments pipeline (`build` → `submit` → `poll` → `process` → `assemble`, and optional ground-truth compare). Keeps enough context to reproduce, debug, or correlate with `pdf_file_manager` book groups.

**Convention:** Newest runs at the **top**. Copy the template below for each run; replace placeholders and add rows under **Artifacts** as files appear.

---

## Template (copy below the line)

```
### <short slug> — <book group label>

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
```

---

## Runs

### english_weekly_revision_primary_1.v02 — English Weekly Revision Primary 1

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

### english_weekly_revision_primary_1.v01 — English Weekly Revision Primary 1

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

### science_thematic_tests_and_exam_practice_primary_4.v01 — Science Thematic Tests and Exam Practice Primary 4

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

### science_revision_guide_primary_4.v01 — Science Revision Guide Primary 4

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

### math_model_drawing_p3_p4.v01 — Math Model Drawing Made Easy and Inspiring Primary 3 and 4

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
