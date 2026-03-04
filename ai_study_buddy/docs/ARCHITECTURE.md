# AI Study Buddy — Architecture

> Status: **Exploratory** — options and recommendations, not final decisions.
>
> Sources: ChatGPT 5.2 Thinking conversation (3 Mar 2026), supplemented with independent analysis (Opus 4.6 Max, 4 Mar 2026).

---

## Design Philosophy

The core architectural principle (from ChatGPT) is to **split the brain into two parts**:

- **Deterministic core** (databases, planners, rules, analytics) — reliable, testable, auditable.
- **LLM layer** (understanding, explanation, conversation) — flexible, kid-friendly, multimodal.

This separation prevents the system from becoming a "hallucination-driven blob" and keeps planning, scoring, and logging predictable.

---

## High-Level System Diagram

(From ChatGPT, with minor formatting edits.)

```
            ┌─────────────── UI (Kid / Parent) ───────────────┐
            │  chat, voice, upload, quests, dashboard, streaks │
            └───────────────┬──────────────────────────────────┘
                            │
                     API Gateway (Auth + Rate limits)
                            │
      ┌─────────────────────┼─────────────────────┐
      │                     │                     │
Planner Service        Tutor Service          Content Service
(schedules,            (Socratic hints,       (RAG retrieval,
spaced practice,       rubrics, feedback)     textbook/worksheet Q&A)
calendar)                    │                     │
      │                      │                     │
      └───────────────┬──────┴─────────┬───────────┘
                      │                │
                Student Model      Safety/Policy
           (mastery + misconceptions) (answer-gating, child rules)
                      │
              Analytics / Logging
         (events → metrics → insights)
                      │
     ┌────────────────┴───────────────────┐
     │                                     │
Structured DB (Postgres)          Search/Vector Index (pgvector)
(skills, attempts, plans,         (worksheet chunks, textbook chunks,
calendar, rewards)                 question bank, embeddings)
     │                                     │
Object Storage (GCS/local)  ← stores PDFs/images/audio/video artifacts
```

---

## The 6 Modules

### 1. Curriculum & Skill Map ("the spine")

A **skill graph** per subject, aligned to MOE syllabuses and what the school actually teaches.

- **Nodes:** individual skills (e.g., Math → Fractions → Add unlike fractions; English → Editing → Subject-verb agreement)
- **Edges:** prerequisite relationships
- **Attachments:** examples, worked solutions, common misconceptions, and each child's historical mistakes

For Math, MOE publishes the Primary 1–6 syllabus. Note that **Primary 6 uses the 2021 Math syllabus from 2026 onwards**. ([MOE Syllabus PDF](https://www.moe.gov.sg/api/media/92bff26d-b2b4-4535-b868-b8415c744b91/2021-Primary-Mathematics-Syllabus-P1-to-P6-Updated-October-2025.pdf))

**Why this matters:** Planning becomes computable ("what should Winston do next?") instead of vibes.

### 2. Content Memory (RAG retrieval)

PDFs become queryable knowledge through two sub-systems:

**A. Document memory** — ingested PDF content (worksheets, textbooks) stored as searchable chunks with metadata (child, subject, date, score, etc.). See [DATA_STRATEGY.md](./DATA_STRATEGY.md).

**B. Structured learning memory (student model)** — relational tables, not embeddings:

| Table | Purpose |
|-------|---------|
| `skill_mastery` | child × skill → mastery estimate, confidence, last practiced |
| `attempts` | child × question → outcome, error tags, hints used, time spent |
| `misconceptions` | child × error pattern → examples, frequency, last seen |

### 3. Diagnostic Engine

The **teacher markings + scores** on worksheets are the goldmine. The system should extract:
- What question types each child misses
- *Why* they miss (careless, concept gap, misread question, weak vocabulary, method marks missing)
- Whether errors repeat across months

Example diagnostic outputs:
- "Winston: consistent loss of method marks in Math Paper 2 (units, model drawing, incomplete explanation)"
- "Emma: English editing errors cluster around tenses + pronouns"
- "Abigail: reading fluency + sight-word gaps"

### 4. Multi-Horizon Planner

**Inputs:** calendar (terms + WA/exams), available study time, skill mastery estimates, exam weighting, forgetting risk (time since last practice).

**Outputs:** weekly plan (focus + review + timed practice), daily "quests" (20–40 min), auto-adjustment when a child struggles or misses a day.

**Key design choice (ChatGPT):** The planner should prefer **spaced practice + retrieval practice**, not cramming. See the evidence review in [VISION.md](./VISION.md).

### 5. Tutor / Coach Behaviors

Optimize for *learning*, not completion:

| Behavior | Description |
|----------|-------------|
| **Socratic mode** | Ask targeted questions, reveal hints progressively |
| **Worked example + fading** | Show a solved example, then remove steps |
| **Error diagnosis** | "Which step is wrong?" / "What assumption did you make?" |
| **Teach-back** | Child explains; system checks clarity + missing pieces |
| **Metacognitive prompts** | Confidence rating, "what was confusing?", "what will you do next time?" |

See [AI_AGENTS.md](./AI_AGENTS.md) for the detailed agent design.

### 6. Logging & Analytics

Every interaction produces structured event logs:
- `session_start/end`, `time_spent`
- `question_attempt`, `hint_used`, `correctness`
- `mastery_update`
- `motivation_signals` (quit early, frustration markers)

These feed a **parent dashboard** showing: top weak skills, fastest-improving skills, predicted readiness, consistency streaks. See [USER_EXPERIENCE.md](./USER_EXPERIENCE.md).

---

## Data Architecture: "Two Memories" + "One Event Stream"

### A. Document Memory (RAG)

Per asset:
- Raw PDF / page images
- Extracted text (OCR or native)
- Layout metadata (page → blocks → question regions)
- Tags: child, subject, date, assessment type, score

Indexed for hybrid retrieval (metadata filters + keyword + embeddings), chunked per question (not arbitrary 800-token chunks), with image pointers preserved.

### B. Structured Learning Memory (Student Model)

```
skills(skill_id, subject, grade, prerequisites…)
attempts(child_id, question_id, skill_id, correct, error_tags, hints_used, time_spent, timestamp)
mastery(child_id, skill_id, mastery_score, confidence, last_practiced)
misconceptions(child_id, tag, examples, last_seen)
plans(child_id, week, tasks, status, outcomes)
rewards(child_id, xp, badges, streaks, inventory…)
```

### C. Event Stream (Logging)

Events: `question_attempted`, `hint_requested`, `plan_generated`, `task_completed`, `session_abandoned`, `frustration_signal`, `reward_granted`.

Start simple (append-only Postgres table), upgrade to a proper event pipeline later if needed.

---

## Core Workflows

### Workflow A: Ingestion (PDF → structured + searchable)

1. Upload PDFs
2. Page rendering + OCR (for scans; keep images for handwriting)
3. Layout segmentation (detect question boundaries, mark regions)
4. Metadata extraction (subject/date/score; manual override UI)
5. Indexing (keyword + embedding) + artifact storage

See [DATA_STRATEGY.md](./DATA_STRATEGY.md) for full details.

### Workflow B: Tutoring Session

1. Child asks a question or uploads a page photo
2. Tutor retrieves: the exact question region, similar past mistakes, relevant textbook chunk
3. Tutor runs a hint ladder + checks understanding
4. Logs attempt → updates mastery → awards XP
5. Planner optionally adjusts upcoming tasks

### Workflow C: Weekly Planning

1. Planner reads: upcoming assessments, mastery gaps, time budget
2. Generates a plan
3. Outputs daily quests (short, game-like)
4. Parent Coach summarizes + provides control knobs

---

## Deployment Options

(From ChatGPT.)

| Option | Description | Trade-offs |
|--------|-------------|------------|
| **Fast + practical** (recommended start) | Postgres + pgvector, GCS, Cloud Run, hosted multimodal LLM, simple web UI | Fastest to MVP; some cloud dependency |
| **Max privacy / self-host** | Local OCR + local embedding + local LLM, own server/NAS | Full control; quality may be lower, more ops burden |
| **Hybrid** | All data local; send only minimal de-identified snippets to cloud LLM; cache aggressively | Good balance; more complex to build |

---

> [!NOTE]
> **Opus 4.6 Max analysis** — architectural considerations beyond the ChatGPT conversation.

### Strengths of this architecture

1. **Separation of deterministic and LLM layers** is sound. It avoids the common trap of making the LLM responsible for state management, which leads to drift and hallucination.
2. **Question objects as the atomic unit** (not PDFs or pages) is the right abstraction. It keeps token usage bounded and enables precise diagnostics.
3. **Hybrid retrieval** (metadata + keyword + embedding) is well-suited for educational content where exact matching ("Q6", "Section B") matters as much as semantic similarity.

### Risks to watch

1. **Skill graph construction is a large upfront effort.** Building a complete, prerequisite-linked skill graph for 4+ subjects across P1–P6 is non-trivial. Consider starting with a flat skill list and adding edges incrementally.
2. **Mastery estimation is an open problem.** Simple rolling averages over recent attempts can be a pragmatic start, but more sophisticated models (e.g., Bayesian Knowledge Tracing, or even simplified Elo-like systems) should be explored once there's enough data.
3. **The diagnostic engine depends heavily on extraction quality.** If question-level extraction from scanned worksheets is noisy, the whole diagnostic pipeline degrades. Budget for human-in-the-loop review, especially in the early months.

### Alternative architecture patterns to consider

- **Event sourcing** for the student model: rather than updating mastery in place, store every event and compute mastery as a derived view. This makes it easy to replay and re-derive mastery if the estimation algorithm improves.
- **Feature flags per child** for the tutor behavior: instead of hard-coding answer-gating policies, make them configurable per child so they can evolve as each child matures.
