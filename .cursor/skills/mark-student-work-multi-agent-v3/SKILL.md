---
name: mark-student-work-multi-agent-v3
description: v3 orchestrator entrypoint for student-work marking. Uses deterministic input normalization/registration-first resolution, mode guardrails, and redo-practice reference resolution before downstream phase execution.
---

# v3 Orchestrator Entrypoint (Phase A/B + runtime delegation boundary)

This skill is the top-level v3 orchestrator entrypoint and runtime policy boundary.

Use these workflow APIs from `ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3`:

- `V3InputRequest`
- `resolve_attempt_input_to_pdf_file(...)`
- `resolve_v3_marking_context(...)`
- `build_context_resolution_debug_record(...)`
- `write_context_resolution_debug_artifact(...)`
- `V3ModeSignals`
- `resolve_v3_mode(...)`
- `require_no_user_asset_contradiction(...)`
- `resolve_redo_practice_reference(...)`
- `find_latest_in_progress_bundle(...)`
- `resolve_or_create_bundle_for_v3_run(...)`
- `write_run_state(...)`
- `collect_stale_partial_bundle_paths(...)`
- `cleanup_stale_partials_for_v3_run(...)`
- `move_bundle_to_trash(...)`

## Phase A contract (must pass before any phase execution)

0. Capture one canonical run timestamp at orchestration start (single source of truth).
   - Generate once using the runtime clock at invocation time (do not hardcode placeholders like `00:00:00`).
   - Reuse this same value for:
     - `resolve_or_create_bundle_for_v3_run(..., run_marked_at=...)`
     - any artifact path derivation for this run
     - final artifact timestamps (`created_at`, `updated_at`, review metadata timestamps).
   - Do not regenerate a second timestamp later in the run unless you are intentionally starting a new run.
1. Normalize user input into `V3InputRequest` from one of:
   - `attempt_file_id_or_path` (`file_id`)
   - `attempt_file_id_or_path` (full path)
   - `student_name + file_name`
   - for `student_name + file_name`, treat the provided `file_name` as a candidate exact `normal_name` value first (no punctuation/casing rewrites before exact lookup).
2. Resolve attempt file through `resolve_attempt_input_to_pdf_file(...)`.
   - This enforces registration-first behavior for unregistered path input.
3. Resolve canonical marking context through `resolve_v3_marking_context(...)`.
4. Persist context-resolution provenance debug artifact:
   - build record with `build_context_resolution_debug_record(...)`
   - write file with `write_context_resolution_debug_artifact(...)` to `debug/context_resolution_provenance.json` under run bundle.
5. Bundle hygiene guardrail (run-start + run-end):
   - before creating a new bundle, call `resolve_or_create_bundle_for_v3_run(...)` so existing in-progress bundles are resumed automatically; when no in-progress bundle exists, prior runs for that completion (including finalized siblings) are trashed before the new bundle is created.
   - after successful finalize, call `cleanup_stale_partials_for_v3_run(...)` to trash every other bundle/JSON/report for the same completion (not only partial bundles).
   - update run progress with `write_run_state(...)` at major boundaries (`phase_ab_done`, `phase2_done`, `phase3_done`, `finalized`).

### Phase A filename resolution policy (efficiency + correctness)

When user intent is "mark this completion file" and the invocation provides a human-readable file title:

1. Use exact `normal_name` equality against the provided title first.
2. Scope by student identity in the same query (`student_id` or resolved student record).
3. If multiple exact matches exist (for example both `_raw_` and `_c_` with the same `normal_name`), prefer `_c_` as the attempt input for marking runs.
4. Only if exact `normal_name` match returns zero rows, fall back to broader matching (`contains` / fuzzy / path search).
5. Persist which branch was used (`exact_normal_name`, `exact_with_student_scope`, or fallback branch) in the context-resolution debug provenance artifact.

## Phase B contract (must pass before Phase C+)

1. Build `V3ModeSignals` from runtime/user signals.
2. Enforce contradiction stop gate via `require_no_user_asset_contradiction(...)`.
3. Resolve mode via `resolve_v3_mode(...)`.
   - hard-fail when signals are ambiguous.
   - no template-link bypass override.
4. If mode is `redo-practice`, resolve reference through `resolve_redo_practice_reference(...)`.
   - use first/original marking result as golden reference.
   - include amendment payload when present.

## Phase 2 / Phase 3 `Task` spawning (mandatory)

When using the `Task` tool to launch grading subagents after Phase A/B:

- **Phase 2:** `subagent_type="marking-phase2-fast-pass-grader-v3"` — **one Task per authoritative section** (`sections[]` / `Phase2SectionInput`). Each grader receives only that section’s `question_ids` and page slices (`stem_page_range`, `questions_page_range`, `answers_page_range` when present). **Never** combine multiple sections into one Phase 2 Task.
- **Phase 3:** `subagent_type="marking-phase3-deep-dive-v3"` — **one Task per escalated question** (not per section).

`plan_phase2_batches(...)` only caps **parallel** section Tasks (default 5); it is not a multi-section grader scope.

**Model selection:** Do **not** pass a `model` argument on these `Task` calls. The subagent definitions use frontmatter `model: inherit`; omitting `model` preserves that behavior (same policy as `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md` for its phase workers).

**Phase 2 / Phase 3 prompt reminder:** Ensure Task prompts reinforce agent rules: **`diagnosis.reasoning` is only for learner-centric mistake explanation**—not provenance or how teacher marks were read (see `.cursor/agents/marking-phase2-fast-pass-grader-v3.md` and `marking-phase3-deep-dive-v3.md`).

Also reinforce ink policy in Task prompts for teacher-annotated papers:

- black/blue = original student attempt evidence for grading;
- green = student correction/rework, excluded from original-attempt scoring;
- red = teacher marking authority when visible/clear.

## Downstream phase ownership (Phase C/D/E)

- This skill remains responsible for runtime orchestration decisions after Phase A/B (Task fan-out/fan-in, bounded concurrency, targeted retries, and escalation behavior).
- Deterministic data-shaping contracts for Phase C/D/E are implemented in `ai_study_buddy.marking.workflows.mark_student_work_multi_agent_v3` and related helpers; invoke those APIs rather than re-implementing transforms in prompts.
- Finalization must remain on package boundaries (`validate_marking_artifact_dict(...)` then `write_marking_artifact(...)`).

## Orchestrator boundary

- Do not perform grading/transcription directly in this skill.
- Treat this skill as the control-plane entrypoint: it enforces A/B contracts directly and orchestrates downstream C/D/E runtime flow through deterministic workflow APIs and phase subagents.

## Batch queue integration ([batch-mark-student-work](../batch-mark-student-work/SKILL.md))

When marking via a **work queue** (`utility_scripts/batch_mark_student_work/queues/*.json`):

1. **Phase A/B** — parent runs `batch_item_prep.py` only.
2. **Phase 2 / Phase 3** — parent launches **one** Task: `subagent_type="mark-student-work-v3-batch-orchestrator"` (see `.cursor/agents/mark-student-work-v3-batch-orchestrator.md`). That agent **must read this skill first**, then spawn `marking-phase2-fast-pass-grader-v3` (one Task per `sections[]` entry). Parent chat must **not** call graders directly.
3. **Validate + debug persist** — `batch_item_validate_phase2.py` then `batch_item_persist_grade_debug.py` (copies phase2 into `debug/phase2_fast_pass.json`, routing trace, section splits).
4. **Phase E** — parent runs `batch_item_finalize.py` after validate passes.

Prompt/context for the orchestrator Task is generated by `batch_item_grade_context.py`. The orchestrator agent must write live traces (`v3_batch_orchestration_trace.json`, `phase2_section_*.json`, `phase2_orchestrator_summary.json`) under `bundle/debug/`; see `.cursor/agents/mark-student-work-v3-batch-orchestrator.md`.
