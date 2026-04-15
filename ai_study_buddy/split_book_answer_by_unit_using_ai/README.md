# split_book_answer_by_unit_using_ai

Version: **v0.1.1**

This utility detects answer-page ranges for per-unit files using a single production pipeline:

1. Build a Gemini batch request with the continuation-aware page-segments prompt.
2. Submit and poll the Gemini batch job.
3. Parse batch output into structured JSON.
4. Assemble deterministic per-unit page ranges (including split-page flags).
5. Optionally compare against saved ground truth.

**v0.1.1:** Continuation prompt clarified: `continued_unit_index` is the last answer-unit still continuing at the top of the page (skip manifest-only units with no answer section), with an explicit `08`→`10` example.

## Why this MVP exists

After iterative attempts, the continuation-aware page-segments design (finalized in Attempt 24) is the baseline:

- Handles top-of-page continuation explicitly via `continued_unit_index`.
- Keeps visible starts explicit via `visible_unit_indices`.
- Preserves non-registry prefix content (for intro/front sections).
- Produces deterministic assembly with validation diagnostics.

## Folder layout

- `prompts/book_answer_page_segments_continuation_prompt.md`: Canonical prompt.
- `scripts/book_context.py`: Registry + book-context helpers.
- `scripts/build_gemini_page_segments_continuation_batch_input.py`: Build one-book Gemini JSONL request.
- `scripts/submit_gemini_batch.py`: Upload JSONL and create Gemini batch job.
- `scripts/check_gemini_batch_status.py`: Poll job and download output.
- `scripts/process_gemini_batch_output.py`: Parse Gemini output JSONL.
- `scripts/assemble_ranges_from_page_segments_continuation.py`: Deterministic range assembly.
- `scripts/compare_with_ground_truth.py`: Optional validation against a saved truth JSON.
- `pilot_ground_truth/*.json`: Preserved historical ground-truth records.
- `batch_artifacts/`: Runtime output location (intentionally not curated as source).

## Prerequisites

- `GOOGLE_AI_DAYDREAMEDU_KEY` set in environment.
- Local PDF registry available via `PdfFileManager`.
- Python deps used by scripts (`google-genai`, `PyMuPDF`, `Pillow`).

## Standard run (one book)

From repo root:

```bash
python3 ai_study_buddy/split_book_answer_by_unit_using_ai/scripts/build_gemini_page_segments_continuation_batch_input.py \
  --book-label "Science Practice Primary 5 and 6" \
  --output ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/science_practice_primary_5_and_6.v01.jsonl

python3 ai_study_buddy/split_book_answer_by_unit_using_ai/scripts/submit_gemini_batch.py \
  ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/science_practice_primary_5_and_6.v01.jsonl \
  --job-info ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/science_practice_primary_5_and_6.v01.job.json \
  --job-name-file ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/science_practice_primary_5_and_6.v01.job_name.txt

python3 ai_study_buddy/split_book_answer_by_unit_using_ai/scripts/check_gemini_batch_status.py \
  --job-info ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/science_practice_primary_5_and_6.v01.job.json \
  --poll --poll-interval 30 \
  --output ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/science_practice_primary_5_and_6.v01.output.jsonl

python3 ai_study_buddy/split_book_answer_by_unit_using_ai/scripts/process_gemini_batch_output.py \
  -i ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/science_practice_primary_5_and_6.v01.output.jsonl \
  -o ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/science_practice_primary_5_and_6.v01.processed.json

python3 ai_study_buddy/split_book_answer_by_unit_using_ai/scripts/assemble_ranges_from_page_segments_continuation.py \
  --custom-id book:science_practice_primary_5_and_6:page_segments_continuation_gemini:p1_39 \
  --processed ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/science_practice_primary_5_and_6.v01.processed.json \
  --output ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/science_practice_primary_5_and_6.v01.assembled.json
```

## Optional: compare to ground truth

```bash
python3 ai_study_buddy/split_book_answer_by_unit_using_ai/scripts/compare_with_ground_truth.py \
  --processed ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/science_practice_primary_5_and_6.v01.assembled.json \
  --ground-truth ai_study_buddy/split_book_answer_by_unit_using_ai/pilot_ground_truth/science_practice_primary_5_and_6_ground_truth.json
```

## Notes

- `unit_index` ordering is resolved from registry filenames/metadata in `book_context.py`.
- `batch_artifacts/` is for local run outputs, not long-term archival.
- Historical attempt logs/runbooks/artifacts were retired in this v0.1 cleanup; see `CHANGELOG.md`.
