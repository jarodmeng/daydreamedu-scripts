# Proposal 18: Registry-sourced `subject_context` for marking artifacts

## Status

**Implemented**.

Implemented on May 10, 2026 (Phases 1-4 completed).

Validation snapshots (May 10, 2026):

- `pytest -q ai_study_buddy/marking/tests/test_context_resolver.py ai_study_buddy/marking/tests/test_file_question_info.py ai_study_buddy/marking/tests/test_v3_workflow_helpers.py -k "not cleanup_stale_partials_for_v3_run_moves_only_stale_nonfinalized"`
- Result: `75 passed, 1 deselected` (deselected test is sandbox/Trash-path dependent).
- `pytest -q ai_study_buddy/marking/tests/test_context_resolver.py ai_study_buddy/marking/tests/test_file_question_info.py ai_study_buddy/marking/tests/test_v3_workflow_helpers.py`
- Result: `77 passed`.
- Registry audit command: `PYTHONPATH=. python3 ai_study_buddy/marking/workflows/audit_registry_subjects.py`
- Registry audit result: `total_files=5464`, `missing_subject_count=0`, `invalid_subject_count=0`.
- Note: audit JSON artifact is not retained in-repo.

Supersedes the subject-context portion of Proposal 17.

Depends on concepts from:

- Proposal 1 (`context_resolver` MVP)
- Proposal 11 (marking context production contract)
- Proposal 16 (v3 workflow)

## Why this proposal exists

Production runs have shown that v3 artifact finalization can fail to determine `subject_context` when runtime filenames/paths do not contain token patterns expected by the workflow helper.

Current behavior in `mark_student_work_multi_agent_v3.py`:

1. `_resolve_subject_context_from_runtime_context(context)` first checks `context.subject_context`.
2. If missing, it infers from path substrings like `".english."` or `"/english/"`.
3. If no match, it raises `V3WorkflowError`.

This is brittle for real layouts such as:

- basenames like `c_EPO_...pdf` that omit dotted subject tokens
- directory names like `Singapore Primary English` that do not include slash-delimited `/english/`

Meanwhile, the registry already stores definitive subject on `PdfFile.subject` and the file-question-info layer already maps those subjects to marking scopes (`singapore_primary_english`, etc.).

## Problem statement

The marking pipeline currently has two inconsistent sources for subject scope:

- **Authoritative source:** `PdfFile.subject` in registry rows linked to context
- **Fallback heuristic source:** path/filename string parsing in v3 finalization

Because finalization still depends on heuristics, runs can fail despite complete registry linkage.

## Goals

1. Make registry subject (`PdfFile.subject`) the primary source for artifact `subject_context`.
2. Move subject mapping to one shared helper used by both resolver and file_question_info code.
3. Remove path heuristics from v3 subject-context resolution entirely.
4. Preserve existing artifact schema (`marking_result` version unchanged).

## Non-goals

- Introducing finer-grained subject scopes beyond current `singapore_primary_*` set.
- Backfilling all historical artifacts.
- Redesigning file_question_info storage.

## Proposed design

### 1) Add required `subject_context` to `MarkingContext`

Add field to `MarkingContext` (`core/models.py`):

- `subject_context: str`

Resolver ownership:

- Compute once inside `resolve_marking_context`.
- Prefer template file subject when available.
- Else use attempt file subject.
- If neither template nor attempt subject can be resolved, fail with hard error.

### 2) Extract shared subject mapping helper

Create `marking/core/subject_scope.py` with stable public function:

- `subject_context_from_pdf_subject(subject: str | None) -> str`

Mapping table:

- `english -> singapore_primary_english`
- `math -> singapore_primary_math`
- `science -> singapore_primary_science`
- `chinese -> singapore_primary_chinese`

Both call sites import this helper:

- `marking/core/context_resolver.py`
- `marking/file_question_info/api.py` (replacing private duplicated mapper)

### 3) Use resolved context in v3 finalization and remove heuristics

Update `_resolve_subject_context_from_runtime_context` behavior:

1. Return `context.subject_context` when present.
2. Do not attempt path/filename heuristics.
3. If absent/unresolved, raise with actionable hard error including file ids/paths.

### 4) Strict-mode rollout and debug observability

Use strict behavior by default:

- fail when registry subject is missing or unsupported
- no compatibility heuristics fallback path

Write subject-context resolution diagnostics to JSON debug artifact for failed runs.

## Implementation plan

### Phase 1: Shared subject-scope foundation

#### TODO checklist

- [x] Create `ai_study_buddy/marking/core/subject_scope.py`.
- [x] Add public helper `subject_context_from_pdf_subject(subject: str | None) -> str`.
- [x] Move existing mapping table to this helper and centralize unsupported-subject error behavior.
- [x] Update `ai_study_buddy/marking/file_question_info/api.py` to use the shared helper instead of local private mapping.

#### Test checklist

- [x] Add/adjust unit tests that verify mapping of `english|math|science|chinese` to expected `singapore_primary_*`.
- [x] Add test for unsupported or missing subject value and assert deterministic error.
- [x] Run existing `file_question_info` tests to confirm no behavior regression.

#### Phase success criteria

- [x] Exactly one mapping implementation exists in codebase for `PdfFile.subject -> subject_context`.
- [x] `file_question_info` tests pass with no subject-mapping regressions.

### Phase 2: Resolve required `subject_context` in `MarkingContext`

#### TODO checklist

- [x] Add required `subject_context: str` to `MarkingContext` in `core/models.py`.
- [x] Populate `subject_context` in `resolve_marking_context`:
  - [x] prefer template file subject
  - [x] fallback to attempt file subject
- [x] Ensure resolver hard-fails when registry subject is missing/invalid after template->attempt lookup.
- [x] Update context-related fixture builders/constructors in tests.

#### Test checklist

- [x] Add resolver unit test: template subject present and selected.
- [x] Add resolver unit test: template subject missing, attempt subject used.
- [x] Add resolver unit test: both missing/invalid subject raises hard error.
- [x] Run resolver and model serialization tests affected by dataclass field addition.

#### Phase success criteria

- [x] Resolver never returns a `MarkingContext` without `subject_context`.
- [x] No resolver tests fail due to `MarkingContext` field evolution.

### Phase 3: v3 finalization strict behavior and debug artifacts

#### TODO checklist

- [x] Update `_resolve_subject_context_from_runtime_context` in `mark_student_work_multi_agent_v3.py`:
  - [x] return `context.subject_context` first
  - [x] remove path heuristic fallback logic entirely
  - [x] emit actionable hard error when unresolved
- [x] Add JSON debug artifact fields for subject-resolution failures (inputs, attempted sources, failure reason).

#### Test checklist

- [x] Add v3 helper test: context with `subject_context` finalizes without path token inference.
- [x] Add v3 helper test: context without `subject_context` raises hard error (no heuristic fallback).
- [x] Add v3 helper test: unresolved case emits clear error and writes expected JSON debug artifact diagnostics.
- [x] Run `ai_study_buddy/marking/tests/test_v3_workflow_helpers.py`.

#### Phase success criteria

- [x] v3 finalization succeeds for path-token-poor files when registry subject is present.
- [x] v3 finalization fails deterministically when subject is missing, with inspectable JSON debug diagnostics.

### Phase 4: Registry readiness audit and release hardening

#### TODO checklist

- [x] Update `ai_study_buddy/marking/CHANGELOG.md` with behavior change summary.
- [x] Add architecture/proposal cross-reference notes for new source-of-truth rule.
- [x] Add a one-time registry audit script/report to count files with missing/invalid `PdfFile.subject`.
- [x] Share audit output and remediation plan before rollout in environments with legacy rows.

#### Test checklist

- [x] Run focused marking test suite covering resolver + v3 finalization + file_question_info.
- [x] Perform one end-to-end local dry run on a known Winston-style English completion.
- [x] Execute registry audit and confirm counts are known and tracked.

#### Phase success criteria

- [x] Documentation reflects registry-first subject-context behavior.
- [x] Team has explicit visibility on missing/invalid subject rows prior to rollout.

## Risks and mitigations

- **Risk:** registry rows with null/invalid `subject` still exist and now hard-fail.
  - **Mitigation:** run one-time registry audit and remediate rows before broad rollout.

- **Risk:** inconsistent mapping behavior between modules during migration.
  - **Mitigation:** single shared mapper and removal of local mapping tables.

## Success criteria

1. [x] v3 finalization no longer depends on path tokens when registry subject is present.
2. [x] Winston-style English completions finalize correctly with `PdfFile.subject='english'` even if paths lack `/english/` or `.english.`.
3. [x] Missing/unsupported subject now fails fast with actionable error and JSON debug diagnostics.
