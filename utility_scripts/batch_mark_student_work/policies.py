"""Marking policy presets for batch student-work queues."""

from __future__ import annotations

from typing import Any

# policy_kind -> detector subagent (Task tool subagent_type)
DETECTOR_BY_POLICY_KIND: dict[str, str] = {
    "book": "math-question-section-detector",
    "exercise": "math-question-section-detector",
    "english_exercise": "english-paper-2-question-section-detector",
    "science_exercise": "science-question-section-detector",
    "chinese_exercise": "chinese-paper-2-question-section-detector",
}

BOOK_MARKING_POLICY: dict[str, Any] = {
    "policy_kind": "book",
    "detector": DETECTOR_BY_POLICY_KIND["book"],
    "notes": (
        "Book unit worksheets with book_answer_mapping. Use standard math types "
        "(MCQ, SAQ, LAQ) from layout; grade from mapped answer-key pages."
    ),
}

BOOK_MARKING_POLICY_PROMPT = """Batch marking policy (book unit practice — answer-key mapped):
- Use standard Singapore primary math question types (MCQ, SAQ, LAQ) from the worksheet layout.
- Non-MCQ without per-question assigned marks ([1m], [2m], [n], etc.): default question_type to SAQ (not LAQ).
- question_index: Q1, Q19(a), Q19(b) (parentheses, not Q19a)
- Grade student attempt against answers/ pages in the marking bundle (not teacher ink on completion)
- When marks are not printed on the worksheet: single-part numbered question → question_mark = 2;
  separate (a)/(b) sub-parts with separate Ans: lines → one question_info row each, question_mark = 1
"""

EXERCISE_MARKING_POLICY: dict[str, Any] = {
    "policy_kind": "exercise",
    "detector": DETECTOR_BY_POLICY_KIND["exercise"],
    "notes": (
        "Math exercise worksheets. Standard math types (MCQ, SAQ, LAQ) from layout. "
        "teacher_annotated when no book_answer_mapping."
    ),
}

EXERCISE_TEACHER_INK_SCORING_RULE = """Exercise teacher-ink scoring (default for MCQ/SAQ and most items):
- Red checkmark/tick on a question (no explicit partial score) → outcome=correct, earned_marks = that question's max marks (from authoritative_marks_by_question / file_question_info).
- Red cross/X on a question (no explicit partial score) → outcome=wrong, earned_marks=0.
- Only when the teacher writes an explicit numeric or fractional mark (common on LAQ mark boxes or step marks) → use that value for earned_marks; outcome partial if 0 < earned < max, wrong if 0, correct if earned = max.
- Do not treat incidental red "1" step tallies as the question total when the item is fully ticked for credit."""

EXERCISE_MARKING_POLICY_PROMPT = """Batch marking policy (math exercise worksheets):
- Use standard Singapore primary math question types (MCQ, SAQ, LAQ) from the worksheet layout.
- Do NOT force SAQ-only unless the worksheet truly has no MCQ/LAQ.
- Non-MCQ without per-question assigned marks ([1m], [2m], [n], etc.): default question_type to SAQ.
- Marking mode: teacher_annotated — grade from red/green/black/blue ink on the completion PDF.
- No answer-key PDF pages; omit answers/ renders in the marking bundle.
- Ink policy: black/blue = student attempt; green = student correction (exclude from original score); red = teacher marks when visible.
""" + EXERCISE_TEACHER_INK_SCORING_RULE

ENGLISH_EXERCISE_MARKING_POLICY: dict[str, Any] = {
    "policy_kind": "english_exercise",
    "detector": DETECTOR_BY_POLICY_KIND["english_exercise"],
    "notes": (
        "English Paper 2-style exercise worksheets. Standard section types from layout. "
        "teacher_annotated when no separate answer-key mapping."
    ),
}

SCIENCE_EXERCISE_MARKING_POLICY: dict[str, Any] = {
    "policy_kind": "science_exercise",
    "detector": DETECTOR_BY_POLICY_KIND["science_exercise"],
    "notes": (
        "Science exam/practice PDFs (Booklet A MCQ + OAS + Booklet B OEQ). "
        "teacher_annotated; MCQ graded from OAS shading and teacher ticks on OAS."
    ),
}

CHINESE_EXERCISE_MARKING_POLICY: dict[str, Any] = {
    "policy_kind": "chinese_exercise",
    "detector": DETECTOR_BY_POLICY_KIND["chinese_exercise"],
    "notes": (
        "Chinese / Higher Chinese Paper 2 (试卷二). teacher_annotated; "
        "use chinese-paper-2 detector for 华文 and higher-chinese-paper-2 for 高华."
    ),
}

SCIENCE_EXERCISE_MARKING_POLICY_PROMPT = """Batch marking policy (science exam / practice — teacher_annotated):
- Section types from layout: MCQ (Booklet A) and OEQ (Booklet B) only.
- Booklet A MCQ — grade from the Optical Answer Sheet (OAS) in the completion PDF:
  - Locate the OAS page (grid of numbered rows with options (1)–(4)); often recorded in question_sections.json input_context notes.
  - student_answer = the shaded/filled option only, e.g. "(2)" or "2" — NOT parentheses written on question booklet pages.
  - OAS row crossed out / voided by teacher: outcome=disqualified, scoring_status=excluded_disqualified, earned_marks=0 — exclude from summary (do not award marks even if an oval is shaded).
  - Correctness (when not crossed out): if the student's shaded row has no red teacher mark/slash, treat as correct (2 marks). If wrong, a red slash/tick on another option shows the keyed answer — use that option as correct_answer; student gets 0 marks.
  - Do NOT treat a red slash as the student's choice; it marks the correct option when the student shaded wrong.
- Booklet B OEQ — grade written answers in the booklet + teacher red/green ink on answer lines and page score boxes.
- Ink: black/blue = student attempt; green = correction (exclude from original score); red = teacher authority on OEQ lines/boxes.
- No separate answer-key PDF; omit answers/ renders unless present in bundle.
"""

CHINESE_EXERCISE_MARKING_POLICY_PROMPT = """Batch marking policy (Chinese Paper 2 — teacher_annotated):
- Section types from layout (语文应用, 完成对话, 阅读理解, 作文, etc. per question_sections.json).
- Marking mode: teacher_annotated — grade from teacher red/purple ink and score boxes on the completion PDF.
- Teacher total on 作答簿 cover: read `input_context.hints` for `teacher_total_mark_cover_page=N` (1-based page in merged PDF). After item-level grading, reconcile summary earned_marks to the handwritten total on that page when visible.
- Ink: black/blue = student attempt; green = correction (exclude from original score); red/purple = teacher authority.
- MCQ / bracket items: student_answer = what the student wrote or shaded in the bracket; teacher red tick/slash governs correctness.
- Open-ended / composition: transcribe student Chinese; use teacher marks on lines/boxes for earned_marks.
- Language: diagnosis.reasoning may be in Chinese; keep mistake_type in English enums.
- No separate answer-key PDF unless present in bundle.
- 高华 papers: same rules; detector uses higher-chinese schema when template metadata chinese_variant=higher.
"""

ENGLISH_EXERCISE_MARKING_POLICY_PROMPT = """Batch marking policy (English exercise / practice worksheets):
- Use English Paper 2 section types from layout (Grammar MCQ, Vocabulary MCQ, Cloze, Editing, Synthesis, Comprehension, etc.).
- Marking mode: teacher_annotated — grade from teacher ink on the completion PDF when present.
- No answer-key PDF pages unless explicitly provided in the bundle.
- Ink policy: black/blue = student attempt in answer blanks only (use "" if blank); green = correction excluded; red = teacher authority.
- **Unmarked sections (no teacher ticks/crosses on items):** Do not default items to wrong. Read the questions/passage (word bank, editing lines, etc.), derive reference `correct_answer` values yourself, and grade by comparing the student's black/blue attempt to that reference. Award full marks when equivalent (ignore case on editing words and letter-prefix choices such as `(M) What` vs `(M) what`). Use `outcome=wrong` only when the attempt is blank or clearly incorrect vs your reference.
- OAS (optical answer sheet): student_answer = shaded/filled oval only; if correct there is no red slash; if incorrect a red slash marks the correct option (not the student's choice). Do not treat red slashes as the student's answer.
- question_index may include year suffix when needed: Q51 (2020), Q51 (2021).
"""

POLICY_BY_NAME: dict[str, dict[str, Any]] = {
    "book": BOOK_MARKING_POLICY,
    "exercise": EXERCISE_MARKING_POLICY,
    "english_exercise": ENGLISH_EXERCISE_MARKING_POLICY,
    "science_exercise": SCIENCE_EXERCISE_MARKING_POLICY,
    "chinese_exercise": CHINESE_EXERCISE_MARKING_POLICY,
}

PROMPT_BY_POLICY_KIND: dict[str, str] = {
    "book": BOOK_MARKING_POLICY_PROMPT,
    "exercise": EXERCISE_MARKING_POLICY_PROMPT,
    "english_exercise": ENGLISH_EXERCISE_MARKING_POLICY_PROMPT,
    "science_exercise": SCIENCE_EXERCISE_MARKING_POLICY_PROMPT,
    "chinese_exercise": CHINESE_EXERCISE_MARKING_POLICY_PROMPT,
}


def resolve_policy(name: str) -> dict[str, Any]:
    if name not in POLICY_BY_NAME:
        raise ValueError(f"Unknown policy {name!r}; choose from {sorted(POLICY_BY_NAME)}")
    return dict(POLICY_BY_NAME[name])


def policy_prompt_for_payload(payload: dict[str, Any]) -> str:
    kind = (payload.get("marking_policy") or {}).get("policy_kind")
    if kind in PROMPT_BY_POLICY_KIND:
        return PROMPT_BY_POLICY_KIND[kind]
    return BOOK_MARKING_POLICY_PROMPT


def policy_prompt_for_item(item: dict[str, Any], payload: dict[str, Any]) -> str:
    """Per-item policy wins when queue rows set ``policy`` (mixed-subject batches)."""
    policy_name = item.get("policy")
    if isinstance(policy_name, str) and policy_name in POLICY_BY_NAME:
        kind = resolve_policy(policy_name)["policy_kind"]
        return PROMPT_BY_POLICY_KIND.get(kind, BOOK_MARKING_POLICY_PROMPT)
    return policy_prompt_for_payload(payload)


def marking_mode_for_item(item: dict[str, Any], payload: dict[str, Any]) -> str | None:
    mode = item.get("marking_mode") or payload.get("marking_mode")
    return "teacher_annotated" if mode == "teacher_annotated" else None


def english_finalize_required_for_item(item: dict[str, Any], payload: dict[str, Any]) -> bool:
    subject = str(item.get("subject") or payload.get("subject") or "").strip().lower()
    if subject == "english":
        return True
    policy_name = item.get("policy")
    if isinstance(policy_name, str) and policy_name in POLICY_BY_NAME:
        return resolve_policy(policy_name)["policy_kind"] == "english_exercise"
    return english_finalize_required(payload)


def default_marking_mode_for_policy(policy_name: str) -> str:
    """Return queue-level marking_mode string: teacher_annotated | standard_mapped_answer."""
    if policy_name in ("exercise", "english_exercise", "science_exercise", "chinese_exercise"):
        return "teacher_annotated"
    return "standard_mapped_answer"


def english_finalize_required(payload: dict[str, Any]) -> bool:
    subject = (payload.get("subject") or "").strip().lower()
    if subject == "english":
        return True
    kind = (payload.get("marking_policy") or {}).get("policy_kind")
    return kind == "english_exercise"
