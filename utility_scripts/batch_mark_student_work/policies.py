"""Marking policy presets for batch student-work queues."""

from __future__ import annotations

from typing import Any

# policy_kind -> detector subagent (Task tool subagent_type)
DETECTOR_BY_POLICY_KIND: dict[str, str] = {
    "book": "math-question-section-detector",
    "exercise": "math-question-section-detector",
    "english_exercise": "english-paper-2-question-section-detector",
}

BOOK_MARKING_POLICY: dict[str, Any] = {
    "policy_kind": "book",
    "detector": DETECTOR_BY_POLICY_KIND["book"],
    "question_type": "SAQ",
    "single_part_marks": 2,
    "sub_part_marks": 1,
    "notes": (
        "Model Drawing / book unit worksheets: SAQ only (never MCQ or LAQ). "
        "Single-part numbered question: 2 marks; (a)/(b) sub-parts: 1 mark each."
    ),
}

BOOK_MARKING_POLICY_PROMPT = """Batch marking policy (book unit practice — answer-key mapped):
- question_type: SAQ only for every section (never MCQ or LAQ)
- Single-part numbered question (no printed (a)/(b)): question_mark = 2
- Sub-parts (a) and (b) with separate Ans: lines: one question_info row each, question_mark = 1
- question_index: Q1, Q19(a), Q19(b) (parentheses, not Q19a)
- Grade student attempt against answers/ pages in the marking bundle (not teacher ink on completion)
"""

EXERCISE_MARKING_POLICY: dict[str, Any] = {
    "policy_kind": "exercise",
    "detector": DETECTOR_BY_POLICY_KIND["exercise"],
    "notes": (
        "Math exercise worksheets. Standard math types (MCQ, SAQ, LAQ) from layout. "
        "teacher_annotated when no book_answer_mapping."
    ),
}

EXERCISE_MARKING_POLICY_PROMPT = """Batch marking policy (math exercise worksheets):
- Use standard Singapore primary math question types (MCQ, SAQ, LAQ) from the worksheet layout.
- Do NOT force SAQ-only unless the worksheet truly has no MCQ/LAQ.
- Non-MCQ without per-question assigned marks ([1m], [2m], [n], etc.): default question_type to SAQ.
- Marking mode: teacher_annotated — grade from red/green/black/blue ink on the completion PDF.
- No answer-key PDF pages; omit answers/ renders in the marking bundle.
- Ink policy: black/blue = student attempt; green = student correction (exclude from original score); red = teacher marks when visible.
"""

ENGLISH_EXERCISE_MARKING_POLICY: dict[str, Any] = {
    "policy_kind": "english_exercise",
    "detector": DETECTOR_BY_POLICY_KIND["english_exercise"],
    "notes": (
        "English Paper 2-style exercise worksheets. Standard section types from layout. "
        "teacher_annotated when no separate answer-key mapping."
    ),
}

ENGLISH_EXERCISE_MARKING_POLICY_PROMPT = """Batch marking policy (English exercise / practice worksheets):
- Use English Paper 2 section types from layout (Grammar MCQ, Vocabulary MCQ, Cloze, Editing, Synthesis, Comprehension, etc.).
- Marking mode: teacher_annotated — grade from teacher ink on the completion PDF.
- No answer-key PDF pages unless explicitly provided in the bundle.
- Ink policy: black/blue = student attempt in answer blanks only (use "" if blank); green = correction excluded; red = teacher authority.
- question_index may include year suffix when needed: Q51 (2020), Q51 (2021).
"""

POLICY_BY_NAME: dict[str, dict[str, Any]] = {
    "book": BOOK_MARKING_POLICY,
    "exercise": EXERCISE_MARKING_POLICY,
    "english_exercise": ENGLISH_EXERCISE_MARKING_POLICY,
}

PROMPT_BY_POLICY_KIND: dict[str, str] = {
    "book": BOOK_MARKING_POLICY_PROMPT,
    "exercise": EXERCISE_MARKING_POLICY_PROMPT,
    "english_exercise": ENGLISH_EXERCISE_MARKING_POLICY_PROMPT,
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


def default_marking_mode_for_policy(policy_name: str) -> str:
    """Return queue-level marking_mode string: teacher_annotated | standard_mapped_answer."""
    if policy_name in ("exercise", "english_exercise"):
        return "teacher_annotated"
    return "standard_mapped_answer"


def english_finalize_required(payload: dict[str, Any]) -> bool:
    subject = (payload.get("subject") or "").strip().lower()
    if subject == "english":
        return True
    kind = (payload.get("marking_policy") or {}).get("policy_kind")
    return kind == "english_exercise"
