from __future__ import annotations

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
import re
from pathlib import Path

from ai_study_buddy.marking.core.artifact_paths import build_marking_artifact_path, normalize_attempt_stem
from ai_study_buddy.marking.core.artifact_schema import compute_percentage, validate_marking_artifact_dict
from ai_study_buddy.marking.core.artifact_writer import write_marking_artifact
from ai_study_buddy.marking.core.models import (
    ArtifactQuestionResult,
    ArtifactSummary,
    Diagnosis,
    GenerationMeta,
    MarkingArtifact,
    MarkingArtifactContext,
    QuestionSelection,
    ReviewMeta,
)
from ai_study_buddy.marking.core.taxonomy import derive_skill_tags_from_embedding_label
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

_HEADER_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.MULTILINE)
_RESULT_LINE_RE = re.compile(r"^- (?P<label>[^:]+): (?P<value>.+)$")
_PDF_MANAGER = None
_PDF_MANAGER_LOADED = False


def _section_map(markdown: str) -> dict[str, str]:
    matches = list(_HEADER_RE.finditer(markdown))
    sections: dict[str, str] = {}
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(markdown)
        sections[match.group("title")] = markdown[start:end].strip()
    return sections


def _strip_wrappers(value: str) -> str:
    text = value.strip()
    if text.startswith("`") and text.endswith("`"):
        text = text[1:-1]
    if text.startswith("**") and text.endswith("**"):
        text = text[2:-2]
    return text.strip()


def _parse_result_section(section: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in section.splitlines():
        match = _RESULT_LINE_RE.match(line.strip())
        if not match:
            continue
        parsed[match.group("label").strip()] = _strip_wrappers(match.group("value"))
    return parsed


def _parse_context_section(section: str) -> dict[str, str]:
    parsed: dict[str, str] = {}
    for line in section.splitlines():
        match = _RESULT_LINE_RE.match(line.strip())
        if not match:
            continue
        parsed[match.group("label").strip()] = _strip_wrappers(match.group("value"))
    return parsed


def _parse_table(section: str) -> list[dict[str, str]]:
    table_lines = [line for line in section.splitlines() if line.strip().startswith("|")]
    if len(table_lines) < 2:
        return []
    header = [_strip_wrappers(cell) for cell in table_lines[0].strip().split("|")[1:-1]]
    rows: list[dict[str, str]] = []
    for line in table_lines[2:]:
        cells = [_strip_wrappers(cell) for cell in line.strip().split("|")[1:-1]]
        if len(cells) != len(header):
            continue
        rows.append(dict(zip(header, cells)))
    return rows


def _parse_outcome(name_cell: str, obtained_marks: int, total_marks: int) -> tuple[str, str]:
    text = name_cell.strip()
    label = text
    outcome = "wrong"
    if text.startswith("⛔"):
        outcome = "disqualified"
        label = text[1:].strip()
    elif text.startswith("✅"):
        outcome = "correct"
        label = text[1:].strip()
    elif text.startswith("⚠️"):
        outcome = "partial"
        label = text[2:].strip()
    elif text.startswith("❌"):
        outcome = "wrong"
        label = text[1:].strip()
    elif obtained_marks == total_marks:
        outcome = "correct"
    elif obtained_marks > 0:
        outcome = "partial"
    if outcome == "disqualified":
        label = re.sub(r"\s*\(disqualified\)\s*$", "", label, flags=re.IGNORECASE).strip()
    return outcome, label


def _iso_from_file_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat().replace("+00:00", "Z")


def _combine_report_date_with_file_time(report_date: str | None, path: Path) -> str:
    file_dt = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    if not report_date:
        return file_dt.isoformat().replace("+00:00", "Z")
    try:
        report_day = datetime.strptime(report_date, "%Y-%m-%d").date()
    except ValueError:
        return file_dt.isoformat().replace("+00:00", "Z")
    combined = datetime.combine(report_day, file_dt.timetz())
    return combined.isoformat().replace("+00:00", "Z")


def _get_pdf_file_manager():
    global _PDF_MANAGER, _PDF_MANAGER_LOADED
    if _PDF_MANAGER_LOADED:
        return _PDF_MANAGER
    _PDF_MANAGER_LOADED = True
    try:
        _PDF_MANAGER = PdfFileManager()
    except Exception:
        _PDF_MANAGER = None
    return _PDF_MANAGER


def _resolve_file_id_from_path(file_path: str | None) -> str | None:
    if not file_path:
        return None
    candidate_path = _extract_pdf_path_from_mixed_text(file_path)
    if not candidate_path:
        return None
    manager = _get_pdf_file_manager()
    if manager is None:
        return None
    try:
        pdf_file = manager.get_file_by_path(candidate_path)
    except Exception:
        return None
    if pdf_file is None:
        return None
    return pdf_file.id


def _extract_pdf_path_from_mixed_text(file_path: str | None) -> str | None:
    if not file_path:
        return None
    candidate_path = file_path.strip()
    backtick_match = re.search(r"`([^`]+\\.pdf)`", candidate_path, flags=re.IGNORECASE)
    if backtick_match:
        candidate_path = backtick_match.group(1).strip()
    elif not candidate_path.casefold().endswith(".pdf"):
        pdf_match = re.search(r"(/[^\\n]+?\\.pdf)", candidate_path, flags=re.IGNORECASE)
        if pdf_match:
            candidate_path = pdf_match.group(1).strip()
    return candidate_path


def _resolve_book_group_from_file_ids(*file_ids: str | None) -> tuple[str | None, str | None]:
    manager = _get_pdf_file_manager()
    if manager is None:
        return None, None
    for file_id in file_ids:
        if not file_id:
            continue
        try:
            groups = manager.get_file_group_membership(file_id)
        except Exception:
            continue
        for group in groups:
            if getattr(group, "group_type", None) == "book":
                return getattr(group, "id", None), getattr(group, "label", None)
    return None, None


def _derive_unit_label(unit_file_id: str | None, template_file_path: str | None) -> str | None:
    manager = _get_pdf_file_manager()
    if manager is not None and unit_file_id:
        try:
            unit_file = manager.get_file(unit_file_id)
        except Exception:
            unit_file = None
        if unit_file is not None and getattr(unit_file, "name", None):
            return normalize_attempt_stem(unit_file.name)
    extracted = _extract_pdf_path_from_mixed_text(template_file_path)
    if extracted:
        return normalize_attempt_stem(Path(extracted).name)
    return None


def parse_legacy_learning_report(report_path: str | Path) -> tuple[MarkingArtifact, list[str]]:
    path = Path(report_path)
    text = path.read_text(encoding="utf-8")
    sections = _section_map(text)
    warnings: list[str] = []

    result_data = _parse_result_section(sections.get("Result", ""))
    context_data = _parse_context_section(sections.get("Report Context", ""))
    table_rows = _parse_table(sections.get("Marking Table", ""))

    student_name = result_data.get("Student")
    report_date = result_data.get("Date")
    score = result_data.get("Score")
    percentage_text = result_data.get("Percentage")
    overall_assessment = result_data.get("Overall assessment", "")

    earned_marks = 0
    total_marks = 0
    if score and "/" in score:
        earned_text, total_text = score.split("/", 1)
        earned_marks = int(_strip_wrappers(earned_text))
        total_marks = int(_strip_wrappers(total_text))
    else:
        warnings.append("missing or malformed Score field")

    percentage = compute_percentage(earned_marks, total_marks)
    if percentage_text:
        cleaned_percentage = percentage_text.replace("%", "").strip()
        try:
            percentage = float(cleaned_percentage)
        except ValueError:
            warnings.append("malformed Percentage field")

    question_results: list[ArtifactQuestionResult] = []
    for row in table_rows:
        total_row_marks = int(_strip_wrappers(row.get("Total marks", "0")))
        obtained_row_marks = int(_strip_wrappers(row.get("Obtained marks", "0")))
        outcome, result_id = _parse_outcome(row.get("Name", ""), obtained_row_marks, total_row_marks)
        scoring_status = "excluded_disqualified" if outcome == "disqualified" else "counted"
        embedding_label = row.get("Embedding", "")
        skill_tags = ()
        if scoring_status == "counted":
            skill_tags = derive_skill_tags_from_embedding_label(embedding_label)
        question_results.append(
            ArtifactQuestionResult(
                result_id=result_id,
                max_marks=total_row_marks,
                earned_marks=obtained_row_marks,
                outcome=outcome,
                student_answer=row.get("Student answer") or None,
                correct_answer=row.get("Correct answer") or None,
                scoring_status=scoring_status,
                feedback=None,
                error_tags=(),
                skill_tags=skill_tags,
                diagnosis=Diagnosis(),
                human_note=None,
            )
        )

    attempt_file_path = context_data.get("Attempt file")
    template_file_path = context_data.get("Template book file")
    answer_file_path = context_data.get("Book answer file")
    attempt_file_id = _resolve_file_id_from_path(attempt_file_path)
    template_file_id = _resolve_file_id_from_path(template_file_path)
    answer_file_id = _resolve_file_id_from_path(answer_file_path)
    unit_file_id = template_file_id
    unit_label = _derive_unit_label(unit_file_id, template_file_path)
    book_group_id, book_label = _resolve_book_group_from_file_ids(unit_file_id, template_file_id, attempt_file_id, answer_file_id)
    page_range = (
        context_data.get("Answer page range for this exercise")
        or context_data.get("Answer page range for this test")
        or context_data.get("Answer page range for this chapter")
    )
    answer_page_start = None
    answer_page_end = None
    if page_range and "-" in page_range:
        start_text, end_text = page_range.split("-", 1)
        try:
            answer_page_start = int(start_text.strip())
            answer_page_end = int(end_text.strip())
        except ValueError:
            warnings.append("malformed answer page range")
    else:
        warnings.append("missing answer page range")

    created_at = _combine_report_date_with_file_time(report_date, path)

    counted_rows = [row for row in question_results if row.scoring_status == "counted"]
    summary_total = sum(row.max_marks for row in counted_rows) or total_marks
    summary_earned = sum(row.earned_marks for row in counted_rows) or earned_marks

    summary = ArtifactSummary(
        total_marks=summary_total,
        earned_marks=summary_earned,
        percentage=compute_percentage(
            summary_earned,
            summary_total,
        ),
        overall_assessment=overall_assessment,
        human_note=None,
    )

    if percentage_text and abs(round(summary.percentage) - percentage) >= 0.01:
        warnings.append("percentage in report differs from percentage recomputed from table rows")

    context = MarkingArtifactContext(
        student_id=path.parent.parent.name,
        student_name=student_name,
        subject_context=path.parent.name,
        attempt_file_id=attempt_file_id,
        attempt_file_path=attempt_file_path or path.stem.replace(" - Marking Report", "") + ".pdf",
        template_file_id=template_file_id,
        template_file_path=template_file_path,
        book_group_id=book_group_id,
        book_label=book_label,
        unit_file_id=unit_file_id,
        unit_file_path=template_file_path,
        unit_label=unit_label,
        answer_file_id=answer_file_id,
        answer_file_path=answer_file_path,
        answer_page_start=answer_page_start,
        answer_page_end=answer_page_end,
        starts_mid_page=False,
        ends_mid_page=False,
        answer_mapping_source=context_data.get("Mapping source"),
        answer_mapping_notes=context_data.get("Answer page note"),
        question_selection=QuestionSelection(raw_text=None),
    )
    generation_notes = "Migrated from legacy markdown learning report."
    if warnings:
        generation_notes += " Warnings: " + " | ".join(warnings)
    artifact = MarkingArtifact(
        schema_version="marking_result.v1",
        created_at=created_at,
        updated_at=created_at,
        context=context,
        summary=summary,
        question_results=tuple(question_results),
        review_meta=ReviewMeta(),
        generation=GenerationMeta(
            produced_by="migrate_learning_reports",
            mode="migration_from_legacy_markdown",
            notes=generation_notes,
        ),
    )
    validate_marking_artifact_dict(artifact.to_dict())
    return artifact, warnings


def migrate_learning_reports(
    *,
    reports_root: str | Path = "ai_study_buddy/context/learning_reports",
    context_root: str | Path = "ai_study_buddy/context",
    student: str | None = None,
    subject_context: str | None = None,
    limit: int | None = None,
    overwrite: bool = False,
    dry_run: bool = False,
) -> list[dict[str, str | int | bool]]:
    root = Path(reports_root)
    report_paths = sorted(root.rglob("* - Marking Report.md"))
    if student is not None:
        report_paths = [path for path in report_paths if path.parent.parent.name == student]
    if subject_context is not None:
        report_paths = [path for path in report_paths if path.parent.name == subject_context]
    if limit is not None:
        report_paths = report_paths[:limit]

    results: list[dict[str, str | int | bool]] = []
    for report_path in report_paths:
        artifact, warnings = parse_legacy_learning_report(report_path)
        destination = build_marking_artifact_path(artifact, context_root=context_root)
        status = "pending"
        if destination.exists() and not overwrite:
            status = "skipped_existing"
        elif not dry_run:
            write_marking_artifact(artifact, output_path=destination, context_root=context_root)
            status = "written"
        results.append(
            {
                "report_path": str(report_path),
                "output_path": str(destination),
                "status": status,
                "warning_count": len(warnings),
                "dry_run": dry_run,
            }
        )
    return results


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Migrate legacy markdown learning reports into marking_result.v1 JSON artifacts.")
    parser.add_argument("--reports-root", default="ai_study_buddy/context/learning_reports")
    parser.add_argument("--context-root", default="ai_study_buddy/context")
    parser.add_argument("--student")
    parser.add_argument("--subject-context")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser


def main() -> int:
    args = _build_arg_parser().parse_args()
    results = migrate_learning_reports(
        reports_root=args.reports_root,
        context_root=args.context_root,
        student=args.student,
        subject_context=args.subject_context,
        limit=args.limit,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    print(json.dumps(results, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
