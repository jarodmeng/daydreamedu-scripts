"""Shared helpers for batch student-work marking queues."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ai_study_buddy.marking import find_marking_artifacts_for_attempt
from ai_study_buddy.marking.file_question_info import (
    QuestionSectionsNotFoundError,
    get_latest_question_sections_for_file_id,
)
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager, normalize_pdf_display_name

from policies import (  # noqa: F401
    BOOK_MARKING_POLICY,
    BOOK_MARKING_POLICY_PROMPT,
    DETECTOR_BY_POLICY_KIND,
    ENGLISH_EXERCISE_MARKING_POLICY,
    EXERCISE_MARKING_POLICY,
    EXERCISE_MARKING_POLICY_PROMPT,
    policy_prompt_for_payload,
)

SCRIPT_DIR = Path(__file__).resolve().parent
QUEUES_DIR = SCRIPT_DIR / "queues"
DEFAULT_WORK_QUEUE_PATH = QUEUES_DIR / "winston_model_drawing.json"

DEFAULT_SOURCE_FOLDER = Path(
    "/Users/jarodm/Library/CloudStorage/GoogleDrive-genrong.meng@gmail.com/My Drive/"
    "DaydreamEdu/completion/Singapore Primary Math/winston.ry.meng@gmail.com/P6/Book/"
    "Model Drawing Made Easy and Inspiring for P5 and P6"
)

COMPLETION_GLOBS = ("_c_*.pdf", "c_*.pdf")

# Back-compat aliases (old module names)
WORK_QUEUE_PATH = DEFAULT_WORK_QUEUE_PATH
MARKING_POLICY = BOOK_MARKING_POLICY
MARKING_POLICY_PROMPT = BOOK_MARKING_POLICY_PROMPT
EXERCISE_MARKING_POLICY_PROMPT = EXERCISE_MARKING_POLICY_PROMPT


def scan_completion_paths(folder: Path) -> list[Path]:
    """DaydreamEdu _c_ completions and GoodNotes c_ completions (deduped)."""
    seen: set[Path] = set()
    out: list[Path] = []
    for pattern in COMPLETION_GLOBS:
        for path in sorted(folder.glob(pattern)):
            key = path.resolve()
            if key in seen:
                continue
            seen.add(key)
            out.append(path)
    return out


def infer_subject_from_folder(folder: Path) -> str:
    text = str(folder.resolve())
    if "Singapore Primary English" in text or "singapore_primary_english" in text:
        return "english"
    if "Singapore Primary Chinese" in text or "singapore_primary_chinese" in text:
        return "chinese"
    if "Singapore Primary Science" in text or "singapore_primary_science" in text:
        return "science"
    return "math"


def infer_student_email(
    manager: PdfFileManager,
    folder: Path,
    items: list[dict[str, Any]],
) -> str | None:
    for item in items:
        file_id = item.get("completion_file_id")
        if not file_id:
            continue
        pf = manager.get_file(file_id)
        if pf is None or not pf.student_id:
            continue
        student = manager.get_student(pf.student_id)
        if student is not None and student.email:
            return student.email
    folder_str = str(folder).casefold()
    if "emma.rs.meng@gmail.com" in folder_str:
        return "emma.rs.meng@gmail.com"
    if "winston.ry.meng@gmail.com" in folder_str:
        return "winston.ry.meng@gmail.com"
    return None


def detector_for_payload(payload: dict[str, Any]) -> str:
    explicit = payload.get("detector")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    kind = (payload.get("marking_policy") or {}).get("policy_kind")
    if kind in DETECTOR_BY_POLICY_KIND:
        return DETECTOR_BY_POLICY_KIND[kind]
    subject = (payload.get("subject") or "").lower()
    if subject == "english":
        return "english-paper-2-question-section-detector"
    if subject == "science":
        return "science-question-section-detector"
    if subject == "chinese":
        return "chinese-paper-2-question-section-detector"
    return "math-question-section-detector"


def detector_for_template(manager: PdfFileManager, template_file_id: str) -> str:
    """Pick Chinese vs Higher Chinese detector from template metadata."""
    pf = manager.get_file(template_file_id)
    if pf is None:
        return "chinese-paper-2-question-section-detector"
    meta = pf.metadata or {}
    if meta.get("chinese_variant") == "higher":
        return "higher-chinese-paper-2-question-section-detector"
    return "chinese-paper-2-question-section-detector"


def marking_artifacts_for_completion(manager: PdfFileManager, completion_file_id: str) -> list:
    return find_marking_artifacts_for_attempt(completion_file_id, manager=manager)


def template_needs_detection(template_file_id: str) -> bool:
    try:
        get_latest_question_sections_for_file_id(template_file_id, require_valid=False)
        return False
    except QuestionSectionsNotFoundError:
        return True


def load_work_queue(path: Path = DEFAULT_WORK_QUEUE_PATH) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_work_queue(payload: dict[str, Any], path: Path = DEFAULT_WORK_QUEUE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    text = json.dumps(payload, indent=2, ensure_ascii=True) + "\n"
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def build_item_from_completion(
    *,
    manager: PdfFileManager,
    ord_num: int,
    completion_path: Path,
    allow_teacher_annotated: bool = False,
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "ord": ord_num,
        "completion_path": str(completion_path.resolve()),
        "completion_file_id": None,
        "completion_normal_name": normalize_pdf_display_name(completion_path),
        "template_file_id": None,
        "template_path": None,
        "template_normal_name": None,
        "book_answer_pages": None,
        "needs_detection": False,
        "needs_marking": False,
        "status": "blocked",
        "skip_reason": None,
        "detector_completed_at": None,
        "marking_artifact_path": None,
        "error": None,
    }

    pf = manager.get_file_by_path(completion_path.resolve())
    if pf is None:
        row["error"] = "not_registered"
        return row

    row["completion_file_id"] = pf.id
    refs = marking_artifacts_for_completion(manager, pf.id)
    if refs:
        row["status"] = "skipped"
        row["skip_reason"] = "already_marked"
        row["marking_artifact_path"] = str(refs[0].marking_result_json.resolve())
        row["needs_marking"] = False
        tmpl = manager.get_template(pf.id)
        if tmpl is not None:
            row["template_file_id"] = tmpl.id
            row["template_path"] = tmpl.path
            row["template_normal_name"] = tmpl.normal_name
            row["needs_detection"] = template_needs_detection(tmpl.id)
        return row

    tmpl = manager.get_template(pf.id)
    if tmpl is None:
        row["error"] = "no_template_link"
        return row

    row["template_file_id"] = tmpl.id
    row["template_path"] = tmpl.path
    row["template_normal_name"] = tmpl.normal_name
    row["needs_detection"] = template_needs_detection(tmpl.id)

    mapping = manager.get_book_answer_mapping(tmpl.id)
    if mapping is None:
        if allow_teacher_annotated:
            row["marking_mode"] = "teacher_annotated"
            row["needs_marking"] = True
            row["status"] = "pending"
            return row
        row["error"] = "no_book_answer_mapping"
        return row

    row["book_answer_pages"] = {
        "start_page": mapping.answer_page_start,
        "end_page": mapping.answer_page_end,
        "starts_mid_page": mapping.starts_mid_page,
        "ends_mid_page": mapping.ends_mid_page,
    }
    row["marking_mode"] = "standard_mapped_answer"
    row["needs_marking"] = True
    row["status"] = "pending"
    return row


# Valid phase2 mistake_type values -> normalize invalid grader output
MISTAKE_TYPE_ALIASES: dict[str, str | None] = {
    "conceptual_error": "wrong_method",
    "grammar_rule": "other",
    "grammar": "other",
    "spelling": "careless_error",
}


def normalize_phase2_rows(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for row in rows:
        r = dict(row)
        qid = r.get("question_id") or r.get("result_id")
        if isinstance(qid, str):
            r["question_id"] = qid
            r["result_id"] = qid
        diag = r.get("diagnosis")
        if isinstance(diag, dict):
            if diag.get("mistake_type") == "":
                diag["mistake_type"] = None
            elif diag.get("mistake_type") not in (
                None,
                "wrong_method",
                "careless_error",
                "misread_question",
                "incomplete_explanation",
                "vocabulary_gap",
                "other",
                "concept_gap",
                "missing_units",
                "computation_error",
            ):
                diag["mistake_type"] = MISTAKE_TYPE_ALIASES.get(
                    str(diag.get("mistake_type")), "other"
                )
            if diag.get("reasoning") == "":
                diag["reasoning"] = None
            if isinstance(diag.get("confidence"), dict):
                diag["confidence"] = "high"
            r["diagnosis"] = diag
        if r.get("human_note") == "":
            r["human_note"] = None
        out.append(r)
    return out
