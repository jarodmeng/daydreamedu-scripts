# MVP 2 Plan: Daily Micro-Session (Meaning in Context)

Date: 2026-02-08  
Related doc: `Learning Functions Research & Brainstorming.md` (MVP notes + learning principles)  
Prerequisite: **MVP 1** (Pinyin Recall) — see `MVP1_Pinyin_Micro_Session_Plan.md`

---

## Why MVP 2 (and why after MVP 1)

Based on teaching experience, the **first barrier at the character level is pronunciation (pinyin + tone)**. Without being able to say a character, meaning recall is often fragile or misleading, especially because meaning depends on word/sentence context. Therefore:

- **MVP 1** tests **hanzi → pinyin** (pronunciation recall) first.
- **MVP 2** focuses on **meaning-in-context** once pronunciation is established.

MVP 1 can be shipped first as a smaller slice using the same backend scaffolding; MVP 2 builds on it.

---

## Goal (after MVP 1 validates pinyin recall)

Ship **MVP 2** that tests meaning in context using words/sentences:

- **Hanzi + word/sentence → meaning** (MCQ)
- **Meaning → hanzi** (MCQ)
- **Hanzi → pinyin** is retained but becomes a smaller mix

---

## Key differences from MVP 1

- Prompts require **context** (word or sentence) to avoid misleading "character-only meaning"
- Item metadata must include **example word/sentence**
- Distractors include **semantic confusions** and **context-aware lures**
- Analytics focus on **semantic confusions**, not only pinyin confusions

Everything else (scheduler, queue builder, logging, APIs) stays the same as MVP 1.

---

## Shared design (scheduler, queue, APIs)

MVP 2 reuses from MVP 1:

- **Scheduling**: same v0 stage ladder (see MVP 1 doc).
- **Queue builder**: due items + small number of new items; candidate pool and filters differ (meaning-ready items, context required).
- **Backend APIs**: same endpoint shape; `prompt_type` and `choices` content are meaning-focused.
- **Logging**: same event schema; analysis focuses on semantic confusions.

---

## Next step (recommended)

Lock MVP 1 scope and implement it first. Then use MVP 1 data to decide which character sets and contexts are most reliable for MVP 2.
