from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ai_study_buddy.marking.file_question_info import iter_questions_ordered

_HAN_RANGE_START = 0x4E00
_HAN_RANGE_END = 0x9FFF


def _contains_han(text: str) -> bool:
    return any(_HAN_RANGE_START <= ord(ch) <= _HAN_RANGE_END for ch in text)


def normalize_outcome(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip().casefold()
    if cleaned == "incorrect":
        return "wrong"
    if cleaned in {"correct", "partial", "wrong", "disqualified"}:
        return cleaned
    return value.strip()


def select_phase3_question_ids(rows: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    selected: list[str] = []
    for row in rows:
        qid = row.get("question_id") or row.get("result_id")
        if not isinstance(qid, str) or not qid.strip():
            continue
        outcome = normalize_outcome(row.get("outcome") if isinstance(row.get("outcome"), str) else None)
        confidence = row.get("confidence")
        low_conf = False
        if isinstance(confidence, Mapping):
            low_conf = any(isinstance(v, str) and v.strip().casefold() == "low" for v in confidence.values())
        if outcome != "correct" or low_conf:
            selected.append(qid.strip())
    return tuple(selected)


def find_language_violations(
    rows: Sequence[Mapping[str, Any]],
    *,
    english_required: bool,
) -> tuple[str, ...]:
    if not english_required:
        return ()
    violations: list[str] = []
    for row in rows:
        qid = row.get("question_id") or row.get("result_id")
        row_id = qid.strip() if isinstance(qid, str) and qid.strip() else "<unknown>"
        diagnosis = row.get("diagnosis")
        diagnosis_reasoning = diagnosis.get("reasoning") if isinstance(diagnosis, Mapping) else None
        fields = (
            row.get("student_answer"),
            row.get("correct_answer"),
            row.get("human_note"),
            diagnosis_reasoning,
        )
        has_han = any(isinstance(v, str) and _contains_han(v) for v in fields)
        if has_han:
            violations.append(row_id)
    return tuple(violations)


def find_human_note_policy_violations(rows: Sequence[Mapping[str, Any]]) -> tuple[dict[str, str], ...]:
    violations: list[dict[str, str]] = []
    for row in rows:
        qid = row.get("question_id") or row.get("result_id")
        row_id = qid.strip() if isinstance(qid, str) and qid.strip() else "<unknown>"
        note = row.get("human_note")
        source = row.get("human_note_source")
        is_verbatim = row.get("human_note_is_verbatim")
        has_note = isinstance(note, str) and bool(note.strip())

        if has_note:
            if source in (None, "", "none"):
                violations.append({"question_id": row_id, "reason": "human_note requires non-none source"})
            if is_verbatim is not True:
                violations.append({"question_id": row_id, "reason": "human_note requires human_note_is_verbatim=true"})
        elif source not in (None, "", "none"):
            violations.append({"question_id": row_id, "reason": "human_note_source requires human_note content"})
    return tuple(violations)


def build_authoritative_marks_by_question(payload: Mapping[str, object]) -> dict[str, float]:
    rows = iter_questions_ordered(payload)
    marks: dict[str, float] = {}
    for row in rows:
        question_id = row["question_index"]
        question_mark = row.get("question_mark")
        if isinstance(question_mark, (int, float)) and not isinstance(question_mark, bool):
            marks[question_id] = float(question_mark)
    return marks


@dataclass(frozen=True)
class MergeResult:
    merged_rows: tuple[dict[str, Any], ...]
    phase3_applied_question_ids: tuple[str, ...]


def merge_phase2_phase3_rows(
    phase2_rows: Sequence[Mapping[str, Any]],
    phase3_rows: Sequence[Mapping[str, Any]],
    *,
    authoritative_marks: Mapping[str, float],
) -> MergeResult:
    phase3_by_id: dict[str, Mapping[str, Any]] = {}
    for row in phase3_rows:
        qid = row.get("question_id") or row.get("result_id")
        if isinstance(qid, str) and qid.strip():
            phase3_by_id[qid.strip()] = row

    merged: list[dict[str, Any]] = []
    applied: list[str] = []
    for base in phase2_rows:
        qid_raw = base.get("question_id") or base.get("result_id")
        qid = qid_raw.strip() if isinstance(qid_raw, str) and qid_raw.strip() else None
        row = dict(base)
        if qid and qid in phase3_by_id:
            candidate = dict(phase3_by_id[qid])
            candidate.pop("max_marks", None)
            row.update(candidate)
            applied.append(qid)

        if qid:
            row["result_id"] = qid
            mark = authoritative_marks.get(qid)
            if mark is not None:
                row["max_marks"] = mark
        if isinstance(row.get("outcome"), str):
            row["outcome"] = normalize_outcome(row["outcome"])
        merged.append(row)
    return MergeResult(
        merged_rows=tuple(merged),
        phase3_applied_question_ids=tuple(applied),
    )


def build_generation_telemetry(
    *,
    phase2_subagents: int,
    deep_dive_count: int,
    total_duration_seconds: float | None,
) -> dict[str, Any]:
    telemetry: dict[str, Any] = {
        "fast_pass_count": max(0, int(phase2_subagents)),
        "deep_dive_count": max(0, int(deep_dive_count)),
        "total_duration_seconds": None if total_duration_seconds is None else max(0.0, float(total_duration_seconds)),
    }
    if phase2_subagents > 0:
        telemetry["phase2_task_subagents"] = True
    return telemetry


def reconcile_teacher_tally(
    rows: Sequence[Mapping[str, Any]],
    *,
    teacher_total_marks: float | int | None,
    teacher_earned_marks: float | int | None,
) -> dict[str, Any]:
    computed_total = 0.0
    computed_earned = 0.0
    for row in rows:
        mx = row.get("max_marks")
        er = row.get("earned_marks")
        if isinstance(mx, (int, float)) and not isinstance(mx, bool):
            computed_total += float(mx)
        if isinstance(er, (int, float)) and not isinstance(er, bool):
            computed_earned += float(er)
    qc_passed = True
    if isinstance(teacher_total_marks, (int, float)) and not isinstance(teacher_total_marks, bool):
        qc_passed = qc_passed and abs(float(teacher_total_marks) - computed_total) < 1e-6
    if isinstance(teacher_earned_marks, (int, float)) and not isinstance(teacher_earned_marks, bool):
        qc_passed = qc_passed and abs(float(teacher_earned_marks) - computed_earned) < 1e-6
    return {
        "teacher_total_marks": teacher_total_marks,
        "teacher_earned_marks": teacher_earned_marks,
        "computed_total_marks": computed_total,
        "computed_earned_marks": computed_earned,
        "qc_passed": qc_passed,
    }
