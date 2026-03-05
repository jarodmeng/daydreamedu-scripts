# AI Study Buddy — Architecture

> Status: **Exploratory** — options and recommendations, not final decisions.
>
> Sources: ChatGPT 5.2 Thinking conversation (3 Mar 2026), supplemented with independent research and analysis (Opus 4.6 Max, 4–5 Mar 2026).

---

## Design Principles

**1. Deterministic core, LLM surface.** State management, scheduling, scoring, and logging live in deterministic code (database queries, algorithms, rules). The LLM handles what it's uniquely good at: understanding questions, generating explanations, adapting tone, and making study plans feel fun. This means the data is always trustworthy even if the LLM occasionally picks a suboptimal tutoring step.

**2. Questions, not PDFs.** The system's atomic unit is the individual question — not the PDF or page it came from. Every worksheet is decomposed into question-level objects (text + image crop + skill tags + metadata). This keeps LLM context small, enables precise diagnostics ("Winston missed 3 of the last 5 fraction-of-remainder questions"), and makes retrieval accurate.

**3. Per-child everything.** Each child has their own student model, mastery levels, answer-gating rules, and tone profile. Winston (P6, preparing for PSLE) gets different content, difficulty, and autonomy than Abigail (P2, learning to read). This is not a configuration flag — it's a core data-model decision.

---

## System Overview

```
                ┌────────────────────────────────────────┐
  Frontend      │  Kid View  ·  Parent Dashboard  (PWA)  │
                └───────────────────┬────────────────────┘
                                    │
  Gateway                 API Gateway (Auth)
                                    │
                ┌───────────────────┴────────────────────┐
  Application   │  Tutor · Planner · Content  (services) │
                │  Diagnostic Engine · Safety / Policy    │
                └───────────────────┬────────────────────┘
                                    │
                ┌───────────────────┴────────────────────┐
  Data          │  Postgres · pgvector · Object Storage   │
                └────────────────────────────────────────┘

  Background:    Ingestion Pipeline
  Cross-cutting: Analytics / Event Logging
```

Four layers:

- **Frontend** — what kids and parents interact with.
- **Gateway** — authentication, rate limiting, routing.
- **Application** — services that handle requests + shared domain logic (diagnostics, safety rules). The Tutor and Planner services each embed an AI agent (LLM + tools + state) for decision-making.
- **Data** — Postgres for structured data and the event log, pgvector for content embeddings, object storage for files.

The **Ingestion Pipeline** is a background job that processes uploaded PDFs — it lives at the application layer but runs asynchronously. **Analytics / Logging** is cross-cutting — every service emits events to an append-only log in Postgres.

---

## Components

### Frontend (React PWA)

Two views in a single app:

- **Kid view:** Chat interface for tutoring sessions. Daily quest list. Streaks and XP. Camera/upload for question photos.
- **Parent view:** Progress dashboard per child. Weekly narrative summary. Upcoming assessment calendar. Configuration knobs (study time budget, answer-gating strictness).

### API Gateway

Authentication (Google OAuth), rate limiting, and routing. All client requests pass through here before reaching the application layer.

### Tutor Service

The core kid-facing component. When a child asks a question or starts a quest:

1. Creates a **tutoring session** (persisted in Postgres — survives page reloads)
2. Invokes the **Tutor Agent**, an LLM with tools, session state, and pedagogical policies

The agent runs a step function on each child message:

```
tutor_step(session_state, child_input) → {response, tool_calls, updated_state}
```

Each step follows a tutoring loop:

1. **Diagnose** — What skill is being tested? What does the child already know?
2. **Prompt** — Socratic question ("What does 'remaining' refer to here?")
3. **Hint** — Tiny hint → bigger hint → worked example → partial solution
4. **Check** — Teach-back ("Explain your reasoning in your own words")
5. **Update** — Log attempt → update mastery → tag misconception → award XP

The agent calls backend tools (retrieve content, check mastery, log attempts, award XP) but doesn't do computation itself. Deterministic rules enforce the flow and guardrails; the LLM handles language and pedagogy. See [AI_AGENTS.md](./L2_AI_AGENTS.md) for the full agent design.

### Planner Service

Decides what each child should study and when.

**Inputs:** School calendar (terms, WA/exam dates), skill mastery levels, available study time, forgetting risk (time since last practice), exam weighting.

**Outputs:** Weekly study plan (focus + review + timed practice), daily "quests" (20–40 min), auto-adjustments when a child struggles or misses a day.

The scheduling logic is entirely deterministic — spaced practice algorithms, calendar constraints, priority scoring over mastery gaps. The Planner Agent (LLM) is only used to present the plan in a motivating, kid-friendly voice. See the evidence base for spaced practice in [VISION.md](./L1_VISION.md).

### Content Service

Finds relevant question objects, textbook chunks, or similar past attempts when the Tutor or Planner needs them. Uses hybrid retrieval: metadata filters (child, subject, skill) + keyword match ("Q6", "Section B") + embedding similarity. Hybrid matters because educational content needs exact matching as much as semantic search.

### Ingestion Pipeline

A background job that turns uploaded PDFs into the structured, searchable question objects that the rest of the system operates on.

1. Render pages to images, run OCR on scans
2. Layout segmentation — detect question boundaries
3. Extract or manually tag metadata (subject, date, score, child)
4. Store: question text + image crop → Postgres, embedding → pgvector, raw files → object storage

For messy scanned worksheets, the **Ingestion Agent** (LLM) handles structure extraction that rules-based processing can't. See [DATA_STRATEGY.md](./L3_DATA_STRATEGY.md) for the full pipeline.

### Diagnostic Engine

Analyzes patterns across a child's attempt history to surface systematic weaknesses:

- **What** question types each child misses
- **Why** they miss — careless error, concept gap, misread question, weak vocabulary, missing method marks
- **Whether** errors repeat across weeks and months

Example outputs:

- "Winston: consistent loss of method marks in Math Paper 2 (units, model drawing, incomplete explanation)"
- "Emma: English editing errors cluster around tenses + pronouns"
- "Abigail: reading fluency + sight-word gaps"

Feeds into the Planner (which skills to prioritize), the Tutor (which misconceptions to address), and the Parent Dashboard (what to flag). Depends heavily on extraction quality — if question-level extraction is noisy, diagnostics degrade.

### Analytics / Logging

Every service emits structured events to an append-only log in Postgres:

`question_attempted` · `hint_requested` · `plan_generated` · `task_completed` · `session_abandoned` · `frustration_signal` · `reward_granted`

Two outputs for parents:

- **Dashboard (deterministic).** Charts and stats derived from the event log: top weak skills, fastest-improving skills, predicted assessment readiness, consistency streaks.
- **Weekly narrative (LLM-generated).** A short, readable digest per child — what they worked on, where they improved, and what to watch for. Generated by passing structured analytics data through an LLM, not a multi-turn agent.

Future upgrade path: the parent-facing service could evolve into a conversational agent where parents ask follow-up questions ("Why did Winston's math score drop?", "Should we focus more on English?"). See [USER_EXPERIENCE.md](./L3_USER_EXPERIENCE.md).

### Safety / Policy

Rules enforced across all services:

- **Answer-gating** — per-child controls on how much help the AI provides. Abigail (P2) gets strict scaffolding; Winston (P6) gets more autonomy.
- **Content rules** — child-appropriate language and behavior from all agents.
- **Data protection** — Singapore PDPA compliance.

See [SAFETY_AND_PRIVACY.md](./L3_SAFETY_AND_PRIVACY.md).

---

## How Agents Connect to Data

An LLM can only generate text — it can't query a database or read a file directly. The connection between agents and the data layer works through **tool-calling**:

```
1. Service receives user request, loads session state
2. Sends the LLM: system prompt + conversation history + available tool schemas
3. LLM responds with either:
   (a) a text message for the user, or
   (b) a tool call: "call get_mastery(child_id=winston, skill_id=fractions)"
4. Service executes the tool against the real backend (DB query, vector search, etc.)
5. Sends the tool result back to the LLM
6. Repeat from step 3 until the LLM produces a text response
```

Each agent has a set of **tools** — small functions that wrap database queries, vector searches, or storage reads and are exposed to the LLM through typed schemas. The LLM decides *which* tools to call and *with what arguments*; the backend executes them and returns results. The data layer never talks to the LLM directly.

For example, the Tutor Agent's runtime looks like:

```
Tutor Service
  └─ Agent Runtime
       ├─ LLM (Gemini / LearnLM) — generates responses and tool call requests
       ├─ Tool Executor — runs tool functions against the data layer
       │    ├─ get_mastery()       → Postgres query
       │    ├─ retrieve_similar()  → pgvector similarity search
       │    ├─ get_question()      → Postgres + Object Storage read
       │    ├─ log_attempt()       → Postgres write
       │    └─ award_xp()          → Postgres write
       └─ Session Store — persists conversation + state between HTTP requests
```

The **agent runtime** (the box that manages the tool-calling loop, session persistence, and schema validation) can be built with **Google ADK** (Agent Development Kit) or as a custom implementation. See [TECH_STACK.md](./L2_TECH_STACK.md) for the ADK maturity assessment and alternatives. See [AI_AGENTS.md](./L2_AI_AGENTS.md) for the ADK mapping and tool schemas per agent.

---

## AI Agents

The system uses four specialized agents, not one monolithic prompt:

| Agent | Purpose | User-facing? | LLM role |
|-------|---------|-------------|----------|
| **Tutor** | Guide kids through problems via Socratic dialogue | Yes (chat) | Core — hints, explanations, teach-back |
| **Planner** | Schedule study sessions and daily quests | Indirectly (quests) | Minimal — present the plan in a fun voice |
| **Ingestion** | Extract structure from messy scanned PDFs | No | Assist — handle edge cases rules can't |
| **Parent Coach** | Generate weekly progress narrative per child | Yes (dashboard) | Core — summarize analytics into readable digest |

The Tutor is the most complex agent (multi-turn, stateful, tool-calling in a feedback loop). The Parent Coach is the simplest (one-shot LLM call over structured analytics data). All four are tracked as agents because each involves LLM-generated content that needs prompt management, quality monitoring, and cost tracking.

See [AI_AGENTS.md](./L2_AI_AGENTS.md) for the detailed agent design, including the Tutor loop, session state schema, decision policies, and known limitations of LLM tutors.

---

## Domain Model

### Skill Graph

A directed graph of skills per subject, aligned to Singapore MOE syllabuses:

- **Nodes:** individual skills (e.g. Math → Fractions → Add unlike fractions)
- **Edges:** prerequisite relationships (can't add unlike fractions before finding common denominators)

The graph makes planning computable — "what should Winston practice next?" becomes a traversal over mastery gaps and prerequisites rather than a guess.

For Math, MOE publishes the Primary 1–6 syllabus. Primary 6 uses the 2021 syllabus from 2026 onwards. ([MOE Syllabus PDF](https://www.moe.gov.sg/api/media/92bff26d-b2b4-4535-b868-b8415c744b91/2021-Primary-Mathematics-Syllabus-P1-to-P6-Updated-October-2025.pdf))

### Student Model

Per-child state that tracks learning:

```
skills(skill_id, subject, grade, prerequisites…)
mastery(child_id, skill_id, score, confidence, last_practiced)
attempts(child_id, question_id, skill_id, correct, error_tags, hints_used, time_spent, ts)
misconceptions(child_id, error_tag, examples, frequency, last_seen)
plans(child_id, week, tasks, status, outcomes)
rewards(child_id, xp, badges, streaks, inventory…)
```

**Mastery estimation** starts simple — rolling average over recent attempts, weighted by hint usage — and can evolve to Bayesian Knowledge Tracing or Elo-like scoring once there's data to validate.

### Event Log

An append-only Postgres table capturing every interaction. Start simple; upgrade to a proper event pipeline if volume demands it. Consider **event sourcing** — storing every event and computing mastery as a derived view makes it easy to re-derive mastery when the estimation algorithm improves.

---

## Data Stores

| Store | Technology | Contents |
|-------|-----------|---------|
| Structured DB | Postgres | Skills, mastery, attempts, misconceptions, plans, rewards, event log |
| Vector Index | pgvector (same Postgres instance) | Embeddings for question objects and textbook chunks |
| Object Storage | GCS or local filesystem | Raw PDFs, page images, question image crops |

---

## Key Workflows

### 1. PDF Ingestion

```
Parent uploads PDF
  → Pipeline renders pages, runs OCR on scans
  → Layout segmentation detects question boundaries
  → Metadata extracted or manually tagged (subject, date, score, child)
  → Each question stored: Postgres + pgvector + Object Storage
```

### 2. Tutoring Session

```
Child asks a question or starts a quest
  → Tutor Service creates session, invokes Tutor Agent
  → Agent retrieves: question, child's past mistakes, relevant textbook content
  → Hint ladder: diagnose → prompt → hint → check → teach-back
  → Each attempt: log → update mastery → award XP
  → Planner optionally adjusts upcoming quests
```

### 3. Weekly Planning

```
Planner Service runs (scheduled or on-demand)
  → Reads: upcoming assessments, mastery gaps, time budget
  → Deterministic scheduling: prioritize skills, allocate to days, apply spaced practice
  → LLM wraps plan in kid-friendly quest framing
  → LLM generates weekly narrative summary for parents
```

---

## Risks

1. **Skill graph is a large upfront effort.** A complete prerequisite-linked graph for 4+ subjects across P1–P6 is non-trivial. Start with a flat skill list and add edges incrementally.

2. **Mastery estimation is an open problem.** Rolling averages are a pragmatic start, but they're crude. More sophisticated models need data to validate. Ship simple, iterate with data.

3. **Diagnostic quality depends on extraction quality.** If question-level OCR and segmentation from scanned worksheets is noisy, the entire diagnostic pipeline degrades. Budget for human-in-the-loop review in the early months.

4. **LLM tutoring accuracy is imperfect.** Current models choose the pedagogically optimal next step roughly 52–70% of the time. The hybrid approach (deterministic rules for flow, LLM for language) mitigates this. The agent should have a confidence gate — when unsure about a child's error, ask a clarifying question rather than guessing wrong.

5. **False mastery from over-scaffolding.** Heavy AI scaffolding can make a child appear to master a skill they can't replicate independently — the score goes up but real understanding hasn't changed. Mitigations: weight unassisted correct answers higher than heavily-hinted ones; schedule periodic "cold checks" (no hints available) on mastered skills where failure drops mastery back into the practice queue; require teach-back (child explains the concept in their own words) before marking a skill as fully mastered.

6. **Math notation is hard for LLMs.** Fractions, long division, and model drawing don't survive text formatting. The Tutor should show the actual worksheet crop (image) rather than trying to render math in chat.

7. **Answer-gating policies should be per-child, not global.** Consider feature flags per child so policies can evolve as each child matures, rather than hard-coding rules.
