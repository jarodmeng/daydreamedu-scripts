# AI Study Buddy — Documentation

This folder contains the design exploration documents for the AI Study Buddy project — a personalized AI learning coach for three children (Winston P6, Emma P4, Abigail P2) in Singapore's primary school system.

## Status

All documents are **exploratory**. They present options, trade-offs, and recommendations — not final decisions. The project is in the design/research phase.

## Documents

| Document | What it covers |
|----------|---------------|
| [VISION.md](./VISION.md) | Goals, target users, learning philosophy, evidence base |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System components, data architecture, deployment options |
| [TECH_STACK.md](./TECH_STACK.md) | Language choices (TS vs Go vs Python), ADK, database |
| [DATA_STRATEGY.md](./DATA_STRATEGY.md) | PDF ingestion, OCR, embeddings, storage, question objects |
| [COST_ANALYSIS.md](./COST_ANALYSIS.md) | Cost model, monthly projections, optimization strategies |
| [USER_EXPERIENCE.md](./USER_EXPERIENCE.md) | Kid UI, parent dashboard, admin/ingestion review UI |
| [GAMIFICATION.md](./GAMIFICATION.md) | Game mechanics, motivation design, research evidence |
| [AI_AGENTS.md](./AI_AGENTS.md) | Agent patterns, tutor loop, multi-agent system |
| [SAFETY_AND_PRIVACY.md](./SAFETY_AND_PRIVACY.md) | Singapore PDPA, answer-gating, data protection |
| [ROADMAP.md](./ROADMAP.md) | Phased plan, MVP timeline, risks, next steps |

Start with [VISION.md](./VISION.md) for the big picture, or [ROADMAP.md](./ROADMAP.md) for a summary of all documents and suggested next steps.

## Sources and attribution

Each document draws from two sources, clearly labeled:

- **ChatGPT 5.2 Thinking** — a conversation on 3 Mar 2026 that produced the initial blueprint. The full transcript is preserved at [research/ai_chats/20260303__chatgpt_5_2_thinking__ai_study_buddy_blueprint.md](./research/ai_chats/20260303__chatgpt_5_2_thinking__ai_study_buddy_blueprint.md).
- **Opus 4.6 Max** — independent research and analysis added on 4 Mar 2026, marked with `> [!NOTE]` callout blocks and `(Opus 4.6 Max)` labels. These sections include external citations with URLs for traceability.

## How to edit these documents

- **Resolve open questions.** Most documents end with an "Open Questions" section listing decisions that haven't been made yet. As you make decisions, move the answers into the relevant sections and remove them from the open questions list.
- **Update as you build.** When design choices become implementation decisions, update the relevant document to reflect what was actually built (and why, if it differs from the original recommendation).
- **Add new research.** If you have a conversation with another AI or do your own research, add findings to the relevant document with a clear attribution header (model name, date). Keep the raw transcript in `research/ai_chats/` with the naming convention `YYYYMMDD__<model>__<topic>.md`.
- **Keep the ROADMAP current.** As phases complete or priorities shift, update [ROADMAP.md](./ROADMAP.md) to reflect the current state.
