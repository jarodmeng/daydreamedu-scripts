# Artifact lookup by completion (marking JSON + learning report)

Status: Proposal (not implemented)

Audience: Maintainers of `ai_study_buddy/marking`, `pdf_file_manager`, and the `mark-goodnote-completion` skill

## 1) Goal

Add a **small, deterministic helper** that answers:

> For this completion PDF (identified by **registry `file_id`** and/or **absolute filesystem path**), do canonical marking artifacts exist, and where are they?

Artifacts (per `SPEC.md` and `.cursor/skills/mark-goodnote-completion/SKILL.md`):

| Tier | Path pattern |
| --- | --- |
| Canonical JSON | `context/marking_results/<student_slug>/<subject_context>/<attempt_basename>.json` |
| Derived report | `context/learning_reports/<student_slug>/<subject_context>/<attempt_basename> - Marking Report.md` |

`<attempt_basename>` is **not** the completion `file_id`; it is derived from the attempt filename stem (prefix-stripped) plus `__YYYYMMDD_HHMMSS` from artifact `created_at` (`artifact_paths.build_attempt_basename`). Therefore **lookup cannot be a single formula from `file_id` alone** without scanning JSON under `marking_results/` (or maintaining a separate index, which is out of scope for this proposal).

## 2) Scope

### In scope

- One public API (name TBD, e.g. `find_marking_artifacts_for_attempt`) exported from `ai_study_buddy/marking/api.py`.
- Implementation in `ai_study_buddy/marking/core/artifact_lookup.py` (or equivalent `core/` module name).
- Deterministic matching rules (see §4).
- Unit tests under `ai_study_buddy/marking/tests/` using temporary `context_root` trees (no dependency on a real GoodNotes/DaydreamEdu layout).
- Short entries in `README.md` / `TESTING.md` when the helper lands.

### Out of scope (for v1)

- SQLite or other **persistent index** of completion → artifact (could be a later optimization).
- Fuzzy discovery of “which PDF did the user mean?” (orchestration stays in skills/scripts).
- Treating markdown as source of truth (JSON remains canonical; report existence is **paired** to a matched JSON stem).
- Changing `marking_result.v1` schema to add redundant index fields.

## 3) Proposed public shape (sketch)

Exact names are negotiable; shape should stay small.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


@dataclass(frozen=True)
class MarkingArtifactRef:
    """One marking run: canonical JSON plus expected derived report path."""

    marking_result_json: Path
    learning_report_md: Path
    # Optional: parsed created_at / student_slug / subject_context if useful to callers


def find_marking_artifacts_for_attempt(
    attempt_file_id_or_path: str | Path,
    *,
    match_condition: Literal["json_only", "json_and_report"] = "json_only",
    manager: PdfFileManager | None = None,
    context_root: str | Path = "ai_study_buddy/context",
) -> list[MarkingArtifactRef]:
    """Return matching marking artifacts for this completion under the requested condition.

    Results are sorted by created_at (descending; newest first), then by JSON path
    (ascending) as a deterministic tie-breaker. Empty list if none match.
    """
    ...
```

**Input semantics** (align with `resolve_marking_context`):

- Input classification must follow the same heuristic used by `resolve_marking_context` (`core/context_resolver.py::_resolve_attempt_file_by_id_or_path`): treat as path-like when the candidate contains `/` or `\\` or ends with `.pdf` (case-insensitive); otherwise treat as registry id.
- If the argument is a **registry id**, resolve the completion file via `PdfFileManager.get_file(...)` when `manager` is provided; if `manager` is `None`, fail fast with a clear error that id-based lookup requires a manager.
- If the argument is a **path**, normalize with `Path(...).expanduser().resolve(strict=False)` for comparison.

**Output**:

- **List**, because the same completion PDF can be marked multiple times (different `created_at` → different `__timestamp` suffixes).
- Each item includes **both** expected paths.
- `match_condition` controls inclusion:
  - `json_only` (default): include a row when canonical JSON matches the completion; report may be present or missing.
  - `json_and_report`: include a row only when canonical JSON matches and `learning_report_md.exists()` is true.

## 4) Matching rules (normative for implementation)

Precedence: **file id match** is authoritative when both sides have a non-empty `context.attempt_file_id` in the JSON and a known id for the completion.

1. **Primary — `attempt_file_id`**

   - Load each candidate `marking_results/**/*.json` (see §5 for scan strategy).
   - Parse minimal payload: `context.attempt_file_id`, `context.attempt_file_path`, top-level `created_at` if needed for sorting.
   - If `context.attempt_file_id` equals the completion’s registry id → **match**.

2. **Secondary — resolved attempt path**

   - Use when JSON has no `attempt_file_id` (legacy / migration gaps) or when the caller is path-only.
   - Expand placeholders in `context.attempt_file_path` with existing **`resolve_marking_artifact_paths`** (`path_privacy.py`) so `GOODNOTES_ROOT` / `DAYDREAMEDU_ROOT` / `<student_email>` align with the caller’s environment.
   - Compare to the completion’s absolute path with a **normalization policy** documented in code:
     - use `Path(...).expanduser().resolve(strict=False)` on both sides
     - compare as normalized POSIX strings
     - do not require the file to exist at lookup time (deleted/moved completion files can still match legacy artifacts by path)
   - If JSON has a non-empty `context.attempt_file_id` that does not match the caller's known completion id, treat as **non-match** even if paths happen to match.

3. **Non-match**

   - Do not match on filename stem alone without id/path agreement (too many collisions across students/subjects).

4. **Condition filter (post-match)**

   - First determine JSON matches via rules 1-3.
   - Then apply `match_condition`:
     - `json_only`: keep all JSON matches.
     - `json_and_report`: keep only JSON matches where the paired report file exists.

## 5) Scan strategy (performance note)

v1 must use a **student-scoped walk** rooted at:

- `context_root / "marking_results" / <student_slug>`

The helper must derive `<student_slug>` from the completion file's student identity (via `PdfFileManager` metadata when available, using `artifact_paths.slugify_student` rules). Do not full-walk all students for normal lookup.

If the caller provides a path-only input and no manager context is available to derive student identity, fail fast with a clear error instead of scanning globally.

Error handling contract for scan:

- If a JSON file is malformed, unreadable, missing required fields, or has an unexpected shape, the helper must skip it and continue scanning.
- The helper should not fail the whole lookup because one artifact file is bad.
- Optional: provide debug-level diagnostics (`logger.debug`) with path + reason for skipped files.

This keeps lookup deterministic and bounded without introducing a persistent index.

## 6) Dependencies and boundaries

- **`PdfFileManager`**: optional but recommended for `file_id` input and for consistent student/path resolution.
- **No direct SQLite access** in the helper (project rule: use manager APIs).
- **Package boundary**: lives under `ai_study_buddy/marking` per `ARCHITECTURE.md`; skills import the public API only.

## 7) Testing plan

- **Unit tests** with `tmp_path`:
  - Two JSON files under different `subject_context` folders: one matches `attempt_file_id`, one does not.
  - Student-scope guard: artifacts under a different `marking_results/<other_student_slug>/` subtree are never scanned/matched.
  - Path-only match when `attempt_file_id` is absent but expanded `attempt_file_path` matches.
  - ID precedence guard: when JSON has a non-empty mismatching `attempt_file_id`, it must not match even if normalized `attempt_file_path` matches.
  - Multiple timestamps for the same completion → list length > 1, stable ordering asserted.
  - Sorting contract: `created_at` descending, JSON path ascending as tie-breaker.
  - Corrupt JSON / missing `context` files are skipped without raising.
  - Learning report path equals `build_learning_report_path` / naming rule relative to the same basename as the JSON file.
  - `match_condition="json_only"` returns matches even when report file is missing.
  - `match_condition="json_and_report"` excludes matches whose report file is missing.
- **No network**, no real `GOODNOTES_ROOT` unless tests inject fake roots via monkeypatch where `resolve_marking_artifact_paths` is used.

## 8) Acceptance criteria

1. For a registered completion, `find_marking_artifacts_for_attempt(file_id, manager=...)` returns the same logical artifacts a human would find by searching `marking_results/**/*.json` for that `attempt_file_id`.
2. Path-based input matches JSON whose expanded `attempt_file_path` equals the resolved completion path.
3. Lookup only scans within the completion's student slug subtree under `marking_results/<student_slug>/` (no cross-student scan).
4. API supports `match_condition` with default `json_only`; `json_and_report` requires report existence.
5. Public API is documented in `README.md` and exported from `api.py`.
6. Full test suite passes; new tests cover edge cases in §7.

## 9) Implementation plan (phase-by-phase)

Ship in small phases with tests passing at each phase.

### Phase 0 — Baseline and contract lock

Goal: lock behavior before code changes.

TODO checklist:

- [ ] Confirm no existing public API in `api.py` already overlaps this helper name/signature.
- [ ] Confirm final function name and argument order (`attempt_file_id_or_path`, `match_condition`, `manager`, `context_root`).
- [ ] Freeze deterministic sort contract (`created_at desc`, `json path asc` tie-breaker).
- [ ] Freeze student-scoped scan requirement (`marking_results/<student_slug>/` only).
- [ ] Freeze condition semantics (`json_only` default, `json_and_report` optional).

Exit criteria:

- Team agrees on final public contract and matching policy in this proposal.

### Phase 1 — Public API surface and types

Goal: create stable API entry points and return model.

TODO checklist:

- [ ] Add `MarkingArtifactRef` dataclass (or equivalent frozen model) in `marking/core/`.
- [ ] Implement `find_marking_artifacts_for_attempt(...)` in `marking/core/artifact_lookup.py`.
- [ ] Re-export helper from `marking/api.py` and include in `__all__`.
- [ ] Add concise docstring with condition semantics and sort behavior.

Exit criteria:

- Helper is callable from `ai_study_buddy.marking` public surface.

### Phase 2 — Student-scoped candidate discovery

Goal: build bounded candidate list safely.

TODO checklist:

- [ ] Resolve completion input (id or path) using `PdfFileManager`-consistent heuristics.
- [ ] Derive completion student identity and compute `student_slug` via `artifact_paths.slugify_student`.
- [ ] Walk only `context_root/marking_results/<student_slug>/**/*.json`.
- [ ] Fail fast when student identity cannot be derived without global scan (path-only + missing manager context).
- [ ] Add robust file iteration that skips unreadable files.

Exit criteria:

- Candidate set is always limited to one student subtree.

### Phase 3 — Core JSON matching engine

Goal: implement authoritative matching rules.

TODO checklist:

- [ ] Parse minimal fields: `context.attempt_file_id`, `context.attempt_file_path`, `created_at`.
- [ ] Apply primary id match when completion id is known.
- [ ] Apply secondary path match only per proposal constraints.
- [ ] Enforce mismatch guard: non-empty mismatching `attempt_file_id` blocks path fallback.
- [ ] Normalize paths with `expanduser().resolve(strict=False)` + normalized POSIX compare.
- [ ] Skip malformed JSON or missing-shape payloads; continue scan.

Exit criteria:

- JSON match behavior exactly follows section 4 rules.

### Phase 4 — Condition filter and result assembly

Goal: apply caller-selected condition and return deterministic output.

TODO checklist:

- [ ] Build paired `marking_result_json` + expected `learning_report_md` for each JSON match.
- [ ] Implement `match_condition="json_only"` (include all JSON matches).
- [ ] Implement `match_condition="json_and_report"` (require existing report file).
- [ ] Sort results by `created_at desc`, then JSON path asc.
- [ ] Validate unknown condition values fail clearly (defensive guard).

Exit criteria:

- Returned list is deterministic and condition-aware.

### Phase 5 — Test implementation

Goal: lock behavior with focused unit coverage.

TODO checklist:

- [ ] Add tests for id match and id non-match.
- [ ] Add tests for path fallback when id is absent.
- [ ] Add test for mismatching non-empty `attempt_file_id` blocking path fallback.
- [ ] Add cross-student isolation test (`other_student_slug` artifacts ignored).
- [ ] Add sorting tests (`created_at` and tie-breaker path ordering).
- [ ] Add malformed JSON / missing `context` skip tests.
- [ ] Add `json_only` vs `json_and_report` condition tests.
- [ ] Add failure-mode tests for missing manager/student derivation paths.

Exit criteria:

- `python3 -m pytest ai_study_buddy/marking/tests -q` passes with new helper coverage.

### Phase 6 — Documentation updates (required)

Goal: keep docs aligned with shipped behavior.

TODO checklist:

- [ ] Update `ai_study_buddy/marking/README.md`:
  - [ ] add helper overview and use cases
  - [ ] add one `json_only` example (default)
  - [ ] add one `json_and_report` example
- [ ] Update `ai_study_buddy/marking/SPEC.md`:
  - [ ] add normative helper contract and condition definitions
  - [ ] add student-scoped scan rule and error policy
- [ ] Update `ai_study_buddy/marking/TESTING.md`:
  - [ ] include new test module/commands and regression focus areas for artifact lookup
- [ ] Keep `ai_study_buddy/marking/ARCHITECTURE.md` high-level, with pointer to `SPEC.md` for normative matching details.
- [ ] Keep this proposal in sync with final code behavior (remove ambiguity that no longer applies).

Exit criteria:

- A maintainer can use helper correctly from docs without source-diving.

### Phase 7 — Release housekeeping (small version bump)

Goal: ship as a small `marking/` package release.

TODO checklist:

- [ ] Add new top entry in `ai_study_buddy/marking/CHANGELOG.md` (next version, e.g. `0.2.0`) with:
  - [ ] `Added`: new artifact lookup helper API
  - [ ] `Changed`: any related docs/tests updates
- [ ] Bump `Current version` in `ai_study_buddy/marking/README.md` to the same version.
- [ ] Verify changelog + README versions match exactly.
- [ ] Run package tests and include command list in implementation summary.

Exit criteria:

- Changelog, README version, and tested behavior are consistent for release.

## 10) Follow-ups (optional)

- If full-directory scans become slow, add a **lazy cache** (process-local) or a **generated manifest** under `context/` (explicitly out of v1).
- Wire the helper into the `mark-goodnote-completion` skill “preflight” section (check whether marking already exists before re-running).
