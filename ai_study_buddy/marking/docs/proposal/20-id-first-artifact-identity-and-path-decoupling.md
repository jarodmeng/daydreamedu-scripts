# Proposal 20: ID-first artifact identity and path decoupling

## Status

In progress.

Depends on:

- Proposal 2 (artifact lookup by completion)
- Proposal 6 (marking run artifact removal)
- Proposal 11 (context production contract hardening)
- Proposal 19 (unit label contract hardening)

## Current progress snapshot (2026-05-28)

Completed in this cycle:

- Implemented guarded rename workflow in `pdf_file_manager`:
  - `ai_study_buddy/pdf_file_manager/scripts/rename_file_with_context_guardrail.py`
  - single-file rename, dry-run/apply, fail-fast + recovery manifest
  - linked-family cascade for `marking_results`, `learning_reports`, `marking_assets`, `student_review_states`, `marking_amendments`
  - archive exclusion (`archive`, `_archive`)
- Added transactional `study_buddy.db` remap in apply mode for path-coupled fields (`artifact_path`/`artifact_stem`/`marking_asset`, review/amendment paths, and import identity/quarantine source paths).
- Added focused tests:
  - `ai_study_buddy/pdf_file_manager/tests/test_rename_file_with_context_guardrail.py`
- Added drift reporting CLIs in `learning_db`:
  - `ai_study_buddy/learning_db/cli/context_db_drift_report.py`
  - `ai_study_buddy/learning_db/cli/triage_missing_marking_assets.py`
- Resolved active artifact-path and active marking-asset drift in current local data (active counts now zero for those two checks).

Remaining for this proposal:

- Medium-term ID-first hardening (introduce `marking_run_id`; re-key review/amendment to IDs).
- Long-term full normalization/deprecation of stem-identity assumptions.
- CI policy wiring and explicit operator policy docs for mandatory guarded rename flow.

## Decision framing

This proposal adopts a staged strategy:

1. **Short term (high priority):** ship strong rename guardrails to prevent most real-world drift/breakage now.
2. **Medium term (targeted):** migrate highest-risk wiring to ID-first, especially review-state/amendment retrieval and writes.
3. **Long term (optional):** complete full ID-first normalization across all artifact families if scale/rename frequency justifies it.

## Why this proposal exists

Today, the system is partially ID-driven and partially filename/path-stem-driven.

- Good: primary attempt lookup is mostly `attempt_file_id` first.
- Risk: review-state and amendment persistence still key by artifact stem/path.
- Risk: operational scripts (cleanup/prune/migration) still rely heavily on path conventions.

This creates rename drift: if a registry file's normal name changes but historical `context/` paths are not migrated, behavior can silently diverge or break in specific flows.

## Problem statement

Identity is not uniformly modeled across artifact families.

Current behavior mixes three identity styles:

1. Stable IDs (`attempt_file_id`, registry IDs)
2. Relative artifact paths (`marking_results/.../*.json`)
3. Derived stems (`<normal_name>__<timestamp>`)

When these diverge, the system can:

- miss review-state/amendments
- create forked state under new stems
- show inconsistent UI status
- misclassify rows in path-based prune/cleanup tools

## Goals

1. Prevent rename-induced drift and breakage immediately with operational guardrails.
2. Progressively make IDs the canonical identity for marking/review artifacts.
3. Preserve human-readable paths for operability, but treat them as non-authoritative.
4. Make file normal-name renames safe without requiring synchronous filesystem-wide renames.
5. Maintain backward compatibility with existing corpus during migration.

## Non-goals

- Replacing all human-readable artifact path segments with opaque IDs immediately.
- One-shot destructive migration with no fallback.
- Rewriting unrelated `pdf_file_manager` domain logic.

## Proposed design

### 1) Short-term rename guardrails (primary immediate investment)

Implement one supported rename workflow and block ad-hoc/manual partial renames.

Guardrail requirements:

- single rename command (dry-run + apply)
- atomic cascade across:
  - `marking_results`
  - `learning_reports`
  - `marking_assets`
  - `student_review_states`
  - `marking_amendments`
- transactional DB remap for linked rows in `study_buddy.db`:
  - `marking_artifacts.artifact_path`
  - `marking_artifacts.artifact_stem`
  - `marking_artifacts.marking_asset` (when bundle path changes)
  - `student_review_states.review_state_path`
  - `student_review_states.marking_result_path`
  - `marking_amendments.amendment_path`
  - `marking_amendments.marking_result_path`
  - `import_identity_map.source_path` (including note-scope suffix keys)
  - `import_quarantine.source_path` (best-effort for open entries)
- post-rename verification:
  - no orphan old-stem files for the target run(s)
  - all expected companion artifacts resolve
  - no stale old-path rows remain in DB for the linked artifact scope
- audit logging for each rename operation
- preflight/CI check to fail when partial rename drift is detected

This is expected to prevent most observed operational drift without immediate full schema migration.
Without this DB remap, filesystem-only rename can still break ingestion/link resolution because
review/amendment and import identity tables retain path-linked fields.

### 2) Introduce stable `marking_run_id` (medium-term foundation)

Add a stable run identity for each marking artifact set (JSON/report/assets/review/amendments).

Contract:

- immutable UUID-style value generated once per run
- present in canonical marking JSON payload context
- persisted in DB rows for all dependent artifact families

`marking_run_id` becomes the authoritative key for run-level joins.

### 3) Re-key review state and amendments to IDs (medium-term priority)

Current write/read paths use `artifact_stem`.
Move to ID-first storage and retrieval:

- primary key: (`attempt_file_id`, `marking_run_id`)
- fallback/read-compat: legacy stem path resolution

Path layout may remain human-readable, but lookup must be ID-driven.

### 4) Keep paths readable, but decouple identity from paths

Paths continue to use readable names by default for operator ergonomics.
However:

- API and DB joins use IDs only.
- path mismatch is treated as drift, not identity loss.
- services can rewrite/relocate paths without losing referential integrity.

### 5) Add rename-safe reconciliation workflow

Provide a dedicated command/workflow that:

1. finds all artifacts by IDs
2. computes desired canonical paths from current naming policy
3. dry-runs move plan
4. applies coordinated renames/moves
5. updates DB path mirrors and validates post-conditions

This workflow is the only supported path-normalization tool.

### 6) Harden cleanup/prune tooling with ID checks

Before deleting or pruning rows/files, verify ID-level linkage:

- do not prune solely because a historical path is missing
- allow path drift if IDs still connect valid artifacts
- emit drift diagnostics for manual/automated reconciliation

## Data model and API changes

### Marking payload

- Add `context.marking_run_id` (required for new writes).
- Keep existing fields (`attempt_file_id`, `attempt_file_path`, `marking_asset`) for compatibility.

### Learning DB

- Ensure marking artifact table stores `marking_run_id`.
- Ensure review-state and amendment tables store:
  - `attempt_file_id`
  - `marking_run_id`
  - optional `artifact_path` mirror (non-authoritative)

### Service APIs

New internal signatures should accept IDs first, not stem:

- `load_review_state(..., attempt_file_id, marking_run_id, ...)`
- `load_amendment(..., attempt_file_id, marking_run_id, ...)`
- `save_*` counterparts similarly ID-first

Legacy stem-based routes remain as adapters during migration.

## Phased implementation plan

### Phase A (short term): guardrails first

#### TODO checklist

- [ ] Implement one canonical rename command/workflow with dry-run and apply modes.
- [ ] Enforce full artifact-family cascade for rename operations.
- [ ] Add transactional `study_buddy.db` remap for all linked path-keyed fields.
- [ ] Add post-rename verifier with fail-closed checks.
- [x] Implement one canonical rename command/workflow with dry-run and apply modes.
- [x] Enforce full artifact-family cascade for rename operations.
- [x] Add transactional `study_buddy.db` remap for all linked path-keyed fields.
- [x] Add post-rename verifier with fail-closed checks.
- [ ] Add CI/preflight drift check for partial renames.
- [ ] Document "no manual artifact renames" operational policy.

#### Test checklist

- [ ] Dry-run outputs complete and correct move plan.
- [ ] Apply mode updates all required trees atomically for test fixtures.
- [ ] Apply mode updates linked DB path rows consistently (no stale old paths).
- [ ] Verifier catches intentionally induced partial rename drift.
- [x] Dry-run outputs complete and correct move plan.
- [x] Apply mode updates all required trees atomically for test fixtures.
- [x] Apply mode updates linked DB path rows consistently (no stale old paths).
- [x] Verifier catches intentionally induced partial rename drift.

#### Phase success criteria

- [ ] Normal-name rename operations no longer produce partial artifact drift in standard workflows.
- [x] Normal-name rename operations no longer produce partial artifact drift in standard workflows.
- [ ] Teams can safely perform renames without manual multi-folder edits.

### Phase B (medium term): targeted ID-first hardening

Focus on highest-risk breakage points first (review/amendment paths and joins).

#### TODO checklist

- [ ] Add `marking_run_id` generation and persist it in new writes.
- [ ] Extend DB schema for `marking_run_id` and index key read paths.
- [ ] Re-key review-state/amendment read/write services to IDs first.
- [ ] Keep legacy stem/path fallback with telemetry for compatibility.

#### Test checklist

- [ ] Review-state/amendment retrieval remains correct after simulated normal-name rename.
- [ ] ID-first reads prefer ID joins while legacy corpus remains readable.
- [ ] Telemetry captures fallback usage for migration tracking.

#### Phase success criteria

- [ ] Hard-break class from stem mismatch in review/amendment flows is eliminated.
- [ ] Backward compatibility is preserved for existing data.

### Phase C (long term, optional): full normalization

Proceed only if operational signals justify it (frequent renames, higher contributor count, automation scale).

#### TODO checklist

- [ ] Backfill `marking_run_id` across historical artifacts/rows.
- [ ] Reduce or remove legacy fallback paths after coverage thresholds are met.
- [ ] Fully transition cleanup/prune/migration tools to ID-authoritative logic.
- [ ] Publish final deprecation/removal plan for stem-identity assumptions.

#### Test checklist

- [ ] Backfill and reconciler are idempotent at corpus scale.
- [ ] Drift detection stays near zero over sustained runs.
- [ ] Legacy fallback can be disabled with no regressions.

#### Phase success criteria

- [ ] IDs are authoritative across all core artifact families.
- [ ] Path naming is fully decoupled from runtime identity joins.

## Risks and mitigations

- **Risk:** Migration complexity across filesystem + DB mirrors.
  - **Mitigation:** phased rollout, dry-run reconciler, idempotent backfills.

- **Risk:** Temporary dual-mode logic increases code complexity.
  - **Mitigation:** explicit deprecation gates and telemetry-based removal criteria.

- **Risk:** Historical artifacts missing enough metadata for perfect backfill.
  - **Mitigation:** deterministic heuristics + manual review queue for unresolved cases.

## Success criteria

### Short-term success criteria

1. Normal-name renames are executed only via the guarded workflow.
2. Partial rename drift is detected automatically before merge/release.
3. Rename incidents no longer cause missing review/amendment state in normal operations.

### Medium-term success criteria

1. Review/amendment reads and writes resolve by IDs first.
2. Renaming a file normal name in registry does not break review/amendment retrieval.
3. Legacy corpus remains readable via controlled fallback.

### Long-term success criteria

1. All core joins for marking/review workflows resolve by IDs, not filename stems.
2. Path drift is detectable and repairable with first-class reconciliation tooling.
3. Cleanup/prune actions are safe against path-only drift.

## Recommended location

This proposal should live under:

- `ai_study_buddy/marking/docs/proposal/`

Rationale:

- primary breakage surface is in marking/review artifact wiring
- existing proposal lineage for artifact path/lookup contracts is already in this folder
- it still references `learning_db` and `pdf_file_manager` changes as dependencies
