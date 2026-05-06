# TODO

- [ ] 2026-05-06 11:15 SGT: Defer archiving `.cursor/skills/mark-student-work-multi-agent-v2` and its v2 subagents in `.cursor/agents/` until v3 completes production burn-in; keep v2 as fallback safety net, then archive after v3 is validated across subjects/modes and no active workflows depend on v2.
- [ ] 2026-05-06 12:08 SGT: Implement `pdf_file_manager/docs/proposals/11-hardening-agent-facing-api-and-skill-for-pdffile-shape.md` (agent-facing PdfFile shape hardening)—proposal drafted, implementation still pending.
- [ ] 2026-05-06 10:43 SGT: Wrap up `ai_study_buddy/docs/L4_LOCAL_LEARNING_DB.md` once the current 200-successful-dual-writes gating condition is met (finalize doc based on production dual-write experience).
- [x] 2026-05-06 16:48 SGT: Add backup tooling for `ai_study_buddy/db/study_buddy.db` mirroring the `pdf_registry.db` pipeline (e.g. `pdf_file_manager/scripts/backup_pdf_registry.py`-style copy, tiering, optional wake/runbook hooks).
- [ ] 2026-05-06 17:30 SGT: Author an AI-agent proposal standard (template + required sections, filename/numbering, scope vs GitHub issues, acceptance/review signals) so new `**/docs/proposal(s)/**` writeups stay consistent and machine-followable.
    - There should be an Open Questions section.
    - Implementation plan section should be phase-by-phase and each phase should have todo checklists, test checklists, and success/handoff criteria.
    - The implementation plan should always have a phase on updating relevant documentations.
    - The implementation plan phase should use numbered index (e.g. Phase 1) rather than alphabet.
    - Mention what a "final sweep" means (e.g. check for completeness/accuracy/consistency, get ready for implementation).
    - If the implementation of the proposal completes a bullet (or multiple bullets) in the TODO.md file, add an implementation task in the last phase of the implementation plan to check those bullet(s).
- [x] 2026-05-06 11:21 SGT: Create `ai_study_buddy/learning_db/SPEC.md` to define scope, architecture, contracts, and operational expectations for the learning DB module.