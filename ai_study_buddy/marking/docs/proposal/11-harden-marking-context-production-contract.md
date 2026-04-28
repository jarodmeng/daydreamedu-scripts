# Proposal: Harden Marking Context Production Contract (Resolver-Only Context)

Status: Implemented (`v0.2.16`)

Audience: Maintainers of `ai_study_buddy/marking`, marking-run workflow owners, and review workspace consumers

## 1) Goal

Guarantee that canonical `marking_result` context fields are produced by trusted Python resolver functions (in `ai_study_buddy.marking`) rather than manually assembled by marking agents or ad-hoc workflow scripts.

Primary outcomes:

1. Eliminate context drift across marking run modes (standard / embedded-answer / teacher-annotated).
2. Make context invariants enforceable at write-time.
3. Prevent display regressions caused by inconsistent context derivation (for example `_c_` leakage in `unit_label`).
4. Keep producer flexibility while forcing all producers through a typed resolver API.

## 2) Problem Statement

Today, canonical artifact writing validates schema shape but does not enforce that `context` came from resolver output. This allows producer paths to assemble `context` manually and still pass JSON schema validation.

Observed consequence:

- Different runs produce inconsistent `context.unit_label` for equivalent naming patterns.
- Resolver-normalized behavior exists, but some producer flows bypass it.

This is a contract gap, not only a prompt-quality issue.

## 3) Non-Goals

1. Redesigning question grading logic.
2. Changing `question_results[]` semantics.
3. Replacing the existing context resolver architecture.
4. Blocking all experimentation; this proposal scopes hardening to canonical writer paths.

## 4) Current State Analysis

Current contract pieces:

1. `resolve_marking_context(...)` computes `MarkingContext` with normalization and deterministic lookups.
2. `write_marking_artifact(...)` validates schema + path rules, but accepts any `MarkingArtifact` payload.
3. Agent workflows can still construct `context` fields directly before write.

Root gaps:

1. No provenance marker that context was resolver-produced.
2. No write-time assertion that required resolver invariants were applied.
3. No strict API boundary forcing context creation via resolver entrypoints.
4. Teacher-annotated flows may encourage manual context assembly if resolver APIs are not explicit enough.

### 4.1 Resolver gap surface area (critical feasibility analysis)

This proposal depends on upgrading `resolve_marking_context(...)` so all accepted run modes can be resolved without agent-side context assembly. The gap surface area below is the implementation guide for that upgrade.

Current corpus tally baseline (from existing `marking_results` artifacts):

1. A (standard mapped-answer): 124
2. B (embedded-answer override): 15
3. C (teacher-annotated family modes): 15

Implication: migration implementation scope is A/B/C.

Resolver sufficiency summary:

| Class | Current `resolve_marking_context(...)` sufficiency | What is missing for hardened contract |
|---|---|---|
| A (standard mapped-answer) | Mostly sufficient for context assembly. | Add explicit resolver provenance/mode metadata and writer-enforced invariants so context lineage is auditable and fail-closed. |
| B (embedded-answer override) | Functionally supported via `self_answer_pages`. | Add explicit override-mode provenance/invariant signaling and stronger writer checks for override consistency (answer source + page-range coherence). |
| C (teacher-annotated family) | Partially sufficient in practice, not fully contractized as resolver-first mode. | Add explicit teacher-annotated mode parameterization in resolver, define mode-specific required/optional context fields, and remove need for any producer-side context assembly. |

#### A) Standard mapped-answer mode (template linked + answer mapping present)

Current support:

- Largely covered by current resolver flow.

Remaining gaps to harden:

1. Explicit mode declaration is not first-class in resolver output/provenance.
2. Invariant reporting is implicit; writer cannot easily assert which resolver path was used.

Upgrade implications:

- Add explicit resolved mode/provenance fields and invariant flags in resolver output.

#### B) Embedded-answer override mode (`self_answer_pages`)

Current support:

- Supported via `self_answer_pages` override in existing resolver.

Remaining gaps to harden:

1. Needs stronger contract-level signaling that this was an intentional override mode.
2. Needs deterministic invariant checks for page-range coherence and answer source semantics.

Upgrade implications:

- Extend resolver output to encode mode-specific provenance/invariants for override usage.
- Add writer assertions for override-consistent context fields.

#### C) Teacher-annotated, no answer key mapping

Current support:

- Partially supported in practice by producer behavior, but not yet fully contractized as a resolver-first mode.

Observed risk signals:

1. Artifacts can carry teacher-annotated mapping notes while still showing context inconsistencies.
2. Some runs appear to bypass resolver normalization and assemble context directly.

Upgrade implications:

- Upgrade `resolve_marking_context(...)` to accept explicit teacher-annotated mode parameters.
- Define mode-specific required/optional context fields under this mode.
- Ensure resolver emits normalized `unit_label` and coherent nullable template/answer fields.

### 4.2 Required outputs of the gap analysis (must be completed before Phase 2 build)

Before implementing resolver upgrades, produce and baseline:

1. A mode matrix: inputs, required fields, allowed nullability, and expected provenance flags per mode.
2. A resolver parameter map: which new/updated params encode each mode without ambiguity.
3. A failure taxonomy: deterministic resolver errors for unsupported/ambiguous requests.
4. A migration replay comparison spec: strict vs normalized vs mode-aware comparisons.
5. A fixture set: one canonical artifact fixture per supported mode for regression testing.
6. Explicit fail-fast policy: if a scenario is outside supported A/B/C resolver modes, marking must stop and require resolver-function upgrade first.

### 4.3 Locked mode enum and resolver parameter contract (for Phase 0–3 implementation)

Use these canonical mode identifiers everywhere (resolver output provenance, tests, migration reporting):

1. `standard_mapped_answer` (Class A)
2. `embedded_answer_override` (Class B)
3. `teacher_annotated` (Class C)

Resolver parameter contract table:

| Mode enum | Required inputs | Optional inputs | Must be absent | Core resolver expectations |
|---|---|---|---|---|
| `standard_mapped_answer` | `attempt_file_id_or_path` | `student_id`/`student_name`, `book_label`, `unit_query`, `question_request`, `question_refs`, `section_hint`, `auto_register_attempt`, `auto_link_template` | `self_answer_pages` | Template + answer mapping are resolved via standard linked/template mapping flow. |
| `embedded_answer_override` | `attempt_file_id_or_path`, `self_answer_pages` | same optional inputs as A | none | Resolver uses embedded-answer override semantics and emits override-consistent mapping provenance. |
| `teacher_annotated` | `attempt_file_id_or_path` | same optional inputs as A plus explicit mode selector param to be added in Phase 2 (for example `marking_mode=\"teacher_annotated\"`) | `self_answer_pages` unless explicitly allowed by future policy | Resolver emits teacher-annotated context semantics and mode-specific nullability/provenance per contract. |

Notes:

1. If caller inputs do not match one of these mode rows, resolver must fail with deterministic error.
2. Any future mode requires explicit contract extension here before implementation.

## 5) Contract Decision

Adopt a **Resolver-Only Context Contract** for canonical artifact production:

1. All canonical `marking_result` writes must use context returned by marking package resolver functions.
2. Manual context dict assembly is unsupported for canonical writes.
3. Writer performs runtime provenance + invariant checks and fails closed on violations.
4. Resolver APIs must cover all supported run modes so no producer needs to bypass resolver.
5. Contract enforcement ownership is centralized: resolver-contract invariants must be enforced in one writer-side gate (`assert_context_contract`) before schema validation.

## 6) Proposed Design

### 6.1 New context provenance metadata

Add explicit provenance fields to context (or an adjacent metadata block, schema-compatible choice to be finalized in Phase 1):

1. `context_resolution.method` (enum):
   - `resolve_marking_context`
   - optional mode-specific markers from the same resolver (if needed)
   - future explicit resolver entrypoints only as fallback
2. `context_resolution.resolver_version` (string)
3. `context_resolution.resolved_at` (ISO timestamp)
4. `context_resolution.invariants` (object flags; optional but recommended)

Purpose: auditable evidence that context passed through resolver contract.

### 6.2 Strict writer guardrail

In `write_marking_artifact(...)`:

1. Add a pre-validation gate `assert_context_contract(payload)`.
2. Fail if provenance metadata missing/invalid.
3. Fail if required invariants are violated.

Minimum invariants (centralized writer contract requirements):

1. Writer contract gate (`assert_context_contract`) enforces:
   - required resolver provenance fields (`method`, `resolver_version`, `resolved_at`, `mode`);
   - `method == resolve_marking_context`;
   - `mode` enum membership;
   - `context.unit_label` canonical normalization against `unit_file_path` when both are present.
2. Writer contract gate also enforces:
   - `context.subject_context` non-empty;
   - `context.attempt_file_path` non-empty;
   - mode-specific coherence checks required by resolver-only contract.
3. Existing write pipeline path-sanitization (`sanitize_marking_artifact_paths`) runs before writer contract gate checks.
4. JSON Schema remains structural/shape validation, but resolver-contract semantics must not rely on schema-only enforcement.

Centralization rule:

1. Resolver-only contract checks must have one authoritative implementation entrypoint (`assert_context_contract`).
2. Any duplicate checks in schema/runtime validators are allowed only as defensive redundancy, not as primary contract ownership.
3. New resolver-contract invariants must be added to `assert_context_contract` first, then reflected in docs/tests.

### 6.3 Consolidated label normalization helper

Create a shared helper for filename-derived display labels in `marking/core/artifact_paths.py` (or dedicated normalization module):

1. `derive_unit_label_from_attempt_name(name_or_path)`
2. Internally reuse prefix-stripping behavior from `normalize_attempt_stem(...)`.

Then:

1. `context_resolver._infer_unit_label(...)` uses this helper.
2. Any alternative resolver mode uses this helper.
3. Writer invariant check can recompute expected value when metadata `unit` is absent.

### 6.4 Resolver API coverage expansion

Preferred approach: keep **one public resolver entrypoint** and expand `resolve_marking_context(...)` to cover all accepted run modes via typed parameters and strict validation.

Design rules:

1. All valid run modes should map to `resolve_marking_context(...)`.
2. Mode-specific behavior must be explicit in validated parameters (no implicit agent-side context inference).
3. Resolver output must remain a single normalized typed `MarkingContext`.
4. Add additional public resolver entrypoints only if extending one function would become ambiguous or unsafe.

### 6.5 Producer integration contract

Update all producer orchestrators/skills:

1. Producer must call resolver API first.
2. Producer may not mutate structural context fields except approved write-time enrichments (`marking_asset`, `attempt_sequence`, etc., already controlled in writer).
3. Producer-generated telemetry remains under `generation` fields, not `context` structure.

## 7) Schema and Versioning Strategy

Because provenance fields are new contract surface, this proposal commits to a schema bump:

1. Add `marking_result.v1.6` schema with provenance fields required for new writes.
2. Keep read support for `v1.5`.
3. Migrate legacy `v1.5` artifacts by replaying current `resolve_marking_context(...)` and comparing resolved context against stored context:
   - if contexts match (per approved comparison rules), backfill provenance as resolver-produced by current function;
   - if contexts differ, overwrite selected context fields with resolver output and backfill provenance; keep a migration queue/report log for auditability.

Decision: migrate canonical writes and legacy corpus to `v1.6` for explicitness and long-term auditability.

## 8) Implementation Plan

### Phase 0 — Discovery and lock scope

TODO checklist:

- [x] Inventory every canonical writer call site.
- [x] Classify producer modes that currently bypass resolver.
- [x] Define exact invariant set and acceptable mode exceptions.
- [x] Add call-site inventory doc snippet in this proposal or a follow-up report.
- [x] Produce agreed invariant matrix per mode.
- [x] Produce detailed resolver gap surface-area write-up (Section 4.1) validated against real producer flows.
- [x] Produce resolver parameter-upgrade design mapping each identified gap to concrete `resolve_marking_context(...)` API changes.

### Phase 1 — Shared normalization + invariant functions

TODO checklist:

- [x] Add shared `derive_unit_label_from_attempt_name(...)` helper.
- [x] Refactor `_infer_unit_label(...)` to use shared helper.
- [x] Add `assert_context_contract(...)` function with unit tests.
- [x] Wire `assert_context_contract(...)` into `write_marking_artifact(...)` behind a temporary feature flag.
- [x] Keep unit tests green for normalization + invariant checks.
- [x] Confirm no behavior change when flag is disabled.

### Phase 2 — Resolver provenance + schema evolution

TODO checklist:

- [x] Add provenance block to resolver outputs.
- [x] Expand `resolve_marking_context(...)` parameter contract to represent all supported run scenarios explicitly.
- [x] Introduce `marking_result.v1.6` schema with required provenance fields.
- [x] Update schema loader defaults to new version for writers.
- [x] Keep parsers/readers backward-compatible for `v1.5`.
- [x] Ensure writer emits `v1.6` artifacts by default.
- [x] Ensure validation gates pass for resolver-produced artifacts.

### Phase 3 — Phase-2 verification and contract testing

TODO checklist:

- [x] Add focused tests for resolver provenance fields (presence, shape, and mode correctness).
- [x] Add focused tests for expanded `resolve_marking_context(...)` parameter handling across A/B/C modes.
- [x] Add schema validation tests for `marking_result.v1.6` required provenance fields.
- [x] Add writer contract tests that fail when provenance/invariants are missing or inconsistent.
- [x] Add migration replay comparator tests (match vs mismatch classification).
- [x] Run targeted test suite and record baseline pass results before producer migration.

### Phase 4 — Legacy artifact migration and cleanup

TODO checklist:

- [x] Add one-off migration workflow for existing artifacts.
- [x] For each legacy artifact, run current `resolve_marking_context(...)` using artifact-identifiable inputs.
- [x] Compare resolved context vs stored context with deterministic field rules.
- [x] Apply strict-equal checks (for example `student_id`, `subject_context`, `attempt_file_path`, page ranges when applicable).
- [x] Apply normalized-equal checks where formatting differences are expected (for example equivalent path placeholder normalization).
- [x] Apply explicit mode-aware allowances documented in the comparison spec.
- [x] If match: backfill provenance to indicate context is consistent with current resolver contract.
- [x] If mismatch: overwrite selected context fields with resolver output and backfill provenance; record queue/report entries for audit.
- [x] Publish migration report including matched count, mismatched count, and review-queue path.
- [x] Confirm corpus compatibility is maintained.
- [x] Confirm mismatch queue/report is produced for audit review.
- [x] Document residual risk.
- [x] Scope migration execution to A/B/C only.

### Phase 5 — Producer migration

TODO checklist:

- [x] Update all official marking producer skills/workflows to call resolver APIs exclusively.
- [x] Remove/forbid manual context assembly snippets from skills/docs.
- [x] Add CI contract test that simulates producer output path and asserts context provenance.
- [x] Update producer docs.
- [x] Ensure contract tests enforce resolver-only flow.

### Phase 6 — Enforce fail-closed in writer

TODO checklist:

- [x] Turn on strict writer context contract checks unconditionally.
- [x] Remove temporary feature flag.
- [x] Add actionable error messages for violations.
- [x] Verify manual context writes fail deterministically.
- [x] Verify supported resolver flows continue passing.
- [x] Centralize all resolver-contract invariants in `assert_context_contract` (writer-owned enforcement boundary).
- [x] Keep schema validation focused on structural contract; do not depend on schema-only checks for resolver-contract semantics.
- [x] Add tests proving centralized writer gate rejects missing `subject_context`, missing `attempt_file_path`, and mode-incoherent payloads before schema validation.

### Phase 7 — Documentation updates and small version bump

TODO checklist:

- [x] Update `ai_study_buddy/marking/SPEC.md` for resolver-only context contract and `v1.6` provenance requirements.
- [x] Update `ai_study_buddy/marking/README.md` with the new canonical context-production rules and migration notes.
- [x] Update `ai_study_buddy/marking/ARCHITECTURE.md` to reflect writer enforcement boundary and resolver provenance flow.
- [x] Update `ai_study_buddy/marking/TESTING.md` with new contract checks and migration validation steps.
- [x] Add `ai_study_buddy/marking/CHANGELOG.md` entry summarizing the resolver-only hardening and `v1.6` rollout.
- [x] Apply a small `ai_study_buddy/marking` package version bump and keep docs/version references aligned.

## 9) Testing Plan

Add/extend tests under `ai_study_buddy/marking/tests/`:

1. Resolver unit tests:
   - standard mapped-answer mode
   - self-answer override mode
   - teacher-annotated mode (if new resolver)
2. Normalization tests:
   - repeated prefix stripping
   - label derivation consistency across helper + resolver
3. Writer contract tests:
   - resolver-produced context passes
   - manual context missing provenance fails
   - inconsistent `unit_label` fails
4. Backward compatibility tests:
   - `v1.5` reads still work
   - migration script outputs schema-valid artifacts
   - resolver replay comparison classifies match vs mismatch correctly
5. End-to-end smoke:
   - one run per mode produces valid canonical artifact with provenance

## 10) Risks and Mitigations

1. Risk: strict enforcement breaks existing producer scripts.
   - Mitigation: migration-first rollout, producer contract updates, and fail-fast writer errors with actionable messages.
2. Risk: teacher-annotated edge cases still need explicit nullability rules for selected context fields.
   - Mitigation: explicit mode parameters within `resolve_marking_context(...)` + invariant matrix with mode-specific allowances.
3. Risk: legacy artifacts cannot be provenance-verified.
   - Mitigation: resolver replay + deterministic comparison; auto-backfill only on match, otherwise human-review queue with no mutation.
4. Risk: schema churn impacts downstream consumers.
   - Mitigation: backward-compatible reads and clear changelog/docs.

## 11) Definition of Done

Done means:

1. Canonical writer rejects non-resolver context in strict mode.
2. All supported marking modes have resolver API coverage.
3. `unit_label` derivation is centralized and consistent.
4. Producer docs/skills no longer instruct manual context assembly.
5. Tests + CI enforce the contract.
6. Migration (if applicable) completed with report.
7. Resolver-contract invariants are centrally enforced by writer gate (`assert_context_contract`), not distributed as primary ownership across layers.

## 12) Decisions Locked

1. Provenance location:
   - Use `context` (not top-level `generation`).
2. Mismatched replay artifacts:
   - Queue-only mode keeps canonical artifacts unchanged and records mismatches in review queue/report.
   - Optional migration apply mode (`--overwrite-mismatches`) may overwrite selected context fields with resolver output, then re-validate and record audit entries.
3. Cryptographic signing:
   - Not required for this proposal scope.
4. Contract-enforcement ownership:
   - Writer gate (`assert_context_contract`) is the single authoritative resolver-contract enforcement boundary.
   - Schema validation is structural and complementary, not the primary owner of resolver-contract semantics.

## 13) Rollout Recommendation

1. Complete resolver/schema/test hardening and run producer migration + corpus audit in staging/dev.
2. Keep canonical writes fail-closed by default in `write_marking_artifact(...)` (no runtime feature flag).
3. Use migration workflow modes as needed:
   - queue-only mismatch review mode;
   - optional `--overwrite-mismatches` apply mode with audit logs.
4. Keep proposal/docs/checklists aligned with implementation and migration reports.
