# Marking Result v1.5 Feedback-Prune Migration Report (2026-04-28)

Migration path:

- `marking_result.v1.4` -> `marking_result.v1.5`
- field migration policy:
  - Case A: `feedback` non-empty + `human_note` empty/null -> copy to `human_note`
  - Case B: both present and different -> append into `human_note` with marker block
  - Case C: `feedback` empty/null -> prune `feedback`

Marker used for Case B append:

- `[Migrated feedback]`

Scope:

- `ai_study_buddy/context/marking_results/**/*.json`

Summary:

- Files migrated: `154`
- Question rows processed: `2655`
- Non-empty feedback rows: `149`
- Case A rows: `109`
- Case B rows: `40`
- Case C rows: `2506`

Post-migration checks:

- `schema_version = marking_result.v1.5` files: `154`
- Remaining `feedback` fields: `0`
