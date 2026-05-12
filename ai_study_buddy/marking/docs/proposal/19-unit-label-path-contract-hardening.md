# Proposal 19: Relaxed `unit_label` contract hardening (display-first)

## Status

**Implemented** (core contract/docs/tests complete for relaxed validation).

Supersedes prior path-only and source-marker variants of Proposal 19.

Depends on concepts from:

- Proposal 11 (`derive_unit_label_from_attempt_name` and context contract)

## Why this proposal exists

`write_marking_artifact` currently enforces a strict equality rule between:

- `context.unit_label`
- normalized label derived from `context.unit_file_path`

This fail-closed check has caused avoidable write failures when label sources drift (for example metadata/display naming differences), even when the artifact is otherwise valid and useful.

For SyncIt and current workflows, `unit_label` is primarily display/context metadata. Reliability of writes is more important than strict label-source equivalence checks.

## Problem statement

Current unit-label validation is over-constrained:

- It blocks writes on label-source drift.
- It does not materially improve grading correctness.
- It introduces operational friction for otherwise valid artifacts.

## Goals

1. Keep schema unchanged (`marking_result.v1.6`).
2. Require `unit_label` presence for display-oriented artifact quality.
3. Remove strict equality coupling to path- or registry-derived labels.
4. Preserve optional diagnostics for visibility without blocking writes.

## Non-goals

- Adding new schema fields.
- Registry lookups during writer validation for strict unit-label enforcement.
- Bulk registry/data migrations.

## Proposed design

### 1) Validation rule: presence, not equivalence

In `write_marking_artifact` context contract:

- Require `context.unit_label` to be a non-empty string for all artifact writes.
- Do **not** require `unit_label` to equal:
  - `derive_unit_label_from_attempt_name(unit_file_path)`, or
  - `metadata.unit` from registry.

### 2) Keep context self-contained

Writer validation remains payload-local and deterministic:

- no new schema fields
- no registry joins/lookups at write time
- no source-marker encoding hacks in `context_resolution.invariants`

### 3) Diagnostics are optional and non-blocking

If desired, emit warnings/telemetry when drift is detected by resolver-side logic:

- `unit_label` differs from path-derived normalized label
- book metadata unit differs from emitted `unit_label`

These events are observability-only and never block canonical writes.

## Implementation plan

### Phase 1: Writer contract relaxation

#### TODO checklist

- [x] Update `core/artifact_writer.py` to remove strict unit-label equivalence gate.
- [x] Add/keep non-empty `context.unit_label` requirement for all artifact writes.
- [x] Ensure error messaging reflects presence requirement only.

#### Test checklist

- [x] Update existing test that expects path-equivalence failure.
- [x] Add test: non-empty `unit_label` + mismatched path-derived label still writes successfully.
- [x] Add test: missing/blank `unit_label` fails with clear contract error.

#### Phase success criteria

- [x] False-negative contract failures from label drift are eliminated.
- [x] Missing-label artifacts are still blocked.

### Phase 2: Resolver consistency (best effort)

#### TODO checklist

- [x] Keep current resolver derivation behavior (book metadata when present, fallbacks as needed).
- [x] Optionally normalize/trim labels consistently before emit. (No additional resolver change required for this proposal scope.)

#### Test checklist

- [x] Resolver tests confirm stable non-empty label emission for typical book and non-book flows.

#### Phase success criteria

- [x] Resolver continues producing useful display labels without writer coupling.

### Phase 3: Docs and rollout

#### TODO checklist

- [x] Update `README.md` and `SPEC.md` to reflect relaxed unit-label contract.
- [x] Update changelog with rationale and behavior change.

#### Test checklist

- [x] Run targeted validation flow covering unit-label behavior in writer + resolver tests. (Full production E2E run intentionally deferred.)
- [x] Confirm canonical writes are no longer blocked by label-source drift.

#### Phase success criteria

- [x] Contract is simpler and operationally robust.

## Risks and mitigations

- **Risk:** Label quality drift goes undetected in strict-validation path.
  - **Mitigation:** optional non-blocking diagnostics and periodic audits.

- **Risk:** Teams may assume `unit_label` is canonical identity.
  - **Mitigation:** document clearly that `unit_label` is display metadata, not identity key.

## Success criteria

1. `write_marking_artifact` no longer fails due to unit-label source mismatch.
2. Artifacts still require non-empty `unit_label` for display quality.
3. No schema upgrade required.
4. Validation remains deterministic and self-contained.
