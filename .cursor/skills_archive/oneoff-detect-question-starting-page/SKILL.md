---
name: oneoff-detect-question-starting-page
description: One-off AI operator workflow to populate `context.question_page_map` for a single canonical marking-result JSON by visually mapping each gradable `question_results[].result_id` to its earliest attempt page. This workflow may repair/generate missing attempt PNG assets first, then mutates only mapping data (plus explicit schema upgrade step when needed).
---

# One-off Detect Question Starting Page

Use this skill when you need per-question attempt-page anchors in one existing marking artifact.

## Goal

Given one marking-result JSON file, produce a valid `context.question_page_map` with one entry per confidently mapped gradable question:

- `result_id`
- `attempt_page_start`
- `confidence`
- `source`
- optional `evidence_image`
- optional `note`

## Input

- Exactly one canonical JSON path under:
  - `ai_study_buddy/context/marking_results/**`

## Required procedure

1. **Load target artifact**
   - Read JSON and verify it has `context` and `question_results`.

2. **Build gradable result list**
   - Extract gradable `result_id` rows from `question_results`.
   - Preserve row order for review and reporting.

3. **Resolve marking assets**
   - Resolve `context.marking_asset` directory under `ai_study_buddy/context/`.
   - Verify attempt PNG set exists and is complete for the intended grading scope.
   - Preferred attempt folder: `<marking_asset>/attempt/`.
   - Preferred filename pattern: `attempt-page-NN.png`.

4. **Repair/generate attempt PNGs when needed**
   - If asset folder is missing, or attempt PNG set is incomplete/unusable:
     - regenerate attempt page PNGs from `context.attempt_file_path` PDF
     - write into `<marking_asset>/attempt/`
   - Do not continue mapping until attempt pages are complete for the intended scope.

5. **Visual mapping pass**
   - Inspect attempt PNGs page-by-page.
   - For each `result_id`, assign earliest page where the question first appears.
   - Add `confidence`:
     - `high`: clear, unambiguous first appearance
     - `medium`: readable but partially occluded/ambiguous numbering
     - `low`: weak evidence only (include explanatory `note`)
   - Set `source`:
     - `manual_visual` for this one-off workflow
   - Add `evidence_image` when available (typically `attempt/attempt-page-NN.png`).

6. **Constrained JSON mutation**
   - Allowed write scope:
     - `context.question_page_map`
   - Optional explicit migration step:
     - if needed, set `schema_version` to `marking_result.v1.4`
   - Do **not** edit other fields (scores, diagnosis, generation, summary, etc.).

7. **Validate**
   - Validate with package validator after write.
   - Ensure map membership/uniqueness/page/enum checks pass.

8. **Run summary**
   - Report:
     - target JSON path
     - number of gradable rows
     - number of mapped rows
     - unresolved rows (if any)
     - whether PNG regeneration was required
     - whether validation passed

## Mutation guardrails

- Never fabricate page `0`.
- Never duplicate map entries for one `result_id`.
- If a row is unresolved, omit it and document reason.
- Keep operation idempotent: re-runs should converge to same map unless better evidence is introduced.
