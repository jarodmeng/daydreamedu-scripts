# Singapore Primary Math — Exam format & visual structure

**Scope:** **Standard (mainstream) PSLE Mathematics** — not [Foundation Mathematics](https://www.seab.gov.sg/files/PSLE%20Syllabus%20documents/2026%20PSLE/0038_y26_sy.pdf).

> Status: **Exploratory** — background/reference for ingestion and diagnostics.
>
> Parent overview: [L3_EXAM_FORMATS.md](../../../docs/L3_EXAM_FORMATS.md).

**Authoritative format (from 2026):** [PSLE Mathematics (0008)](https://www.seab.gov.sg/files/PSLE%20Syllabus%20documents/2026%20PSLE/0008_y26_sy.pdf) — *For Examination from 2026* ([index](https://www.seab.gov.sg/psle/psle-formats-examined-in-2026/)).

**Why SEAB differs from many school prelims:** The **national PSLE** adopted a **revised Mathematics format from 2026** (see syllabus PDF). **School prelim papers** are usually **past-year–style practice** (sets recycled or modelled on **earlier** national papers). Until a school updates its papers, prelims can still show **45 + 55** and the older Booklet A/B split — **not** a mistake in the SEAB table.

**Samples (school prelims):** e.g. `_c_p6.math.prelim.1.pdf`, `_c_p6.math.prelim.13.pdf` under `DAYDREAMEDU_ROOT/Singapore Primary Math/PSLE/Exam/`. Treat **cover totals** as ground truth for each PDF; compare against the SEAB 2026 row below when inferring “official” structure.

---

## PSLE Mathematics (2026 SEAB) — two papers, 100 marks

| | **Paper 1** | **Paper 2** |
|---|-------------|-------------|
| **Marks** | **50** | **50** |
| **Duration** | **1 hour 10 minutes** (both booklets) | **1 hour 20 minutes** |
| **Calculator** | Not allowed | Allowed |
| **Combined** | | **2 hours 30 minutes** total (same day, break between papers) |

### Paper 1 — Booklet A (MCQ, non-calculator)

- **10** multiple-choice questions, **1 mark** each.
- **8** multiple-choice questions, **2 marks** each.
- Answers shaded on an **Optical Answer Sheet (OAS)** where used; **four options (1)–(4)** per item.

### Paper 1 — Booklet B (short answer, non-calculator)

- **12** short-answer questions, **2 marks** each — working in spaces provided; method marks per SEAB item-type rules.

### Paper 2 (structured / long answer, calculator allowed)

- **5** short-answer questions, **2 marks** each → **10 marks**.
- **10** structured / long-answer questions, **3, 4 or 5 marks** each → **40 marks** (stated total for this block).

---

## Visual layers (for scored papers)

| Layer | Typical role |
|-------|----------------|
| **Printed** | Question text, diagrams, grids, “Ans:” lines, mark brackets `[n]`, section instructions; footers may show **page position** for navigation only |
| **Candidate** | Pencil (OAS); pen for Booklet B and Paper 2 — workings, models |
| **Teacher** | Red ticks/crosses, scores in margin/page boxes, method marks (e.g. “✓m”), corrections |
| **Review** | Green ink or extra working from revision sessions (where applicable) |

**Paper 1 Booklet A:** Mostly **print + light pencil** on MCQ pages. **OAS** is the canonical MCQ surface when present.

**Paper 1 Booklet B and Paper 2:** **Heavy working** is normal; bar models and long division where needed.

---

## Other formats

Non-PSLE **weighted assessments** may use different booklets or all free-response. Ingestion should use **cover-page metadata** and **section headers**.

---

## Question type details

For detailed agent-relevant question type descriptions and visual examples, see [math_exam_question_types.md](./math_exam_question_types.md).
