---
name: mark-student-work-multi-agent-v2
description: Orchestrates a multi-agent workflow to mark a student's completion PDF (either against an answer key or from teacher annotations). Uses the `Task` tool to spawn isolated subagents for structural mapping, parallel transcription/grading, and taxonomy tagging. Outputs a canonical JSON marking artifact and a derived markdown learning report. Use when the user asks to mark, grade, or diagnose a student's work using the multi-agent architecture.
---

# Multi-Agent Student Work Marking Orchestrator

This skill acts as the **Orchestrator** for a Hierarchical Multi-Agent System. Do not attempt to read the attempt images, grade the questions, or assign skill tags yourself. Your job is to resolve the context, spawn specialized subagents using the `Task` tool, assemble their outputs, and write the final artifacts.

## Language Policy (mandatory)

Language consistency is a hard quality gate for all phases that emit free-text fields:

- For `subject_context` in `{singapore_primary_math, singapore_primary_science, singapore_primary_english}`:
  - Require **English-only** free text in agent outputs (`student_answer`, `correct_answer`, `diagnosis.reasoning`, `human_note`, and other narrative fields).
- For `subject_context` in `{singapore_primary_chinese, singapore_primary_higher_chinese}`:
  - Allow Chinese in `diagnosis.reasoning` (and optional explanatory notes), but keep taxonomy keys (`mistake_type`, `error_tags`) in English enums.
- Always pass explicit language instructions in every Phase 2 and Phase 3 Task prompt:
  - `subject_context=<...>`
  - `required_output_language=english|chinese`
  - `language_policy=<one-line rule>`

If a subagent output violates language policy, treat it as malformed output and retry that subagent with explicit correction instructions. Do not proceed with mixed-language payloads.

**CRITICAL ORCHESTRATOR BOUNDARY:**
You are the Orchestrator. You manage the workflow, but you **MUST NEVER** perform the grading, transcription, or tagging tasks yourself. 
If a subagent fails, times out, or returns malformed data, you MUST either:
1. Retry launching the subagent for that specific task.
2. Stop the workflow and report the error to the user.

**Under NO circumstances** should you attempt to "fill in the blanks" or grade the remaining questions yourself. If you do, you will hallucinate and corrupt the final artifact.

## 1. Resolve the Marking Context

Before spawning any subagents, you must resolve the context using `PdfFileManager` (or `ai_study_buddy.marking.resolve_marking_context(...)`). 

Determine:
1. The student attempt PDF path.
2. The template PDF path (if applicable).
3. The answer PDF path and page range (if applicable).
4. The workflow mode:
   - **Mode A (Standard):** An answer key is available (either mapped or embedded).
   - **Mode B (Teacher-Annotated):** No answer key is available; the attempt is annotated by a teacher.

Render the required pages into the standard Marking Asset Bundle (`context.marking_asset`) under `attempt/page-{nn}.png` and `answers/page-{nn}.png` (if applicable).

**Preferred package entrypoints:**
- `ai_study_buddy.marking.render_attempt_pdf_to_bundle(...)`
- `ai_study_buddy.marking.render_answers_pdf_pages_to_bundle(...)`

Example:
```python
from ai_study_buddy.marking import render_answers_pdf_pages_to_bundle, render_attempt_pdf_to_bundle

render_attempt_pdf_to_bundle(input_attempt_pdf, bundle_root, dpi_scale=2.0)
render_answers_pdf_pages_to_bundle(input_answer_pdf, bundle_root, pages_1_based=[11, 12, 13], dpi_scale=2.0)
```

**MAB directory (bundle root):** Do not render into ad-hoc paths such as `ai_study_buddy/context/marking_asset_bundles/...`. The bundle root must match the directory that `write_marking_artifact` will record as `context.marking_asset`: under `ai_study_buddy/context/marking_assets/<student_slug>/<subject_context>/<attempt_basename>/`, where `<attempt_basename>` follows `build_attempt_basename(...)` in `ai_study_buddy.marking.core.artifact_paths` (same timestamp you will use for `created_at` on the artifact). Resolve `bundle_root` with `marking_asset_rel_path_from_artifact_path(build_marking_artifact_path(provisional_artifact), context_root=...)` joined to `context_root`, then render PNGs there so Phase 1–4 subagents read the same tree the finalized JSON points at.

## 2. Phase 1: Scope, Mapper & Key Verifier Subagent

Use the `Task` tool to launch the project subagent `marking-phase1-mapper` (by name), and omit explicit model pinning so frontmatter (`model: inherit`) is respected.

Pass bundle paths and context (mode, attempt pages, answer pages) to this subagent. It returns the JSON mapping of `question_id` → `attempt_pages`.

**Task template (Phase 1):**
```python
phase1 = Task(
    subagent_type="marking-phase1-mapper",
    prompt=(
        "Read attempt/answer bundle images and return ONLY JSON array "
        "of {question_id, attempt_pages}.\\n"
        f"mode={workflow_mode}\\n"
        f"bundle_root={bundle_root}\\n"
        f"attempt_glob={bundle_root / 'attempt/page-*.png'}\\n"
        f"answers_glob={bundle_root / 'answers/page-*.png'}"
    ),
)
```

Wait for this subagent to return the JSON array. Save this array to `context.marking_asset/debug/phase1_mapping.json`.

### Phase 1 Quality Check Gate (required)

Before proceeding to Phase 2, validate the Phase 1 mapping output:

1. **Duplicate `question_id` check (hard fail):**
   - Build the set/count of all `question_id` values.
   - If any `question_id` appears more than once, do **not** continue.
   - Retry Phase 1 with an explicit correction instruction to disambiguate/relabel duplicated IDs.

2. **Section collision check (hard fail for sectioned papers):**
   - If the paper is sectioned (e.g., Section A / Section B), `question_id` values MUST encode section context (for example `A1`, `A2b`, `B1`, `B1a`) instead of bare labels like `Q1`, `Q1(a)`.
   - Treat this as a hard fail if section context is missing from IDs in a sectioned paper, even when exact string duplicates do not exist.
   - Also treat it as a hard fail when IDs share the same parent stem across sections without section prefixes (for example `Q1` in one section and `Q1(a)` in another), because users will still read these as conflicting.
   - On fail, retry Phase 1 and explicitly require section-prefixed IDs for every row.

3. **Persist QC evidence:**
   - Write a small QC artifact to `context.marking_asset/debug/phase1_qc.json` containing:
     - `total_rows`
     - `unique_question_ids`
     - `duplicate_question_ids` (array)
     - `section_collision_detected` (boolean)
     - `qc_passed` (boolean)
   - Only allow Phase 2 when `qc_passed` is `true`.

## 3. Phase 2: Optimistic Fast-Pass Grader Subagent

Use the `Task` tool to launch `marking-phase2-fast-pass-grader` subagents to do a fast pass over ALL questions.

**CRITICAL PERFORMANCE OPTIMIZATION:** Do not pass all questions to a single subagent if the paper has more than 15 questions. The subagent will hit output token limits and truncate the JSON. Instead, split the `attempt_pages_map` into chunks of 10-15 questions each. Launch a separate `marking-phase2-fast-pass-grader` subagent **IN PARALLEL** for each chunk.

### Phase 2 MCQ Bracket Safeguards (required)

Before finalizing any MCQ as unanswered:

- Perform a focused read of the answer bracket region (where the final choice is written).
- Treat faint, thin, or single-stroke digit-like marks (for example a lightly written `1`) as a **potential response**, not immediate blank.
- If the mark is ambiguous (could be a valid digit or noise), do **not** emit `no_response` at high confidence. Emit low transcription confidence so it is forced into Phase 3 review.
- If the student indicates a choice indirectly (for example by ticking statements that map to one option, as in “A and B only”), treat that as a valid response signal and describe it in `student_answer` / `human_note`.
- **Localization QC gate (minimal, required):** before emitting a high-confidence blank/no_response for any MCQ, save:
  - one full-page overlay image with the bracket box drawn (`debug/mcq_box_checks/<question_id>_overlay.png`)
  - one tight bracket crop (`debug/mcq_box_checks/<question_id>_tight.png`)
  If the overlay does not clearly land on the intended question row, retry localization once. If still uncertain, do not emit a confident blank; downgrade confidence and route to Phase 3.

For each chunked invocation, pass:

- `attempt_pages_map` chunk
- standard vs teacher-annotated mode
- attempt and answer bundle paths
- reminder that output must be strict JSON array

Do not pin a model in Task calls; allow agent frontmatter (`model: inherit`) to decide.

**Task template (Phase 2, one chunk):**
```python
phase2_job = Task(
    subagent_type="marking-phase2-fast-pass-grader",
    prompt=(
        "Fast-pass grade this chunk. Return ONLY JSON array.\\n"
        f"mode={workflow_mode}\\n"
        f"subject_context={subject_context}\\n"
        f"required_output_language={required_output_language}\\n"
        f"language_policy={language_policy}\\n"
        f"attempt_pages_map_chunk={attempt_pages_map_chunk}\\n"
        f"bundle_root={bundle_root}\\n"
        f"attempt_glob={bundle_root / 'attempt/page-*.png'}\\n"
        f"answers_glob={bundle_root / 'answers/page-*.png'}"
    ),
)
```

Wait for ALL parallel subagents to return their JSON arrays. Combine them into a single array. Save this array to `context.marking_asset/debug/phase2_fast_pass.json`.

### Phase 2 Language QC Gate (required)

Before Phase 3 routing:

- Validate language compliance for each row’s free-text fields (`student_answer`, `correct_answer`, `human_note`, `diagnosis.reasoning`).
- For English-required subjects, detect CJK Han characters and treat any occurrence as a hard QC failure.
- Persist `context.marking_asset/debug/phase2_language_qc.json` with:
  - `total_rows`
  - `english_required` (boolean)
  - `violating_question_ids` (array)
  - `qc_passed` (boolean)
- If `qc_passed` is false:
  - retry only the violating Phase 2 chunks with explicit “English-only output” correction instructions;
  - replace only the violating rows;
  - re-run Phase 2 language QC before continuing.

## 4. Phase 3: Deep-Dive Remediation Subagents

Filter the JSON array from Phase 2. For ANY question where `outcome != "correct"` OR any value in the `confidence` object is `"low"`, use the `Task` tool to launch `marking-phase3-deep-dive` subagents **IN PARALLEL**.

### Phase 3 MCQ Adjudication Safeguards (required)

For any MCQ flagged as wrong/partial/low-confidence, the deep-dive agent must explicitly adjudicate bracket evidence:

- Is there **any intentional pen stroke** inside the answer bracket?
- If yes, what is the most likely digit / option?
- If ambiguous, what are plausible alternatives, and how does that affect confidence?

Do not allow Phase 3 to simply repeat a fast-pass `no_response` claim without this explicit bracket adjudication.

### Phase 3 mark allocation (mandatory)

Phase 2 is the **only** source of truth for **`max_marks`** per `question_id` (read from the printed key / rubric on the answer pages).

- Pass **`fast_pass_max_marks=<n>`** (and optionally the full Phase 2 row snapshot) in every Phase 3 Task prompt so the subagent knows the mark ceiling.
- The deep-dive subagent **must not emit `max_marks`**, or if legacy prompts still ask for it, the orchestrator **must discard** any Phase 3 `max_marks` and **always** use the Phase 2 value for that `question_id`.
- After merge, **`earned_marks` must never exceed** the Phase 2 `max_marks` for that row; if Phase 3 violates this, treat output as malformed and retry Phase 3 for that `question_id`.

For each invocation, pass:

- one `question_id`
- `fast_pass_max_marks=<n>` copied from the Phase 2 row for that `question_id`
- candidate `attempt_pages`
- attempt/answer bundle paths
- strict JSON object output requirement

Do not pin a model in Task calls; allow agent frontmatter (`model: inherit`) to decide.

**Task template (Phase 3, one question):**
```python
phase3_job = Task(
    subagent_type="marking-phase3-deep-dive",
    prompt=(
        "Deep-dive ONLY this question. Return ONLY one JSON object.\\n"
        f"question_id={question_id}\\n"
        f"subject_context={subject_context}\\n"
        f"required_output_language={required_output_language}\\n"
        f"language_policy={language_policy}\\n"
        f"attempt_pages_hint={attempt_pages_hint}\\n"
        f"fast_pass_max_marks={fast_pass_max_marks}\\n"
        f"bundle_root={bundle_root}\\n"
        f"attempt_glob={bundle_root / 'attempt/page-*.png'}\\n"
        f"answers_glob={bundle_root / 'answers/page-*.png'}"
    ),
)
```

Wait for ALL parallel subagents to complete. Save their combined outputs to `context.marking_asset/debug/phase3_deep_dive.json`.

### Phase 3 Language QC Gate (required)

Before merging Phase 3 rows into final results:

- Validate language policy on each deep-dive object (`student_answer`, `correct_answer`, `human_note`, `diagnosis.reasoning`).
- For English-required subjects, any Han character is a hard fail.
- Persist `context.marking_asset/debug/phase3_language_qc.json` with:
  - `total_rows`
  - `english_required` (boolean)
  - `violating_question_ids` (array)
  - `qc_passed` (boolean)
- If QC fails, retry only violating `question_id`s with explicit language correction instructions and re-run QC.

## 5. Phase 4: Taxonomy Tagger Subagent

Merge the final results (using Phase 3 results to overwrite Phase 2 results where applicable). Use the `Task` tool to launch ONE `marking-phase4-taxonomy-tagger` subagent to tag them.

**CRITICAL PERFORMANCE OPTIMIZATION:** Do not pass the entire transcribed JSON array (which contains verbose `student_answer`, `correct_answer`, and `diagnosis` fields) to the Taxonomy Tagger. This wastes massive amounts of tokens and slows down the subagent.
Instead, pass ONLY a simplified array containing `question_id` and the question text/stem (if available) or just the `question_id` if the topic can be inferred from the section.

Pass:

- `subject_context`
- simplified question list
- syllabus markdown path/content
- strict JSON array output requirement

Do not pin a model in Task calls; allow agent frontmatter (`model: inherit`) to decide.

**Task template (Phase 4):**
```python
phase4 = Task(
    subagent_type="marking-phase4-taxonomy-tagger",
    prompt=(
        "Map question_id to syllabus skill_tags. Return ONLY JSON array.\\n"
        f"subject_context={subject_context}\\n"
        f"simplified_questions={simplified_questions}\\n"
        f"syllabus_path={syllabus_path}"
    ),
)
```

Wait for this subagent to return the tags. Save this array to `context.marking_asset/debug/phase4_tags.json`.

### Phase 4 Tag QC Gate (required)

Before proceeding to assembly, validate the Phase 4 tags:

- For `subject_context = singapore_primary_science`, each `skill_tags` entry MUST use exactly:
  - `<theme> > <chapter> > <topic>`
- Treat the following as QC failures:
  - chapter-number-prefixed chapter labels (for example `15. The Digestive System`)
  - malformed path shapes (missing or extra `>` segments)
  - placeholder topic `—` when a concrete topic is clearly inferable from the paper/question set
- If QC fails, retry Phase 4 once with an explicit correction instruction. Do not continue to assembly with failed tags.
- Persist QC evidence to `context.marking_asset/debug/phase4_qc.json` with:
  - `total_rows`
  - `invalid_format_rows` (array of `question_id`)
  - `placeholder_topic_rows` (array of `question_id`)
  - `qc_passed` (boolean)

## 6. Phase 5: Assembly and Finalization

As the Orchestrator, you must now assemble the final artifacts:

1. **Merge Data:** Combine the final grades/diagnoses and the skill tags into the `question_results` array. Ensure the `question_id` is mapped to the `result_id` field in the final schema.
   - **Preserve `max_marks` from Phase 2** for every row. When applying Phase 3 objects, merge fields such as `student_answer`, `correct_answer`, `outcome`, `earned_marks`, `diagnosis`, `human_note`, and `corrected_attempt_pages` from Phase 3, but **never** overwrite Phase 2 `max_marks` with a Phase 3 value (Phase 3 must not be able to inflate totals).
   - If Phase 3 omits `earned_marks`/`outcome`, keep the Phase 2 values; if Phase 3 includes them, they must satisfy `0 <= earned_marks <= max_marks` from Phase 2.
   - Persist `context.marking_asset/debug/phase5_merge_qc.json` with `{ "max_marks_source": "phase2_only", "phase3_max_marks_discarded": <bool>, "qc_passed": true }` after verifying every row.
2. **Build Page Map:** Use the `corrected_attempt_pages` (from Phase 3) or `attempt_pages` (from Phase 1) to build the `context.question_page_map`. Ensure the `attempt_page_start` is set to the first page in the array.
3. **Calculate Totals:** Calculate `summary.earned_marks` and `summary.total_marks` by summing the `question_results`.
4. **Determine Scope:** Set `context.is_partial` based on whether the graded questions represent the full expected paper.
5. **Write JSON:** Write the canonical `marking_result.v1.4.json` file to `context/marking_results/<student_slug>/<subject_context>/<attempt_basename>.json`. Use `write_marking_artifact` to ensure timestamps are normalized to SGT.
6. **Render Markdown:** Run the `report_renderer` to generate the Markdown report in `context/learning_reports/`.
7. **Write Profiling Log:** Create a `context.marking_asset/debug/profiling_log.md` file. Record the start and end times (in SGT) for Phase 1, Phase 2, Phase 3, and Phase 4. Calculate the total duration of the marking run.
8. **Write Telemetry Data:** In the `generation` block of the final JSON, include a `telemetry` object: `{"fast_pass_count": X, "deep_dive_count": Y, "total_duration_seconds": Z}`. This allows you to track the efficiency of the Optimistic Fast-Pass architecture over time.

### Pre-Finalization MCQ No-Response Validator (required)

Before writing the final JSON/report:

- Collect all MCQ rows currently labeled as `no_response` / blank-answer equivalents.
- Re-check each of those rows against attempt-page evidence with a dedicated bracket-focused pass.
- If any bracket shows plausible intentional ink (including faint single-stroke numerals), do not finalize as blank without adjudication.
- If ambiguity remains unresolved, downgrade confidence and annotate `human_note` rather than silently committing a definite blank response.

### Pre-Finalization Language Validator (required)

Before writing final JSON/report:

- Re-scan merged `question_results` free-text fields:
  - `student_answer`
  - `correct_answer`
  - `feedback`
  - `human_note`
  - `diagnosis.reasoning`
- Enforce `subject_context` language policy (English-only for non-Chinese contexts).
- Persist `context.marking_asset/debug/final_language_qc.json` with:
  - `total_rows`
  - `english_required` (boolean)
  - `violating_result_ids` (array)
  - `qc_passed` (boolean)
- Do **not** finalize JSON/report until `qc_passed` is true.

**Quality Bar:**
- Do not hallucinate data if a subagent fails. If a Phase 3 subagent fails or returns malformed JSON, you may retry launching a subagent for that specific `question_id`.
- Ensure the final JSON strictly adheres to the `marking_result.v1.4` schema.

## 7. Error Handling and Cleanup

If the marking run fails to complete (e.g., a subagent repeatedly fails, or you encounter an unrecoverable error during orchestration), you MUST clean up any temporary files or folders created during the run to avoid polluting the filesystem.

- Delete the entire Marking Asset Bundle directory (`context.marking_asset`) that was created for this run.
- Do not leave orphaned PNGs or intermediate JSON files in the workspace.
- Inform the user that the run failed and the temporary assets were cleaned up.
