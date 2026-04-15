# CHANGELOG

## v0.1.1 - 2026-04-15

### Changed

- Continuation prompt (`prompts/book_answer_page_segments_continuation_prompt.md`): clarified `continued_unit_index` as the last answer-unit still continuing at the top of the page, including manifest units that have no answer section (explicit `08`→`10` example).
- Assembler (`scripts/assemble_ranges_from_page_segments_continuation.py`): manifest-order predecessor mismatches (e.g. continued `08` before visible `10` when manifest `09` has no answer section) are recorded as **`continuation_rule_warnings`** with `severity: warning`, not **`continuation_rule_violations`**.

## v0.1.0 - 2026-04-13

### Added

- Cleaned, production-oriented MVP layout centered on continuation-aware page-segments pipeline.
- Shared context helper module: `scripts/book_context.py`.
- Updated README to document a single canonical workflow.

### Kept

- All `pilot_ground_truth/*.json` files for record-keeping and regression checks.

### Removed (historical / superseded artifacts)

- Iteration logs and attempt notes:
  - `ATTEMPT_ITERATION.md`
  - `GEMINI3_DEBUG_BRIEF_ATTEMPT22.md`
  - `ATTEMPT24_RUNBOOK.md`
  - `ATTEMPT24_FULL_RUNBOOK.md`
  - `ATTEMPT24_CONTINUATION_SCHEMA_SPEC.md`
- Non-MVP prompt variants:
  - `prompts/book_answer_mapping_prompt.md`
  - `prompts/book_answer_boundary_prompt.md`
  - `prompts/book_answer_page_segments_prompt.md`
- Legacy/one-off scripts and superseded pipelines:
  - `_build_model_drawing_*`
  - `_rename_model_drawing_global_index.py`
  - `build_book_batch_input.py`
  - `build_book_boundary_batch_input.py`
  - `build_gemini_boundary_batch_input.py`
  - `build_gemini_page_segments_batch_input.py`
  - `assemble_ranges_from_boundaries.py`
  - `assemble_ranges_from_page_segments.py`
  - `run_gemini_boundary_pilot.py`
  - `run_gemini_page_segments_pilot.py`
  - `run_zai_boundary_pilot.py`
  - `submit_batch.py`
  - `check_batch_status.py`
  - `process_batch_output.py`
- Derived experiment outputs and scratch verification files:
  - all contents under `batch_artifacts/`
  - all contents under `tmp_verification/`
- Non-JSON pilot note:
  - `pilot_ground_truth/english_practice_1000_ground_truth_by_answer_page.md`

## v0.0.900 - Historical snapshot retired on 2026-04-13

This tag captures the pre-cleanup experimental era (Attempts 1-24), culminating in the continuation-ownership page-segments design validated in Attempt 24.

### Historical highlights (Attempts 19-24)

- Attempt 19: mapping-style output remained unreliable under spot-checking.
- Attempt 20-22: boundary-first design improved structure but still had practical misses/ambiguities.
- Attempt 23: page-segments design achieved full row coverage with much higher quality.
- Attempt 24: continuation-ownership schema removed the major residual failure mode and reached 39/39 pilot accuracy in the documented U1-U2 validation slice.

The v0.1.0 MVP is built from these lessons and keeps only the forward path.
