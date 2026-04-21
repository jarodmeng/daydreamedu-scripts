from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.core.artifact_paths import build_learning_report_path
from ai_study_buddy.marking.core.path_privacy import resolve_marking_artifact_paths
from ai_study_buddy.marking.core.artifact_schema import validate_marking_artifact_dict
from ai_study_buddy.marking.core.models import MarkingArtifact
from ai_study_buddy.marking.core.taxonomy import prettify_skill_tags

# Markdown table: show Chinese labels for taxonomy keys on Chinese / Higher Chinese papers.
_CHINESE_SUBJECT_MARKDOWN = frozenset(
    {
        "singapore_primary_chinese",
        "singapore_primary_higher_chinese",
    }
)

_MISTAKE_TYPE_LABEL_ZH: dict[str, str] = {
    "concept_gap": "概念不清",
    "misread_question": "审题偏差",
    "careless_error": "粗心失误",
    "incomplete_explanation": "阐述不完整",
    "wrong_method": "方法不当",
    "missing_units": "单位遗漏",
    "computation_error": "计算错误",
    "vocabulary_gap": "词汇问题",
    "other": "其他",
}


def _fmt_diagnosis_cell(*, subject_context: str | None, row: dict[str, Any]) -> str:
    """Table cell text: English snake_case prefix by default; Chinese labels for Chinese/HC."""
    diagnosis = row.get("diagnosis") or {}
    mistake_type = diagnosis.get("mistake_type")
    reasoning = diagnosis.get("reasoning")

    if subject_context in _CHINESE_SUBJECT_MARKDOWN:
        label_zh = _MISTAKE_TYPE_LABEL_ZH.get(mistake_type, mistake_type) if mistake_type else None
        if label_zh and reasoning:
            return f"{label_zh}：{reasoning}"
        if reasoning:
            return str(reasoning)
        if label_zh:
            return str(label_zh)
        return ""

    if mistake_type:
        text = str(mistake_type)
        if reasoning:
            text += f": {reasoning}"
        return text
    return _fmt_value(reasoning)


def _fmt_value(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return str(value)


def _fmt_code(value: Any) -> str:
    text = _fmt_value(value)
    return f"`{text}`" if text else ""


def _fmt_percentage(value: Any) -> str:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return _fmt_value(value)
    return str(int(round(numeric)))


def _row_icon(outcome: str) -> str:
    # Emoji legend:
    # - ✅ full marks
    # - ⚠️ partial credit
    # - ❌ zero marks
    # - 🚫 disqualified / excluded
    return {"correct": "✅", "partial": "⚠️", "wrong": "❌", "disqualified": "🚫"}.get(outcome, "❓")


def render_marking_report_markdown(data: dict[str, Any]) -> str:
    validate_marking_artifact_dict(data)
    data = resolve_marking_artifact_paths(data)

    context = data["context"]
    summary = data["summary"]
    rows = data["question_results"]

    lines: list[str] = [
        "# Learning Report",
        "",
        "## Result",
        "",
        f"- Student: `{_fmt_value(context.get('student_name') or context.get('student_id') or 'Unknown')}`",
        f"- Date: `{_fmt_value(data['created_at'])[:10]}`",
        f"- Score: `{summary['earned_marks']}/{summary['total_marks']}`",
        f"- Percentage: `{_fmt_percentage(summary['percentage'])}%`",
        f"- Overall assessment: {summary['overall_assessment']}",
    ]
    if isinstance(context.get("attempt_sequence"), int):
        lines.append(f"- Attempt #{context['attempt_sequence']}")
    if summary.get("human_note"):
        lines.append(f"- Human note: {_fmt_value(summary['human_note'])}")

    lines.extend(
        [
            "",
            "## Marking Table",
            "",
            "Convention: `✅` = full marks, `⚠️` = partial credit, `❌` = zero marks, `🚫` = disqualified/excluded.",
            "",
            "| Name | Scoring status | Student answer | Correct answer | Total marks | Obtained marks | Skill tags | Diagnosis | Human note |",
            "| --- | --- | --- | --- | ---: | ---: | --- | --- | --- |",
        ]
    )

    for row in rows:
        obtained = str(row["earned_marks"])
        if float(row["earned_marks"]) < float(row["max_marks"]) - 1e-9:
            obtained = f"**{obtained}**"
        diagnosis_text = _fmt_diagnosis_cell(
            subject_context=context.get("subject_context"),
            row=row,
        )
        # Join policy: see prettify_skill_tags (path-per-element vs legacy hierarchy).
        skill_text = prettify_skill_tags(row.get("skill_tags", []))
        lines.append(
            "| {name} | {scoring_status} | {student_answer} | {correct_answer} | {total_marks} | {obtained_marks} | {skill_tags} | {diagnosis} | {human_note} |".format(
                name=f"{_row_icon(row['outcome'])} {row['result_id']}",
                scoring_status=_fmt_code(row.get("scoring_status", "counted")),
                student_answer=_fmt_code(row.get("student_answer")),
                correct_answer=_fmt_code(row.get("correct_answer")),
                total_marks=row["max_marks"],
                obtained_marks=obtained,
                skill_tags=_fmt_code(skill_text),
                diagnosis=diagnosis_text,
                human_note=_fmt_value(row.get("human_note")),
            )
        )

    lines.extend(
        [
            "",
            "## Report Context",
            "",
            f"- Attempt file: `{_fmt_value(context.get('attempt_file_path'))}`",
            f"- Template book file: `{_fmt_value(context.get('template_file_path'))}`",
            f"- Book answer file: `{_fmt_value(context.get('answer_file_path'))}`",
            f"- Answer page range for this exercise: `{_fmt_value(context.get('answer_page_start'))}-{_fmt_value(context.get('answer_page_end'))}`",
            f"- Mapping source: `{_fmt_value(context.get('answer_mapping_source'))}`",
            "",
            "## Notes",
            "",
            f"- This report was rendered from canonical `{data['schema_version']}` JSON.",
        ]
    )
    if context.get("question_selection", {}).get("raw_text"):
        lines.append(f"- Gradable scope request: `{context['question_selection']['raw_text']}`")
    if context.get("answer_mapping_notes"):
        lines.append(f"- Answer mapping notes: {_fmt_value(context['answer_mapping_notes'])}")
    lines.append(f"- Generation mode: `{_fmt_value(data.get('generation', {}).get('mode'))}`")
    if data.get("generation", {}).get("notes"):
        lines.append(f"- Generation notes: {_fmt_value(data['generation']['notes'])}")

    return "\n".join(lines) + "\n"


def render_learning_report_from_json(
    artifact_json_path: str | Path,
    *,
    output_path: str | Path | None = None,
    context_root: str | Path = "ai_study_buddy/context",
) -> Path:
    input_path = Path(artifact_json_path)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    markdown = render_marking_report_markdown(data)

    if output_path is None:
        artifact = MarkingArtifact.from_dict(data)
        destination = build_learning_report_path(artifact, context_root=context_root)
    else:
        destination = Path(output_path)

    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(markdown, encoding="utf-8")
    return destination


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render a markdown learning report from canonical marking JSON.")
    parser.add_argument("artifact_json", help="Path to marking_result.v1/v1.1 JSON")
    parser.add_argument("--output", help="Optional explicit markdown output path")
    parser.add_argument("--context-root", default="ai_study_buddy/context")
    return parser


def main() -> int:
    args = _build_arg_parser().parse_args()
    destination = render_learning_report_from_json(
        args.artifact_json,
        output_path=args.output,
        context_root=args.context_root,
    )
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
