# AI Study Buddy Marking Architecture

Status: Minimal contract for current production use.

This document defines:

1. package architecture and boundaries for `ai_study_buddy/marking/`
2. the minimum viable context resolver contract
3. an implementation plan that grows only when real use cases emerge

This is a design contract for implementation work. `SPEC.md` remains the canonical package functional spec, and `README.md` remains the quick-start entry point.

## 1) Scope and Design Principles

The marking package is the canonical implementation layer for marking workflows.

### Responsibilities

- resolve deterministic marking context from registry-backed metadata
- enforce canonical artifact contract (`marking_result.v1`)
- write canonical JSON first, then render markdown as derived view
- provide stable programmatic APIs for workflows and agent skills

### Non-Responsibilities (for this package layer)

- direct registry table querying bypassing `PdfFileManager`
- ad hoc context resolution logic inside skill files
- treating markdown as canonical source data

### Architecture Rule

Business logic lives in `ai_study_buddy/marking/`; skills and runbooks orchestrate usage but should not duplicate core resolution logic.

## 2) Module Boundaries

Current package modules are grouped into three layers.

### A. Domain layer (`core/`)

- `models.py`: immutable dataclasses (`MarkingContext`, `QuestionSelection`, artifact models)
- `context_resolver.py`: deterministic context resolution orchestration
- `artifact_schema.py`: schema loading, validation, and score consistency checks
- `artifact_paths.py`: canonical path and basename derivation
- `artifact_lookup.py`: deterministic completion -> artifact lookup (student-scoped)
- `artifact_writer.py`: canonical JSON write path
- `path_privacy.py`: canonical path sanitization and runtime placeholder expansion
- `taxonomy.py`: diagnosis/error taxonomy normalization and helpers

### B. Workflow layer (`workflows/`)

- `migrate_learning_reports.py`: markdown -> canonical JSON migration
- `report_renderer.py`: canonical JSON -> markdown rendering
- `edit_human_notes.py`: safe human note updates with validation

### C. Public API layer

- `api.py`: re-exported stable import surface for consumers

## 3) Primary Use Case (MVP)

The current flagship use case is the `mark-goodnote-completion` skill flow:

1. User gives a natural-language request such as:
   - "Emma has completed unit X of book Y (in GoodNotes)"
2. Agent performs fuzzy search in GoodNotes leaf folders to find exactly one completion PDF.
3. Agent passes the discovered completion file path to:
   - `resolve_marking_context(attempt_file_id_or_path=<path>)`
4. Resolver returns full deterministic marking context:
   - completion file (registered `main`)
   - linked template file
   - template's book group
   - mapped answer file and answer page range
5. Marking workflow uses this context to grade and produce artifacts (JSON first, markdown derived).
6. Canonical artifact writer sanitizes path fields before persistence; renderer expands placeholders for runtime readability when configuration/registry data exists.
7. Optional preflight: lookup existing artifacts for the same completion using
   `find_marking_artifacts_for_attempt(...)` before deciding whether to re-run marking.

MVP variant (weighted assessment / embedded answers):

1. Agent still finds one unique completion file path from the GoodNotes request.
2. Caller passes:
   - `attempt_file_id_or_path=<path>`
   - `self_answer_pages=(begin_page, end_page)`
3. Resolver uses the template file itself as the answer source and uses the supplied page range.

Important boundary:

- Fuzzy discovery of the completion file is orchestration logic (skill/workflow layer).
- Deterministic registry-backed context assembly is marking core logic (`context_resolver.py`).

## 4) Context Resolver Contract

Primary function:

`resolve_marking_context(...) -> MarkingContext`

Resolver architecture summary (MVP):

1. Path-first deterministic resolution is the default.
2. Caller-owned orchestration resolves fuzzy user intent to one attempt file path.
3. Resolver-owned logic assembles one complete marking context from registry data.
4. Resolver supports two answer modes:
   - registry mapping mode
   - self-answer override mode for embedded-answer papers (`self_answer_pages`)
5. Context scope is full attempt file in MVP.

Normative resolver behavior (inputs, invariants, errors, and algorithm) is specified in `SPEC.md` under the context resolver section.

## 5) What We Explicitly Defer

The following are intentionally deferred until there is a concrete workflow need:

- index-aware resolver return contracts
- dedicated `resolve_marking_context_with_index(...)` API
- resolver-owned question-reference parsing and strict/non-strict resolution modes
- question-level scope selection in resolver contract

Reference context remains in `L4_QUESTION_INDEX_SCHEMA.md`, but it is not part of the MVP contract in this file.

## 6) Implementation Plan

Plan is incremental and use-case-driven.

### Phase 1 — Lock MVP contract (now)

1. Keep one core contract: path-first `resolve_marking_context`.
2. Keep skill/workflow responsibility: fuzzy discovery of unique GoodNotes completion path.
3. Keep resolver responsibility: deterministic context assembly with two answer modes:
   - registry mapping mode
   - `self_answer_pages` override mode for embedded-answer papers
4. Support first-touch onboarding path via optional auto-registration when completion file exists on disk but is not yet in registry.

Exit criteria:

- MVP flow is fully documented and unambiguous

### Phase 2 — Test hardening for current resolver

1. Add focused tests for `context_resolver.py` covering:
   - path-based attempt resolution by ID/path
   - GoodNotes/main/template constraints
   - auto-link template behavior
   - book group cardinality checks
   - answer mapping presence checks
2. Ensure error-message snapshots are actionable.

Exit criteria:

- deterministic resolver behavior protected by tests

### Phase 3 — Skill integration contract

1. In `mark-goodnote-completion` instructions, make path-first resolver call explicit.
2. Require clear failure handling when fuzzy search is not unique.
3. Document canonical input/output examples for the MVP flow.

Exit criteria:

- orchestration and core contracts are aligned across docs and skill usage

### Phase 4 — Add contract only when needed

When a new real workflow requires more behavior (for example question-index-aware resolution), extend contract additively:

1. write the use case first
2. define the minimal new API/type additions
3. add tests for only that new behavior
4. keep existing path-first flow stable

## 7) Open Decisions (MVP)

1. Should we support a dedicated helper that does fuzzy GoodNotes discovery before calling the resolver, or keep that entirely in skill orchestration?
2. Should student/book/unit hints remain secondary optional inputs, or be removed from the resolver in a future cleanup?
3. What is the minimum evidence we want in logs when path-based resolution fails?

## 8) Backward Compatibility Promise

Until a `v0.3.0` contract update is announced:

1. `resolve_marking_context(...)` remains stable and file-level.
2. Existing artifact schema (`marking_result.v1`) remains unchanged.
3. New resolver behavior is introduced only from concrete use cases and added additively.
