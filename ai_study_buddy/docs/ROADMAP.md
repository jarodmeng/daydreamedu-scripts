# AI Study Buddy — Roadmap

> Status: **Exploratory** — phased plan with recommendations, not committed timelines.
>
> Sources: ChatGPT 5.2 Thinking conversation (3 Mar 2026), supplemented with independent analysis (Opus 4.6 Max, 4 Mar 2026).

---

## Phased Build Plan (from ChatGPT)

### Phase 1 — MVP: Winston PSLE Coach

**Scope:** Get something working and useful for Winston first, since his PSLE is in ~6 months (Sep 2026).

**Deliverables:**
- PDF ingestion + retrieval (Google Drive → question objects → searchable index)
- Manual tagging for a small set of core skills (Math, English)
- Daily/weekly plan generation
- Tutor behaviors (hint ladder + teach-back + logging)
- Simple kid UI (Quest Board + Tutor screen + Upload)

### Phase 2 — Automated Extraction + Analytics

**Scope:** Reduce manual effort and add visibility.

**Deliverables:**
- Automated extraction (question detection, score extraction, skill tagging)
- Analytics dashboard for parent
- Template learning (school paper formats recognized automatically)
- Improved ingestion review UI

### Phase 3 — Expand to Emma + Abigail

**Scope:** Age-appropriate experiences for younger children.

**Deliverables:**
- Age-appropriate UX (voice for Abigail, micro-quizzes for Emma)
- Richer gamification layer (questlines, team mode, family rewards)
- Cross-child analytics (family dashboard)

---

## MVP Components (What to Build First)

(From ChatGPT — the "minimum viable architecture," not minimum features.)

| Priority | Component | Why first |
|----------|-----------|-----------|
| 1 | **Postgres + pgvector** | Foundation for everything |
| 2 | **Ingestion pipeline** | PDF → page images + OCR text + question-level chunks |
| 3 | **Student model tables** | mastery + attempts + misconceptions |
| 4 | **Tutor loop** | hint ladder + teach-back + logging |
| 5 | **Weekly planner** | deterministic scheduling |
| 6 | **Simple kid UI** | quests + streak + upload + chat |

Everything else (dashboards, leaderboards, voice, knowledge graphs) layers on safely.

---

> [!NOTE]
> **Opus 4.6 Max analysis** — additional considerations on roadmap, risks, and prioritization.

### Winston's PSLE timeline creates real constraints

With PSLE written papers starting **24 Sep 2026**, there are roughly **29 weeks** from today (4 Mar 2026). A realistic MVP timeline:

| Milestone | Target | Weeks from now |
|-----------|--------|---------------|
| Architecture decisions finalized | Late Mar 2026 | ~4 |
| Ingestion pipeline working (basic) | Mid Apr 2026 | ~6 |
| Tutor loop functional | Early May 2026 | ~9 |
| Winston starts using MVP | Mid May 2026 | ~10 |
| PSLE Oral exams | 12–13 Aug 2026 | ~23 |
| PSLE Written exams | 24–30 Sep 2026 | ~29 |

This gives Winston ~4 months of daily use before PSLE if the MVP ships by mid-May. That's tight but feasible, especially with AI-assisted development.

**Risk:** If the MVP takes longer than expected, Winston may get limited value before PSLE. Consider a **"Phase 0.5"** fallback: even a basic daily plan + question bank (without the full tutor agent) could be useful.

### What to defer (things that feel important but aren't MVP)

| Feature | Why defer |
|---------|----------|
| Automated question boundary detection | Manual question tagging is fine for a small initial corpus. Automate once templates are learned. |
| Voice input/output | Winston (P6) can type. Voice is critical for Abigail but that's Phase 3. |
| Fancy gamification (questlines, team mode) | Simple XP + streak is enough for Phase 1. |
| Parent analytics dashboard | A weekly summary email/message is enough initially. |
| Embedding-based retrieval | Keyword + metadata search may be sufficient for Phase 1; add embeddings when the corpus is larger. |
| ADK adoption | A thin custom agent loop is lower-risk for Phase 1. Migrate to ADK when it matures (or when multi-agent composition becomes necessary). |

### Risk assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Question extraction from scanned PDFs is too noisy** | High | Medium | Start with manual tagging; human-in-the-loop review screen; build template profiles gradually |
| **LLM tutoring quality is inconsistent** | Medium | High | Hybrid approach (rules for flow, LLM for language); human review of edge cases; log everything |
| **Children lose interest quickly** | Medium | High | Ship gamification early (even simple XP + streaks); involve children in design ("what would make this fun?") |
| **Scope creep delays MVP** | High | High | Ruthlessly cut Phase 1 scope; defer everything that isn't Winston + Math + English |
| **ADK TypeScript is too immature** | Medium | Low | Use a thin custom agent loop instead; ADK concepts (tools, sessions, events) are straightforward to implement directly |
| **Cost overruns** | Low | Low | At family scale, costs are inherently low; set API caps + alerts from day 1 |

### Alternative MVP approach: "PDF + Plan + Practice"

If the full tutor agent is too ambitious for Phase 1, consider a simpler MVP:

1. **Ingest PDFs** → extract question text + scores (even manually)
2. **Generate a weekly plan** based on identified weak areas (deterministic)
3. **Present practice questions** from the corpus (no AI tutoring, just question selection)
4. **Log results** (child self-reports correctness; parent can verify)

This gives Winston a structured study plan based on his actual performance data, without needing the tutor agent to work perfectly. The tutor agent becomes a Phase 1.5 addition.

### Build vs. buy considerations

Before building everything custom, evaluate existing tools:

| Capability | Build custom | Existing alternatives |
|-----------|-------------|----------------------|
| Spaced repetition engine | Medium effort | Anki (open-source), SM-2 algorithm (public domain) |
| PDF OCR + extraction | High effort | Cloud Vision + layout heuristics (as proposed) |
| AI tutoring | High effort | Khanmigo, LearnLM (not open), various EdTech platforms |
| Gamification | Medium effort | No good off-the-shelf for this use case |
| Student model / mastery tracking | Medium effort | No good off-the-shelf that integrates with custom content |

The custom build is justified because:
- **Personalization requires custom data** (their specific worksheets, teacher markings, school curriculum)
- **No existing tool combines** all of: PDF ingestion + Singapore curriculum + gamification + multi-child + parent dashboard
- **Control over pedagogy** (answer-gating, teach-back enforcement) is critical and not available in commercial tools

---

## Suggested Next Steps

1. **Resolve open questions** from [VISION.md](./VISION.md) — especially subjects in scope, devices, and PDF organization.
2. **Set up the project structure** — monorepo with frontend (React + TS), backend (TS), and ingestion worker (Python).
3. **Stand up Postgres + pgvector** — define the initial schema (skills, attempts, mastery, plans, rewards, doc_chunks).
4. **Build the ingestion pipeline** — start with a few of Winston's Math worksheets; manual tagging is fine.
5. **Build the weekly planner** — deterministic scheduling based on mastery gaps + calendar.
6. **Build a minimal Quest Board UI** — display today's quests + upload.
7. **Build the tutor loop** — start with a simple hint ladder on text-based questions.

---

## Document Index

| Document | What it covers |
|----------|---------------|
| [VISION.md](./VISION.md) | Goals, target users, learning philosophy, evidence base |
| [ARCHITECTURE.md](./ARCHITECTURE.md) | System components, data architecture, deployment options |
| [TECH_STACK.md](./TECH_STACK.md) | Language choices, ADK, database, alternatives |
| [DATA_STRATEGY.md](./DATA_STRATEGY.md) | Ingestion pipeline, OCR, embeddings, storage, question objects |
| [COST_ANALYSIS.md](./COST_ANALYSIS.md) | Cost model, projections, optimization strategies |
| [USER_EXPERIENCE.md](./USER_EXPERIENCE.md) | Kid UI, parent UI, admin UI, multi-modal input |
| [GAMIFICATION.md](./GAMIFICATION.md) | Game mechanics, motivation design, research evidence |
| [AI_AGENTS.md](./AI_AGENTS.md) | Agent patterns, tutor loop, multi-agent system |
| [SAFETY_AND_PRIVACY.md](./SAFETY_AND_PRIVACY.md) | PDPA compliance, answer-gating, data protection |
| [ROADMAP.md](./ROADMAP.md) | This document |

Source material:
| Document | Location |
|----------|----------|
| ChatGPT conversation (full transcript) | [research/ai_chats/20260303__chatgpt_5_2_thinking__ai_study_buddy_blueprint.md](./research/ai_chats/20260303__chatgpt_5_2_thinking__ai_study_buddy_blueprint.md) |
