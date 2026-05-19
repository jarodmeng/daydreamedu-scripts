# Proposal: Hierarchical Multi-Agent Marking Architecture

## 1. Executive Summary

This proposal outlines a structural decomposition of the current monolithic AI marking workflows (`mark-goodnote-completion` and `diagnose-student-school-work`) into a **Hierarchical Multi-Agent System** using Cursor's native `Task` tool (Subagents). 

By shifting from a single-pass "read everything and grade it all" prompt to a coordinated graph of specialized, isolated subagents, we can drastically reduce AI hallucinations (especially in page mapping and transcription), improve pedagogical diagnosis quality, and achieve parallel execution—all without incurring external API costs beyond the fixed-price Cursor subscription.

## 2. Problem Statement

Currently, the marking agent is given a massive context window containing:
- The full multi-page student attempt PDF (rendered as PNGs)
- The full answer key (or crops)
- Complex instructions for scoring, diagnosis, and syllabus tagging

This monolithic approach leads to several failure modes:
1. **Context Bleed:** The model hallucinates text from page 4 when transcribing an answer on page 2.
2. **Spatial Reasoning Failures:** The model mis-maps questions to pages because it doesn't re-scan boundaries carefully when distracted by grading.
3. **Cognitive Overload:** The model satisfices on `diagnosis.reasoning` (producing generic boilerplate) because its attention is consumed by visual transcription and scoring logic.
4. **Sequential Bottleneck:** Grading a 20-question paper takes a long time because the model processes everything in a single, linear generation.

**Constraint:** We cannot move this orchestration to a Python script calling external LLM APIs (like OpenAI/Anthropic) because the per-run cost would be prohibitive for a personal/alpha project. We must solve this using Cursor's built-in chat and background agent capabilities.

## 3. Proposed Architecture: Orchestrator + Subagents

The solution is to use the main Cursor chat agent as an **Orchestrator** that delegates specific, isolated tasks to background **Subagents** via the `Task` tool.

### 3.1 The Agent Graph

```mermaid
graph TD
    %% Main Orchestrator
    O[Main Agent<br/>Orchestrator]:::orchestrator

    %% Phase 1: Context & Structure Analysis (Vision)
    S1[Subagent 1:<br/>Scope, Mapper & Key Verifier]:::vision
    O -- "1. Pass All Attempt & Answer PNGs" --> S1
    S1 -. "Return Gradable Question List & Page Map" .-> O

    %% Phase 2: Optimistic Fast-Pass Grading (Vision + Text)
    S2[Subagent 2:<br/>Fast-Pass Grader]:::vision
    O -- "2. Pass ALL PNGs + Full Question Map" --> S2
    S2 -. "Return Initial Grades & Confidence Scores" .-> O

    %% Phase 3: Deep-Dive Remediation (Vision + Text - Parallel)
    subgraph Phase 3: Deep-Dive Remediation
        T1[Subagent 3a:<br/>Deep-Dive Q4 (Wrong/Low Conf)]:::vision
        T2[Subagent 3b:<br/>Deep-Dive Q7 (Wrong/Low Conf)]:::vision
    end
    O -- "3. Pass PNGs + Q4 Target (Filtered)" --> T1
    O -- "3. Pass PNGs + Q7 Target (Filtered)" --> T2
    T1 -. "Return Q4 Deep Diagnosis & Correction" .-> O
    T2 -. "Return Q7 Deep Diagnosis & Correction" .-> O

    %% Phase 4: Taxonomy Tagger (Text-Only)
    S4[Subagent 4:<br/>Taxonomy Tagger]:::text
    O -- "4. Pass ALL Final Transcribed Qs + Syllabus" --> S4
    S4 -. "Return skill_tags for all Qs" .-> O

    %% Phase 5: Assembly & Debug Logging
    A[(marking_result.json)]:::artifact
    L[(debug_trace.json)]:::artifact
    O -- "5. Assemble, Validate & Log" --> A
    O -- "5. Save Subagent Traces" --> L

    classDef orchestrator fill:#2d3748,stroke:#4fd1c5,stroke-width:2px,color:#fff
    classDef vision fill:#2b6cb0,stroke:#63b3ed,stroke-width:2px,color:#fff
    classDef text fill:#805ad5,stroke:#90cdf4,stroke-width:2px,color:#fff
    classDef artifact fill:#4a5568,stroke:#a0aec0,stroke-width:2px,color:#fff
```

### 3.2 Agent Roles & Contracts

#### 1. The Orchestrator (Main Agent)
- **Role:** Drives the workflow, interacts with the user, and manages the filesystem.
- **Responsibilities:**
  - Calls `PdfFileManager` to resolve paths.
  - Renders PDFs to PNGs in `context.marking_asset`.
  - Spawns subagents using the `Task` tool.
  - Aggregates subagent JSON outputs.
  - Writes the final `marking_result.v1.4.json` and renders the Markdown report.

#### 2. Scope, Mapper & Key Verifier Subagent (Vision)
- **Input:** All attempt page PNGs AND the Answer Key PNGs (if available).
- **Prompt (Standard):** "Analyze the attempt pages alongside the answer key. Determine the gradable question structure. Use BOTH the attempt pages (looking for `[x]` mark allocations) and the answer key to determine boundaries. Identify the page number(s) where the question text/stem appears AND where the student's answer appears. Handle shared reading passages and multi-part questions by duplicating context pages across relevant `result_id`s. **CRITICAL FOR SUB-PARTS:** If a question is a sub-part (e.g., B4a), you MUST look backwards to find where the parent stem (e.g., B4) starts. The `attempt_pages` for B4a MUST include the parent stem's starting page (e.g., `[12, 13]`)."
- **Prompt (Teacher-Annotated / No Key):** "Analyze the teacher-annotated attempt pages. Determine the gradable question structure based on teacher ticks, crosses, and mark allocations. Identify the page number(s) where each question and its answer/annotations appear. **CRITICAL FOR SUB-PARTS:** If a question is a sub-part (e.g., B4a), you MUST look backwards to find where the parent stem (e.g., B4) starts. The `attempt_pages` for B4a MUST include the parent stem's starting page (e.g., `[12, 13]`)."
- **Output:** JSON array of `{"result_id": "Section A Q1", "attempt_pages": [2, 3, 10]}`.
- **Benefit:** Solves the "un-indexed question" problem, gracefully handles both standard answer-key marking and teacher-annotated school work, and ensures sub-parts never lose their parent stem context.

#### 3. Optimistic Fast-Pass Grader Subagent (Vision + Text)
- **Input:** **ALL** attempt page PNGs, **ALL** Answer Key PNGs (if available), the full `attempt_pages` mapping, and the `subject_context`.
- **Prompt:** "You are performing a fast-pass grading on ALL questions in the provided map. Locate them across the attempt pages and answer key. 
  - **Standard Mode:** Transcribe the student's blue/black ink answer. Transcribe the correct answer from the key. Compare them to assign an `outcome` and `earned_marks`. For correct answers, keep it brief. For wrong/partial answers, provide a basic diagnosis explaining the gap.
  - **Teacher-Annotated Mode:** Transcribe the student's original answer from blue/black ink (keep final non-crossed-out text). Infer the `outcome` and `earned_marks` from the teacher's red ink. Infer the correct answer from the student's green corrections or teacher's red annotations. If neither exists, generate a reference answer and state `(Reference answer — not written on paper)`. Capture verbatim teacher comments in `human_note`.
  - **Confidence Metric (CRITICAL):** Output a `confidence` object for each question: `{transcription: "high"|"low", grading: "high"|"low", diagnosis: "high"|"low"}`. If the handwriting is messy, the logic is complex, or the diagnosis requires deep pedagogical thought, mark the confidence as `low` so a specialist agent can review it."
- **Output:** JSON array containing one object per question: `[{"result_id": "...", "student_answer": "...", "correct_answer": "...", "outcome": "...", "earned_marks": 1, "diagnosis": {...}, "confidence": {"transcription": "high", "grading": "high", "diagnosis": "low"}}]`.
- **Benefit:** Massive speedup. 80% of a student's answers are usually correct and easy to read. A single monolithic prompt can quickly grade "1+1=2" across 20 questions without cognitive overload.

#### 4. Deep-Dive Remediation Subagents (Vision + Text - Spawned in Parallel)
- **Input:** **ALL** attempt page PNGs, **ALL** Answer Key PNGs (if available), the `attempt_pages` mapping, the `subject_context`, and a specific target `result_id` that was flagged by the Fast-Pass Grader.
- **Prompt:** "You are performing a deep-dive remediation on ONLY Question X. The fast-pass agent flagged this question because it was either marked incorrect, partial, or had low confidence. You have been provided a hint that Question X is on page(s) [mapped_pages]. You MUST verify this boundary yourself. Transcribe the student's blue/black ink answer with extreme care. Compare it to the correct answer to assign a definitive `outcome` and `earned_marks`. 
  - **Deep Diagnosis Requirement:** For any wrong or partial row, you MUST write a highly specific pedagogical diagnosis explaining *why* the student got it wrong. Do not write generic boilerplate like 'student did not understand'. Name the specific distinction missed, the method error, or the calculation slip. Look at previous sub-parts if this question depends on them (e.g., error carried forward)."
- **Language Constraint:** "If `subject_context` is Chinese/Higher Chinese, `diagnosis.reasoning` MUST be written in Simplified Chinese. `mistake_type` and `error_tags` must use the standard English taxonomy."
- **Output:** JSON `{"result_id": "...", "student_answer": "...", "correct_answer": "...", "outcome": "...", "earned_marks": 1, "diagnosis": {...}, "human_note": "...", "corrected_attempt_pages": [2, 3]}`.
- **Benefit:** Focuses the expensive, parallel compute *only* on the questions that actually require deep pedagogical thought. This resolves the speed vs. quality tradeoff.

#### 5. Taxonomy Tagger Subagent (Text-Only)
- **Input:** A simplified JSON array containing ONLY the `question_id` and question text/stem (stripped of verbose `student_answer` and `diagnosis` fields to save tokens) AND the specific syllabus markdown file.
- **Prompt:** "Map each question to the exact syllabus strand/topic. If `subject_context` is English or Chinese, return an empty array `[]` for `skill_tags` as per the rules."
- **Output:** JSON array mapping `result_id` to `skill_tags`.
- **Benefit:** Decoupling syllabus tagging ensures perfect schema adherence and saves massive token costs. By stripping the input array of verbose grading data, the subagent runs significantly faster.

#### 6. The Orchestrator (Main Agent Final Assembly & Logging)
- **Responsibilities:**
  - Merge the Fast-Pass results (Phase 3) with the Deep-Dive results (Phase 4).
  - Calculate `summary.earned_marks` and `summary.total_marks`.
  - Determine `context.is_partial`.
  - Write the `generation` block.
  - Write the final `marking_result.v1.4.json` and trigger the markdown report renderer.
  - **Debug Logging:** Save the intermediate JSON outputs (from Phase 1, 3, 4, and 5) into a `debug_trace.json` file inside the `context.marking_asset` bundle so the developer can inspect the agents' reasoning and confidence scores.
  - **Profiling Logging:** Save a `profiling_log.md` inside the `context.marking_asset/debug/` bundle recording the start/end times and total duration of each subagent phase.
  - **Telemetry Data:** Include a `telemetry` object in the `generation` block of the final JSON to track the number of Fast-Pass vs Deep-Dive questions and the total run duration.

## 4. Implementation Strategy and Status

### 4.1 Status Legend

- `[x]` Implemented
- `[~]` Partially implemented
- `[ ]` Not implemented

### 4.2 Phase 1: Unified Multi-Agent Orchestrator

This architecture is now implemented as a dedicated orchestrator skill plus role-specific subagent files.

- `[x]` Orchestrator skill implemented (active): `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md`
- `[x]` Initial orchestrator skill implemented then archived: `.cursor/skills_archive/mark-student-work-multi-agent/SKILL.md`
- `[x]` Monolithic skills archived:
  - `.cursor/skills_archive/mark-goodnote-completion/SKILL.md`
  - `.cursor/skills_archive/diagnose-student-school-work/SKILL.md`

Decision note (updated): separate `.cursor/agents/*.md` files were required in practice. This allows each subagent to set `model: inherit`, so every phase follows the orchestration agent's Auto mode/model selection policy consistently.

- `[x]` Subagent roles implemented with `model: inherit`:
  - `.cursor/agents/marking-phase1-mapper.md`
  - `.cursor/agents/marking-phase2-fast-pass-grader.md`
  - `.cursor/agents/marking-phase3-deep-dive.md`
  - `.cursor/agents/marking-phase4-taxonomy-tagger.md`

### 4.3 Multi-Agent Workflow Checklist (Implementation Plan)

- `[x]` Phase 1 mapper: question structure and `attempt_pages` extraction
- `[x]` Phase 2 fast-pass: parallel chunked grading with confidence outputs
- `[x]` Phase 3 deep-dive: parallel remediation for wrong/low-confidence rows
- `[x]` Phase 4 taxonomy tagging: text-only syllabus mapping
- `[x]` Phase 5 assembly guidance: merge, totals, report generation, profiling log, telemetry fields in `generation`
- `[~]` Debug artifact shape alignment: currently phase-specific debug files are specified (`phase1_mapping.json`, `phase2_fast_pass.json`, etc.); not yet standardized as a single `debug_trace.json` artifact
- `[ ]` Dedicated automated tests for the multi-agent orchestration flow (phase orchestration/QC/telemetry assertions)
- `[ ]` Canonical schema contract for telemetry keys (for example explicit required fields for `generation.telemetry`)

### 4.4 Phase 2: Amendment UI (Parallel Track)

This phase has been split into its own proposal. Please see [1-marking-amendment-ui.md](../../../review_workspace/docs/proposal/1-marking-amendment-ui.md) for details on the human-in-the-loop review workspace.

## 5. Advantages of this Architecture

1. **Zero Marginal Cost:** Uses Cursor's included background agents instead of external API calls.
2. **Context Isolation:** Eradicates cross-page hallucinations.
3. **Speed:** Grading 20 questions sequentially takes minutes. Grading them in parallel via 20 subagents takes seconds.
4. **Resilience:** If the subagent grading Q4 fails, the Orchestrator can retry just Q4 without restarting the entire paper.
5. **Observability:** Because each subagent returns a discrete JSON chunk, we can easily see exactly where a failure occurred (e.g., did the vision agent misread the handwriting, or did the text agent misapply the rubric?).
