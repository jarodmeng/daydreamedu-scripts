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
| [DATA_STRATEGY](./L3_DATA_STRATEGY.md) | PDF ingestion, OCR, embeddings, storage, question objects |
| [USER_EXPERIENCE](./L3_USER_EXPERIENCE.md) | Kid UI, parent dashboard, admin/ingestion review UI |
| [SAFETY_AND_PRIVACY](./L3_SAFETY_AND_PRIVACY.md) | Singapore PDPA, answer-gating, data protection |
| [GAMIFICATION](./L3_GAMIFICATION.md) | Game mechanics, motivation design, research evidence |

### Level 4 — Implementation Proposals

Actionable plans for building specific components. Each L4 doc drills into one deliverable with technology choices, schema, workflow, and MVP scope.

| Document | What it covers |
|----------|---------------|
| [INGESTION_PIPELINE](./L4_INGESTION_PIPELINE.md) | PDF-to-question-object pipeline: steps, tools, schema, review workflow, MVP scope |

## Sources and attribution

Each document draws from two sources, clearly labeled:

- **ChatGPT 5.2 Thinking** — a conversation on 3 Mar 2026 that produced the initial blueprint. The full transcript is preserved at [research/ai_chats/20260303__chatgpt_5_2_thinking__ai_study_buddy_blueprint.md](./research/ai_chats/20260303__chatgpt_5_2_thinking__ai_study_buddy_blueprint.md).
- **Opus 4.6 Max** — independent research and analysis added on 4 Mar 2026, marked with `> [!NOTE]` callout blocks and `(Opus 4.6 Max)` labels. These sections include external citations with URLs for traceability.

## How to edit these documents

- **Resolve open questions.** Most documents end with an "Open Questions" section listing decisions that haven't been made yet. As you make decisions, move the answers into the relevant sections and remove them from the open questions list.
- **Update as you build.** When design choices become implementation decisions, update the relevant document to reflect what was actually built (and why, if it differs from the original recommendation).
- **Add new research.** If you have a conversation with another AI or do your own research, add findings to the relevant document with a clear attribution header (model name, date). Keep the raw transcript in `research/ai_chats/` with the naming convention `YYYYMMDD__<model>__<topic>.md`.
- **Keep the ROADMAP current.** As phases complete or priorities shift, update [ROADMAP](./L1_ROADMAP.md) to reflect the current state.
