# VISION — Product Strategy and Direction

This document describes the product’s purpose, strategy, and future direction. For technical implementation see [ARCHITECTURE.md](ARCHITECTURE.md). For release history see [CHANGELOG.md](CHANGELOG.md).

---

## 1. Overview

The app helps **Singapore primary school students** learn **simplified Chinese**. The goal is to support both on-demand lookup (utility) and structured practice (learning) in a way that is **data-driven** and **customized** per logged-in user.

---

## 2. Two Pillars: Utility and Learning

### 2.1 Utility (reactive)

The user initiates the action when they have a specific need: find a character they haven’t seen, look up a character by pinyin, understand meanings, or see how to write a character. The app provides:

- Character search (by character or pinyin)
- Radicals and stroke-count browsing
- Stroke-order animation and dictionary (HWXNet) information
- Editable character metadata for the 冯氏早教识字卡 set

### 2.2 Learning (proactive)

The user uses the app as a **learning facilitator**, not only as a dictionary. This part is data-driven and game-like: short daily sessions, personalized queues, retrieval practice, and spaced repetition. The first shipped experience is **Pinyin Recall** (hanzi → pinyin-with-tone, with feedback and scheduling). Future experiences may include meaning-in-context, compound builder, and radical-based inference.

---

## 3. Product Characteristics

- **Data-driven:** Logging of key actions (character views, pinyin-recall events) supports analysis and iteration. Qualitative feedback (e.g. 报错) is captured where relevant.
- **Customized:** Each logged-in user has their own activity and learning state. Learning features (e.g. pinyin-recall queue, profile 未学字/在学字/已学字) are personalized by user.

---

## 4. Learning Loop (model)

Learning features are designed around a closed loop:

1. **Diagnose** — Infer skills and gaps from behavior and state.
2. **Select** — Choose the next items to practice (e.g. due reviews, limited new items).
3. **Practice** — Guided retrieval (e.g. MCQ with distractors, 我不知道 option).
4. **Feedback** — Immediate correctness and, where appropriate, a short learning moment.
5. **Schedule** — Update next encounter (spacing and cooling by score band).
6. **Measure** — Retention and transfer over time via events and outcomes.

Content is necessary, but the **loop** is the product: scheduling, feedback, and transfer practice differentiate the app from “more content” alone.

---

## 5. Product Vision (learning functions)

Build a **personalized Chinese practice loop** that turns short daily practice into durable gains in:

- **Reading** — Recognition and comprehension
- **Vocabulary** — Characters → words → sentences
- **Writing** — Optional; supported via a production path (e.g. stroke-order replay/tracing)
- **Pronunciation/tones** — Optional module; perception then production

The differentiator is **better scheduling, feedback, and transfer practice** using existing content and data.

---

## 6. Goals and North-Star Metric

### 6.1 Tangible goals (6–12 weeks)

- Establish a **daily practice habit** with 5–8 minute sessions that kids can complete independently.
- Show **durable retention** (not only same-day performance) on a meaningful slice of items.
- Show **transfer** in at least one dimension (e.g. radical-based meaning inference in new contexts, or new sentences using previously learned words).

### 6.2 North-star metric

**Retained items per active learner per week (30-day retention).**

An item counts as “retained” if the learner answers it correctly on a check **≥30 days** after first introduction (or first “learned” milestone), without hints. This optimizes for durability and is interpretable across cohorts and UX changes.

---

## 7. Design Principles (from research)

These principles guide learning-feature design:

1. **Make retrieval the default** — Quizzing drives learning; avoid “read more” as the primary action.
2. **Keep retrieval guided** — Prompts, partial cues, and progressive difficulty; avoid overload.
3. **Separate channels** — Recognition vs recall; perception vs production (e.g. handwriting supports writing recall more than pinyin typing; Chen et al.).
4. **Use substructure** — Radicals, phonetic components, morphemes, and confusion sets.
5. **Interleave for discrimination** — Mix related types where discrimination matters (e.g. tone pairs, visually similar characters).
6. **Prioritize time-on-task** — Low-friction sessions; motivation is designed in, not assumed.
7. **Instrument everything** — Events and outcomes so the system can be iterated.

Research implications used here include: retrieval practice and spacing (Carpenter et al.; Latimier et al.); semantic radicals and transfer (Nguyen et al.); morphological awareness and compounding (Marks et al.); tone training and English-dominant learners (Cao et al.); home language environment and “low Mandarin outside the app” (Li, Tan, & Goh); extensive reading and accountability (Sangers et al.). Detailed notes and references are in `docs/archive/research/Learning_Functions_Research_and_Brainstorming.md`.

---

## 8. Future Direction

### 8.1 Next learning experiences (after Pinyin Recall)

- **Meaning in context (MVP 2)** — Hanzi + word/sentence → meaning (MCQ); meaning → hanzi (MCQ). Pronunciation recall remains; meaning becomes a parallel strand. Requires context (word/sentence) for every prompt to avoid misleading character-only meaning.
- **Compound Builder** — Word-level practice using 词组 and dictionary examples; build vocabulary via morphology/compounding. Light “radical hint” prompts can support transfer without turning into standalone radical trivia.
- **Radical Detective (lightweight)** — Semantic category inference; teach radicals as categories and include transfer tasks. Must be tied to reading/context, not trivia.

### 8.2 Later candidates

- Character Mastery Loop (recognize → understand → recall → write), with handwriting/stroke-order production.
- Tone ear training (perception → production), tone-aware and adaptive.
- Graded micro-stories (read + optional listen), with level-matching and light accountability.

### 8.3 Open questions

- How much to prioritize writing (handwriting) vs recognition/reading.
- Whether to teach pinyin/tones as a “phonology first” pathway or keep phonology in support of reading.
- What forms of “accountability” work for kids without feeling like homework.

---

## 9. References

- **Archived research and plans:** `archive/research/`, `archive/plans/`, `archive/Product_Requirements_Doc.md` (under `docs/`). These hold the original PRD, learning-functions research, MVP1/MVP2 plans, and proposal history.
- **Current technical reality:** [ARCHITECTURE.md](ARCHITECTURE.md), `backend/DATABASE.md`.
