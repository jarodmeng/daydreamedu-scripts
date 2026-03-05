# AI Study Buddy — Vision & Goals

> Status: **Exploratory** — options and recommendations, not final decisions.
>
> Sources: ChatGPT 5.2 Thinking conversation (3 Mar 2026), supplemented with independent research (Opus 4.6 Max, 4 Mar 2026).

---

## What is the AI Study Buddy?

A personalized AI agent that acts as a **learning coach** — not a homework-completion tool — for three children in Singapore's primary school system:

| Child | Grade (2026) | Key milestone | Timeline |
|-------|-------------|---------------|----------|
| Winston | Primary 6 | PSLE | ~6 months (Sep 2026) |
| Emma | Primary 4 | End-of-year exams | ~8 months (Oct 2026); PSLE in ~2.5 years |
| Abigail | Primary 2 | End-of-year exams | ~8 months (Oct 2026); PSLE in ~4.5 years |

The agent should feel like a **smart second brain + coach**: it plans, teaches, remembers, adapts, and motivates.

---

## Core Design Principles

### 1. Learning over completion

The emphasis is on **learning** — when a child innately understands knowledge and skills and can confidently apply them — not on "finishing homework." The agent should optimize for durable understanding, not throughput.

### 2. Smart multi-horizon planning

Planning across multiple time horizons, from daily study sessions to long-term exam preparation:

| Horizon | Example |
|---------|---------|
| **Lifetime** | Aspirational (deferred) |
| **PSLE / major exam** | 6 months (Winston) to 4.5 years (Abigail) |
| **Current school year** | End-of-year exams in Oct |
| **Term / weighted assessment** | End-of-term WA cycles |
| **Weekly** | Focus skills + review skills + timed practice |
| **Daily** | 20–40 minute "quests" |

### 3. Long memory

The agent should accumulate and efficiently access data over months and years — remembering each child's mistake patterns, growth trajectories, and learning preferences. This implies both **document memory** (searchable content from PDFs) and **structured memory** (mastery scores, attempt logs, misconception tags).

### 4. Data-driven iteration

Every interaction should produce structured logs so that improvement comes from **data analysis**, not intuition alone. This includes session events, attempt outcomes, mastery updates, and motivation signals.

### 5. Gamification

The children respond strongly to game-like elements — progress tracking, streaks, challenges, rewards. Gamification should be a first-class design concern, not an afterthought. (See [GAMIFICATION.md](./L3_GAMIFICATION.md) for detailed design.)

---

## PSLE 2026 Timeline (verified)

Winston's PSLE dates (from [MOE 2026 PSLE Exam Calendar](https://file.go.gov.sg/2026-psle-exam-cal.pdf)):

- **Oral:** 12–13 Aug 2026
- **Listening Comprehension:** 15 Sep 2026
- **Written papers (Block 1):** 24–25 Sep 2026
- **Written papers (Block 2):** 28–30 Sep 2026

This gives a concrete ~6–7 month runway from today (4 Mar 2026) for Winston's preparation. The planner can work backwards from these dates with revision cycles, timed practices, and targeted remediation.

---

## What to Digitize (data inputs)

Already available:
- **Worksheets** (scanned PDFs) — some with handwritten workings and teacher markings/scores; some blank. Estimated ~4,000 pages currently, growing ~500 pages/month.

Planned for digitization:
- **Textbooks and teaching materials** — shows what has been taught
- **MOE curriculum documents** — shows high-level government/school learning goals
- **School calendar** — term structure and assessment schedules

Additional high-value data suggested (ChatGPT):
1. **Baseline diagnostic tests** per subject (even 30–45 min each)
2. **Writing samples over time** (composition + situational writing)
3. **Reading aloud audio** (fluency, pronunciation, confidence)
4. **Parent observation journal** (quick tags: "careless", "rushing", "avoids hard questions")
5. **Tuition worksheets / past-year papers** by topic (taggable training set)

---

## Learning Philosophy

> [!NOTE]
> **Opus 4.6 Max analysis** — independent research on the evidence base for the learning strategies proposed.

The ChatGPT conversation recommended **spaced practice + retrieval practice** as core learning strategies. The evidence supports this:

### Spaced retrieval practice

- A 2025 meta-analysis on mathematics learning found spaced practice improves learning with effect sizes of *g* = 0.28 (overall) and *g* = 0.43 (isolated practice). ([Springer, 2025](https://link.springer.com/article/10.1007/s10648-025-10035-1))
- Spaced retrieval practice vs. massed retrieval showed a strong effect (*g* = 0.74). ([ERIC, 2021](https://eric.ed.gov/?id=EJ1310148))
- A 2025 study confirmed that retrieval practice enhances learning in real primary school settings, with 5th graders showing improved long-term retention vs. re-reading. ([Frontiers in Psychology, 2025](https://www.frontiersin.org/journals/psychology/articles/10.3389/fpsyg.2025.1632206/full))

**Caveat:** In real classroom settings, manipulating exact spacing intervals did not always yield significant differences, suggesting the system should focus on *ensuring regular spaced review happens* rather than obsessing over precise interval optimization.

### Socratic tutoring with AI

- A UK RCT found students guided by LearnLM (a pedagogically fine-tuned AI) were **5.5 percentage points more likely to solve novel problems** compared to human tutors alone (66.2% vs 60.7%). ([Google DeepMind, LearnLM paper, 2025](https://storage.googleapis.com/deepmind-media/LearnLM/learnLM_nov25.pdf))
- AI-mediated Socratic dialogue promoted higher-order thinking: students "felt they learned more — and thought more." ([Socratic Mind Research, 2025](https://www.socraticmind.com/research/impact-student-learning-high-order-thinking-2025))
- **Limitation:** Current LLMs achieve ~52–70% accuracy on tutoring next-step actions. Human expert supervision improved reliability, with tutors approving 76.4% of AI messages with zero/minimal edits. This suggests a **human-in-the-loop** review mechanism is important, especially early on.

### AI tutoring systems in K–12

- A systematic review of 28 studies (4,597 students) found AI-driven intelligent tutoring systems have **generally positive but modest effects** on K–12 learning (*g* = 0.271). ([Nature npj Science of Learning, 2025](https://www.nature.com/articles/s41539-025-00320-7))
- Low-achieving students benefited consistently.
- Worked-out examples and longer intervention durations improved outcomes.
- Most research is STEM-focused; less evidence exists for language arts tutoring.

**Implication for design:** The agent should combine AI tutoring with strong **guardrails against false mastery** (kids thinking they know because the AI made it easy). Teach-back, confidence rating, and requiring explanation before revealing answers are evidence-supported safeguards.

---

## Traits and Features Summary

| Trait | Description | Priority |
|-------|-------------|----------|
| Smart planning | Multi-horizon, calendar-aware, adapts to reality | High |
| Learning-focused tutoring | Socratic, hint ladder, teach-back, error diagnosis | High |
| Long memory | Structured student model + document retrieval | High |
| Data logging | Event stream for every interaction | High |
| Gamification | XP, quests, streaks, badges, team mode | High |
| Multi-modal input | Image upload, camera scan, voice (especially for Abigail) | Medium |
| Parent dashboard | Weekly summaries, risk flags, control knobs | Medium |
| Safety / answer-gating | Age-appropriate policies per child | High |
| Privacy compliance | Singapore PDPA for children | High |

---

## Open Questions

These questions (originally posed by ChatGPT) remain unanswered and should be resolved as the project progresses:

1. **Subjects in scope:** Which subjects per child first? (English, Math, Science, Mother Tongue?) Which Mother Tongue(s)?
2. **Answer policy:** Strictly "no answers," or "answers allowed after hints + teach-back"?
3. **Devices:** iPad, laptop, phone? (Drives UX: voice, handwriting input, session length.)
4. **PDF organization:** How are existing PDFs organized — by date/subject/child, or mixed? Any filenames that encode metadata?
5. **Calendar integration:** Should the planner schedule actual calendar blocks + send reminders, or just generate plans?
6. **PSLE readiness score:** Should the system produce a per-component readiness score (Oral/LC/Written)?
7. **Motivator currency:** What works at home — screen time, treats, privileges, badges, family points?
