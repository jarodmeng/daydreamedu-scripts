# Proposal 15: Consumer layer and marking orchestration for question_sections.json

## What this proposal is

Validated **`question_sections.json`** is usable **ergonomically**: stable iterators over sections and questions, a bridge into **`context.question_page_map`**, and marking workflows (**`mark-student-work-multi-agent-v2`** SKILL + **`marking-phase*.md`**) that **prefer** that structure when **`file_question_info`** exists instead of hand-walking **`sections[i]`** in prose. This proposal is **self-contained**: its APIs and rollouts live here; it **does not** redefine on-disk layout, **`rendered_pages/`** naming, or the canonical **`load`/`validate`** gate (Proposal **13** owns those).

**Related:** Proposal **14** mirrors detector JSON into **`study_buddy.db`** and needs **`load`/`validate`** from Proposal **13**; it does **not** require this document. SKILL and marking agents **can** adopt consumer helpers **before or after** the SQLite mirror, depending on prioritization.

## Prerequisite APIs (from Proposal 13)

Consumer and orchestration work assumes these exist (see **`13-file-question-info-marking-python-apis.md`**):

- **`file_question_info_run_dir_for_pdf`**
- **`render_file_question_info_pages_for_pdf`**
- **`load_question_sections_json`**
- **`validate_question_sections_dict`**
- Aligned **`.cursor/agents/*-question-section-detector*.md`** specs (registry prerequisite, mandatory terminal **`load`/`validate`**)

Timeline: **Proposal 13 can merge independently**; this document **waits on** those symbols when implementing iterators/orchestration, not the other way around.

## How this relates to Proposal 13

Proposal **13** answers **where** artifacts live on disk, **how** page PNGs are produced, and **whether** persisted JSON conforms to **`schema_version`**. This proposal answers **what callers do next**: typed walks of the payload, **`question_page_map`** construction, and doc updates so multi-agent marking treats that structure as **first-class**. The numbering of phases below (**E–H**) is **local to this file**—it does **not** line up with Proposal **13**’s letters (**13** stops at **Phase E**, marking **`README`/`CHANGELOG`**; **15** uses **E–H** only here).

## Sibling scopes (cross-reference)

| Doc | Responsibility |
|-----|----------------|
| [**13**](13-file-question-info-marking-python-apis.md) | **`run_folder`**, **`rendered_pages/`**, canonical **`load`/`validate`**, detector agent alignment (**Phase D**), marking package **`README`/`CHANGELOG`** (**Phase E**) |
| **15** (this) | iterators (§**3**), **`question_page_map`** bridge (§**4**), SKILL + **`marking-phase*`** rewires |
| [**14**](14-persist-file-question-info-in-study-buddy-db.md) | SQLite ingest; **`validate`** before **`upsert`** |

## Proposed Python surface (extends `marking.file_question_info`)

Assume `validate_question_sections_dict(payload)` has already run (Proposal 13). Section 3 and section 4 helpers dispatch by `schema_version`; subjects do not share one rigid dataclass.

### Section 3: Normalized consumer views

Higher-level helpers return immutable dataclass or typed-dict rows:

- `iter_sections_ordered(payload)` — at minimum: `question_type`, optional `printed_section_title`, `questions_page_range`, optional `stem_page_range`, optional `answers_page_range` / `answer_page_range`, `answers_in_separate_booklet` when present.

- `iter_questions_ordered(payload)` — stable `question_index` (for example `Q1`, `Q11(a)`), optional `question_mark`, optional `start_page`, `section_index`, `question_type` (section-level label). Walk each section's `question_info` in document order (Chinese, English, Higher Chinese, Math, Science contracts).

Use iterators for structure QC, SKILL migration, and mapper-or-detector parity while orchestration flips to JSON-backed structure.

### Section 4: Bridge to `question_page_map`

Validated `question_sections.json` is the structural source of truth for `context.question_page_map` (given registry resolution and page-index conventions). Extend marking enums so rows can use `detector_layout`-style `source` / `confidence` / `note`, not a permanent `script_inferred` story.

- `build_detector_question_id_list(payload) -> tuple[str, ...]` — ordered `question_index` values for duplicate-ID and ordering checks (same gates as Phase 1 mapper QC today).

- `question_page_map_from_question_sections(...)` (name TBD) — from `iter_questions_ordered`, map `start_page` and subject-specific span fields into `attempt_page_start` / `attempt_page_end` for `context.question_page_map`, keyed by `question_index`, with `bundle_attempt_page_offset` for 1-based detector pages vs bundle numbering. Residual risk handled by validation, review, and detector re-run—not by downgrading JSON to a weak hint.

- `section_hint_strings_for_context(detector_payload) -> tuple[str, ...]` — one short label per section (`question_type`, optionally with `printed_section_title`). Does not set `MarkingContext.question_selection.section_hint` automatically; exposes a canonical menu for UI, `question_refs`, or Phase 2/3 prompts.

### Additional non-goals

Inherits Proposal 13 Explicit non-goals (no `question_sections.json` writer in this package, no OCR/layout inference, no fabricated payloads off registry policy). Also: no automatic overwrite of Phase 3 `max_marks` from detector fields without human policy (Phase 2 remains authoritative per SKILL).

## Implementation plan: Phases E through H

Phase letters **E–H** belong **only** to this document’s sequencing. Extend **`marking/file_question_info/api.py`** **`__all__`** with §**3**/**§**4 names when stable. Phase **H** freezes **`README` `python -c`** snippets so they stay byte-identical across **`*-question-section-detector`** footers (updated under Proposal **13**), **`marking-phase*.md`**, and **`mark-student-work-multi-agent-v2/SKILL.md`**.

### Phase E — iterators (section 3)

Objective: `iter_sections_ordered` / `iter_questions_ordered` walk validated payloads without raw `sections[i]` in callers.

Todos: row types; iterators and tests per schema_version; edge cases (empty `question_info`, multi-section Higher Chinese). Ordering tests vs `build_detector_question_id_list` once Phase F exists.

Success: after `validate_question_sections_dict`, iterators do not raise KeyError on schema-guaranteed fields.

### Phase F — marking bridge (section 4)

Objective: deterministic `question_page_map`-shaped output and duplicate-ID tooling for SKILL QC.

Todos: `build_detector_question_id_list` vs Phase E fixtures; `question_page_map_from_question_sections` with offset; math + english variance tests; `section_hint_strings_for_context` length and titles; `source`/`confidence`/`note` aligned with `4-question-page-mapping-v1_4.md`.

Success: map output matches `context.question_page_map` consumer expectations; duplicate `question_index` scenarios produce deterministic failures or tuples as designed.

### Phase G — marking pipeline agents and SKILL

Objective: when `file_question_info` is present, prefer `run_folder` then `load_question_sections_json` then `validate_question_sections_dict` then `question_page_map_from_question_sections`, `build_detector_question_id_list`, `section_hint_strings_for_context`—not ad hoc crawling of `sections[i]` in prose alone. Proposal 14 is not required for this cut.

Scope: `.cursor/agents/marking-phase1-mapper.md`, `marking-phase2-fast-pass-grader.md`, `marking-phase3-deep-dive.md`, `marking-phase4-taxonomy-tagger.md`, `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md`, `8-multi-agent-marking-architecture.md`. **`.cursor/agents/*-question-section-detector*.md`** copy is Proposal **13**’s responsibility; this proposal consumes validated JSON emitted under that contract.

Depends on Proposal **13** **`validate_question_sections_dict`** (**always**) and **`file_question_info_run_dir_for_pdf`** (**strongly recommended** for SKILL path discovery); Phase **E** optional if callers only invoke Phase **F** helpers directly.

G.1 — Update each `marking-phase*.md`: Phase 1 prefers detector-backed `question_page_map` plus `build_detector_question_id_list` QC with explicit image-only mapper fallback (binary choice, no hybrid). Phases 2–4 align prompts and taxonomy with map rows and `question_info` where applicable. `rg` review for matching import paths vs Phase H.

G.2 — SKILL: Phase 1 preamble locates JSON via `PdfFile` and `file_question_info_run_dir_for_pdf`; load and validate; build map and QC; skip Phase 1 mapper when fallback is not needed. Optional `section_hint_strings_for_context` in Phase 2 batching. Align `8-multi-agent-marking-architecture.md` diagram with validate to map to QC to phases.

Testing: golden path with on-disk `file_question_info`; fallback when JSON missing or invalid; corrupt JSON must not silently succeed; SKILL and `marking-phase1-mapper` policies match.

Success — agents: all four `marking-phase*.md` state Phase F vs mapper-only; QC parity when JSON path applies; no contradiction of `question_page_map` without documented override.

Success — SKILL + architecture: deterministic imports or pointer to `README`; happy path uses Phase F helpers; single ordering narrative (validate, map, QC, fan-out).

### Phase H — consolidation

Objective: ship §**3** and §**4** exports; freeze canonical import paths for **`*-question-section-detector`** footers (Proposal **13**) and for Phase **G** consumers (`marking-phase*.md`, `SKILL.md`).

Todos: `api.py` `__all__` lists foundation exports landed by Proposal **13** plus §**3**–§**4** when stable; `CHANGELOG` / `README` when shipped; lock `python -c` blocks across detector footers, marking agents, SKILL, `README`; optional CLI `validate_question_sections <path>` respects Proposal **13** non-goals (no mandated writer in **`file_question_info`**).

Success: clean-env imports; pytest over `file_question_info` + consumer tests; one stable import story across all cited docs.

## References

- `13-file-question-info-marking-python-apis.md`
- `14-persist-file-question-info-in-study-buddy-db.md`
- `4-question-page-mapping-v1_4.md`, `8-multi-agent-marking-architecture.md`
- `.cursor/agents/*-question-section-detector*.md` — layout + mandatory **`load`/`validate`** (Proposal **13**)
- `.cursor/skills/mark-student-work-multi-agent-v2/SKILL.md`, `.cursor/agents/marking-phase*.md`
