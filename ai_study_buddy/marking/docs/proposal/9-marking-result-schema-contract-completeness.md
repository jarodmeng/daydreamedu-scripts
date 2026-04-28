# Marking Result v1.4 Schema Completeness and Forward Versioning Model

Status: Implemented (`v0.2.14`) with deferred CI follow-up

Audience: Maintainers of `ai_study_buddy/marking` and skills/workflows that emit `marking_result` JSON

## Implementation Status (`v0.2.14`)

Implemented in this pass:

1. Added standalone schema file: `schemas/marking_result.v1.4.schema.json`.
2. Switched runtime schema loading to explicit versioned loader: `load_marking_result_schema(version)`.
3. Enforced strict runtime version policy (`v1.4` only in normal validation path) with `UnsupportedSchemaVersionError`.
4. Added JSON Schema validation in runtime validator before semantic Python invariants.
5. Enforced closed-contract schema behavior (`additionalProperties: false` in top-level and key nested objects).
6. Updated migration workflow artifact construction to use `SCHEMA_VERSION` (`v1.4`).
7. Updated docs/changelog:
   - `README.md` (`v0.2.14`, schema path update)
   - `SPEC.md` (strict `v1.4` runtime contract and schema source update)
   - `CHANGELOG.md` (`0.2.14` entry)
8. Added tests for unsupported-version rejection and closed-contract extra-field rejection.
9. Completed corpus validation dry-run and recorded result:
   - `docs/reports/2026-04-28_marking_result_v1_4_corpus_validation.md`
   - `154` files scanned, `154` at `marking_result.v1.4`, `0` validation failures after remediation.
10. Updated multi-agent marking operator instructions to enforce the new strict contract:
   - `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md`
   - `.cursor/agents/marking-phase1-mapper.md`
   - `.cursor/agents/marking-phase2-fast-pass-grader.md`
   - `.cursor/agents/marking-phase3-deep-dive.md`
   - `.cursor/agents/marking-phase4-taxonomy-tagger.md`
   - Added explicit `v1.4` schema compliance guidance, field-shape constraints, and enum/closed-object expectations in agent outputs.

Deferred follow-ups:

1. Revisit corpus-gate CI only if/when corpus files become available in CI inputs.

## 1) Goal

Make `marking_result.v1.4` the fully explicit, authoritative schema contract now, and establish a strict forward-versioning pattern for `v1.5+` where unsupported/legacy versions are rejected by default.

Primary goals:

1. Fully specify the current production contract (`v1.4`) in JSON Schema.
2. Remove runtime backward-compat acceptance for legacy versions (`v1`..`v1.3`) in normal code paths.
3. Define a maintainable process for future versioned schema files.

## 2) Problem Statement

Current state has one schema file (`marking_result.v1.schema.json`) that includes multiple version enums while detailed behavior largely lives in `core/artifact_schema.py`.

Issues:

1. Version contracts are not cleanly isolated.
2. Schema consumers cannot easily select a single version contract.
3. Schema and Python validator can drift.
4. New version work risks tightening older versions unintentionally.

## 3) Proposed Architecture

### 3.1 Start with `v1.4` as the explicit baseline

Given current repository state (`context/marking_results/**/*.json`) is fully `marking_result.v1.4`, we will:

1. Keep one explicit schema file for the active contract:
   - `marking_result.v1.4.schema.json`
2. Avoid recreating dedicated historical schema files for `v1`, `v1.1`, `v1.2`, `v1.3` in this phase.
3. Treat legacy versions as unsupported in normal validators/parsers and fail fast with explicit exceptions.

Rationale:

- avoids low-value historical reconstruction work
- focuses effort on the active, real production contract
- avoids silent behavior that can mask stale artifacts

### 3.2 Inline schema policy (no external shared defs for now)

For risk reduction and maintainability, keep `marking_result.v1.4.schema.json` self-contained:

1. No external shared-defs schema file in this phase.
2. Keep all `$defs` local and inline within the `v1.4` schema file.
3. If/when `v1.5+` introduces meaningful duplication across active versions, re-evaluate extracting shared defs in a separate proposal.

### 3.3 Python versatile version handling

Refactor `core/artifact_schema.py` into a clear version-aware model:

1. Detect `schema_version` from payload early.
2. If version is `v1.4`, run strict JSON Schema validation against `marking_result.v1.4.schema.json`.
3. For legacy versions (`v1`..`v1.3`), raise explicit `UnsupportedSchemaVersionError` in normal validation/read/write paths.
4. Run Python semantic validation for invariants not well-expressed in JSON Schema.

Design requirements:

- single mapping table for supported schema versions (currently `v1.4`)
- clear unsupported-version error
- no version-specific conditionals spread across unrelated functions
- easy extension for `v1.5+` by adding a schema file + mapping entry + tests
- explicit version constants only (no implicit `latest` alias resolution)

### 3.4 Writer and parser behavior

Writers/parsers should support:

1. Default write version remains latest (`v1.4` now).
2. Optional explicit target version argument is supported only for explicitly supported schema versions.
3. Reading/validating legacy versions is rejected by default.

Version selection rule:

- Python APIs/config must pass explicit schema version constants; do not support `"latest"` aliases.

## 4) Contract Strategy

### 4.1 Active baseline policy

`v1.4` is the active explicit schema baseline and must be fully specified in JSON Schema.

Legacy versions:

1. are unsupported in normal runtime validators/parsers
2. do not require dedicated schema files in this phase
3. are out of scope for this proposal's implementation work

### 4.2 `question_results[]` policy

For `v1.4`, define full `question_results.items` structure:

- required core fields
- optional fields and defaults semantics
- enum restrictions
- nested `diagnosis` object

For future versions, encode changed requiredness in each new version file (for example, `v1.5`) rather than introducing a single multi-version conditional mega-schema.

### 4.3 Additional properties stance

Contract-closed rollout:

1. For `marking_result.v1.4`, set `additionalProperties: false` for top-level and key nested objects (`context`, `summary`, `question_results.items`, `diagnosis`, `review_meta`, `generation`, and `context.question_page_map.items`).
2. New field additions are forbidden unless they go through an approved proposal and are implemented universally (schema, Python validator, writers/parsers, tests, docs/changelog).
3. For this implementation, no open-object exceptions are planned for key objects.

## 5) Risks and Mitigations

### Risk A: Hard failure on old artifacts

Removing backward compatibility means old artifacts fail immediately in normal flows.

Mitigation:

1. Make the exception message actionable.
2. Prioritize explicit schema quality for actively produced versions.

### Risk B: Schema/Python drift for active version

`v1.4` schema can drift from runtime validation if parity guardrails are weak.

Mitigation:

1. Parity tests for `v1.4` schema + runtime validator.
2. Single Python dispatch entrypoint.
3. Required update policy: schema + runtime + tests in same PR.

### Risk C: Operational interruption during rollout

Teams with stale local artifacts may hit exceptions immediately.

Mitigation:

1. Keep strict schema CI targeted to supported schema versions (`v1.4` now).
2. Keep runtime error messages explicit so unsupported versions are easy to diagnose.

### Risk D: Runtime ambiguity for default output version

Different scripts may emit different versions unintentionally.

Mitigation:

1. Centralize default write version constant.
2. Log/write schema version explicitly in writer metadata.
3. Add tests asserting default output version behavior.

## 6) Detailed Implementation Plan (Phases)

Ship in small phases with green tests and explicit exit criteria.

### Phase 0 - Decision freeze and baseline inventory

Goal: lock architecture and collect current behavior by version.

TODO checklist:

- [x] Confirm strategy: explicit schema starts at `v1.4`; no historical schema recreation in this phase.
- [x] Confirm strict policy: legacy versions are rejected in normal runtime flows.
- [x] Freeze actively supported schema versions set (`v1.4` initially).
- [x] Inventory current runtime rules in `artifact_schema.py` and map each to versions.
- [x] Confirm inline-only schema policy for `v1.4` (no external shared-defs file).
- [x] Confirm closed-contract policy for `v1.4` (`additionalProperties: false` by default).
- [x] Define "Python-only invariants" list (for docs/tests).

Exit criteria:

- Approved architecture note and version-rule matrix committed in proposal updates.

### Phase 1 - Create explicit `v1.4` schema contract

Goal: make the currently produced contract fully explicit.

TODO checklist:

- [x] Add `marking_result.v1.4.schema.json` as the explicit active contract.
- [x] Retain existing `marking_result.v1.schema.json` only as transitional/compat artifact (or deprecate with clear docs).
- [x] Keep all reusable definitions inline within `marking_result.v1.4.schema.json`.
- [x] Ensure `v1.4` has explicit `question_results.items`.
- [x] Ensure `v1.4` fixes `schema_version` to one value.
- [x] Ensure `v1.4` explicitly requires `context.question_page_map`.
- [x] Apply `additionalProperties: false` to top-level and key nested objects in `v1.4`.
- [x] Confirm no intentionally open key object remains in `v1.4`.

Exit criteria:

- `v1.4` has a dedicated, valid schema file with explicit row shape.

### Phase 2 - Refactor Python to strict version handling

Goal: cleanly route validation/load by schema version.

TODO checklist:

- [x] Introduce supported-version->schema-path mapping constant (starts with `v1.4`).
- [x] Replace single-schema loader with `load_marking_result_schema(version)` for supported schema versions.
- [x] Implement central dispatch validator:
  - [x] parse `schema_version`
  - [x] run JSON Schema validation for supported schema versions (now `v1.4`)
  - [x] run semantic Python checks
- [x] Raise `UnsupportedSchemaVersionError` for `v1`..`v1.3` in normal validator path.
- [x] Keep semantic checks modular (shared + version-specific helper functions).
- [x] Add clear errors for unsupported/missing version.
- [x] Update public API docs to state strict rejection policy.

Exit criteria:

- Runtime validation path handles supported schema versions and rejects legacy versions with explicit errors.

### Phase 3 - Writer/parser strategy

Goal: make producer/consumer paths version-aware and predictable.

TODO checklist:

- [x] Add central `DEFAULT_MARKING_RESULT_VERSION` constant.
- [x] Ensure writers emit default latest unless explicitly overridden.
- [x] Add optional writer arg to target a specific supported schema version (future-ready).
- [x] Ensure parsers/readers reject unsupported legacy versions by default.
- [x] Document when to add a new schema file (`v1.5+`).
- [x] Ensure API/config surfaces accept explicit versions only (reject `"latest"` alias).

Exit criteria:

- Write/read behavior is deterministic; unsupported legacy versions fail fast.

### Phase 4 - Tests and parity harness

Goal: prevent future drift and regressions.

TODO checklist:

- [x] Add fixture folders for `v1.4` schema validation (`valid`/`invalid`).
- [x] Add schema-only validation tests for `v1.4`.
- [x] Add runtime semantic validation tests for `v1.4`.
- [x] Add tests asserting legacy version rejection with actionable errors.
- [x] Add parity tests asserting `v1.4` schema + Python agreement where intended.
- [x] Add targeted mismatch tests for known Python-only invariants.
- [x] Add tests for dispatch errors (unknown version, missing schema_version).
- [x] Add negative tests asserting unexpected extra fields are rejected in closed objects.

Exit criteria:

- Test suite reliably detects `v1.4` schema/runtime drift, legacy rejection behavior, and version-routing errors.

### Phase 5 - Corpus dry-run and remediation

Goal: quantify impact on real artifacts and resolve incompatibilities safely.

TODO checklist:

- [x] Run version-routed validation over `context/marking_results/**/*.json`.
- [x] Report failures grouped by `schema_version` and failure type (expect `v1.4` only in current corpus).
- [x] Classify each failure:
  - [x] artifact defect
  - [x] schema too strict
  - [x] unexpected legacy version
- [x] Implement minimal fixes:
  - [x] schema relaxations where justified
  - [x] operational remediation decisions where needed
- [x] Re-run until failure profile is accepted.

Exit criteria:

- Rollout impact is understood, and blockers are resolved.

### Phase 6 - Documentation and CI rollout

Goal: institutionalize the strict schema governance workflow.

TODO checklist:

- [x] Update `marking/README.md` with `v1.4` baseline and strict rejection policy.
- [x] Update `marking/SPEC.md` with strict dispatch flow and "how to add `vNext`".
- [x] Update `marking/TESTING.md` with fixture/parity conventions.
- [x] Update `CHANGELOG.md` with architecture shift and apply a small version bump.
- [x] Keep corpus validation as local/operator check for now (no CI corpus gate).
- [ ] Add CI checks (schema/parity) if/when repository CI scope is expanded for marking package changes.
- [x] Add contributor checklist: "how to add `vNext` or new fields safely" (proposal required + universal implementation required).
- [x] Update marking orchestration skill and phase-agent instructions to comply with strict `marking_result.v1.4` contract.
- [x] Update this proposal doc to record implemented scope, completed checklist items, and any approved deviations.

Exit criteria:

- Maintainers have clear rules and CI enforcement for schema evolution.

## 7) Acceptance Criteria

1. `marking_result.v1.4` has an explicit standalone schema with complete `question_results[]` contract.
2. Python validation/read/write uses centralized version-aware handling with strict rejection of unsupported legacy versions.
3. Schema/runtime parity tests exist and pass for `v1.4`.
4. Legacy rejection tests are present and pass (pre-`v1.4` rejected in normal flows).
5. Historical corpus impact has been assessed before strict CI enforcement.
6. Documentation clearly explains how future versions (`v1.5+`) should be created and maintained.
7. Closed-contract behavior is enforced: arbitrary extra fields are rejected for `v1.4` objects under policy.
