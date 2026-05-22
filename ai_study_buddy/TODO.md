# TODO

## Rules of engagement

- **Purpose:** Lightweight backlog for `ai_study_buddy/` work tracked in-repo alongside code and specs.
- **Priorities:** **P0** = needs immediate attention; **P1** = within roughly the next seven days; **P2** = when there is spare bandwidth.
- **IDs:** **`Px-n`** — **x** is the tier (`0`, `1`, or `2`); **n** is the **1-based index inside that heading’s list**. Open **`## P{n}`** and **`## Completed › P{n}`** each restart at **`Pn-1`** (cite “open **P1-2**” vs “Completed **P1-1**”).
- **List order:** Within each heading whose items carry timestamps, keep bullets **sorted by time ascending** (oldest first). After moving or reordering, **renumber `n`** so it matches the sorted list.
- **Timestamps:** When **adding or materially updating** an item, set **`YYYY-MM-DD HH:MM SGT`** (`SGT`). Use stamps that agree with reality (avoid “later today” times if the row is logged earlier the same calendar day unless that is truthful).
- **Completion:** Toggle `[ ]` → `[x]`, move to **`## Completed` → `### P{same tier}`**; keep chronological order inside that subsection.

## P0 — require immediate attention

- [ ] **P0-1** · 2026-05-20 13:15 SGT: **Marking writer guard — one active result per completion `file_id`** — design and implement policy so a second marking run for the same completion PDF cannot leave two competing “active” results (see [L4_COMPLETION_MARKING_FRAMEWORK.md](docs/L4_COMPLETION_MARKING_FRAMEWORK.md) follow-up #2). **Constraint:** the superseded run may already have **amendments** and **review notes** keyed to its artifact stem — we cannot assume “prune the old JSON” is always safe. **Out of scope for** [completion-series proposal](pdf_file_manager/docs/proposals/15-completion-series-derived.md) (tracked here instead). Needs a small proposal or spec slice: replace vs supersede vs block-at-write, and how Review Workspace / learning DB honor the canonical run.

## P1 — require attention within 7 days

- [ ] **P1-1** · 2026-05-06 10:55 SGT: Author an AI-agent proposal standard (template + required sections, filename/numbering, scope vs GitHub issues, acceptance/review signals) so new `**/docs/proposal(s)/**` writeups stay consistent and machine-followable.
    - There should be an Open Questions section.
    - Implementation plan section should be phase-by-phase and each phase should have todo checklists, test checklists, and success/handoff criteria.
    - The implementation plan should always have a phase on updating relevant documentations.
    - The implementation plan phase should use numbered index (e.g. Phase 1) rather than alphabet.
    - Mention what a "final sweep" means (e.g. check for completeness/accuracy/consistency, get ready for implementation).
    - If the implementation of the proposal completes a bullet (or multiple bullets) in the TODO.md file, add an implementation task in the last phase of the implementation plan to check those bullet(s).
- [ ] **P1-2** · 2026-05-06 12:32 SGT: Audit **error type enums** across the marking module (schemas, graders, ingest/learning DB) for drift, undocumented values, and consistent naming—align or document canon so downstream consumers do not silently misclassify errors.
- [ ] **P1-3** · 2026-05-13 10:34 SGT: Establish a **DaydreamEdu template filename policy** (and migration path) to replace or avoid characters **GoodNotes silently normalizes or drops**—e.g. `&` rewritten as `-`—so `DAYDREAMEDU_ROOT` / `…/DaydreamEdu/template/…` basenames stay aligned with GoodNotes `c_` / `_c_` exports and **`pdf_file_manager.resolve_goodnotes_template_path`** / `link_goodnotes_templates_for_root` do not miss on exact `_c_{stem}.pdf` matches.
- [ ] **P1-4** · 2026-05-19 14:00 SGT: **Move path inference into `files.path_facets`** — migrate implementation out of `PdfFileManager._infer_from_path` into `ai_study_buddy.files.infer_path_facets` (Phase B of v0.3.0); make `pdf_file_manager` a thin delegate; port/extend `pdf_file_manager/tests/test_inference.py` parity into `files/tests/test_path_facets.py`. See L4 Student File Management Open Questions §4.

## P2 — require attention when there's free time

- [ ] **P2-1** · 2026-05-06 11:15 SGT: Defer archiving `.cursor/skills/mark-student-work-multi-agent-v2` and its v2 subagents in `.cursor/agents/` until v3 completes production burn-in; keep v2 as fallback safety net, then archive after v3 is validated across subjects/modes and no active workflows depend on v2.
- [ ] **P2-2** · 2026-05-06 12:08 SGT: Implement `pdf_file_manager/docs/proposals/11-hardening-agent-facing-api-and-skill-for-pdffile-shape.md` (agent-facing PdfFile shape hardening)—proposal drafted, implementation still pending.
- [ ] **P2-3** · 2026-05-22 09:15 SGT: **Optional:** add a granular PATCH-style learning-DB write path for `marking_result` (e.g. one `question_results[]` row or a few fields) keyed by `artifact_path` / `question_id`—today whole-artifact upsert via `write_marking_artifact` / `dual_write` or `import_context_json` already keeps the DB correct; the gap is ergonomics (must re-project the full JSON) and drift risk when JSON is hand-edited on disk without re-import or an API save. **Not a Phase 4 DB-first-write blocker** if production writes stay on repository APIs.
- [ ] **P2-4** · 2026-05-06 21:46 SGT: Reduce filename dependence in `marking/core/context_resolver.py` by improving `_infer_unit_label` fallback behavior (currently `derive_unit_label_from_attempt_name(file.name)`), preferring stricter metadata-first resolution where feasible.
- [ ] **P2-5** · 2026-05-19 14:30 SGT: **`student_file_browser` HTTP tests (`tests/test_serve.py`)** — add a thin test hook on `serve.py` (e.g. injectable `roots` / `index_rows` / `enriched_cache` or `create_app(...)`) so tests do not require operator sync roots; then integration tests for `/api/health`, `/api/config`, `/api/inventory` (query → JSON `items` / `meta`), and `/api/pdf` path-guard failures. Complements existing `test_filters.py` + `test_path_guard.py` + manual smoke. See L4 Student File Management Open Questions §5.

## Completed

### P0

- [x] **P0-1** · 2026-05-06 09:18 SGT: Add backup tooling for `ai_study_buddy/db/study_buddy.db` mirroring the `pdf_registry.db` pipeline (e.g. `pdf_file_manager/scripts/backup_pdf_registry.py`-style copy, tiering, optional wake/runbook hooks).
- [x] **P0-2** · 2026-05-19 14:00 SGT: **Review Workspace attempt deep links (patch release)** — `review_workspace` v0.1.4 URL bootstrap (`?attempt_id=` + `student_id=`); `student_file_browser` v0.1.1 card action; see [proposal](review_workspace/docs/proposal/2-attempt-deep-links.md).
- [x] **P0-3** · 2026-05-20 12:00 SGT: **`root_id` filter** in **Student File Browser** — `files` v0.3.2 `FilterCriteria.root_id` + contextual meta; `student_file_browser` v0.1.3 filter bar + URL param (`all` \| `daydreamedu` \| `goodnotes`, default **All roots**); operator-verified. Proposal [student_file_browser/docs/proposal/1-root-id-filter.md](student_file_browser/docs/proposal/1-root-id-filter.md).

### P1

- [x] **P1-1** · 2026-05-06 11:21 SGT: Create `ai_study_buddy/learning_db/SPEC.md` to define scope, architecture, contracts, and operational expectations for the learning DB module.
- [x] **P1-4** · 2026-05-13 10:35 SGT: Add an **opt-in (or default-on) auto-link step** after GoodNotes completion registration—e.g. when `PdfFileManager.scan_for_new_files(roots=[…])` lands new **`c_`/`_c_` mains** under `GOODNOTES_ROOT`, run **`link_goodnotes_template_for_file`** per file (non-aborting) or a thin wrapper so **`link_goodnotes_templates_for_root`** is not a mandatory second pass; document behavior on unresolved templates, dry-run hooks, and interplay with **P1-3** exact-stem limits. Shipped in `pdf_file_manager` **v0.3.20** (`auto_link_goodnotes=True`, `ScanResult.template_link`).
- [x] **P1-2** · 2026-05-22 08:40 SGT: Wrap up `ai_study_buddy/docs/L4_LOCAL_LEARNING_DB.md` after the 200-op dual-write provisional gate passed — Phase 3 provisional sign-off recorded (660 ops, 0 failures); final 1,000-op gate and Phase 4 JSON demotion remain open.

### P2

_No completed items._
