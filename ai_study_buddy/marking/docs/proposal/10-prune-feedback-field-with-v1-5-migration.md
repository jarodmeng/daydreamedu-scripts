# Proposal: Introduce `marking_result.v1.5` by Pruning `question_results[].feedback`

Status: Implemented (`v0.2.15`)

Audience: Maintainers of `ai_study_buddy/marking`, artifact migration tooling, and reporting/consumer code reading `question_results[]`

## Implementation Status (`v0.2.15`)

Implemented in this pass:

1. Added `ai_study_buddy/schemas/marking/marking_result.v1.5.schema.json` and removed `question_results[].feedback` from the `v1.5` contract.
2. Switched runtime schema default/validation target to `marking_result.v1.5` in `core/artifact_schema.py`.
3. Migrated existing corpus artifacts under `context/marking_results/**/*.json` from `v1.4` to `v1.5`:
   - files migrated: `154`
   - rows processed: `2655`
   - non-empty feedback rows: `149`
   - Case A: `109`
   - Case B (conservative auto-merge): `40`
   - Case C: `2506`
4. Applied approved Case B merge marker: `[Migrated feedback]`.
5. Added one-off migration workflow script:
   - `workflows/_migrate_feedback_to_human_note.py`
6. Removed `feedback` from producer/consumer runtime surfaces:
   - `core/models.py`
   - `workflows/migrate_learning_reports.py`
   - `ai_study_buddy/schemas/marking/marking_amendment.v1.schema.json`
   - `student_review/amendment_service.py`
   - `student_review/detail_service.py`
   - `review_workspace/frontend/src/App.tsx`
7. Updated marking producer instructions to align with `v1.5` (no `feedback` field):
   - `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md`
   - phase subagent contracts reviewed as aligned with no direct `feedback` emission requirements.
8. Updated package docs/changelog (`README.md`, `SPEC.md`, `TESTING.md`, `ARCHITECTURE.md`, `CHANGELOG.md`) with a small version bump to `v0.2.15`.
9. Added migration run report:
   - `docs/reports/2026-04-28_marking_result_v1_5_feedback_migration.md`
10. Verified test suite:
   - `python3 -m pytest ai_study_buddy/marking/tests -q` -> `85 passed`.

## 1) Goal

Introduce `marking_result.v1.5` that removes `question_results[].feedback` and converges on `question_results[].human_note` as the single free-text per-question note field.

Primary goals:

1. Reduce duplicate/overlapping text fields in `question_results[]`.
2. Preserve existing artifact information with a deterministic migration.
3. Preserve strict closed-contract behavior (`additionalProperties: false`) while avoiding an in-place breaking change to `v1.4`.

## 2) Why This Change

Current schema contains three nearby free-text channels at question level:

- `feedback`
- `diagnosis.reasoning`
- `human_note`

Even with clarified descriptions, `feedback` and `human_note` remain operationally close in many producer flows. Maintaining both increases prompt ambiguity and migration burden for future versions.

## 3) Measured Migration Surface Area (Current Corpus)

Scope scanned:

- `ai_study_buddy/context/marking_results/**/*.json`
- `schema_version == "marking_result.v1.4"`

Observed counts:

1. Total `v1.4` files: `154`
2. Total `question_results[]` rows: `2655`
3. Rows with `feedback` key present: `2655` (all rows)
4. Rows where `feedback` is non-empty/non-null: `149`
5. Unique marking result files containing those `149` rows: `11`

Comparison of non-empty `feedback` rows against `human_note`:

1. Exact text match (`feedback == human_note`): `0`
2. `feedback` non-empty while `human_note` empty/null: `109`
3. Both present but different text: `40`

Conclusion:

- Pruning `feedback` without migration causes guaranteed information loss in at least `149` rows.
- In-place schema pruning inside `v1.4` would invalidate all `154` files under strict closed contract.

## 4) Proposed Contract Decision

Create a new schema file `marking_result.v1.5.schema.json` and keep `v1.4` frozen.

`v1.5` contract changes:

1. Remove `question_results.items.properties.feedback`.
2. Keep `question_results.items.properties.human_note` as optional nullable text.
3. Keep `diagnosis.reasoning` unchanged as grader-internal rationale channel.
4. Set `schema_version` const to `marking_result.v1.5`.

Versioning policy:

1. Do not mutate `marking_result.v1.4.schema.json` in a breaking way.
2. During the migration transition window, validators/parsers should support both `v1.4` and `v1.5`.
3. Writers should switch default output to `v1.5` after migration cutover.

Interpretation in `v1.5`:

- Student/report-facing and reviewer note text should be persisted in `human_note`.
- Evidence/rationale for grading logic remains in `diagnosis.reasoning`.

## 5) Migration Method by Case

Migration unit: one `question_results[]` row.

### Case A: `feedback` non-empty, `human_note` empty/null (`109` rows)

Action:

1. Copy `feedback` into `human_note`.
2. Remove `feedback`.
3. Set artifact `schema_version` to `marking_result.v1.5`.

Rationale:

- Lossless and deterministic.

### Case B: `feedback` non-empty, `human_note` present and different (`40` rows)

Action (approved policy: conservative auto-merge):

1. Preserve existing `human_note` as primary.
2. Append `feedback` into `human_note` with a stable delimiter/prefix.
   - Example merge format:
     - `"<existing human_note>\n\n[Migrated feedback]\n<feedback text>"`
3. Remove `feedback`.
4. Set artifact `schema_version` to `marking_result.v1.5`.

Rationale:

- Avoids dropping either channel.
- Keeps migration idempotent and auditable.

### Case C: `feedback` empty/null

Action:

1. Remove `feedback`.
2. Set artifact `schema_version` to `marking_result.v1.5`.

Rationale:

- No content to preserve.

## 6) Implementation Plan

### Phase 0 - Merge policy lock (completed)

TODO checklist:

- [x] Approve Case B handling policy: conservative auto-merge.

Exit criteria:

- Case B policy is explicitly locked to conservative auto-merge in this proposal.

### Phase 1 - Add versioned schema + migration script

TODO checklist:

- [x] Add `ai_study_buddy/schemas/marking/marking_result.v1.5.schema.json` (derived from `v1.4` with `feedback` removed).
- [x] Update schema loader/validator mapping to include `v1.5` (and drop normal runtime support for `v1.4` after full migration).
- [x] Add one-off script (leading underscore naming): `_migrate_feedback_to_human_note.py`.
- [x] Implement script scan scope: `context/marking_results/**/*.json`.
- [x] Process only artifacts where `schema_version == "marking_result.v1.4"`.
- [x] Apply Case A/B/C transforms per this proposal.
- [x] Update artifact `schema_version` to `marking_result.v1.5`.
- [x] Emit deterministic summary report (counts + per-file affected rows).
- [x] Ensure idempotency (running twice produces no additional semantic change).

Exit criteria:

- Dry-run report matches expected order-of-magnitude counts (`149` non-empty feedback rows; `109/40` split).

### Phase 2 - Execute migration + verification

TODO checklist:

- [x] Run migration in write mode.
- [x] Re-validate all migrated artifacts via `validate_marking_artifact_dict` under `v1.5`.
- [x] Recompute corpus stats and confirm:
  - [x] `feedback` occurrences are `0`.
  - [x] Preserved text rows remain recoverable in `human_note`.
  - [x] `schema_version == "marking_result.v1.5"` count matches migrated artifact count.
  - [x] Migrated artifact count is exactly `154` (all previously observed `v1.4` files).

Exit criteria:

- `0` validation failures.
- `0` `feedback` fields in corpus.
- All `154` previously observed `v1.4` artifacts are migrated to `v1.5`.

### Phase 3 - Teach marking-result producers to emit `v1.5`

TODO checklist:

- [x] Update producer orchestration skill contract in `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md`:
  - [x] Require `schema_version = marking_result.v1.5`.
  - [x] Explicitly forbid emitting `question_results[].feedback`.
  - [x] Require using `human_note` for per-question note text.
  - [x] Keep `diagnosis.reasoning` as grader-internal rationale.
- [x] Update/review phase subagent instructions to match `v1.5` field contract:
  - [x] `.cursor/agents/marking-phase1-mapper.md`
  - [x] `.cursor/agents/marking-phase2-fast-pass-grader.md`
  - [x] `.cursor/agents/marking-phase3-deep-dive.md`
  - [x] `.cursor/agents/marking-phase4-taxonomy-tagger.md`
- [x] Add explicit prompt-level validation checklist in producer docs:
  - [x] "No `feedback` field in any `question_results[]` item."
  - [x] "Use `human_note` only when needed; keep concise."
  - [x] "Do not overload `diagnosis.reasoning` with student-facing coaching text."
- [x] Run validation-oriented verification via package test suite under `v1.5`.

Exit criteria:

- All producer instructions (skill + subagents) unambiguously target `v1.5` and no longer reference `feedback`.
- Sample produced artifact passes `v1.5` schema validation with no contract drift.

### Phase 4 - Switch producers/consumers to `v1.5`

TODO checklist:

- [x] Switch emitters/prompts to write `v1.5` payloads (no `feedback`).
- [x] Update readers/renderers to consume `human_note` for per-question free-text.
- [x] Remove `v1.4` read support immediately after migration confirms all `154` existing marking results are migrated to `v1.5`.
- [x] Update docs (`README.md`, `SPEC.md`, `TESTING.md`, `CHANGELOG.md`).
- [x] Record this rollout as a small version bump in `ai_study_buddy/marking/CHANGELOG.md`.

Exit criteria:

- New artifacts validate against `v1.5` schema with no `feedback`.
- Tests pass for strict closed contract.

## 7) Risks and Mitigations

### Risk A: Semantic flattening of two distinct tones

`feedback` and `human_note` may differ in audience/tone.

Mitigation:

1. Use explicit merge prefix for Case B so provenance remains visible.
2. Keep `diagnosis.reasoning` untouched for grader rationale details.

### Risk B: Hidden consumer dependency on `feedback`

Downstream renderers may read `feedback` directly.

Mitigation:

1. Add compatibility check sweep (`rg` usages of `.feedback`).
2. Update readers to use `human_note` before default writer flips to `v1.5`.

### Risk C: Non-idempotent migration behavior

Repeated runs could duplicate merged content.

Mitigation:

1. Include marker-aware idempotency guard for Case B merge block.
2. Add fixture tests for rerun behavior.

## 8) Acceptance Criteria

1. `marking_result.v1.5.schema.json` is added and used for migrated artifacts.
2. Migrated corpus artifacts contain no `feedback` field and have `schema_version = marking_result.v1.5`.
3. Case A rows preserve prior `feedback` text in `human_note`.
4. Case B rows preserve both prior texts per approved policy.
5. New outputs are emitted as `v1.5`.
6. `v1.4` read support is removed once migration confirms all `154` existing results are on `v1.5`.
7. Producer and consumer code no longer depends on `feedback` for `v1.5` flows.
