# AI Study Buddy — Data Strategy

> Status: **Exploratory** — options and recommendations, not final decisions.
>
> Sources: ChatGPT 5.2 Thinking conversation (3 Mar 2026), supplemented with independent analysis (Opus 4.6 Max, 4 Mar 2026).

---

## Core Principle: Don't Duplicate Everything

Google Drive is the **canonical document store** (cold source of truth). Only store *derived, compact* things elsewhere:
- Searchable text chunks
- Embeddings (only for question-level chunks)
- Structured learning logs (tiny)
- Cropped images when needed (for handwriting/diagrams)

---

## The "Question Object" — First-Class Unit

This is the single most important design choice for cost control and tutoring quality (from ChatGPT).

**Don't think in PDFs or pages. Think in questions.**

A question object stores:

| Field | Description |
|-------|-------------|
| `child_id` | Which child |
| `grade` | e.g., P6 |
| `paper_id` | e.g., "2026 WA1 PP3 Standard Math" |
| `date` | e.g., 19 Feb 2026 |
| `question_no` | e.g., 6, 14b |
| `max_marks` | From paper structure |
| `earned_marks` | From teacher marking / page subtotals |
| `answer_region_bbox` | Bounding box for child's final answer |
| `working_region_bbox` | Bounding box for child's workings |
| `teacher_feedback_bbox` | Bounding box for teacher corrections/notes |
| `attempt_outcome` | correct / wrong / partial |
| `error_tags` | e.g., `fraction-of-remainder`, `ratio-inversion` |
| `skill_tags` | e.g., `fractions-of-remainder`, `model-drawing` |
| `assets` | Pointers to cropped images (not full pages) |
| `drive_file_id` | Reference back to the Drive PDF |
| `page_number` | Which page in the PDF |

**Why this matters:** The tutor almost always works with one question crop + a few relevant chunks + the child's mastery summary. This keeps token usage and OCR usage bounded.

---

## Storage Layout: 3 Tiers

### Tier 1: Google Drive (raw PDFs)
- Canonical storage, human-manageable
- Lowest operational complexity
- ~4,000 pages now, growing ~500/month

### Tier 2: Object Store (optional — GCS)
- Only for *derived artifacts*: page images, question crops
- Can use colder storage classes for older content
- Cost: pennies per GB/month at this scale

### Tier 3: Database (Postgres)
- Student model (mastery, attempts, misconceptions, plans, rewards)
- Ingestion index (chunks, offsets, file references)
- Event logs
- Doc chunks with embeddings (pgvector)

**Key:** The DB stays small because raw docs stay in Drive.

---

## Ingestion Pipeline

### Architecture: Deterministic Pipeline + AI "Operators"

The extraction is **not** purely AI — it's a Python pipeline with AI used selectively where rules break down.

```
PDF → pages → question objects → marks/outcomes → skill tags → DB rows
```

**What Python does (always):**
- Watch Google Drive folders (new/changed PDFs)
- Download or stream file, compute fingerprint (avoid reprocessing)
- Render pages to images (for scans)
- Run cheap text extraction (digital PDFs)
- Store artifacts + metadata
- Orchestrate AI "operators"
- Write final structured JSON + DB records

**What AI does (only when needed):**
- Detect question boundaries on scanned pages (bounding boxes)
- Read teacher marks / score boxes
- Classify question type ("fraction of remainder", "ratio after changes")
- Summarize error patterns (tagging)

### 3-Tier Extraction Strategy (cost-controlled)

#### Tier 1 — Digital PDFs (cheapest)
If the PDF has selectable text:
1. Python extracts text directly (no OCR)
2. Chunk by question numbers using regex cues (Q1, 1(a), "Section B", "[5]", etc.)
3. Create question objects with page references

**AI not required** unless the layout is unusual.

#### Tier 2 — Scanned but structured (mostly rule-based)
For common school templates (like WA papers):
1. Python renders pages to images
2. Layout heuristics: find "Question X" anchors, detect mark brackets "[5]", detect score boxes
3. Crop each question region + working region
4. Store crops + minimal OCR of printed text only

**AI used only for:** refining boundaries, reading score box values.

#### Tier 3 — Scanned + handwriting/markings heavy (AI-assisted)
Call a vision-capable model on **cropped regions** (not whole pages):
- "Locate question text, final answer line, and teacher score marks"
- "Extract earned marks / corrections"
- "Return bounding boxes + extracted fields"

**Critical cost lever:** Call AI on small crops, only on pages/questions that need it.

### Step-by-Step Workflow Per PDF

| Step | What | Who |
|------|------|-----|
| 0. Preflight | Digital or scanned? How many pages? Known template? | Python |
| 1. Page materialization | Render scanned pages to PNG; keep text for digital | Python |
| 2. Page-level extraction | Section boundaries, question numbering, mark brackets; if low confidence → AI layout parser | Python-first |
| 3. Create question objects | Page number, bounding boxes, max marks | Python |
| 4. Marking & score extraction | Score boxes ("2/4"), ticks/crosses, teacher corrections | AI or rules |
| 5. Tagging | Skill tags (rules + taxonomy, optionally AI-proposed); error tags (AI-proposed, confirmed over time) | Hybrid |
| 6. Persist + cache | Save JSON extraction, crops, indices, embeddings; update student model | Python |

---

## Human-in-the-Loop Review

Early on, the pipeline should output a **review screen** showing:
- Detected questions with bounding boxes
- Extracted marks
- Quick-fix UI for boundaries, marks, question numbering, tags

Corrections become training data for:
- Better heuristics
- "Template profiles" per school/paper type

This reduces AI calls over time as templates become deterministic.

---

## OCR Strategy

### What to expect from OCR on school materials

| Content type | OCR quality | Strategy |
|-------------|-------------|----------|
| **Printed question text** | High accuracy | OCR → searchable text |
| **Handwritten workings** | Variable, often unreliable (messy writing, math notation) | Store as image crop; don't rely on OCR |
| **Teacher markings/scores** | Often reliable for simple marks ("2/4", ticks, corrected answers) | OCR/vision extract into structured fields |

**Key insight (ChatGPT):** OCR is not "to understand everything on the page" — it creates **searchable anchors + structured signals**. The visual ground truth (image crops) is preserved separately.

### OCR tool options

The conversation recommended Google Cloud Vision. Current pricing: first 1,000 pages/month free, then $1.50 per 1,000 pages for Document Text Detection. ([Cloud Vision pricing](https://cloud.google.com/vision/pricing))

---

## Embeddings

### What embeddings are (from the ChatGPT explanation)

An embedding is a vector (list of numbers) representing the *semantic meaning* of text. Similar meaning → vectors close together; different meaning → vectors far apart.

### Why embeddings matter here

They power **semantic retrieval** — finding relevant content even when wording differs. Example: Winston asks about "a question where you take a fraction, then there's some left, then you take another fraction…" — keyword search for "remainder" might fail, but embedding search finds structurally similar questions.

### What to embed

Embed **small, meaningful chunks** only:
- Question text (highest priority)
- Short textbook paragraphs
- Concise misconception notes

**Do not embed:** full pages, whole PDFs, handwritten content.

### Hybrid retrieval (recommended)

Combine three search modes:
1. **Metadata filtering** — child, grade, subject, date
2. **Keyword search** — precise matching ("Q6", "ratio")
3. **Embedding search** — semantic similarity

---

## Retrieval Index Options

| Option | Pros | Cons |
|--------|------|------|
| **Postgres + pgvector** | Simple, cheap, one system for everything | May not scale for very large datasets |
| **OpenSearch** | Strong search features, powerful keyword search | More operational complexity |

**Recommendation (ChatGPT):** Start with Postgres + pgvector for simplicity. At family scale (~4,000 pages + 500/month), it's more than sufficient.

---

> [!NOTE]
> **Opus 4.6 Max analysis** — additional considerations on data strategy.

### On the question object extraction challenge

The conversation presents a clean vision of question objects, but the reality of extracting them from diverse scanned worksheets will be messy. Considerations:

1. **Template diversity:** Singapore primary schools use varied worksheet formats. The "template profile" idea is good, but early extraction will require significant manual correction. Budget for this.

2. **Bounding box accuracy:** Detecting question boundaries on scanned pages with handwritten workings overlapping printed text is a hard computer vision problem. A pragmatic MVP approach: **page-level chunks first**, refined to question-level later as templates are learned.

3. **Score extraction reliability:** Score boxes ("2/4") are relatively reliable to extract, but ticks/crosses scattered across a page are harder. Start with page-level score totals (from the corner boxes visible in the example paper) before attempting per-question correctness.

### On embedding strategy

The ChatGPT advice to embed only question-level chunks is sound. One additional consideration: **embedding the skill taxonomy itself** (skill names + descriptions) enables matching student queries to skills, which can improve the planner's ability to auto-assign relevant practice.

### On Drive as canonical store

This is pragmatically good (no migration needed, familiar UI for organizing), but introduces a dependency on Drive API rate limits and availability. For the ingestion pipeline, consider:
- **Batch syncing** (periodic, not real-time) to avoid hitting Drive API quotas
- **Local caching** of recently ingested files so the pipeline can re-run without re-downloading

### Open Questions

1. **How are PDFs currently organized in Drive?** By child? By subject? By date? Mixed? This determines how much metadata can be inferred from folder structure vs. requiring manual tagging.
2. **What percentage of pages are scanned vs. digital-native?** This drives OCR cost estimates.
3. **Are there common templates** (e.g., the same WA format used each term)? Template recognition could dramatically reduce AI calls.
