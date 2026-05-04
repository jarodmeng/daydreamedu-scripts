# Singapore Primary Higher Chinese — Exam format & visual structure

Higher Chinese (高华) is a **separate** Chinese Language exam taken **in addition to** **Standard Chinese Language** (华文, **200**-mark full PSLE including oral/listening) for pupils who offer it — unless the school reports only one track in a given context. This doc is only about **Higher Chinese**.

**Not covered here:** [Foundation Chinese Language](https://www.seab.gov.sg/files/PSLE%20Syllabus%20documents/2026%20PSLE/0025_y26_sy.pdf).

> Status: **Exploratory** — background/reference for ingestion and diagnostics.
>
> Parent overview: [L3_EXAM_FORMATS.md](../../../docs/L3_EXAM_FORMATS.md).
>
> Standard Chinese Language: [chinese_exam_format.md](./chinese_exam_format.md).

**Authoritative syllabus:** [PSLE Higher Chinese Language (0015)](https://www.seab.gov.sg/files/PSLE%20Syllabus%20documents/2026%20PSLE/0015_y26_sy.pdf) — *For Examination from 2017* ([index](https://www.seab.gov.sg/psle/psle-formats-examined-in-2026/)).

**Samples (school prelims):** e.g. `_c_p6.hc.prelim.1.pdf`, `_c_p6.hc.prelim.2.pdf` under `DAYDREAMEDU_ROOT/Singapore Primary Chinese/PSLE/Exam/`. **Pagination varies.**

---

## Overview — two papers, 100 marks

| | **试卷一** | **试卷二** |
|---|------------|------------|
| **Marks** | **40** | **60** |
| **Duration** | **50 min** | **1 h 20 min** |

**Total: 100 marks** (vs **200** for the **full** Standard Chinese PSLE stack). **No MCQ block on OAS** for Higher Chinese — responses are **handwritten** (Paper 2 still uses **objective-style** items such as 综合填空 where pupils mark or write in boxes per the paper).

---

## 试卷一 — Writing (**40**)

- **命题作文** and **完成文章** — **2 选 1**; **记叙文**; **字数须在 200 以上** (SEAB blueprint).
- **内容 /20 + 表达 /20** on scored papers; **grid paper (方格纸)**; dictionary when permitted per cover.

---

## 试卷二 — 语文应用与阅读理解 (**60**) — SEAB blueprint

| 序 | 考查项目 | 方式 | 题数 | 分数 |
|----|----------|------|------|------|
| 一 | 综合填空 | 多项选择式 | 5 | 10 |
| | 字词改正 | 客观式 | 5 | 10 |
| 二 | 阅读理解（一） | 开放式 | 6 | 16 |
| 三 | 阅读理解（二） | 开放式 | 7 | 24 |
| | **共** | | **23** | **60** |

- **一** combines **word-bank cloze** (综合填空) and **character/word correction** (字词改正) — both counted in the **23**-item Paper 2 total.
- **二 / 三** are **open-ended** comprehension blocks; **0.5** step marking is common on samples.

**How this differs from Standard Chinese (ingestion):**

- Standard 华文 **试卷二** has a **large OAS MCQ block**; Higher Chinese **试卷二** is **no OAS pipeline** in the same way — vision reads **boxes, tables, and paragraphs**.

---

## Ingestion notes

- Model as `subject='chinese'` + `chinese_variant='higher'` (see registry conventions).
- Link **question booklet** and **answer booklet** with `exam_id` when split across files.
- For detailed agent-relevant question type descriptions and visual examples, see [higher_chinese_exam_paper2_question_types.md](./higher_chinese_exam_paper2_question_types.md).
