---
name: process-book-answer-file
description: Find a target book by label/keywords, run the split_book_answer_by_unit_using_ai end-to-end batch pipeline, produce assembled mappings, create ground-truth + human-readable mapping table, and import mappings into pdf_file_manager book_answer_mappings. Use when the user asks to process a book answer file, map units to answer pages, or mentions keywords like 'Math model drawing P3/P4'.
---

# Process Book Answer File

Use this workflow when the user wants a full unit-to-answer-page mapping run from a book name (or fuzzy keywords) through registry import.

## Human checkpoints vs automation

### Human-required checkpoints

- Confirm the intended book when fuzzy keywords match multiple `book` groups.
- Spot-check sampled unit-to-answer-page ranges before final acceptance.
- Approve final promotion to trusted ground truth if ambiguous pages exist.

### Fully automatable steps

- Build, submit, poll, process, and assemble the Gemini batch pipeline.
- Generate ground-truth JSON and human-readable table from assembled output + registry metadata.
- Import mappings into `pdf_file_manager` and verify counts.
- Update `RUN_LOGS.md` with run IDs, artifacts, status, and token usage.

## Guardrails

- Prefer `PdfFileManager` APIs or `pdf_*` tools; do not query registry SQLite directly for normal operations.
- Keep all run artifacts under `ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/`.
- Log every run in `ai_study_buddy/split_book_answer_by_unit_using_ai/RUN_LOGS.md`.
- If the batch has not finished, do not invent token usage; mark pending.

## Inputs to collect

- Book hint from user (exact label or keywords, e.g. `Math model drawing P3 and P4`).
- Whether to submit/poll batch now.
- Whether to import assembled/ground-truth mappings into `pdf_file_manager` now.

## Step-by-step

### 1) Resolve the target book group

1. Use `PdfFileManager().list_file_groups(group_type="book")`.
2. Match by exact `label` first; else fuzzy match on keywords.
3. Confirm selected `book_label` with user if ambiguity exists.

Also verify key members from group:
- one answer file (`Worked Solutions` / `Answers` / answer keywords)
- front matter (if present)
- unit files to map

**Exit criteria**

- Exactly one target `book_label` selected.
- Exactly one answer file identified in group members.
- Unit files are present and indexable for mapping.
- If multiple candidate books exist, user confirmed the chosen one.
- Stop and resolve gaps before proceeding to Step 2.

### 2) Build batch input JSONL

Use:

```bash
python3 ai_study_buddy/split_book_answer_by_unit_using_ai/scripts/build_gemini_page_segments_continuation_batch_input.py \
  --book-label "<EXACT_BOOK_LABEL>" \
  --output ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/<run_id>.jsonl
```

Capture from stdout:
- `key: book:...`
- `answer_pages`
- `unit_count`

Recommended run id: `<slug>.v01`, `<slug>.v02`, etc.

**Exit criteria**

- JSONL exists at `batch_artifacts/<run_id>.jsonl`.
- Build stdout captured `key`, `answer_pages`, and `unit_count`.
- JSONL size is non-zero and loadable as JSONL.
- Stop and resolve gaps before proceeding to Step 3.

### 3) Submit batch

```bash
python3 ai_study_buddy/split_book_answer_by_unit_using_ai/scripts/submit_gemini_batch.py \
  ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/<run_id>.jsonl \
  --job-info ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/<run_id>.job.json \
  --job-name-file ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/<run_id>.job_name.txt
```

Record:
- uploaded file id (`files/...`)
- batch job id (`batches/...`)

**Exit criteria**

- `batch_artifacts/<run_id>.job.json` exists.
- `batch_artifacts/<run_id>.job_name.txt` exists.
- Both uploaded file id and batch job id are recorded.
- Stop and resolve gaps before proceeding to Step 4.

### 4) Poll/download output (if requested)

```bash
python3 ai_study_buddy/split_book_answer_by_unit_using_ai/scripts/check_gemini_batch_status.py \
  --job-info ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/<run_id>.job.json \
  --poll --poll-interval 30 \
  --output ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/<run_id>.output.jsonl
```

**Exit criteria**

- If polling was requested: job state is terminal (`SUCCEEDED` / `FAILED` / `CANCELLED` / `EXPIRED`).
- If `SUCCEEDED`: output JSONL exists at `batch_artifacts/<run_id>.output.jsonl`.
- If user asked not to poll: skip this step and mark status as `submitted`.
- Stop and resolve gaps before proceeding to Step 5.

### 5) Process and assemble mappings

```bash
python3 ai_study_buddy/split_book_answer_by_unit_using_ai/scripts/process_gemini_batch_output.py \
  -i ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/<run_id>.output.jsonl \
  -o ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/<run_id>.processed.json

python3 ai_study_buddy/split_book_answer_by_unit_using_ai/scripts/assemble_ranges_from_page_segments_continuation.py \
  --custom-id <batch_request_key> \
  --processed ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/<run_id>.processed.json \
  --output ai_study_buddy/split_book_answer_by_unit_using_ai/batch_artifacts/<run_id>.assembled.json
```

**Exit criteria**

- Processed JSON exists and contains `results[<custom-id>]`.
- Assembled JSON exists and contains non-empty `mappings`.
- `mapping_count` (if present) equals `len(mappings)`.
- Stop and resolve gaps before proceeding to Step 6.

### 6) Create ground truth + human-readable table

Create both files under:
- `ai_study_buddy/split_book_answer_by_unit_using_ai/pilot_ground_truth/<slug>_ground_truth.json`
- `ai_study_buddy/split_book_answer_by_unit_using_ai/pilot_ground_truth/<slug>_ground_truth_table.md`

Ground-truth JSON should include:
- `book_label`
- `answer_file`
- `source`
- `batch_job`
- `mappings[]` with: `unit_index`, `unit_file`, `unit_label`, `answer_page_start`, `answer_page_end`, `starts_mid_page`, `ends_mid_page`, `notes`

Build `unit_file`/`unit_label` from registry group members mapped by `unit_index` (not guessed from assembled JSON alone).

**Exit criteria**

- Ground-truth JSON created with required fields and non-empty `mappings`.
- Every mapping row has `unit_file` and `unit_label` resolved from registry members.
- Human-readable table created and row count matches mapping count.
- Stop and resolve gaps before proceeding to Step 7.

### 7) Import to pdf_file_manager

```python
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
mgr = PdfFileManager()
mgr.import_book_answer_mappings_from_json(
    "ai_study_buddy/split_book_answer_by_unit_using_ai/pilot_ground_truth/<slug>_ground_truth.json",
    source="ground_truth_<slug>_<version>"
)
```

Then verify mapping count for that book group.

**Exit criteria**

- Import call succeeds without exceptions.
- Imported mapping count equals ground-truth mapping count.
- Post-import mapping count for the book group matches expected total.
- Stop and resolve gaps before proceeding to Step 8.

### 8) Update RUN_LOGS.md

Add/update the run entry with:
- status (`submitted`/`completed`/`failed`)
- artifact paths
- token usage (`response.usageMetadata` from output JSONL when available)
- human validation note if user spot-check confirms quality
- import confirmation count/source

**Exit criteria**

- Run entry exists for `<run_id>` with current status.
- Artifact paths reflect actual files generated in this run.
- Token usage is filled when available, else explicitly marked `pending`.
- Notes include validation/import outcome when those actions were performed.
- Stop and resolve gaps before declaring the run complete.

## Quick checklist (completion)

- [ ] Book resolved to one `book` file group label
- [ ] Batch JSONL built with captured key/page window/unit count
- [ ] Job submitted and IDs logged
- [ ] Output processed + assembled (if batch completed)
- [ ] Ground-truth JSON created
- [ ] Human-readable table created
- [ ] Ground truth imported into `pdf_file_manager`
- [ ] RUN_LOGS.md updated with tokens and validation/import notes
