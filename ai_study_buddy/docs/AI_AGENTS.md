# AI Study Buddy — AI Agent Design

> Status: **Exploratory** — options and recommendations, not final decisions.
>
> Sources: ChatGPT 5.2 Thinking conversation (3 Mar 2026), supplemented with independent research (Opus 4.6 Max, 4 Mar 2026).

---

## What "AI Agent" Means Here

An agent = **LLM + state + tool-calling + policies**.

- **LLM:** Understands the child's request, explains, asks good questions, adapts tone/level.
- **State:** Knows who (Winston/Emma/Abigail), current quest, current question, hint level, time spent.
- **Tools:** Calls backend services (retrieve chunks, fetch mastery profile, log attempts, generate plans, etc.).
- **Policies/guardrails:** "No direct answers for Abigail," "require teach-back," "don't reveal mark schemes."

The agent is the **"coach brain"** that orchestrates everything else. It's not "the whole system" — it's the decision-making layer that sits on top of deterministic services and uses them as tools.

---

## Why Agents (Not Just "RAG Chat Over PDFs")

| RAG-only | Agent + tools |
|----------|--------------|
| "Here's relevant text." | "You struggled with *this exact type* last month — let's fix the misconception." |
| Stateless | "I'll set tomorrow's quest to reinforce it with spaced practice." |
| No learning feedback | "You used 3 hints; mastery increases a little, not a lot." |
| Same for everyone | "For Abigail, I won't reveal answers — only guided steps." |

The agent makes it a study buddy, not a PDF chatbot.

---

## Agent Architecture: 4 Agents (Not 1 Giant Prompt)

### 1. Tutor Agent (kid-facing)

**Purpose:** Help learning on a specific question or skill.

**Tools it uses:**
- `retrieve(question_id | query)` → fetch question crop + relevant textbook snippet + similar past mistakes
- `get_student_model(child_id)` → mastery profile + misconceptions
- `log_attempt(...)` → correctness, hint usage, time spent
- `update_mastery(...)`
- `award_xp(...)`

### 2. Planner Agent (mostly deterministic + LLM for presentation)

**Purpose:** Produce the weekly/daily quest plan and adjust it when reality changes.

**Tools it uses:**
- `get_calendar(child_id)` → school terms, WA dates, exam dates
- `get_mastery(child_id)` → current skill mastery levels
- `generate_plan(...)` → deterministic scheduling code
- `explain_plan_in_kid_voice(...)` → LLM makes it fun and motivating

### 3. Ingestion/Extraction Agent (behind the scenes)

**Purpose:** For messy scanned pages, decide how to extract structure.

**Tools it uses:**
- `classify_pdf(digital vs scan)`
- `segment_page(page_image)`
- `extract_scorebox(crop)`
- `propose_skill_tags(question_text)`
- Emits `question_objects[]`

**Note:** This agent is invoked by the Python pipeline, not by kids.

### 4. Parent Coach Agent

**Purpose:** Summarize progress, flag risks, suggest interventions.

**Tools it uses:**
- `analytics_summary(child_id, timeframe)`
- `top_errors(child_id)`
- `upcoming_assessments(child_id)`
- Generates a short weekly narrative + next steps

---

## The Tutor Agent in Detail

### What it is

The tutor agent is a **controller for a tutoring session** — a stateful, iterative decision-maker, not a single prompt that answers.

**Simplest mental model:** a step function called repeatedly:

```
tutor_step(session_state, user_input) → {assistant_message, tool_calls, updated_state}
```

Called every time the child replies, until the session ends.

### Three layers inside the tutor

#### 1. Session State (stored in DB)

| Field | Description |
|-------|-------------|
| `child_id` | Which child |
| `question_id` | Current question (or "no question yet") |
| `hint_level` | 0, 1, 2, 3… |
| `attempt_count` | How many tries so far |
| `current_skill_target` | The skill being practiced |
| `time_spent` | Total session time |
| `answer_gating_policy` | Per-child rules (Abigail stricter than Winston) |

#### 2. Tools (backend functions it can call)

| Tool | Input | Output |
|------|-------|--------|
| `get_question(question_id)` | Question ID | Question crop/text |
| `retrieve_similar(skill_id)` | Skill ID | Similar practice items |
| `get_mastery(child_id, skill_id)` | Child + skill | Mastery score, confidence, misconceptions |
| `log_attempt(...)` | Attempt details | Confirmation |
| `update_mastery(...)` | New mastery data | Confirmation |
| `award_xp(...)` | XP amount + reason | Updated XP total |

#### 3. Decision Policy (hybrid: rules + LLM)

The policy decides the next action. Implementation options:

| Approach | Description | Trade-offs |
|----------|-------------|------------|
| **Rule-based** (state machine) | If hint_level == 0, ask diagnostic question; if hint_level == 2, show worked example | Predictable, testable; rigid |
| **LLM-based** | LLM chooses tool calls + next prompt each turn | Flexible, natural; less predictable |
| **Hybrid** (recommended) | Rules enforce guardrails and flow; LLM handles language + pedagogy | Best of both |

### The Tutor Loop (finite-state tutoring)

```
1. Diagnose     → What skill is being tested?
2. Prompt       → Socratic question ("What does 'remaining' refer to here?")
3. Hint ladder  → Tiny hint → Bigger hint → Worked example → Partial solution
4. Check        → Teach-back ("Explain your reasoning")
5. Update       → Log attempt → update mastery → tag misconception
```

### Example Session

**Turn 1 (agent):**
- tool: `get_question(...)`
- tool: `get_mastery(Winston, skill_guess)`
- decides: "Ask a diagnostic question first"
- output: "Before we calculate: what does 'remaining' refer to here?"

**Turn 2 (Winston answers):**
- detects misunderstanding
- output: Hint 1 (minimal nudge)
- state: `hint_level=1`

**Turn 3:**
- Winston tries an answer
- tool: `log_attempt(correct=false, error_tag="fraction-of-remainder")`
- decides: show worked example of a similar problem
- output: example + "Now you do step 1"

**End:**
- tool: `update_mastery(...)`
- tool: `award_xp(...)`
- optionally: `schedule_fixit_quest(...)` for tomorrow

---

## How Agents Map to ADK (if adopted)

| Concept | ADK implementation |
|---------|-------------------|
| Tutor Agent | `LlmAgent` with tools and system instruction |
| Session state | ADK `Session` + `state` scratchpad (with `{key}` templating) |
| Tool calls | ADK `Tool` with `ToolContext` for state reads/writes |
| Long-term memory | ADK `MemoryService` (or wrapping your DB) |
| Multi-agent routing | ADK multi-agent composition (Coordinator → Tutor / Planner / Coach) |
| Answer-gating | ADK `Plugin` for policy enforcement |
| Event logging | ADK `Events` (immutable records of all interactions) |

---

> [!NOTE]
> **Opus 4.6 Max analysis** — research-informed considerations on AI tutoring agent design.

### Socratic tutoring effectiveness

Recent research validates the Socratic tutoring approach proposed above:

- **LearnLM (Google DeepMind, 2025):** A pedagogically fine-tuned AI model showed that students guided by Socratic AI were **5.5 percentage points more likely to solve novel problems** on subsequent topics compared to human tutors alone (66.2% vs 60.7%). Importantly, human tutors approved 76.4% of the AI's pedagogical messages with zero or minimal edits. ([LearnLM paper, Nov 2025](https://storage.googleapis.com/deepmind-media/LearnLM/learnLM_nov25.pdf))

- **Socratic Mind (Georgia Tech, 2025):** AI-mediated Socratic questioning showed a "buffering effect" — reducing performance decline on increasingly difficult material by ~3.3 points. Students reported they "felt they learned more — and thought more." ([Socratic Mind Research, 2025](https://www.socraticmind.com/research/impact-student-learning-high-order-thinking-2025))

- **SocraticLM:** Uses a "Thought-Provoking" paradigm where AI engages through multi-round dialogue with hint ladders and guided questioning. Incorporates clarification questions, probing assumptions, and alternative perspectives. ([Proceedings, 2025](https://www.proceedings.com/content/079/079017-2721open.pdf))

### Known limitations of LLM tutors

1. **Accuracy on tutoring actions (~52–70%).** Current LLMs don't always choose the pedagogically optimal next step. The hybrid approach (rules for flow, LLM for language) mitigates this.

2. **Risk of "AI dependency" and false mastery.** If the AI makes learning too easy (always giving clear hints, always being patient), children may not develop independent problem-solving. Worse, they can appear to master a skill because the AI provided enough scaffolding to get the right answer, but they can't replicate it independently — the mastery score goes up while real understanding hasn't changed. Mitigations:
   - **Mastery requires unassisted success.** A skill's mastery score should increase more for correct answers without hints than with hints. After heavy hinting, the skill should be flagged for a follow-up "cold test" (no hints available) within 2–3 days.
   - **Teach-back as a mastery gate.** Before marking a skill as mastered, require the child to explain the concept in their own words. The LLM can assess the quality of the explanation.
   - **Spaced "cold checks."** Periodically test previously "mastered" skills without any scaffolding. If the child fails, the skill's mastery score drops and re-enters the practice queue.

3. **Tone calibration for young children.** An LLM tutor for a 7-year-old (Abigail) needs very different language than for an 11-year-old (Winston). The system instruction per child should include explicit reading-level and tone guidance.

4. **Math notation challenges.** LLMs can struggle with multi-step math workings (fractions, long division, model drawing). For math tutoring, the agent should rely heavily on **image-based question display** (showing the actual worksheet crop) rather than trying to render math in text.

### Design recommendations (Opus 4.6 Max)

1. **Start with the Planner Agent as a pure code service** (no LLM). The scheduling logic (spaced practice, calendar constraints, mastery-based prioritization) is entirely deterministic. Add LLM only for "presenting the plan in a fun way."

2. **The Tutor Agent should have a "confidence gate."** If the LLM is unsure what the child's error is, it should ask a clarifying question rather than guessing. Wrong diagnoses erode trust.

3. **Log everything the agent does** (tool calls, decisions, hints given, mastery updates). This creates a replayable audit trail for debugging and improving the system.

4. **Consider LearnLM as an alternative to generic Gemini.** Google's pedagogically fine-tuned model may produce better tutoring interactions than a general-purpose model. Worth evaluating when the tutor agent is built.

### Open Questions

1. **Should the tutor agent use a system prompt per child, or a single prompt with child context injected?** Per-child prompts are cleaner but harder to maintain; context injection is more flexible.
2. **How should the agent handle "I don't know" from the child?** Should it immediately give a bigger hint, or try a different angle first?
3. **Should the agent track emotional signals?** (e.g., short answers, fast quits, "I hate this") and adjust behavior accordingly.
