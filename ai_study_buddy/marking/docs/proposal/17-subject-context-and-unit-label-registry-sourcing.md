# Proposal 17: Registry-sourced `subject_context` and path-aligned `unit_label`

## Status

**Superseded** by Proposal 18 and Proposal 19 (split by concern).

Depends on concepts from:

- Proposal 1 (`context_resolver` MVP) — `resolve_marking_context` / `MarkingContext`.
- Proposal 11 — marking context production contract and `artifact_writer` invariants.

## Why this proposal exists

Two production issues surfaced when running v3 marking against real GoodNotes completions:

1. **`_resolve_subject_context_from_runtime_context()` in `mark_student_work_multi_agent_v3.py`** cannot infer `singapore_primary_english` from typical paths/filenames (e.g. `c_EPO_…pdf` under `Singapore Primary English/…`), forcing orchestrators to patch or bypass the helper.

2. **`write_marking_artifact` context contract** can fail because **`context.unit_label`** (derived from `PdfFile.name` via `_infer_unit_label`) disagrees with **`derive_unit_label_from_attempt_name(unit_file_path)`**, which validates against the template’s **filesystem basename**.

Both problems share a root cause: **the marking pipeline mixes registry display fields (`name`) and path-derived normalization** for the same conceptual “unit”, and uses **filename/path heuristics** where the registry already exposes **definitive subject** (`pdf_files.subject`).

## Problem statement

### A) Subject context resolution

Today, v3 finalization builds artifacts using `_resolve_subject_context_from_runtime_context(context)` (`mark_student_work_multi_agent_v3.py`), which:

1. Optionally reads a nonexistent `subject_context` on the generic context object (`MarkingContext` has **no** such field).
2. Otherwise scans **`attempt_file_path` / `template_file_path` / `answer_file_path`** for substring patterns such as `.english.` in the **basename** or `/{token}/` in the path.

That fails for layouts where:

- The PDF basename does **not** contain dotted tokens such as `.english.` (many real completions do not).

- Folder names encode subject in human phrases (e.g. `Singapore Primary English`) rather than slash-delimited **`/english/`** segments identical to `_SUBJECT_CONTEXT_BY_TOKEN` keys.

Yet **`MarkingContext` already carries `attempt_file_id` (and template linkage)**. The **`PdfFileManager`** registry stores **`PdfFile.subject`** (`english`, `math`, `science`, `chinese`) per file after scan/inference. That is the authoritative coarse subject for in-scope workflows.

Separately, **`ai_study_buddy/marking/file_question_info/api.py`** already implements the intended mapping **`PdfFile.subject` → artifact `subject_context`** in `_subject_scope_from_pdf_file` → `singapore_primary_english`, etc. Finalization logic should not reinvent this with brittle path rules.

### B) `unit_label` vs `unit_file_path`

`artifact_writer._assert_context_contract` requires:

- `context.unit_label` **equal** to `derive_unit_label_from_attempt_name(context.unit_file_path)` when both are present.

`_infer_unit_label` in `core/context_resolver.py` uses **`derive_unit_label_from_attempt_name(file.name)`** where `file.name` is the **`pdf_files.name`** column.

If **`name`** and the **basename of `path`** ever diverge (abbreviated registration, rename drift, tooling that updated one column only), **normalization differs**:

- Example class of failure: **`name`** strips to **`Comprehension_Open-ended_03`** while **`path`** basename strips to **`EPO_Comprehension_Open-ended_03`** — same logical unit file, **`write_marking_artifact` rejects** the artifact.

The writer’s invariant is inherently **path-based**; **`unit_label` should be derived from the same source of truth**.

## Goals

1. **Single deterministic source** for **`subject_context`** on marking artifacts for primary-scope flows: **`PdfFile.subject` → `singapore_primary_*`** (same semantics as `file_question_info` today).

2. **`unit_label`** always consistent with **`unit_file_path`** per **`derive_unit_label_from_attempt_name`**, eliminating **name-vs-path drift**.

3. **Remove or downgrade** filename/path substring heuristics in v3 to **fallback only** (or delete once registry coverage is trusted).

4. **No schema version bump** for `marking_result` — only enrichment / consistency of **`MarkingArtifact.context`** fields that already exist.

## Non-goals

- Introducing new `subject_context` granularity (e.g. secondary vs PSLE distinctions) beyond what **`PdfFile.subject`** + existing `singapore_primary_*` strings already imply.

- Backfilling or mutating **`pdf_files.name`** wholesale; prefer correcting **resolver derivation** unless a specific row needs a one-off repair.

- Replacing **`file_question_info`** layouts or DB-backed study-buddy stores (proposal 14) — orthogonal.

## Proposed design

### 1) Populate `subject_context` during `resolve_marking_context`

- Add **`subject_context: str | None`** to **`MarkingContext`** (`core/models.py`), or **`subject_context: str`** once all resolver branches set it.

- In **`resolve_marking_context`** (`core/context_resolver.py`), after **`template_file`** (and **`attempt_file`**) resolution:

  - Prefer **`template_file.subject`** when the template exists (unit / key anchor).

  - Else use **`attempt_file.subject`**.

  - Map registry subject → **`singapore_primary_*`** using **one shared helper** reused by **`file_question_info`** (either **export** `_subject_scope_from_pdf_file` under a stable public name such as **`subject_scope_from_pdf_file`**, or **extract** mapping to **`marking/core/subject_scope.py`** and import from both **`file_question_info/api.py`** and the resolver).

- If **`subject` is null** or unsupported: define behavior explicitly — **fail resolution** with a clear error **or** keep a **narrow** fallback (path heuristic / explicit caller override document in proposal 11 style). Recommendation: **fail fast** during marking when **`subject`** is missing for student GoodNotes-scope attempts, unless a legacy flag permits heuristic mode.

### 2) Teach v3 finalize to prefer `MarkingContext.subject_context`

- Update **`_resolve_subject_context_from_runtime_context`** (`mark_student_work_multi_agent_v3.py`) to:

  1. Return **`marking_context.subject_context`** when set.

  2. Optionally retain existing path heuristics behind a deprecation comment **only if** backwards compatibility requires them for tests or unmigrated callers.

- **Remove** duplication of **`_SUBJECT_CONTEXT_BY_TOKEN`** mapping tables where the shared helper supersedes them.

### 3) Align `unit_label` with `unit_file_path`

- Change **`_infer_unit_label`** to derive from **`Path(pdf_file.path).name`** (equivalently **`derive_unit_label_from_attempt_name(pdf_file.path)`**), matching **`artifact_writer`**.

- Add a unit test asserting **`unit_label == derive_unit_label_from_attempt_name(unit_file_path)`** for representative template rows.

### 4) Documentation and changelog

- **`marking/CHANGELOG.md`**: summarize behavior change under a dated entry.

- **Cross-link** proposal 17 from **`ARCHITECTURE.md`** or **`README.md`** marking section if there is an “context resolution” pointer (minimal edit).

## Implementation checklist

- [ ] Extract or export **subject-scope mapping** (`singapore_primary_*`) to a single function (shared by resolver + file_question_info).

- [ ] Add **`subject_context`** to **`MarkingContext`** and populate it in **`resolve_marking_context`**.

- [ ] Extend **`Artifact` / `MarkingArtifactContext.from_marking_context`** to pass **`subject_context`** through unchanged (today `from_marking_context` accepts **`subject_context: str`** explicitly — resolver may compute once and thread into **`from_marking_context(...)`** alongside **`MarkingContext`**).

- [ ] Update **`_resolve_subject_context_from_runtime_context`** to read resolved context first.

- [ ] Fix **`_infer_unit_label`** path alignment; add regression test for **`write_marking_artifact`** contract path.

- [ ] Refresh tests: **`resolve_marking_context`**, **`file_question_info`**, v3 workflow helpers as needed.

## Risks / migration notes

- **Existing persisted JSON**: older artifacts embedded whatever `subject_context` was inferred; historical rows are unchanged.

- **`PdfFile.subject` correctness**: Garbage-in still breaks output; mitigation is registry hygiene scans (existing pdf_file_manager tooling), not this proposal.

- **`MarkingContext` field addition**: Touches serialization tests and `from_dict` paths if **`MarkingContext`** equality / fixtures assume exact field sets — update constructors.

## Success criteria

1. Winston-style GoodNotes English completions finalize **without path-based subject patching** once **`subject='english'`** is set on the linked template/attempt rows.

2. **`unit_label`** contract failures (**expected X, got Y**) **do not occur** when **`name`** drifts but **`path`** is canonical **after** aligning `_infer_unit_label` with path normalization.

---

*Authoring note:* When this proposal is implemented, add a short “Implemented as of …” stanza under **Status** and link to the merge / commit range if helpful.
