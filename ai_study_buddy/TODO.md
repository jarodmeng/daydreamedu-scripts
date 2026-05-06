# TODO

## Rules of engagement

- **Purpose:** Lightweight backlog for `ai_study_buddy/` work tracked in-repo alongside code and specs.
- **Priorities:** **P0** = needs immediate attention; **P1** = within roughly the next seven days; **P2** = when there is spare bandwidth.
- **IDs:** **`Px-n`** — **x** is the tier (`0`, `1`, or `2`); **n** is the **1-based index inside that heading’s list**. Open **`## P{n}`** and **`## Completed › P{n}`** each restart at **`Pn-1`** (cite “open **P1-2**” vs “Completed **P1-1**”).
- **List order:** Within each heading whose items carry timestamps, keep bullets **sorted by time ascending** (oldest first). After moving or reordering, **renumber `n`** so it matches the sorted list.
- **Timestamps:** When **adding or materially updating** an item, set **`YYYY-MM-DD HH:MM SGT`** (`SGT`). Use stamps that agree with reality (avoid “later today” times if the row is logged earlier the same calendar day unless that is truthful).
- **Completion:** Toggle `[ ]` → `[x]`, move to **`## Completed` → `### P{same tier}`**; keep chronological order inside that subsection.

## P0 — require immediate attention

_No open items._

## P1 — require attention within 7 days

- [ ] **P1-1** · 2026-05-06 10:43 SGT: Wrap up `ai_study_buddy/docs/L4_LOCAL_LEARNING_DB.md` once the current 200-successful-dual-writes gating condition is met (finalize doc based on production dual-write experience).
- [ ] **P1-2** · 2026-05-06 10:55 SGT: Author an AI-agent proposal standard (template + required sections, filename/numbering, scope vs GitHub issues, acceptance/review signals) so new `**/docs/proposal(s)/**` writeups stay consistent and machine-followable.
    - There should be an Open Questions section.
    - Implementation plan section should be phase-by-phase and each phase should have todo checklists, test checklists, and success/handoff criteria.
    - The implementation plan should always have a phase on updating relevant documentations.
    - The implementation plan phase should use numbered index (e.g. Phase 1) rather than alphabet.
    - Mention what a "final sweep" means (e.g. check for completeness/accuracy/consistency, get ready for implementation).
    - If the implementation of the proposal completes a bullet (or multiple bullets) in the TODO.md file, add an implementation task in the last phase of the implementation plan to check those bullet(s).
- [ ] **P1-3** · 2026-05-06 12:32 SGT: Audit **error type enums** across the marking module (schemas, graders, ingest/learning DB) for drift, undocumented values, and consistent naming—align or document canon so downstream consumers do not silently misclassify errors.

## P2 — require attention when there's free time

- [ ] **P2-1** · 2026-05-06 11:15 SGT: Defer archiving `.cursor/skills/mark-student-work-multi-agent-v2` and its v2 subagents in `.cursor/agents/` until v3 completes production burn-in; keep v2 as fallback safety net, then archive after v3 is validated across subjects/modes and no active workflows depend on v2.
- [ ] **P2-2** · 2026-05-06 12:08 SGT: Implement `pdf_file_manager/docs/proposals/11-hardening-agent-facing-api-and-skill-for-pdffile-shape.md` (agent-facing PdfFile shape hardening)—proposal drafted, implementation still pending.
- [ ] **P2-3** · 2026-05-06 12:48 SGT: Close the parity gap between **surgical edits** to a `marking_result` JSON file (e.g. one `question_results[]` row or a few fields) and **learning DB sync**: today, `learning_db.ingest.import_context_json` re-import drives a full artifact upsert and replaces all `marking_question_results` (and related) rows for that artifact—there is no supported path for **targeted partial overwrite** keyed by `artifact_path` / `result_id` / changed fields without re-processing the entire JSON payload through the importer.
- [ ] **P2-4** · 2026-05-06 21:46 SGT: Reduce filename dependence in `marking/core/context_resolver.py` by improving `_infer_unit_label` fallback behavior (currently `derive_unit_label_from_attempt_name(file.name)`), preferring stricter metadata-first resolution where feasible.

## Completed

### P0

- [x] **P0-1** · 2026-05-06 09:18 SGT: Add backup tooling for `ai_study_buddy/db/study_buddy.db` mirroring the `pdf_registry.db` pipeline (e.g. `pdf_file_manager/scripts/backup_pdf_registry.py`-style copy, tiering, optional wake/runbook hooks).

### P1

- [x] **P1-1** · 2026-05-06 11:21 SGT: Create `ai_study_buddy/learning_db/SPEC.md` to define scope, architecture, contracts, and operational expectations for the learning DB module.

### P2

_No completed items._
