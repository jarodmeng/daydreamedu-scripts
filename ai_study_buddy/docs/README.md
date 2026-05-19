# AI Study Buddy — Documentation

This folder contains the design exploration documents for the AI Study Buddy project — a personalized AI learning coach for three children (Winston P6, Emma P4, Abigail P2) in Singapore's primary school system.

## Status

All documents are **exploratory**. They present options, trade-offs, and recommendations — not final decisions. The project is in the design/research phase.

## Documents

Documents are organized into four levels. Start with L1 for the big picture, then drill into L2–L4 as needed.

### Level 1 — Strategy

The core documents. What we're building, how we get there, and what it costs.

| Document | What it covers |
|----------|---------------|
| [VISION](./L1_VISION.md) | Goals, target users, learning philosophy, evidence base |
| [ARCHITECTURE](./L1_ARCHITECTURE.md) | System design, components, domain model, key workflows |
| [COST_ANALYSIS](./L1_COST_ANALYSIS.md) | Cost model, monthly projections, optimization strategies |
| [ROADMAP](./L1_ROADMAP.md) | Phased plan, MVP timeline, risks, next steps |

### Level 2 — Critical Technical Detail

Built on top of L1. Expand the two most important technical axes.

| Document | What it covers |
|----------|---------------|
| [AI_AGENTS](./L2_AI_AGENTS.md) | Agent patterns, tutor loop, multi-agent system, LLM limitations |
| [TECH_STACK](./L2_TECH_STACK.md) | Language choices (TS vs Go vs Python), ADK, database, deployment options |

### Level 3 — Domain Deep Dives

Detailed documentation on specific aspects of the project.

| Document | What it covers |
|----------|---------------|
| [DATA_STRATEGY](./L3_DATA_STRATEGY.md) | PDF ingestion, OCR, embeddings, storage, question objects, local durable learning memory |
| [EXAM_FORMATS](./L3_EXAM_FORMATS.md) | Singapore primary exam formats — cross-subject overview; per-subject detail in `context/subject_understandings/` |
| [USER_EXPERIENCE](./L3_USER_EXPERIENCE.md) | Kid UI, parent dashboard, admin/ingestion review UI |
| [SAFETY_AND_PRIVACY](./L3_SAFETY_AND_PRIVACY.md) | Singapore PDPA, answer-gating, data protection |
| [GAMIFICATION](./L3_GAMIFICATION.md) | Game mechanics, motivation design, research evidence |

### Level 4 — Implementation Proposals

Actionable plans for building specific components. Each L4 doc drills into one deliverable with technology choices, schema, workflow, and MVP scope (see the status callout at the top of each file for proposal vs shipped).

| Document | What it covers |
|----------|---------------|
| [INGESTION_PIPELINE](./L4_INGESTION_PIPELINE.md) | PDF-to-question-object pipeline: steps, tools, schema, review workflow, MVP scope |
| [QUESTION_INDEX_SCHEMA](./L4_QUESTION_INDEX_SCHEMA.md) | Proposal (v2): `unit_question_index` — per-template question layout and semantics (vision-LLM pass), bridge between registered template PDFs and enriched `question_objects` / embeddings |
| [FILE_SYSTEM_MANAGEMENT](./L4_FILE_SYSTEM_MANAGEMENT.md) | **Implemented** — `ai_study_buddy.files` v0.3.0+: roots, leaf-folder profiles, `pdf_registry_paths`, and v0.3.0 on-disk main-PDF inventory (`path_facets`, `on_disk_inventory`, …) |
| [MARKING_RESULT_ARTIFACT](./L4_MARKING_RESULT_ARTIFACT.md) | `marking_result.v1.6` (implemented): file-canonical JSON marking artifact, human-editable review fields, markdown learning reports derived from JSON, GoodNotes-oriented workflow |
| [STUDENT_MVP_EXPERIENCE](./L4_STUDENT_MVP_EXPERIENCE.md) | Spec (v0.3): **Review Workspace** shipped in `review_workspace` v0.1.4 (single-student alpha) — attempt index, deep links, canonical marking detail, evidence viewing, `student_review_state.v1` notes, and `marking_amendment.v1` human overrides |
| [STUDENT_FILE_MANAGEMENT](./L4_STUDENT_FILE_MANAGEMENT.md) | **Implemented** — `files` v0.3.0+, `marking` v0.3.8 workflow flags, **Student File Browser** v0.1.1 (8771), `root_pdf_browser` v0.1.6 + Review Workspace v0.1.4 deep links; operator filter-first inventory |
| [LOCAL_LEARNING_DB](./L4_LOCAL_LEARNING_DB.md) | Proposal: create `study_buddy.db` as a local Postgres-shaped SQLite data layer for marking facts, amendments, review state, backup, and future migration |

## Sources and attribution

Each document draws from two sources, clearly labeled:

- **ChatGPT 5.2 Thinking** — a conversation on 3 Mar 2026 that produced the initial blueprint. The full transcript is preserved at [research/ai_chats/20260303__chatgpt_5_2_thinking__ai_study_buddy_blueprint.md](./research/ai_chats/20260303__chatgpt_5_2_thinking__ai_study_buddy_blueprint.md).
- **Opus 4.6 Max** — independent research and analysis added on 4 Mar 2026, marked with `> [!NOTE]` callout blocks and `(Opus 4.6 Max)` labels. These sections include external citations with URLs for traceability.

## How to edit these documents

- **Follow proposal instructions for implementation proposals.** For any new or substantially updated proposal in this folder (especially `L4_*`), follow [PROPOSAL_WRITING_INSTRUCTIONS](./PROPOSAL_WRITING_INSTRUCTIONS.md), including the mandatory detailed implementation-monitoring TODO checklist.
- **Resolve open questions.** Most documents end with an "Open Questions" section listing decisions that haven't been made yet. As you make decisions, move the answers into the relevant sections and remove them from the open questions list.
- **Update as you build.** When design choices become implementation decisions, update the relevant document to reflect what was actually built (and why, if it differs from the original recommendation).
- **Add new research.** If you have a conversation with another AI or do your own research, add findings to the relevant document with a clear attribution header (model name, date). Keep the raw transcript in `research/ai_chats/` with the naming convention `YYYYMMDD__<model>__<topic>.md`.
- **Keep the ROADMAP current.** As phases complete or priorities shift, update [ROADMAP](./L1_ROADMAP.md) to reflect the current state.
