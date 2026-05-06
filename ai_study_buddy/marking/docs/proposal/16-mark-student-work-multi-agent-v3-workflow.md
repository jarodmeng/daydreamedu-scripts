# Proposal 16: `mark-student-work-multi-agent-v3` orchestration workflow

## Status

Implemented as of 2026-05-06 (checklist complete), with responsibilities split across orchestrator skill runtime and deterministic workflow helpers.

Dependency update (as of 2026-05-05):

- Proposal 13 is implemented.
- Proposal 14 is implemented.
- Proposal 15 is implemented.

## Why this proposal exists

Proposal 15 defines `file_question_info` consumer tooling. This proposal defines the orchestration workflow that will consume that tooling in a new v3 skill, while preserving the same external input ergonomics users already rely on.

## Goals

1. Keep v2-compatible user input styles (student+filename, full path, or registry `file_id`).
2. Enforce registry-backed processing before any marking phase runs.
3. Support four explicit marking modes with deterministic branching.
4. Require authoritative question-section structure before Phase 2.
5. Move Phase 2 to section-level parallelization.
6. Keep Phase 3 as deep-dive remediation in bounded parallel batches.
7. Skip taxonomy phase for v3 and emit empty `skill_tags`.

## Non-goals

- Reworking detector prompt internals.
- Reintroducing phase-4 taxonomy tagging in v3.
- Replacing marking artifact schema contract.

## Workflow contract

### 0) Thin-orchestrator architecture (required)

v3 uses a control-plane orchestrator with deterministic helper boundaries:

- Orchestrator owns: mode selection, branch/routing, subagent fan-out/fan-in, retry policy, and stop-and-ask-user escalation on contradictions.
- Deterministic helper layer (Python package functions) owns: schema validation gates, language/human-note QC checks, merge/assembly normalization, telemetry/profiling shaping, and persistence writes.
- Subagents own: perception/transcription/grading judgments only for their assigned section/question scope.

The orchestrator must not become a monolithic data-transform component; repeatable validations and merges should execute through deterministic helper APIs.

### 0b) Ownership matrix (required)

- Orchestrator skill runtime (`.cursor/skills/mark-student-work-multi-agent-v3/SKILL.md`) owns: user-facing entrypoint, Task spawning, bounded concurrency, partial-failure retry routing, escalation decisions, and phase fan-out/fan-in control flow.
- Deterministic workflow module (`ai_study_buddy/marking/workflows/mark_student_work_multi_agent_v3.py`) owns: stable helper contracts for normalization, authority resolution, planning, QC checks, merge/finalization shaping, and persistence boundary calls.
- Phase workers (`.cursor/agents/marking-phase2-fast-pass-grader-v3.md`, `.cursor/agents/marking-phase3-deep-dive-v3.md`) own: scoped grading/transcription judgments only.

### 1) Supported inputs (unchanged from v2 ergonomics)

v3 accepts one of:

- `student + file name`
- complete file path
- `pdf_file_manager` `file_id` (rare but supported)

### 2) Registration-first gate

If input is not already a registry `file_id`, orchestrator must:

1. Resolve full file path.
2. Check registry for an existing file row.
3. If missing, process/register it first.

No marking-phase execution is allowed before this gate passes.

### 3) Four marking modes

v3 determines one of four explicit modes:

- `book-practice`: linked template exists and mapped answer page range exists.
- `embedded-answer`: user explicitly states answers are embedded in completion PDF (typically last 1-2 pages), regardless of missing mapped answer range.
- `teacher-annotated`: no mapped answer range; grading cues and/or corrections are embedded as teacher annotations.
- `redo-practice`: linked template resolves to a previous reviewed completion; prior marking + amendment is authoritative answer reference.

Mode must be persisted in context/generation metadata for traceability.

### 4) Authoritative question-section acquisition (hard prerequisite)

Before Phase 2, orchestrator must obtain authoritative `question_sections` for the completion context.

#### 4a) If linked template exists

1. Resolve via Proposal 15 reader helper (`resolve_question_sections_for_template_file`, or equivalent `...for_file_id` / `...for_pdf_file` path).
2. If found and valid, use it directly.
3. If lookup returns `QuestionSectionsNotFoundError`, run latest subject detector on template file (not completion file), then load+validate and use result.

#### 4b) If linked template does not exist

Fail closed by default. Do not continue with completion-only structure inference in v3.

### 5) Phase 2 redesign: section-level fast pass

Replace single global fast-pass call with section-parallel execution:

- one Phase-2 subagent invocation per section from authoritative `question_sections`
- each section-level subagent must be fed only pages relevant to that section:
  - `stem_page_range` (if present)
  - `questions_page_range`
  - `answers_page_range` (if present)
- initial v3 may still use generic fast-pass prompt, but scoped to one section each
- architecture intentionally prepares for future mode+subject+section specialized agents

### 6) Phase 3 redesign: targeted deep-dive batches

After section-level Phase 2 aggregation:

- route all low-confidence rows and incorrect rows to Phase 3
- run deep-dive subagents in bounded parallel batches (target 4-5 at a time)
- each deep-dive subagent owns one question
- each question-level subagent must be fed only pages relevant to that question:
  - section-level `stem_page_range` (if present)
  - question attempt span from `start_page` to `end_page`
  - if `end_page` is not set, infer it from the next question's `start_page` (current question `end_page` must be before or on that page)
  - `answers_page_range` (if present)

### 7) Taxonomy handling in v3

Skip phase-4 taxonomy subagent entirely.

- emit `skill_tags: []` for all rows
- no taxonomy inference attempt in v3

### 8) Carried-forward v2 guardrails (mandatory in v3)

The following v2 orchestration guardrails remain mandatory in v3:

- enforce schema contract and hard-stop on `validate_marking_artifact_dict(...)` failure before finalize;
- use package persistence boundaries only (`write_marking_artifact`, review repositories), no ad-hoc artifact writes;
- keep single-timestamp run semantics (`run_marked_at` captured once and reused for paths and artifact timestamps);
- retain language QC gates (Phase 2, Phase 3, and pre-final), with scoped retries only for violating rows/chunks;
- retain human-note policy and provenance/QC gates (Phase 2, Phase 3, and pre-final);
- retain teacher-annotated authority safeguards and pre-final teacher tally reconciliation;
- retain strict final assembly field normalization/mapping constraints;
- retain failed-run cleanup contract for temporary bundle/debug assets;
- retain profiling/telemetry output requirements in debug artifacts and generation metadata;
- retain targeted retry policy (retry failed chunk/question only; avoid full reruns).

Explicitly dropped for v3 initial rollout:

- dedicated MCQ no-response/bracket revalidation gate from v2 (to avoid noisy diagnosis pollution during this rollout).

Mark-allocation authority update for v3:

- supersede v2 "Phase 2 owns `max_marks`" with authoritative marks/rubric metadata sourced from `file_question_info` (Proposal 15 structures + linked template context), with Phase 2/3 outputs constrained to that authority.

### 9) v3 subagent strategy

v3 subagent policy is explicit:

- do not use v2 Phase 1 mapper subagent in v3;
- do not use v2 Phase 4 taxonomy subagent in v3;
- create new dedicated v3 Phase 2 and Phase 3 subagents (do not retrofit/modify v2 phase subagents).

## Required dependencies

- Proposal 13 (`file_question_info` foundation APIs)
- Proposal 14 (DB mirror optional but preferred for lookup speed)
- Proposal 15 (consumer-layer helpers + question-page-map bridge)

All three dependencies are now available; Proposal 16 work is orchestration migration/integration.

## Implementation layout (explicit)

v3 implementation should land under `ai_study_buddy/marking` with clear ownership:

- `ai_study_buddy/marking/file_question_info/`
  - keep authoritative question-structure readers/normalizers from Proposal 15;
  - continue to provide section/question normalized contracts and template-linked lookup entrypoints.
- `ai_study_buddy/marking/workflows/v3_helpers.py` (new)
  - deterministic workflow helpers for v3 orchestration:
  - Phase 2/3 language QC evaluators and retry-target selection
  - human-note policy QC evaluators and retry-target selection
  - merge/assembly normalization helpers
  - teacher-annotated tally reconciliation helpers
  - telemetry/profiling shaping helpers
- `ai_study_buddy/marking/workflows/mark_student_work_multi_agent_v3.py` (new)
  - thin orchestration control plane only (mode routing, fan-out/fan-in, retry orchestration, escalation);
  - delegates deterministic transforms/validation to `workflows/v3_helpers.py`;
  - final persistence remains through package validators/writers.
- `.cursor/skills/mark-student-work-multi-agent-v3/SKILL.md` (new)
  - v3 orchestrator skill entrypoint that invokes the workflow module and v3 phase subagents.
- `.cursor/agents/marking-phase2-fast-pass-grader-v3.md` (new)
  - section-scoped v3 fast-pass grader contract.
- `.cursor/agents/marking-phase3-deep-dive-v3.md` (new)
  - question-scoped v3 deep-dive contract aligned to v3 page-slice and authority rules.
- existing core contracts remain authoritative:
  - schema/version/validation: `ai_study_buddy/marking/core/artifact_schema.py`
  - artifact writing: `ai_study_buddy/marking/core/artifact_writer.py`

## Proposed implementation plan

Implementation status note (2026-05-06): Phase A-E checklist items are complete, including deterministic helper-layer contracts, v3 phase subagent wiring, and orchestrator-skill Task runtime loops. Concurrency execution ownership is in the orchestrator skill (`.cursor/skills/mark-student-work-multi-agent-v3/SKILL.md` + Task calls), while `workflows/mark_student_work_multi_agent_v3.py` provides deterministic planning/QC/merge/finalization contracts consumed by that skill. Next step is live-run validation on real papers and any follow-up hardening from production observations.

### Phase A: Input and registration normalization

Objective: deterministic input resolution and registration-first execution.

Todo checklist:

- [x] Define v3 input parser contract for the 3 input styles.
- [x] Implement canonical resolution path: input -> `PdfFile`.
- [x] Implement registration gate for unresolved/unregistered file paths.
- [x] Persist context-resolution provenance in debug artifact.
- [x] Keep this phase orchestration-only (no grading/merge logic embedded here).
- [x] Land orchestration entrypoint scaffold in `workflows/mark_student_work_multi_agent_v3.py`.
- [x] Add v3 orchestrator skill entrypoint at `.cursor/skills/mark-student-work-multi-agent-v3/SKILL.md` and wire it to `workflows/mark_student_work_multi_agent_v3.py`.

Test checklist:

- [x] `student+filename` resolves correctly for common and ambiguous cases.
- [x] full-path input resolves/normalizes consistently.
- [x] `file_id` path skips redundant lookup and remains stable.
- [x] unregistered file path gets registered before phase execution.

Success criteria:

- every run enters marking phases with one resolved registry-backed attempt file.

### Phase B: Mode resolution and policy guardrails

Objective: deterministic branch into one of four modes with explicit user/runtime signals.

Todo checklist:

- [x] Define mode resolver function and precedence rules.
- [x] Require explicit user signal for `embedded-answer` mode, but do not provide a bypass override when hard prerequisites fail.
- [x] Add `redo-practice` resolver using linked template + previous reviewed completion artifacts.
- [x] Fail with actionable error when mode is ambiguous.
- [x] Enforce contradiction handling as an orchestrator escalation gate (stop and ask user).
- [x] Keep mode-policy evaluation logic in deterministic helpers under `workflows/v3_helpers.py` (orchestrator consumes outcomes only).

Test checklist:

- [x] book-practice mode happy path.
- [x] embedded-answer mode requires explicit user signal.
- [x] teacher-annotated mode activates when mapped answer range absent and no embedded override.
- [x] redo-practice mode uses prior reviewed completion + amendment as authoritative answers.
- [x] ambiguity cases fail with deterministic errors.

Success criteria:

- mode selection is reproducible and traceable from stored run metadata.

### Phase C: Question-section authority pipeline

Objective: ensure every run has authoritative question sections before Phase 2.

Todo checklist:

- [x] Implement template-link requirement check.
- [x] Integrate Proposal 15 lookup helpers (`get_latest_question_sections_for_file_id`, `get_latest_question_sections_for_pdf_file`, `resolve_question_sections_for_template_file`) as the default template `file_question_info` path.
- [x] Implement detector fallback orchestration on template file when Proposal 15 lookup returns `QuestionSectionsNotFoundError`.
- [x] Enforce fail-closed when linked template missing.
- [x] Expose normalized, deterministic section/question authority objects for downstream phases via helper-layer APIs.
- [x] Keep authoritative structure reads in `file_question_info/*`; avoid duplicating lookup/normalization logic in workflow files.

Test checklist:

- [x] existing template `file_question_info` path reused.
- [x] detector fallback path works and validates payload.
- [x] missing linked template hard-fails with clear message.
- [x] corrupt detector payload hard-fails (no silent continuation).

Success criteria:

- no Phase 2 starts without validated authoritative question-section payload.

### Phase D: Section-parallel Phase 2

Objective: execute fast-pass marking per section, then merge.

Runtime note:
- Helper-layer planning/aggregation is implemented.
- Parallel Task spawning/execution (including bounded concurrency and retry routing) is owned by the orchestrator skill runtime; this workflow module provides deterministic helper contracts consumed by that runtime.

Todo checklist:

- [x] Define section-scoped phase-2 subagent input contract using Proposal 15 normalized section/question rows (`iter_sections_ordered`, `iter_questions_ordered`).
- [x] Create v3-specific Phase 2 subagent definition (`.cursor/agents/marking-phase2-fast-pass-grader-v3.md`) instead of modifying v2 Phase 2 subagent.
- [x] enforce section page filtering to only `stem_page_range`, `questions_page_range`, `answers_page_range` (when present).
- [x] spawn section-level jobs in parallel with bounded concurrency.
- [x] aggregate section outputs via deterministic helper functions into canonical row set, keyed/validated against Proposal 15 `question_page_map_from_question_sections(...)` output.
- [x] enforce `file_question_info`-driven question/marks authority when shaping section outputs (no mark-ceiling inference outside authoritative structure/context).
- [x] run Phase 2 language/human-note QC via deterministic helper gates; orchestrator only routes retries for failing chunks.
- [x] Implement Phase 2 QC + retry-target helper functions in `workflows/v3_helpers.py`.
- [x] Implement orchestrator-skill runtime Task spawning loop for section-level Phase 2 workers (using `.cursor/agents/marking-phase2-fast-pass-grader-v3.md`).
- [x] Implement orchestrator-skill fan-in collection of all section worker outputs with per-section status/error handling.
- [x] Implement orchestrator-skill bounded-concurrency executor wiring (cap=5 default) for section workers.
- [x] Implement orchestrator-skill partial-failure retry path that re-runs only failed sections while preserving successful section outputs.
- [x] Persist runtime section execution trace (submitted/completed/retried/failed sections) into debug artifacts.

Test checklist:

- [x] single-section paper works.
- [x] verify section-level workers never receive out-of-section pages.
- [x] multi-section paper spawns one worker per section and merges deterministically.
- [x] partial section failure retry does not re-run successful sections.
- [x] merged output is stable across repeated runs.

Success criteria:

- phase-2 throughput improves and outputs remain schema-valid and deterministic.

### Phase E: Batched Phase 3 deep-dive + no-taxonomy finalize

Objective: targeted remediation and final assembly for v3.

Runtime note:
- Helper-layer merge/routing primitives are implemented.
- Parallel deep-dive Task spawning/execution (including bounded concurrency and retry routing) is owned by the orchestrator skill runtime; this workflow module provides deterministic helper contracts consumed by that runtime.

Todo checklist:

- [x] route incorrect + low-confidence rows into deep-dive queue.
- [x] Create v3-specific Phase 3 subagent definition (`.cursor/agents/marking-phase3-deep-dive-v3.md`) instead of modifying v2 Phase 3 subagent.
- [x] build question-level page slices using Proposal 15 normalized rows/map helpers plus section stem range + question span + section answers range.
- [x] when question `end_page` missing, infer from next question `start_page` deterministically.
- [x] execute deep-dive workers in parallel batches of 4-5.
- [x] merge remediated rows back into final results via deterministic helper-layer merge functions.
- [x] enforce final mark-allocation constraints against `file_question_info`-derived authoritative marks/rubric context.
- [x] remove taxonomy subagent invocation from v3 flow.
- [x] ensure empty `skill_tags` output contract.
- [x] finalize only through deterministic validator + writer path (`validate_marking_artifact_dict(...)` then `write_marking_artifact(...)`).
- [x] Implement merge/finalization/teacher-tally/telemetry helper functions in `workflows/v3_helpers.py`.
- [x] Implement orchestrator-skill runtime Task spawning loop for question-level Phase 3 workers (using `.cursor/agents/marking-phase3-deep-dive-v3.md`).
- [x] Implement orchestrator-skill fan-in collection of deep-dive worker outputs with per-question status/error handling.
- [x] Implement orchestrator-skill bounded-concurrency executor wiring (cap=5 default) for deep-dive workers.
- [x] Implement orchestrator-skill partial-failure retry path that re-runs only failed questions while preserving successful deep-dive outputs.
- [x] Implement orchestrator-skill finalization path that performs merge -> QC gates -> `validate_marking_artifact_dict(...)` -> `write_marking_artifact(...)`.
- [x] Persist runtime deep-dive execution trace and finalization telemetry/debug artifacts.

Test checklist:

- [x] routing logic catches all low-confidence/incorrect rows.
- [x] verify question-level workers never receive pages outside computed question scope.
- [x] verify missing `end_page` fallback uses next question `start_page` correctly.
- [x] batched deep-dive execution respects concurrency cap.
- [x] final artifact contains empty `skill_tags` only (no taxonomy leakage).
- [x] schema validation passes for final artifacts.

Success criteria:

- v3 finishes with deterministic deep-dive remediation and no taxonomy phase dependency.

## Decisions (resolved)

1. If user direction contradicts available assets/runtime evidence, stop and ask the user for confirmation; do not silently assume or auto-correct intent.
2. Do not allow override to bypass template-link hard fail in v3 (no bypass for now).
3. For `redo-practice`, use the first marking result as the authoritative baseline ("golden"), including its amendment context when present.
4. Use a maximum of 5 concurrent subagents as the default cap for both section-level Phase 2 and deep-dive Phase 3 batches.
5. v3 will not use Phase 1 mapper or Phase 4 taxonomy subagents; v3 will introduce new dedicated Phase 2 and Phase 3 subagents rather than changing v2 subagents.

## References

- [13-file-question-info-marking-python-apis.md](13-file-question-info-marking-python-apis.md)
- [14-persist-file-question-info-in-study-buddy-db.md](14-persist-file-question-info-in-study-buddy-db.md)
- [15-file-question-info-consumer-layer-and-marking-orchestration.md](15-file-question-info-consumer-layer-and-marking-orchestration.md)
- [8-multi-agent-marking-architecture.md](8-multi-agent-marking-architecture.md)
- `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md`
