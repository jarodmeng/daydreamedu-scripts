# Singapore Primary Chinese (Standard) — Exam format & visual structure

MOE/SEAB offer **three** Chinese examination tracks at PSLE, not two:

| Track | SEAB (example) | Typical role |
|-------|------------------|--------------|
| **Foundation Chinese Language** | e.g. subject 0025 | Mother Tongue at **Foundation** level — **different syllabus and paper** from Standard. |
| **Chinese Language** (**Standard**) | e.g. subject [0005](https://www.seab.gov.sg/files/PSLE%20Syllabus%20documents/2026%20PSLE/0005_y26_sy.pdf) | Mainstream **华文** — **200 marks** at full PSLE (written + oral + listening). |
| **Higher Chinese Language** | e.g. subject [0015](https://www.seab.gov.sg/files/PSLE%20Syllabus%20documents/2026%20PSLE/0015_y26_sy.pdf) | **高华** — additional paper (**100 marks**). |

This doc describes **Standard Chinese Language** (the mainstream 华文 exam). It does **not** describe [Foundation Chinese Language](https://www.seab.gov.sg/files/PSLE%20Syllabus%20documents/2026%20PSLE/0025_y26_sy.pdf). See [higher_chinese_exam_format.md](./higher_chinese_exam_format.md) for Higher Chinese.

> Status: **Exploratory** — background/reference for ingestion and diagnostics.
>
> Parent overview: [L3_EXAM_FORMATS.md](../../../docs/L3_EXAM_FORMATS.md).

**Authoritative syllabus:** [PSLE Chinese Language (0005)](https://www.seab.gov.sg/files/PSLE%20Syllabus%20documents/2026%20PSLE/0005_y26_sy.pdf) — *For Examination from 2017* ([index](https://www.seab.gov.sg/psle/psle-formats-examined-in-2026/)).

**Samples (school prelims):** e.g. `_c_p6.chinese.prelim.1.pdf`, `_c_p6.chinese.prelim.2.pdf` under `DAYDREAMEDU_ROOT/Singapore Primary Chinese/PSLE/Exam/`. Schools may bundle **one PDF or multiple booklets**; **pagination is not canonical**.

---

## Full PSLE — three papers, 200 marks

| Paper | Content | Duration | Marks |
|-------|---------|----------|-------|
| **试卷一** | 写作 | 50 min | **40** |
| **试卷二** | 语文应用与阅读理解 | 1 h 40 min | **90** |
| **试卷三** | 口试 + 听力理解 | ~10 min oral + ~30 min listening | **50** + **20** |

**Written papers (试卷一 + 试卷二) = 130 marks** — the usual focus for scanned workbooks. **口试 / 听力** are separate sittings; ingestion pipelines for PDFs often only see **试卷一、二**.

---

## 试卷一 — Writing (**40**)

- **命题作文** or **看图作文** — **2 选 1**; **不少于 100 字**; **approved dictionary** permitted (SEAB).
- One composition on **grid paper (方格纸)** in the answer booklet; **内容 /20 + 表达 /20** on scored papers.

---

## 试卷二 — Language use & comprehension (**90**) — SEAB blueprint

| 序 | 考查项目 | 方式 | 题数 | 分数 |
|----|----------|------|------|------|
| 一 | 语文应用 | 多项选择 | 15 | 30 |
| | 短文填空 | 多项选择 | 5 | 10 |
| 二 | 阅读理解一 | 多项选择 | 5 | 10 |
| 三 | 完成对话 | 多项选择 | 4 | 8 |
| 四 | 阅读理解二（2 个篇章，含书面互动） | 开放式 | 11 | 32 |
| | **共** | | **40** | **90** |

- School samples often split tools as **Q1–25** on **OAS** and **Q26–40** in the **answer booklet** — align with **cover** when numbering differs slightly.
- **Inline MCQ (短文填空):** options in running text `(1 … 2 … 3 … 4 …)` — visually distinct from block MCQ.
- **四 阅读理解二:** **11** open-ended items (not only “Q30–40” by label — total item count is fixed by blueprint).

---

## 试卷三 — Oral & listening (brief)

- **口试** (~10 min exam): 朗读篇章 + 会话（录像短片）— **50** marks; **10 min** preparation (默读 + 观看短片).
- **听力理解** (~30 min): **10** MCQ — **20** marks.

---

## Ingestion notes

- Link **question booklet**, **answer booklet**, and **OAS** with a common **`exam_id`** when split across files.
- **Registry:** `pdf_file_manager` stores Standard 华文 with `metadata.chinese_variant = 'standard'` (not SEAB “Foundation Chinese Language”). See [ARCHITECTURE.md](../../../pdf_file_manager/ARCHITECTURE.md).
