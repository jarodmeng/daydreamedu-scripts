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
        if row["earned_marks"] < row["max_marks"]:
            obtained = f"**{obtained}**"
        diagnosis = row.get("diagnosis") or {}
        diagnosis_text = ""
        if diagnosis.get("mistake_type"):
            diagnosis_text = diagnosis["mistake_type"]
            if diagnosis.get("reasoning"):
                diagnosis_text += f": {diagnosis['reasoning']}"
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
    parser.add_argument("artifact_json", help="Path to marking_result.v1 JSON")
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
