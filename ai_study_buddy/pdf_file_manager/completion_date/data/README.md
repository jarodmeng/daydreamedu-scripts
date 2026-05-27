# `school_term_calendar.json`

MOE-aligned Singapore primary school term windows used by **`filename_term`** completion-date inference ([proposal 17 §5.2](../../docs/proposals/17-completion-date.md)).

## Schema

- **`schema_version`:** `school-term-calendar-v1` (bump only when shape changes).
- **`years.<calendar_year>.terms.<1–4>`:** each term has `start` and `end` (`YYYY-MM-DD`).
- **`filename_term` mapping:** approximate completion date = **term `end` minus 14 days** (see `completion_date/filename_term.py`).

## When to edit

1. **New calendar year** — add a `years` block before operators run inference for that year’s WA/EoY/Term filenames.
2. **MOE date changes** — update `start`/`end` for affected terms; keep prior years for historical filenames.
3. **P1 anchors** — student P1 calendar years live in `completion_date/core.py` (`STUDENT_P1_CALENDAR_YEAR`), not in this file. Update anchors there when a child enters P1.

## School year vs calendar year

- **School year** (for path `Pn` + student): `p1_year(student_id) + (n - 1)` (proposal 17 §5.2).
- This JSON keys are **calendar years** of term end dates (used to pick the term-end row for `filename_term`).

## Provenance

Store rule id in `source_detail.calendar_rule_id` when applying `filename_term` (see apply scripts). Git history is the audit trail for term table edits.
