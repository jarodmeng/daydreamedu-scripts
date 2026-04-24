# Decisions — `student_review`

## D-001: Separate domain module from app surface

Date: 2026-04-23  
Decision: create `ai_study_buddy/student_review/` as domain logic, keep `review_workspace` as app surface.

Why:

- avoid monolithic route files
- allow reuse by future consumers (parent/teacher/planner/reporting surfaces)
- improve unit-testability of services and repository behavior

## D-002: Keep canonical marking artifacts read-only

Date: 2026-04-23  
Decision: never write to `marking_results/**` from this module.

Why:

- preserve grading artifact integrity
- isolate student reflection data from canonical marking facts

## D-003: Persist review notes as companion artifacts

Date: 2026-04-23  
Decision: store review-state under `context/student_review_states/**` keyed by marking artifact stem.

Why:

- ties comments to a specific feedback version
- avoids ambiguity when attempts are re-marked

## D-004: Latest-marking selection via existing lookup helper

Date: 2026-04-23  
Decision: use `find_marking_artifacts_for_attempt(...)` and select index `0` (latest).

Why:

- reuse canonical artifact matching logic
- avoid duplicate file-matching implementation

