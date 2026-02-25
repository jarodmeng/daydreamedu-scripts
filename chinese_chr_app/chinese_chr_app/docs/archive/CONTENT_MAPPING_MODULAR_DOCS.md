# Content Mapping: Frankendoc → Modular Structure

**Status:** Implemented  
**Date:** 2025-02-25  

**Purpose:** Map existing documentation into the target modular structure and anchor it to **ground truth** (code + git history). This document was the reference for the refactor; the refactor is complete and the modular docs (README, VISION, ARCHITECTURE, CHANGELOG) are in place.

**Target structure:**
- **README.md** (Receptionist) — Project summary, Quick Start/Setup, Table of Contents to other docs
- **VISION.md** (The Why) — Core logic, business requirements, user stories, future/planned
- **ARCHITECTURE.md** (The How) — Technical specs, schemas, system flow; **must match code**
- **CHANGELOG.md** (The History) — Chronological record; **should be derivable from git log**

---

## 0. Ground truth: Code and git (anchor for Architecture and Changelog)

**Rule:** Implemented-feature reality lives in the codebase. Docs (especially ARCHITECTURE and CHANGELOG) should be validated against this ground truth.

### 0.1 Code: Where “current technical reality” lives

| Area | Source of truth (paths under `chinese_chr_app/chinese_chr_app/`) | What to verify in ARCHITECTURE |
|------|-------------------------------------------------------------------|---------------------------------|
| **API routes** | `backend/app.py` — `@app.route` for `/api/characters/search`, `/api/pinyin-search`, `/api/images/`, `/api/strokes`, `/api/radicals`, `/api/stroke-counts`, `/api/profile`, `/api/profile/progress`, `/api/profile/progress/category/<category>`, `/api/games/pinyin-recall/session`, `next-batch`, `answer`, `report-error`, `/api/log-character-view`, `/api/health` | API list and method/contracts must match these routes. |
| **Auth** | `backend/auth.py` — `verify_bearer_token`, `extract_bearer_token`; `app.py` uses Bearer for profile and pinyin-recall | ARCHITECTURE: when auth is required. |
| **Data loading** | `backend/app.py` — `load_characters()`, `load_hwxnet()`; JSON vs DB via `USE_DATABASE` and `database.py` | Data sources (Feng, HWXNet, level-*.json) and when DB is used. |
| **Pinyin recall: constants** | `backend/database.py` — `PINYIN_RECALL_SCORE_*`, `PINYIN_RECALL_COOLING_*`, `PROFILE_PROFICIENCY_MIN_SCORE` (10), `PROFILE_LEARNING_HARD_MAX_SCORE` (-20), `PROFILE_LEARNED_MASTERED_MIN_SCORE` (20), `PROFILE_HWXNET_TOTAL` (3664) | Score range (−50–100), deltas (+10/−10), proficiency threshold (10), five bands, cooling days. |
| **Pinyin recall: queue** | `backend/pinyin_recall.py` — `build_session_queue()` (Active Load modes: Expansion / Consolidation / Rescue), `due_first=8`, `due_confirm_min=4`, `new_count=8` in `app.py`; constants `RESCUE_*`, `EXPANSION_*`, `CONSOLIDATION_*` | Batch size 20, slot reservation (巩固), mode recipes, 新字 cap. |
| **Pinyin recall: categories** | `backend/database.py` — `_category_from_bank_state` (新字/巩固/重测); `pinyin_recall.py` — `_score_band()` (hard, learning_normal, learned_normal, mastered), `_batch_category_for_character` | Display categories vs five-band selection logic. |
| **DB schema and scripts** | `backend/DATABASE.md` + `backend/scripts/` (characters/, pinyin_recall/, radicals/, utils/) | ARCHITECTURE should summarize and link to DATABASE.md; do not duplicate full schema. |
| **Frontend routes** | `frontend/src/App.jsx` — `/`, `/radicals`, `/radicals/:radical`, `/stroke-counts`, `/stroke-counts/:count`, `/pinyin/:query`, `/games/pinyin-recall`, `/profile`, `/profile/category/:category` | Route list and page names. |
| **Nav structure** | `frontend/src/NavBar.jsx` — Search, 分类 (部首, 笔画), 游戏 (拼音记忆) | Navigation and dropdowns. |
| **E2E coverage** | `frontend/e2e/*.spec.js` — core (search, dictionary-only, radicals), pinyin-search, routing, navigation, profile (unauthenticated), pinyin-recall (unauthenticated) | ARCHITECTURE “Testing” should match what E2E actually runs. |

**Key constants (from code) for ARCHITECTURE:**

- **Score:** correct +10 (cap 100), wrong/我不知道 −10 (floor −50). Proficiency = score ≥ 10. Five bands: 难字 ≤ −20; −20 < 普通在学字 ≤ 0; 0 < 普通已学字 < 20; 掌握字 ≥ 20.
- **Cooling days (database.py):** 难字 0, 普通在学字 1, 普通已学字 5, 掌握字 22.
- **Queue:** total_target=20, new_count=8 (app.py); Rescue 4 掌握字 + 8 普通已学字 + 6 在学字 + 2 新字; Expansion 10 新字 + 10 review; Consolidation 5 新字 + 15 review.

### 0.2 Git history: Anchor for CHANGELOG

Use `git log --oneline -- chinese_chr_app/` to derive chronological feature/pivot entries. Below are **key commits** (oldest → newest) that map to CHANGELOG entries. When writing CHANGELOG, prefer one entry per logical change; date can come from commit or release.

| Commit (short) | CHANGELOG-relevant event |
|----------------|--------------------------|
| 5a3ad7d | Add Chinese Character Learning App (initial) |
| d874f96 | Milestone 2: Radicals page |
| 1fbfb82 | HWXNet dictionary view alongside character metadata |
| fde29bf | Stroke-count segmentation pages (笔画) |
| 33d6719 | Remove structures page (pivot) |
| 48c936d | Playwright E2E smoke tests |
| e2db121 | zibiao_index, dictionary-only characters |
| 5694eaf | Stroke order animation |
| 6c43b1c | Segmentation dropdown nav (Search + 分类) |
| c341779 | Radicals from HWXNet dictionary |
| df3474d | Supabase DB support, Psycopg 3 |
| a1bb8a9 | Supabase Auth (Google login) |
| b98acc7 | Milestone 6: Pinyin search |
| 616bf93 | Log character views for signed-in users |
| ca851ab | /api/profile |
| a51bb7b | Profile and progress page (Issue #2) |
| 3136a60 | MVP1: Pinyin recall persistence in Supabase |
| 637c418 | MVP1: Pinyin recall UI, English meaning on review |
| 43c447f | Pinyin recall: symmetric scoring (+10/−10), backfill |
| 1b01b5a | Pinyin recall: score floor −50 |
| 76b15e5 | Profile 汉字掌握度: 未学字 / 在学字 / 已学字 (#11) |
| 21372eb | Queue by five score-based categories, batch logging |
| e2b799b | Reserve slots for 巩固 in session queue |
| 246ef5c | Cap 新字 at 8 per session (session size 20) |
| f2103fc | Add batch_id to pinyin_recall_item_presented |
| b03a092 | Report Error (报错) — DB, API, frontend (Issue #6) |
| c7fd538 | Correct-answer page: all pinyin, English meaning, 基本解释 (Issue #7) |
| e5d0d67 | Auth: certifi SSL context for PyJWKClient |
| 69753c9 | Backend: datetime.now(timezone.utc) |

**Older / structural:** CORS fixes, Cloud Build, Docker, docs moves (e.g. 5443518 consolidate docs, febbb78 group backend scripts, 4f3c37f file organization) can be summarized as “Infrastructure” or “Docs” entries if desired.

**CHANGELOG rule:** Each entry should be traceable to one or more commits (or explicitly marked “pre-git” / “documented from PRD” for M1–M5 if dates are inferred from PRD only).

### 0.3 Versioning scheme and backfill

**Rules:**

| Type | Increment | Example |
|------|-----------|---------|
| **Initial** | First working version = **v0.1** | — |
| **Minor update** | +0.0.1 (patch) | v0.1 → v0.1.1; v0.1.11 → v0.1.12 |
| **Major update** | Second digit +1, patch resets | v0.1.11 → **v0.2** (not v0.1.12) |
| **Complete upgrade** | First digit +1, rest reset | v0.2.10 → **v1.0** |

**Backfilled versions** (assign past changes to versions; use when creating CHANGELOG):

| Version | Scope | Commits / events (see §0.2) |
|---------|--------|-----------------------------|
| **v0.1** | Initial app: character search, 3000 cards, 4-panel (M1) | 5a3ad7d, PRD M1 |
| **v0.1.1** | Radicals page (M2) | d874f96 |
| **v0.1.2** | HWXNet dictionary view | 1fbfb82 |
| **v0.1.3** | Stroke-count (笔画) pages (M5) | fde29bf |
| **v0.1.4** | Remove structures page (pivot) | 33d6719 |
| **v0.1.5** | E2E tests; zibiao_index, dictionary-only characters | 48c936d, e2db121 |
| **v0.1.6** | Stroke order animation (M4); Segmentation dropdown (M3); radicals from HWXNet | 5694eaf, 6c43b1c, c341779 |
| **v0.1.7** | Supabase DB support; Supabase Auth (Google login) | df3474d, a1bb8a9 |
| **v0.1.8** | Pinyin search (M6); character view logging; /api/profile; Profile and progress page | b98acc7, 616bf93, ca851ab, a51bb7b |
| **v0.2** | **Major:** MVP1 Pinyin Recall (persistence, UI, 巩固 reservation, new_count cap) | 3136a60, 637c418, e2b799b, 246ef5c |
| **v0.2.1** | Symmetric scoring +10/−10; score floor −50 | 43c447f, 1b01b5a |
| **v0.2.2** | Profile 未学字/在学字/已学字 (#11) | 76b15e5 |
| **v0.2.3** | Queue by five score-based categories, batch logging; batch_id | 21372eb, f2103fc |
| **v0.2.4** | Report Error (报错); correct-answer page (Issue #7) | b03a092, c7fd538 |
| **v0.2.5** | Auth/backend fixes (certifi SSL, datetime UTC) | e5d0d67, 69753c9 |

**Current app version (after backfill):** **v0.2.5**

**When writing CHANGELOG.md:** Group entries under version headings (e.g. `## [v0.2.5]`, `## [v0.2.4]`, …). List changes under each version; each change traceable to §0.2 commit(s). For future releases: minor change → bump patch (e.g. v0.2.5 → v0.2.6); major product change → bump minor (e.g. v0.2.10 → v0.3); complete upgrade → bump major (e.g. v0.3.2 → v1.0).

---

## 1. README.md (current) → Where each part goes

| Section / content | Destination | Notes |
|-------------------|-------------|--------|
| Title + one-line description | **README** | Keep as receptionist summary |
| Production URLs (frontend, backend, GCS) | **README** | Quick reference; optionally link to ARCHITECTURE “Deployment” |
| **Project Structure** (tree) | **ARCHITECTURE** | Technical layout; README keeps a short “Structure” line + link to ARCHITECTURE |
| **File organization** (where to put new files) | **README** or **ARCHITECTURE** | Convention; could stay in README as “Where to put new files” or move to ARCHITECTURE |
| **Data Model Notes** (characters.json, hwxnet, level-*.json, counts) | **ARCHITECTURE** | Current data reality |
| **Search behavior** (4-panel vs 2-panel, pinyin) | **ARCHITECTURE** | Current behavior |
| **Setup Instructions** (backend, frontend, venv, .env) | **README** | Quick Start / Setup — keep here |
| **E2E tests (Playwright)** | **README** (short) + **ARCHITECTURE** (detail) | README: how to run; ARCHITECTURE: what’s covered |
| **Stroke animation (HanziWriter)** (proxy, cache, SSL) | **ARCHITECTURE** | Technical implementation |
| **Usage** (browser, Sign in, Search, Radicals) | **README** | High-level usage; keep brief |
| **Using the database (Supabase)** (USE_DATABASE, tables, character_views) | **ARCHITECTURE** | Or “see ARCHITECTURE + backend/DATABASE.md” |
| **If you see "psycopg is required"** (troubleshooting) | **README** | Keep in Setup / troubleshooting |
| **API Endpoints** (full list) | **ARCHITECTURE** | API is technical spec |
| Note about port 5001 | **ARCHITECTURE** or README footnote | Either place |

**README after refactor should contain:** Title, one-line summary, production URLs, **Table of Contents** (links to VISION, ARCHITECTURE, CHANGELOG), short “Project structure” line + link, **Setup / Quick Start** (unchanged), short **Usage**, and troubleshooting (psycopg, etc.). No long data model or API details.

---

## 2. docs/Product_Requirements_Doc.md → Where each part goes

| Section / content | Destination | Notes |
|-------------------|-------------|--------|
| **Project Overview** (goal, 2 categories: utility vs learning, data-driven, customized) | **VISION** | Core “why” and product framing |
| **Chinese character data** (§ “Chinese character data” — Feng, HWXNet, stroke data, fields) | **ARCHITECTURE** | Current data sources and schemas; overlaps with README “Data Model” and backend/DATABASE.md |
| **Key Features — Milestone 1** (search, 3000 cards, read-only table) | **CHANGELOG** (entry) + **ARCHITECTURE** (current behavior) | History: “Shipped M1”; Architecture: how search works today |
| **Key Features — Milestone 2** (radicals page) | **CHANGELOG** + **ARCHITECTURE** | Same split |
| **Key Features — Milestone 3** (Search + 分类 dropdown) | **CHANGELOG** + **ARCHITECTURE** | Same split |
| **Key Features — Milestone 4** (stroke order animation) | **CHANGELOG** + **ARCHITECTURE** | Same split |
| **Key Features — Milestone 5** (笔画 page) | **CHANGELOG** + **ARCHITECTURE** | Same split |
| **Key Features — Milestone 6** (pinyin search) | **CHANGELOG** + **ARCHITECTURE** | Same split |
| **Learning Functions: Vision, Goals, and MVP (Milestone 7+)** (research link, vision, goals, north-star, MVP 1 & 2 recommendation) | **VISION** | Future/planned and rationale |
| **Research + brainstorming paper trail** (link to research doc) | **VISION** | Keep as pointer to docs/research/ |
| **Product vision**, **Tangible goals**, **North-star metric**, **MVP recommendation** | **VISION** | All “why” and targets |

---

## 3. docs/plans/ → Where each part goes

### MVP1_Pinyin_Micro_Session_Plan.md

| Section / content | Destination | Notes |
|-------------------|-------------|--------|
| Goal (week 1), success criteria, open-ended format, flow, batch 20 | **ARCHITECTURE** (current) + **VISION** (goals) | Implemented behavior → ARCHITECTURE; goals → VISION |
| Scope boundary (in/out of scope) | **ARCHITECTURE** (implemented) + **VISION** (future exclusions) | What’s in MVP1 vs “we don’t do yet” |
| Key technical constraints / existing system integration | **ARCHITECTURE** | How it plugs in |
| Item representation, stem content, word selection, polyphonic rules | **ARCHITECTURE** | Current spec |
| Algorithm 1: scheduling (stage ladder) | **ARCHITECTURE** | Current scheduler |
| Algorithm 2: queue (due + new, candidate pool, 巩固 slot reservation) | **ARCHITECTURE** | Current queue logic |
| Character bank + score (implemented when USE_DATABASE=true), tables, score update, queue build, logging | **ARCHITECTURE** | Matches backend/DATABASE.md |
| Character and answer categories (新字/重测/巩固), 巩固 slot reservation design | **ARCHITECTURE** | Current behavior |
| Algorithm 3: prompt types, distractor generation, “I don’t know” | **ARCHITECTURE** | Current design |
| Backend API design (session, next-batch, answer) | **ARCHITECTURE** | Current API |
| Frontend UI plan (open-ended, 20 items, feedback, end session) | **ARCHITECTURE** | Current UI spec |
| **Wrong-answer / 我不知道 — learning moment (design, not yet implemented)** | **VISION** | Future work |
| Post-session learning (implemented behavior) | **ARCHITECTURE** | Current |
| Testing + debugging plan, E2E | **ARCHITECTURE** | Current |
| MVP 1 open questions | **VISION** | Open product/design questions |
| **History:** “Implemented (2026-02-21)”, “Implemented when USE_DATABASE=true” | **CHANGELOG** | Entries for MVP1 ship, score/categories, etc. |

### MVP2_Daily_Micro_Session_Plan.md

| Section / content | Destination | Notes |
|-------------------|-------------|--------|
| Entire file | **VISION** | MVP 2 is future/planned; no current implementation |

---

## 4. docs/research/ → Where each part goes

### Learning_Functions_Research_and_Brainstorming.md

| Section / content | Destination | Notes |
|-------------------|-------------|--------|
| Why this doc exists, Executive synthesis, Definitions | **VISION** | Foundational “why” and definitions |
| Model (diagnose → select → practice → feedback → schedule) | **VISION** | Core learning loop |
| Research notes (retrieval, spacing, interleaving, handwriting, radicals, morphology, tone, HLE, ER) | **VISION** | Evidence and principles |
| Design principles (derived) | **VISION** | Product principles |
| Feature/experience catalog (Phase 1: A, F, C; later: B, D, E) | **VISION** | Future feature set |
| Recommendation: MVP 1 & 2 learning slice, v0 spec (item model, scheduling, confusion sets) | **VISION** | Strategy and future spec |
| Measurement + logging plan, product vision, goals, metrics, event taxonomy | **VISION** | Goals and instrumentation plan |
| Open questions / assumptions | **VISION** | Open product questions |
| References | **VISION** | Keep with research section |

### Chinese_Character_Learning_Algorithm_Design.md

| Section / content | Destination | Notes |
|-------------------|-------------|--------|
| Entire content (Gemini conversation: score bands, Fixed Ratio, Priority Weighting, Bucket Ladder, Adaptive Valve, Cooling Period, Emma example) | **VISION** | Research/design input; parts of it are reflected in PROPOSAL_Queue and MVP1 (e.g. Rescue mode, valve) — treat as background and reference for VISION/queue design |

---

## 5. docs/proposals/ → Where each part goes

| File | Status | Destination | Notes |
|------|--------|-------------|--------|
| **PROPOSAL_Pinyin_Recall_Symmetric_Scoring** | Implemented (2026-02-21) | **CHANGELOG** (entry: symmetric +10/−10) + **ARCHITECTURE** (current scoring rule) | Rationale and backfill plan → ARCHITECTURE or appendix; “Implemented” → CHANGELOG |
| **PROPOSAL_Profile_Three_Categories** | Implemented | **CHANGELOG** (entry: 未学字/在学字/已学字 in Profile) + **ARCHITECTURE** (profile progress API and categories) | Same pattern |
| **PROPOSAL_Pinyin_Recall_Negative_Score_Floor** | Implemented (2026-02-21) | **CHANGELOG** (entry: score floor −50) + **ARCHITECTURE** (score range −50–100, queue ordering) | Same pattern |
| **PROPOSAL_Queue_By_Five_Score_Categories** | **Implemented** (commit 21372eb; batch_mode/batch_character_category, add_pinyin_recall_batch_columns.py) | **CHANGELOG** (entry: queue by five score-based categories, batch logging) + **ARCHITECTURE** (current queue: five bands, Active Load modes, Rescue/Expansion/Consolidation recipes, cooling) | Same pattern as other implemented proposals; proposal doc status was stale ("Draft") |

---

## 6. backend/DATABASE.md

| Section / content | Destination | Notes |
|-------------------|-------------|--------|
| Entire file | **ARCHITECTURE** (or keep as-is and reference) | Pure technical reality: config, tables, schema, scripts, data access, backend behavior. Either (a) keep `backend/DATABASE.md` as the canonical DB doc and have ARCHITECTURE link to it, or (b) move/merge its content into ARCHITECTURE and keep a short DATABASE.md that says “see ARCHITECTURE.” |

**Recommendation:** Keep `backend/DATABASE.md` as the single source of truth for DB. **ARCHITECTURE.md** should describe system flow, high-level data model, and API, and link to `backend/DATABASE.md` for schema and scripts.

---

## 7. Summary: What goes where

### README.md (Receptionist)
- Project title and one-line description
- Production URLs
- **Table of Contents** → VISION.md, ARCHITECTURE.md, CHANGELOG.md
- Short “Project structure” + link to ARCHITECTURE
- File organization (where to put new files) — keep or link to ARCHITECTURE
- **Setup / Quick Start** (backend, frontend, venv, .env, E2E run command)
- Short **Usage** (open app, sign in, search, radicals)
- Troubleshooting (psycopg, Python 3.13, etc.)
- No: long data model, full API list, HanziWriter details (link to ARCHITECTURE instead)

### VISION.md (The Why)
- Product overview (utility vs learning, data-driven, customized)
- Learning loop model (diagnose → select → practice → feedback → schedule)
- Research summary and design principles (from Learning_Functions_Research)
- Product vision, tangible goals, north-star metric
- User stories / goals for primary-school learners
- **Future/planned:** MVP 2 (Meaning in Context), Compound Builder, Radical Detective, learning moment (wrong-answer screen)
- Feature/experience catalog (Phase 1 and later)
- Measurement and logging plan (goals, event taxonomy)
- Open questions and assumptions
- References to docs/research/ and algorithm design doc

### ARCHITECTURE.md (The How)
- **Must match code:** Validate every “current” claim against §0.1 (app.py routes, database.py and pinyin_recall.py constants, DATABASE.md, App.jsx routes, NavBar, e2e specs).
- **System overview:** Frontend (React/Vite), Backend (Flask), Supabase/Postgres, GCS, data files
- **Project structure** (directory tree from current README)
- **Data model:** Feng 3000, HWXNet 3664, level-*.json, stroke data (HanziWriter proxy, radical_stroke_counts); link to backend/DATABASE.md for full schema
- **Search behavior:** 4-panel vs 2-panel, pinyin search, routing — per app.py and frontend Search/PinyinResults
- **API endpoints:** Full list from app.py (§0.1): characters/search, pinyin-search, images, strokes, radicals, stroke-counts, profile, profile/progress, profile/progress/category/:category, games/pinyin-recall (session, next-batch, answer, report-error), log-character-view, health
- **Database:** When USE_DATABASE=true, which tables, character_views, pinyin recall bank + event log; link to backend/DATABASE.md
- **Pinyin recall (MVP1):** Current design from database.py + pinyin_recall.py + app.py — session/next-batch/answer, queue (total_target=20, new_count=8, 巩固 reservation, five-band modes), score −50–100, cooling days (0/1/5/22), categories (新字/重测/巩固), distractor rules, logging; link to DATABASE.md for tables/scripts
- **Stroke animation:** HanziWriter proxy, cache, SSL env (app.py get_hanzi_writer_strokes)
- **E2E:** What’s covered — match frontend/e2e/*.spec.js (core, pinyin-search, routing, navigation, profile, pinyin-recall unauthenticated)
- Port 5001 note

### CHANGELOG.md (The History)
- **Versioned:** Group entries under version headings per §0.3. Use backfilled versions (v0.1 through v0.2.5) for past work; for new releases, bump version by rule (minor +0.0.1, major +0.x, complete +x.0).
- **Must be derivable from git:** Each change under a version should be traceable to §0.2 commits; optionally include commit hash or date.
- **Structure:** Reverse-chronological by version (newest first). Under each `## [vX.Y.Z]` list changes as bullet points; each: short title, optional commit/date, 1–2 sentences.
- **Content (backfill):** Use §0.3 backfilled versions; under each version list the scope from the table (e.g. under v0.2: MVP1 Pinyin Recall — persistence, UI, queue, 巩固 reservation, new_count cap; refs 3136a60, 637c418, e2b799b, 21372eb, 246ef5c).

---

## 8. File-level mapping (concise)

**Validation:** When moving content, ARCHITECTURE facts must match §0.1 (code); CHANGELOG entries should come from §0.2 (git log).

| Current file | Primary destination(s) | Action |
|--------------|------------------------|--------|
| README.md | README (summary, ToC, Setup, Usage) + ARCHITECTURE (structure, data, API) | Trim README; move technical blocks to ARCHITECTURE |
| docs/Product_Requirements_Doc.md | VISION (overview, goals, M7+) + ARCHITECTURE (data, M1–6 behavior) + CHANGELOG (M1–6 entries) | Split by section per table above |
| docs/plans/MVP1_Pinyin_Micro_Session_Plan.md | ARCHITECTURE (current MVP1 spec) + VISION (goals, open questions, “learning moment” not implemented) + CHANGELOG (MVP1, score/categories) | Split |
| docs/plans/MVP2_Daily_Micro_Session_Plan.md | VISION | Move or summarize into VISION |
| docs/research/Learning_Functions_Research_and_Brainstorming.md | VISION | Move or summarize into VISION; keep doc as deep-dive or link |
| docs/research/Chinese_Character_Learning_Algorithm_Design.md | VISION (reference) | Keep as reference; link from VISION |
| docs/proposals/PROPOSAL_* (all implemented: Symmetric Scoring, Profile Three Categories, Negative Score Floor, Queue By Five Score Categories) | CHANGELOG (entry per proposal) + ARCHITECTURE (current rule / queue logic) | Summarize each in CHANGELOG; current behavior in ARCHITECTURE |
| backend/DATABASE.md | ARCHITECTURE (link only) or keep as canonical DB doc | Do not duplicate; ARCHITECTURE links to it |

---

## 9. Next steps (when you do the refactor)

1. **Ground truth first:** Use §0.1 to validate any “current” technical claim (open app.py, database.py, pinyin_recall.py, App.jsx, NavBar.jsx, e2e specs). Use §0.2 to draft CHANGELOG entries from real commits.
2. Create **VISION.md** (e.g. under `docs/`) and populate from Product_Requirements_Doc (overview, goals, M7+), research docs, MVP2 plan, and draft proposal.
3. Create **ARCHITECTURE.md** (e.g. under `docs/`) from README (structure, data, API), Product_Requirements_Doc (data, M1–6 behavior), MVP1 plan — **then cross-check every “current” fact against code (§0.1) and backend/DATABASE.md.** Link to DATABASE.md for schema/scripts; do not duplicate.
4. **Create CHANGELOG.md with versioning (backfill):**
   - At the top of CHANGELOG.md, add a short **Versioning** note: initial app = v0.1; minor update = +0.0.1; major update = increment second digit (e.g. v0.1.11 → v0.2); complete upgrade = increment first digit (e.g. v0.2.10 → v1.0). See §0.3.
   - **Backfill** past work using §0.3: create version headings `## [v0.2.5]` … down to `## [v0.1]` (newest first). Under each version, list the changes from the §0.3 table; each change traceable to §0.2 commit(s). Current app version after backfill: **v0.2.5**.
   - For future releases: apply the same version rules (minor → patch bump, major → second-digit bump, complete → first-digit bump).
5. Trim **README.md** to receptionist + ToC + Setup + short Usage + troubleshooting; add links to VISION, ARCHITECTURE, CHANGELOG. Optionally show current version (e.g. “Current version: v0.2.5”) in README or CHANGELOG header.
6. Optionally relocate or archive original docs (e.g. keep plans/proposals/research as supporting docs and link from VISION/ARCHITECTURE).

No files have been modified in this step; the mapping is complete and anchored to code and git history.
