---
name: mark-student-work-multi-agent
description: Orchestrates a multi-agent workflow to mark a student's completion PDF (either against an answer key or from teacher annotations). Uses the `Task` tool to spawn isolated subagents for structural mapping, parallel transcription/grading, and taxonomy tagging. Outputs a canonical JSON marking artifact and a derived markdown learning report. Use when the user asks to mark, grade, or diagnose a student's work using the multi-agent architecture.
---

# Multi-Agent Student Work Marking Orchestrator

This skill acts as the **Orchestrator** for a Hierarchical Multi-Agent System. Do not attempt to read the attempt images, grade the questions, or assign skill tags yourself. Your job is to resolve the context, spawn specialized subagents using the `Task` tool, assemble their outputs, and write the final artifacts.

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

Use the `Task` tool to launch a `generalPurpose` subagent to determine the structure of the paper.

**Subagent Prompt:**
> "Analyze the attempt pages (and answer key pages, if provided). Determine the gradable question structure. 
> 
> **Rules:**
> - Identify the page number(s) where the question text/stem appears AND where the student's answer appears. 
> - If they are in separate booklets, include both. 
> - If multiple questions share a reading passage, include the passage pages in the `attempt_pages` for ALL of those questions. 
> - If a question has sub-parts (e.g., Q2(a), Q2(b)) and each part is graded separately, treat each part as a distinct `question_id`. **CRITICAL FOR SUB-PARTS:** You MUST look backwards to find where the parent stem (e.g., Q2) starts. The `attempt_pages` for Q2(a) MUST include the parent stem's starting page (e.g., `[12, 13]`).
> - If an answer key is provided, use it alongside the attempt pages to determine the boundaries.
> - If no answer key is provided, infer the boundaries based on teacher ticks, crosses, and mark allocations on the attempt pages.
>
> **Output:** Return ONLY a JSON array of objects with `question_id` and `attempt_pages` (e.g., `[{"question_id": "Q1", "attempt_pages": [2, 3]}]`)."

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

Use the `Task` tool to launch `generalPurpose` subagents to do a fast pass over ALL questions.

**CRITICAL PERFORMANCE OPTIMIZATION:** Do not pass all questions to a single subagent if the paper has more than 15 questions. The subagent will hit output token limits and truncate the JSON. Instead, split the `attempt_pages_map` into chunks of 10-15 questions each. Launch a separate `generalPurpose` subagent **IN PARALLEL** for each chunk.

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

**Subagent Prompt:**
> "You are performing a fast-pass grading on ALL questions in the provided map: `[attempt_pages_map]`. You have been provided all pages of the attempt (and the answer key, if applicable). 
> 
> **Instructions for Standard Mode:** 
> - Transcribe the student's final blue/black ink answer (ignore red/green ink, which are teacher/correction marks).
> - Transcribe the correct answer from the key.
> - Compare them to assign an `outcome` (`correct`, `incorrect`, `partial`) and `earned_marks`.
> - For correct answers, keep the diagnosis brief. For wrong/partial answers, provide a basic diagnosis explaining the gap between the student's answer and the key.
>
> **Instructions for Teacher-Annotated Mode:** 
> - Transcribe the student's original answer from blue/black ink (keep final non-crossed-out text). Do not fabricate text; use `[illegible]` if unreadable.
> - Infer the `outcome` and `earned_marks` from the teacher's red ink (ticks, crosses, scores).
> - Infer the correct answer from the student's green corrections or teacher's red annotations. If neither exists, generate a reference answer and state `(Reference answer — not written on paper)`.
> - Capture verbatim teacher comments in `human_note`.
>
> **MCQ Bracket Rules (Critical):**
> - For MCQs, inspect the final-answer bracket as its own evidence region.
> - A faint single-stroke digit (e.g., a light vertical `1`) is still a possible answer; do not auto-classify as blank.
> - If bracket evidence is ambiguous, set transcription confidence to `low` and avoid confident `no_response`.
> - If the final option is implied by statement-level ticks/crosses (instead of writing option number), treat it as a response and record that interpretation explicitly.
>
> **CRITICAL CONFIDENCE METRIC:** For each question, output a `confidence` object: `{"transcription": "high"|"low", "grading": "high"|"low", "diagnosis": "high"|"low"}`. If the handwriting is messy, the logic is complex, or the diagnosis requires deep pedagogical thought (e.g., the student got it wrong and you aren't 100% sure why), mark the confidence as `low` so a specialist agent can review it.
>
> **Output:** Return ONLY a JSON array: `[{"question_id": "...", "student_answer": "...", "correct_answer": "...", "outcome": "...", "earned_marks": 1, "max_marks": 1, "diagnosis": {...}, "human_note": "...", "confidence": {"transcription": "high", "grading": "high", "diagnosis": "low"}}]`."

Wait for ALL parallel subagents to return their JSON arrays. Combine them into a single array. Save this array to `context.marking_asset/debug/phase2_fast_pass.json`.

## 4. Phase 3: Deep-Dive Remediation Subagents

Filter the JSON array from Phase 2. For ANY question where `outcome != "correct"` OR any value in the `confidence` object is `"low"`, use the `Task` tool to launch a `generalPurpose` subagent **IN PARALLEL**.

### Phase 3 MCQ Adjudication Safeguards (required)

For any MCQ flagged as wrong/partial/low-confidence, the deep-dive agent must explicitly adjudicate bracket evidence:

- Is there **any intentional pen stroke** inside the answer bracket?
- If yes, what is the most likely digit / option?
- If ambiguous, what are plausible alternatives, and how does that affect confidence?

Do not allow Phase 3 to simply repeat a fast-pass `no_response` claim without this explicit bracket adjudication.

### Phase 3 mark allocation (mandatory)

- Pass **`fast_pass_max_marks=<n>`** from the Phase 2 row for that `question_id` in every deep-dive prompt.
- Deep-dive output **must not** change total mark weight: **omit `max_marks` from the JSON**, or the orchestrator **must discard** any deep-dive `max_marks` and keep **Phase 2 `max_marks` only** when merging.

**Subagent Prompt (Inject the specific `[question_id]` and `[attempt_pages]` into each prompt):**
> "You are performing a deep-dive remediation on ONLY `[question_id]`. The fast-pass agent flagged this question because it was either marked incorrect, partial, or had low confidence.
> 
> `[question_id]` is expected to be found on attempt page(s) `[attempt_pages]`. You MUST verify this boundary yourself. If the hint is wrong, correct the `attempt_pages` array in your output.
> 
> Transcribe the student's answer with extreme care (blue/black ink only). Compare it to the correct answer to assign a definitive `outcome` and `earned_marks`. 
>
> **MCQ Bracket Adjudication (Mandatory for MCQs):**
> 1) State whether any intentional stroke exists in the answer bracket.
> 2) If yes, infer the most likely selected option (including faint single-stroke digits like `1`).
> 3) If statement-level markings imply an option (e.g., ticked A/B implying option `(1)`), treat that as valid response evidence.
> 4) Only mark `no_response` when bracket and surrounding evidence are both truly blank.
> 
> **Deep Diagnosis Requirement:** For any wrong or partial row, you MUST write a highly specific pedagogical diagnosis explaining *why* the student got it wrong. Do not write generic boilerplate like "student did not understand". Name the specific distinction missed, the method error, or the calculation slip. Look at previous sub-parts if this question depends on them (e.g., error carried forward).
>
> **Language Constraint:** If the subject is Chinese/Higher Chinese, `diagnosis.reasoning` MUST be written in Simplified Chinese. `mistake_type` and `error_tags` must use the standard English taxonomy.
>
> **Output:** Return ONLY a JSON object: `{"question_id": "[question_id]", "student_answer": "...", "correct_answer": "...", "outcome": "...", "earned_marks": 1, "diagnosis": {...}, "human_note": "...", "corrected_attempt_pages": [...]}`. **Do not** include `max_marks` (mark allocation is Phase 2 only; ceiling is `fast_pass_max_marks`)."

Wait for ALL parallel subagents to complete. Save their combined outputs to `context.marking_asset/debug/phase3_deep_dive.json`.

## 5. Phase 4: Taxonomy Tagger Subagent

Merge the final results (using Phase 3 results to overwrite Phase 2 results where applicable). Use the `Task` tool to launch ONE `generalPurpose` subagent to tag them.

**CRITICAL PERFORMANCE OPTIMIZATION:** Do not pass the entire transcribed JSON array (which contains verbose `student_answer`, `correct_answer`, and `diagnosis` fields) to the Taxonomy Tagger. This wastes massive amounts of tokens and slows down the subagent.
Instead, pass ONLY a simplified array containing `question_id` and the question text/stem (if available) or just the `question_id` if the topic can be inferred from the section.

**Subagent Prompt (Inject the `subject_context`, the simplified question list, and the specific syllabus markdown file from `ai_study_buddy/context/subject_understandings/`):**
> "You are an expert curriculum mapper. I am providing you with a list of questions and a syllabus markdown file.
> 
> **Rules:**
> - Map each question to the exact syllabus strand/topic defined in the syllabus document.
> - You must use the exact string formats defined in the syllabus. Do not invent new tags.
> - If `subject_context` is `singapore_primary_english`, `singapore_primary_chinese`, or `singapore_primary_higher_chinese`, return an empty array `[]` for `skill_tags`.
> - If `subject_context` is `singapore_primary_math`, `skill_tags` must be an array of strings in the format `<strand> > <sub-strand> > <topic>`. Use a single space around `>`. Do not invent middle segments. If a question spans two topics, provide two full-path strings in the array.
> - If `subject_context` is `singapore_primary_science`, `skill_tags` must be an array of strings in the format `<theme> > <chapter> > <topic>`. If the syllabus index shows `—` for a topic, use `—` as the third segment.
>
> **Output:** Return ONLY a JSON array mapping `question_id` to `skill_tags` (e.g., `[{"question_id": "Q1", "skill_tags": ["Number and Algebra > Ratio > Ratio"]}]`)."

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

1. **Merge Data:** Combine the final grades/diagnoses and the skill tags into the `question_results` array. Ensure the `question_id` is mapped to the `result_id` field in the final schema. **Always keep `max_marks` from Phase 2** for each row; never overwrite it with Phase 3 output.
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

**Quality Bar:**
- Do not hallucinate data if a subagent fails. If a Phase 3 subagent fails or returns malformed JSON, you may retry launching a subagent for that specific `question_id`.
- Ensure the final JSON strictly adheres to the `marking_result.v1.4` schema.

## 7. Error Handling and Cleanup

If the marking run fails to complete (e.g., a subagent repeatedly fails, or you encounter an unrecoverable error during orchestration), you MUST clean up any temporary files or folders created during the run to avoid polluting the filesystem.

- Delete the entire Marking Asset Bundle directory (`context.marking_asset`) that was created for this run.
- Do not leave orphaned PNGs or intermediate JSON files in the workspace.
- Inform the user that the run failed and the temporary assets were cleaned up.