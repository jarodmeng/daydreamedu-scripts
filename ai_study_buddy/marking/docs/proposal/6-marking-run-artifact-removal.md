# Marking run artifact removal (JSON + report + asset bundle)

Status: Implemented (`v0.2.11`)

Audience: Maintainers of `ai_study_buddy/marking`, skill authors (`mark-goodnote-completion`, `diagnose-student-school-work`), and operators who need safe cleanup of bad/duplicate runs.

## 1) Goal

Add a first-class helper that removes **all filesystem artifacts for one marking run** in one operation:

- canonical JSON under `context/marking_results/...`
- derived learning report under `context/learning_reports/...`
- marking asset bundle under `context/marking_assets/...` (when present)

Historical gap (now closed): we could find artifacts, but we did not have one package-owned cleanup function with guardrails and dry-run behavior.

## 2) Why now

Current pain points:

1. Cleanup is manual and easy to do partially (delete JSON but forget report/bundle).
2. Operators have to re-derive path conventions from memory/scripts.
3. No standard dry-run summary before deletion.
4. No single place to enforce path-safety and scope restrictions.

Consequence: stale artifacts and inconsistent run state make re-marking and debugging harder.

## 3) Scope

In scope:

- one new package API for run-level artifact deletion
- one optional workflow/CLI entrypoint for operator use
- deterministic dry-run plan output
- strict path-safety checks (no escapes outside context root)
- unit tests for happy path + safety edges

Out of scope (v1):

- soft-delete/archive/undo logs
- bulk deletion by date/student/subject (future extension)
- registry-level deletion of source PDFs (handled by `pdf_file_manager` separately)

## 4) Proposed API

Add to `ai_study_buddy/marking/core/artifact_cleanup.py` and export via `api.py`.

```python
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

RemovalMode = Literal["strict", "best_effort"]


@dataclass(frozen=True)
class MarkingRunRemovalPlan:
    marking_result_json: Path
    learning_report_md: Path
    marking_asset_bundle: Path | None
    existing_paths: tuple[Path, ...]
    missing_paths: tuple[Path, ...]


@dataclass(frozen=True)
class MarkingRunRemovalResult:
    requested: MarkingRunRemovalPlan
    deleted_paths: tuple[Path, ...]
    skipped_missing_paths: tuple[Path, ...]


def remove_marking_run_artifacts(
    marking_result_json: str | Path,
    *,
    context_root: str | Path = "ai_study_buddy/context",
    dry_run: bool = False,
    mode: RemovalMode = "strict",
) -> MarkingRunRemovalResult:
    """Remove one run's JSON/report/bundle artifacts as one operation.

    `marking_result_json` may be absolute, or relative to `context_root`.
    `strict`: fail if any expected artifact is missing, or any target resolves outside context root.
    `best_effort`: skip missing targets, still fail on unsafe paths.
    """
```

### Input contract

- Caller identifies the run by **canonical JSON path**.
- v1 requires this path because it is the most precise run identity and avoids ambiguous multi-attempt matching.
- Path is normalized with `resolve(strict=False)` and then validated to stay under `context_root/marking_results`.

### Derived targets

From the canonical JSON payload and path:

1. Learning report path: same stem + ` - Marking Report.md`, mapped from `marking_results` subtree to `learning_reports` subtree.
2. Bundle path: `context.marking_asset` if non-empty, resolved relative to `context_root` and required to remain under `context_root/marking_assets`.

## 5) Deletion behavior

### Ordering (recommended)

1. delete learning report
2. delete marking asset bundle directory recursively (when `context.marking_asset` is set)
3. delete canonical JSON last

Reason: if the operation is interrupted, preserving JSON longest keeps a recoverable pointer to other paths.

### Dry run

`dry_run=True` returns the full plan and existence status, without deleting.

### Mode semantics

- `strict`:
  - error if canonical JSON, learning report, or expected bundle is missing
  - error if any target path is unsafe or invalid
  - operation is all-or-nothing for presence checks
- `best_effort`:
  - same safety checks as strict (never relaxed)
  - missing paths are skipped

Safety rule is invariant: **never delete anything outside context root or outside the expected tier roots.**

## 6) Safety invariants

1. Canonical JSON target must be under `context_root/marking_results/`.
2. Report target must be under `context_root/learning_reports/`.
3. Bundle target must be under `context_root/marking_assets/`.
4. `context.marking_asset` absolute paths are rejected.
5. Any normalized path containing escape semantics (`..` after resolve) is rejected.
6. Bundle deletion must guard against symlink traversal outside bundle root.

## 7) Optional workflow/CLI

Add a thin workflow wrapper:

`python3 -m ai_study_buddy.marking.workflows.remove_run_artifacts <artifact_json> [--dry-run] [--best-effort]`

Output should include:

- canonical run id (json path)
- each target path with status: `exists`, `missing`, `deleted`, `skipped`
- final summary counts

This keeps operator workflows scriptable and consistent with package behavior.

## 8) Testing plan

Add tests in `ai_study_buddy/marking/tests/test_artifact_cleanup.py`:

1. `dry_run` returns correct plan for existing JSON/report/bundle.
2. `strict` delete removes all three artifacts.
3. missing report/bundle fails strict mode with no deletion.
4. missing JSON errors in strict mode.
5. `best_effort` tolerates missing report/bundle but still enforces safety.
6. malformed/unsafe `context.marking_asset` (absolute or escape) raises and deletes nothing.
7. bundle with nested files is removed recursively.
8. report path mapping uses artifact stem parity with JSON.

## 9) Acceptance criteria

1. One API call removes a run’s JSON, report, and bundle safely.
2. Dry-run clearly shows what would be deleted before apply.
3. Safety checks prevent deletion outside `context_root` tier folders.
4. Behavior is deterministic and covered by unit tests.
5. Public API is exported in `ai_study_buddy/marking/api.py` and documented in `README.md`.

## 10) Rollout plan

Phase 1:

- implement core API + tests

Phase 2:

- add workflow CLI wrapper + docs

Phase 3:

- adopt in marking-related skills/scripts for bad-run cleanup and rerun flows

## 11) Resolved decisions

1. `reason` logging: **No for v1**.
2. Strict mode missing-artifact policy: **Any missing artifact is an error**.
3. Delete by completion id/path: **Out of scope for v1**.

## 12) Recommendation

Ship v1 with **JSON-path input only** and **dry-run default in operator scripts**.

This keeps the contract simple, minimizes accidental multi-run deletes, and finally gives us a clean, reusable facility for “remove and rerun” workflows.
