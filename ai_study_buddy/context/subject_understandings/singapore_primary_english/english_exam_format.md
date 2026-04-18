# Singapore Primary English — Exam format & visual structure

> Status: **Exploratory** — background/reference for ingestion and diagnostics.
>
> Parent overview: [L3_EXAM_FORMATS.md](../../../docs/L3_EXAM_FORMATS.md).

**Authoritative format:** [PSLE English Language (0001)](https://www.seab.gov.sg/files/PSLE%20Syllabus%20documents/2026%20PSLE/0001_y26_sy.pdf) — *Implemented from the Year of Examination 2025* ([index](https://www.seab.gov.sg/psle/psle-formats-examined-in-2026/)).

The **full PSLE English** assessment is **200 marks** across **four papers** (Writing; Language Use and Comprehension; Listening; Oral). This doc focuses on **Paper 1** and **Paper 2** (written papers most often ingested from PDFs). **Paper 3** (Listening) and **Paper 4** (Oral) are summarised at the end.

**Samples (school prelims):** e.g. `_c_p6.english.prelim.2.pdf`, `_c_p6.english.prelim.3.pdf` under `DAYDREAMEDU_ROOT/Singapore Primary English/PSLE/Exam/`. **Pagination** varies.

---

## Paper 1 — Writing (**50 marks**, **1 h 10 min**)

| Component | Items | Marks |
|-----------|-------|-------|
| Situational Writing | 1 (OE) | **14** |
| Continuous Writing | 1 (OE) | **36** |

- **Continuous writing:** at least **150 words**; **three pictures** offered; the composition must be based on **at least one** picture (SEAB syllabus wording).
- Responses on **answer sheets** / foolscap, not the question booklet.

---

## Paper 2 — Language Use and Comprehension (**90 marks**, **1 h 50 min**)

### Booklet A (MCQ, OAS) — **25 marks**

| Section | Items | Marks |
|---------|-------|-------|
| Grammar | 10 MCQ | 10 |
| Vocabulary | 5 MCQ | 5 |
| Vocabulary Cloze | 5 MCQ | 5 |
| Visual Text Comprehension | 5 MCQ | 5 |

### Booklet B (open-ended) — **65 marks**

| Section | Items | Marks |
|---------|-------|-------|
| Grammar Cloze | 10 OE | 10 |
| Editing (spelling & grammar) | 10 OE | 10 |
| Comprehension Cloze | 15 OE | 15 |
| Synthesis / Transformation | 5 OE | 10 |
| Comprehension OE | 10 OE | 20 |

- Marks in **square brackets** per part where shown; **shared passage(s)** for comprehension — use one `passage_ref` / stimulus id where applicable.
- Candidates often repeat the **option number in parentheses** on MCQ pages if the **OAS** is missing from a scan.

---

## Papers 3–4 (brief — not typical PDF workbook ingestion)

| Paper | Content | Marks | Duration (approx.) |
|-------|-----------|-------|---------------------|
| **3** Listening Comprehension | 20 MCQ | 20 | ~35 min |
| **4** Oral Communication | Reading aloud + stimulus-based conversation | 15 + 25 | ~10 min exam (+ prep) |

**Total PSLE English = 200 marks.**

---

## Teaching feedback & ingestion

- **Cover / section scores** on Paper 2 are high-signal.
- **Qualitative comments** on open-ended answers (e.g. “use evidence”) are valuable for skills, not only marks.
