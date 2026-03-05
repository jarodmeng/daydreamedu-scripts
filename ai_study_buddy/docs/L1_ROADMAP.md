# AI Study Buddy — Roadmap

> Status: **Exploratory** — phased plan with recommendations, not committed timelines.
>
> Sources: ChatGPT 5.2 Thinking conversation (3 Mar 2026), supplemented with independent analysis (Opus 4.6 Max, 4–5 Mar 2026).

---

## Context

Jarod is currently Winston's primary tutor — reviewing mistakes from exercise papers and doing "just-in-time tutoring" (silently observing Winston take assessments, intervening only for hints or teachable mistakes). This is effective but relies on Jarod's memory and intuition to decide *what* to practice and *where* the gaps are.

The system's first job is not to replace Jarod as tutor. It's to be the **analytical backbone** that makes the tutoring time more targeted: know what skills exist, know where Winston stands on each, and plan what to work on next.

---

## Driving Constraint: Winston's PSLE

Winston's PSLE dates (from [MOE 2026 PSLE Exam Calendar](https://file.go.gov.sg/2026-psle-exam-cal.pdf)):

- **Oral:** 12–13 Aug 2026
- **Listening Comprehension:** 15 Sep 2026
- **Written papers:** 24–30 Sep 2026

| Milestone | Target | Weeks from now |
|-----------|--------|---------------|
| Foundation complete | Late Mar 2026 | ~3 |
| Analytical backbone usable | Mid May 2026 | ~10 |
| Full diagnostic + planner | Early Jul 2026 | ~17 |
| PSLE Oral exams | 12–13 Aug 2026 | ~23 |
| PSLE Written exams | 24–30 Sep 2026 | ~29 |

---

## Phases

### Phase 0: Foundation (weeks 1–3)

Set up the project skeleton and data layer.

| Deliverable | Maps to (Architecture) |
|-------------|----------------------|
| Monorepo: frontend (React + TS), backend (TS), ingestion worker (Python) | Frontend, Application, Ingestion Pipeline |
| Postgres + pgvector, initial schema (skills, mastery, attempts, plans, rewards, events) | Data layer |
| Auth (Google OAuth) + API routing | API Gateway |
| Choose agent runtime: ADK or custom tool-calling loop | Agent runtime (see [TECH_STACK](./L2_TECH_STACK.md)) |

### Phase 1: Winston's Analytical Backbone (weeks 4–10)

**Goal:** Jarod has a data-driven co-pilot for tutoring Winston across all four PSLE subjects: **Math, English, Science, and Chinese**. The system knows what skills exist, where Winston is strong and weak, and generates targeted study plans.

**Primary user for Phase 1 is Jarod, not Winston.** The UI is a tutor/parent dashboard, not a kid chat interface.

| Deliverable | What it does | Maps to (Architecture) |
|-------------|-------------|----------------------|
| **Skill Graph** | Build from MOE syllabus + refined with worksheet content. Flat list first, prerequisite edges added incrementally. | Domain Model (Skill Graph) |
| **Ingestion Pipeline** | Upload worksheets/exams as PDFs → OCR → extract questions → tag each question to a skill. Manual tagging with LLM-assisted suggestions. | Ingestion Pipeline + Ingestion Agent |
| **Student Model** | Ingest Winston's scored worksheets → compute mastery per skill from historical results. Track attempts, error tags, and time patterns. | Student Model |
| **Diagnostic Engine** | Analyze patterns across attempts: which skills are weak, which error types recur, which topics to prioritize. Surface "Winston consistently loses method marks in fraction word problems." | Diagnostic Engine |
| **Planner Service** | Two modes: (1) **Session planner** — "1 hour of Math today, what should we work on?" based on mastery gaps + upcoming assessments. (2) **Horizon planner** — weekly/monthly arc working backwards from WA dates and PSLE. | Planner Service |
| **Tutor Dashboard** | Jarod's primary interface: skill map with mastery heatmap, diagnostic insights, today's recommended plan, upload workflow. | Frontend (parent/tutor view) |
| **Event logging** | Every plan generated, every assessment result logged, every skill update tracked. | Analytics / Logging |

**What Phase 1 deliberately skips:**

| Deferred feature | Why |
|-----------------|-----|
| Tutor Agent (AI tutoring chat) | Jarod is the tutor. The system's job is to inform his tutoring, not replace it. |
| Kid-facing chat UI | Winston interacts with the system through Jarod. A kid view comes in Phase 2. |
| Embedding-based retrieval | Keyword + metadata is sufficient when the corpus is small. |
| Gamification | Not needed when the tutoring is human-led. |
| Voice input/output | Winston can type/point; Jarod is present. |
| Automated question extraction | Manual tagging with LLM suggestions is fine for the initial corpus. Full automation in Phase 2. |
| LLM plan presentation | The planner outputs a structured plan for Jarod, not a kid-friendly narrative. |

### Phase 2: Independent Practice + Analytics (weeks 11–18)

**Goal:** Winston can practice independently when Jarod isn't available. Parents get visibility.

| Deliverable | Maps to (Architecture) |
|-------------|----------------------|
| Tutor Agent: hint ladder, teach-back, Socratic dialogue | Tutor Service + Tutor Agent |
| Kid UI: quest board, chat, upload, streaks + XP | Frontend (kid view) |
| Automated question extraction (template learning) | Ingestion Pipeline + Ingestion Agent |
| Embedding-based hybrid retrieval | Content Service |
| Parent dashboard: stats + LLM-generated weekly narrative | Analytics + Parent Coach Agent |
| Ingestion review UI (human-in-the-loop corrections) | Frontend |
| Answer-gating policies per child | Safety / Policy |

### Phase 3: Emma + Abigail (weeks 19+)

**Goal:** Age-appropriate experiences for younger children.

| Deliverable | Maps to (Architecture) |
|-------------|----------------------|
| Age-appropriate UI and tone (voice for Abigail, micro-quizzes for Emma) | Frontend + Tutor Agent |
| Voice input/output | Frontend |
| Cross-child analytics (family dashboard) | Analytics |
| Conversational parent agent | Parent Coach → full agent |
| Additional subjects + skill graph expansion | Domain Model (Skill Graph) |
| Richer gamification (badges, quest lines, team mode) | Frontend + Student Model |

---

## Fallback: Lightweight Tracking MVP

If the Skill Graph + Diagnostic Engine takes longer than expected, a simpler version still has value:

1. **Flat skill list** (no graph, no prerequisites) — manually curated from MOE syllabus topics
2. **Spreadsheet-grade tracking** — Jarod logs Winston's scores per topic after each session
3. **Simple priority scoring** — weakest skills first, weighted by exam relevance
4. **Calendar-aware reminders** — "WA is in 2 weeks, these topics haven't been reviewed"

This gives Jarod a structured, data-informed view of Winston's readiness without needing the full ingestion pipeline or diagnostic engine. Everything carries forward into the real system.

---

## Risks

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| **Skill graph construction across 4 subjects is a large upfront effort** | High | High | Start with flat skill lists from MOE syllabus topic headings per subject; add prerequisite edges incrementally; prioritize Math and Science (more structured) before English and Chinese (more diffuse) |
| **Question-to-skill tagging is too noisy** | Medium | High | Manual tagging with LLM suggestions; human-in-the-loop review; start with a small corpus and iterate |
| **Diagnostic insights are shallow without enough data** | Medium | Medium | Front-load by ingesting Winston's backlog of past worksheets (~4,000 pages); historical scores are the richest input |
| **Scope creep delays the analytical backbone** | High | High | Phase 1 is Jarod's dashboard, not Winston's app. No chat UI, no gamification, no kid-facing features. 4 subjects is ambitious — if needed, ship Math first and add subjects incrementally. |
| **Planner recommendations feel generic** | Medium | Medium | Start with simple priority scoring (weakest skill × exam weight × time-since-last-practice); iterate with Jarod's feedback |
| **MVP ships too late for Winston** | Medium | High | Fallback to lightweight tracking (see above); even manual skill tracking + priority scoring has value |

---

## Next Steps

1. **Resolve open questions** from [VISION](./L1_VISION.md) — especially subjects in scope for Phase 1 (Math + English?) and how existing PDFs are organized.
2. **Finalize tech stack** — language, agent runtime, database hosting. See [TECH_STACK](./L2_TECH_STACK.md).
3. **Build skill graphs for all 4 subjects** — start from MOE P6 syllabuses for Math, English, Science, and Chinese; create flat skill lists per subject; tag a few of Winston's recent worksheets against each to test granularity. Math and Science are more structured; English and Chinese will need more judgment on skill boundaries.
4. **Set up Postgres + pgvector** — define schema for skills, mastery, attempts, events.
5. **Build the ingestion pipeline** — start with 10–20 of Winston's recent Math worksheets; manual question extraction + skill tagging with LLM assist.
6. **Compute initial mastery profile** — from ingested scored worksheets, produce Winston's first skill-level competency snapshot.
7. **Build the session planner** — "1 hour of Math today" → ordered list of skills to work on, with specific practice questions from the corpus.
8. **Build the tutor dashboard** — Jarod's interface: skill map, mastery heatmap, diagnostic highlights, today's plan.
