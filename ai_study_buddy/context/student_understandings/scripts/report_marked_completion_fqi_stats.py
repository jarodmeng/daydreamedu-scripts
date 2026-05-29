#!/usr/bin/env python3
"""Report marked-completion and FQI question stats for one student × subject scope.

Traces active marking_result rows under
``context/marking_results/<student_slug>/<subject_context>/`` to each completion's
template ``file_question_info`` run and aggregates question counts and counted
``earned_marks`` / ``max_marks`` by FQI ``question_type``.

Examples::

  python3 report_marked_completion_fqi_stats.py --student-slug winston --subject-context singapore_primary_math
  python3 report_marked_completion_fqi_stats.py --student-slug emma --subject-context singapore_primary_english --write-artifacts
  python3 report_marked_completion_fqi_stats.py --student-slug winston --subject-context singapore_primary_math --json
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_STUDENT_UNDERSTANDINGS_ROOT = _SCRIPT_DIR.parent
_REPO_ROOT = _SCRIPT_DIR.parents[3]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_study_buddy.learning_db.core.connection import default_context_root, default_db_path
from ai_study_buddy.marking.file_question_info.api import iter_questions_ordered

_PREFERRED_TYPE_ORDER = ("MCQ", "SAQ", "LAQ")


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _ordered_question_types(types: Counter[str] | dict[str, int]) -> tuple[str, ...]:
    seen = set(types.keys())
    ordered = [t for t in _PREFERRED_TYPE_ORDER if t in seen]
    ordered.extend(sorted(t for t in seen if t not in _PREFERRED_TYPE_ORDER))
    return tuple(ordered)


def default_output_dir(*, student_slug: str, subject_context: str) -> Path:
    return _STUDENT_UNDERSTANDINGS_ROOT / student_slug.strip() / subject_context.strip()


def _marking_prefix(*, student_slug: str, subject_context: str) -> str:
    return f"marking_results/{student_slug.strip()}/{subject_context.strip()}/"


def _empty_marks_bucket() -> dict[str, float | int]:
    return {"question_count": 0, "earned_marks": 0.0, "max_marks": 0.0}


def _accumulate_marks(
    buckets: dict[str, dict[str, float | int]],
    qtype: str,
    *,
    max_marks: float | None,
    earned_marks: float | None,
) -> None:
    bucket = buckets[qtype]
    bucket["question_count"] = int(bucket["question_count"]) + 1
    bucket["earned_marks"] = float(bucket["earned_marks"]) + float(earned_marks or 0)
    bucket["max_marks"] = float(bucket["max_marks"]) + float(max_marks or 0)


def _marks_buckets_to_report(
    buckets: dict[str, dict[str, float | int]],
    *,
    question_types: tuple[str, ...],
) -> dict[str, Any]:
    by_type: dict[str, dict[str, float | int]] = {}
    for qtype in question_types:
        if qtype in buckets:
            by_type[qtype] = dict(buckets[qtype])
    if "UNKNOWN" in buckets:
        by_type["UNKNOWN"] = dict(buckets["UNKNOWN"])
    total_earned = sum(float(v["earned_marks"]) for v in by_type.values())
    total_max = sum(float(v["max_marks"]) for v in by_type.values())
    total_questions = sum(int(v["question_count"]) for v in by_type.values())
    return {
        "question_count": total_questions,
        "earned_marks": round(total_earned, 2),
        "max_marks": round(total_max, 2),
        "percentage": round(100 * total_earned / total_max, 1) if total_max > 0 else None,
        "by_type": {
            t: {
                "question_count": int(by_type[t]["question_count"]),
                "earned_marks": round(float(by_type[t]["earned_marks"]), 2),
                "max_marks": round(float(by_type[t]["max_marks"]), 2),
                "percentage": round(
                    100 * float(by_type[t]["earned_marks"]) / float(by_type[t]["max_marks"]),
                    1,
                )
                if float(by_type[t]["max_marks"]) > 0
                else None,
            }
            for t in by_type
        },
    }


def _load_latest_fqi_payload(conn: sqlite3.Connection, template_file_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT raw_json, schema_version, source_rel_path
        FROM file_question_info_runs
        WHERE primary_file_id = ? AND is_deleted = 0
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (template_file_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"no active file_question_info for template {template_file_id}")
    payload = json.loads(str(row["raw_json"]))
    if not isinstance(payload, dict):
        raise ValueError(f"FQI raw_json is not an object for template {template_file_id}")
    return {
        "payload": payload,
        "schema_version": str(row["schema_version"] or ""),
        "source_rel_path": str(row["source_rel_path"] or ""),
    }


def _fqi_schema_excluded(schema_version: str, prefixes: tuple[str, ...]) -> str | None:
    for prefix in prefixes:
        if schema_version.startswith(prefix):
            return prefix
    return None


def _fqi_schema_included(schema_version: str, prefixes: tuple[str, ...]) -> bool:
    if not prefixes:
        return True
    return any(schema_version.startswith(prefix) for prefix in prefixes)


def _fetch_markings(
    conn: sqlite3.Connection,
    *,
    marking_prefixes: tuple[str, ...],
) -> list[sqlite3.Row]:
    if not marking_prefixes:
        return []
    if len(marking_prefixes) == 1:
        return conn.execute(
            """
            SELECT artifact_id, artifact_path, template_file_id, attempt_file_id
            FROM marking_artifacts
            WHERE is_deleted = 0 AND artifact_path LIKE ?
            ORDER BY artifact_path
            """,
            (marking_prefixes[0] + "%",),
        ).fetchall()
    clause = " OR ".join(["artifact_path LIKE ?"] * len(marking_prefixes))
    params = [prefix + "%" for prefix in marking_prefixes]
    return conn.execute(
        f"""
        SELECT artifact_id, artifact_path, template_file_id, attempt_file_id
        FROM marking_artifacts
        WHERE is_deleted = 0 AND ({clause})
        ORDER BY artifact_path
        """,
        params,
    ).fetchall()


def build_marked_completion_fqi_stats(
    *,
    student_slug: str,
    subject_contexts: tuple[str, ...],
    study_db: Path,
    context_root: Path,
    include_fqi_schema_prefixes: tuple[str, ...] = (),
    exclude_fqi_schema_prefixes: tuple[str, ...] = (),
) -> dict[str, Any]:
    marking_prefixes = tuple(
        _marking_prefix(student_slug=student_slug, subject_context=subject_context)
        for subject_context in subject_contexts
    )
    conn = sqlite3.connect(str(study_db))
    conn.row_factory = sqlite3.Row
    try:
        markings = _fetch_markings(conn, marking_prefixes=marking_prefixes)

        fqi_by_type: Counter[str] = Counter()
        marking_by_type: Counter[str] = Counter()
        marks_by_type: dict[str, dict[str, float | int]] = defaultdict(_empty_marks_bucket)
        excluded_disqualified_count = 0
        files_by_type_mix: Counter[tuple[str, ...]] = Counter()
        schema_versions = Counter()
        per_file: list[dict[str, Any]] = []
        mismatches: list[dict[str, Any]] = []
        missing_fqi: list[str] = []
        missing_template: list[str] = []
        unknown_result_ids: list[dict[str, str]] = []
        excluded_completions: list[dict[str, str]] = []

        for row in markings:
            artifact_path = str(row["artifact_path"])
            template_file_id = str(row["template_file_id"] or "")
            attempt_file_id = str(row["attempt_file_id"] or "")
            artifact_id = str(row["artifact_id"])

            if not template_file_id:
                missing_template.append(artifact_path)
                continue

            try:
                fqi = _load_latest_fqi_payload(conn, template_file_id)
            except ValueError:
                missing_fqi.append(artifact_path)
                continue

            if not _fqi_schema_included(fqi["schema_version"], include_fqi_schema_prefixes):
                excluded_completions.append(
                    {
                        "artifact_path": artifact_path,
                        "artifact_stem": Path(artifact_path).name,
                        "fqi_schema_version": fqi["schema_version"],
                        "exclude_reason": "schema_not_included",
                        "include_fqi_schema_prefixes": ",".join(include_fqi_schema_prefixes),
                        "fqi_source_rel_path": fqi["source_rel_path"],
                    }
                )
                continue

            excluded_prefix = _fqi_schema_excluded(
                fqi["schema_version"], exclude_fqi_schema_prefixes
            )
            if excluded_prefix is not None:
                excluded_completions.append(
                    {
                        "artifact_path": artifact_path,
                        "artifact_stem": Path(artifact_path).name,
                        "fqi_schema_version": fqi["schema_version"],
                        "exclude_reason": "schema_excluded",
                        "exclude_fqi_schema_prefix": excluded_prefix,
                        "fqi_source_rel_path": fqi["source_rel_path"],
                    }
                )
                continue

            payload = fqi["payload"]
            schema_versions[fqi["schema_version"]] += 1
            qrows = list(iter_questions_ordered(payload))
            qid_to_type = {q["question_index"]: q["question_type"] for q in qrows}

            file_fqi_counts: Counter[str] = Counter()
            for qrow in qrows:
                qtype = str(qrow["question_type"])
                fqi_by_type[qtype] += 1
                file_fqi_counts[qtype] += 1

            marking_rows = conn.execute(
                """
                SELECT result_id, max_marks, earned_marks, scoring_status
                FROM marking_question_results
                WHERE artifact_id = ?
                """,
                (artifact_id,),
            ).fetchall()
            marking_count = len(marking_rows)
            types_in_file: set[str] = set()
            for mrow in marking_rows:
                result_id = str(mrow["result_id"])
                qtype = qid_to_type.get(result_id, "UNKNOWN")
                if qtype == "UNKNOWN":
                    unknown_result_ids.append(
                        {"artifact_path": artifact_path, "result_id": result_id}
                    )
                marking_by_type[qtype] += 1
                types_in_file.add(qtype)
                if str(mrow["scoring_status"] or "") != "counted":
                    excluded_disqualified_count += 1
                    continue
                _accumulate_marks(
                    marks_by_type,
                    qtype,
                    max_marks=mrow["max_marks"],
                    earned_marks=mrow["earned_marks"],
                )

            files_by_type_mix[tuple(sorted(types_in_file))] += 1
            fqi_count = len(qrows)
            if marking_count != fqi_count:
                mismatches.append(
                    {
                        "artifact_stem": Path(artifact_path).name,
                        "artifact_path": artifact_path,
                        "marking_count": marking_count,
                        "fqi_count": fqi_count,
                        "delta": fqi_count - marking_count,
                    }
                )

            file_types = _ordered_question_types(file_fqi_counts)
            per_file.append(
                {
                    "artifact_path": artifact_path,
                    "template_file_id": template_file_id,
                    "attempt_file_id": attempt_file_id,
                    "fqi_schema_version": fqi["schema_version"],
                    "fqi_source_rel_path": fqi["source_rel_path"],
                    "fqi_question_count": fqi_count,
                    "marking_question_count": marking_count,
                    "fqi_by_type": {t: file_fqi_counts.get(t, 0) for t in file_types},
                    "type_mix": sorted(types_in_file),
                }
            )

        question_types = _ordered_question_types(fqi_by_type)
        marks_report_types = _ordered_question_types(
            Counter({k: int(v["question_count"]) for k, v in marks_by_type.items()})
        )
        fqi_total = sum(fqi_by_type.values())
        marking_total = sum(marking_by_type.values())
        per_file_counts = [int(row["fqi_question_count"]) for row in per_file]

        subject_label = (
            subject_contexts[0]
            if len(subject_contexts) == 1
            else " + ".join(subject_contexts)
        )

        return {
            "generated_at": _now_iso(),
            "student_slug": student_slug,
            "subject_context": subject_label,
            "subject_contexts": list(subject_contexts),
            "marking_results_prefix": marking_prefixes[0] if len(marking_prefixes) == 1 else "",
            "marking_results_prefixes": list(marking_prefixes),
            "include_fqi_schema_prefixes": list(include_fqi_schema_prefixes),
            "exclude_fqi_schema_prefixes": list(exclude_fqi_schema_prefixes),
            "excluded_completion_count": len(excluded_completions),
            "excluded_completions": excluded_completions,
            "study_buddy_db": str(study_db.resolve()),
            "context_root": str(context_root.resolve()),
            "question_types": list(question_types),
            "marking_result_count": len(markings),
            "included_marking_result_count": len(per_file),
            "templates_with_fqi": len(per_file),
            "missing_template_file_id_count": len(missing_template),
            "missing_fqi_count": len(missing_fqi),
            "fqi_schema_versions": dict(sorted(schema_versions.items())),
            "fqi_question_totals": {
                "total": fqi_total,
                "by_type": {t: fqi_by_type.get(t, 0) for t in question_types},
            },
            "fqi_per_file": {
                "min": min(per_file_counts) if per_file_counts else 0,
                "max": max(per_file_counts) if per_file_counts else 0,
                "avg": round(fqi_total / len(per_file_counts), 1) if per_file_counts else 0.0,
            },
            "marking_question_totals": {
                "total": marking_total,
                "by_type": {
                    t: marking_by_type.get(t, 0)
                    for t in (*question_types, "UNKNOWN")
                    if marking_by_type.get(t, 0) or t == "UNKNOWN"
                },
            },
            "excluded_disqualified_question_count": excluded_disqualified_count,
            "marking_marks_by_type": _marks_buckets_to_report(
                marks_by_type,
                question_types=marks_report_types,
            ),
            "files_by_type_mix": [
                {"types": list(mix), "count": count}
                for mix, count in sorted(
                    files_by_type_mix.items(), key=lambda item: (-item[1], item[0])
                )
            ],
            "fqi_vs_marking_mismatches": mismatches,
            "unknown_result_id_count": len(unknown_result_ids),
            "unknown_result_ids": unknown_result_ids,
            "missing_template_file_id_paths": missing_template,
            "missing_fqi_paths": missing_fqi,
            "per_file": per_file,
        }
    finally:
        conn.close()


def _pct(part: int, whole: int) -> str:
    if whole <= 0:
        return "0.0%"
    return f"{100 * part / whole:.1f}%"


def _fmt_pct(value: float | None) -> str:
    return f"{value:.1f}%" if value is not None else "—"


def render_markdown(report: dict[str, Any]) -> str:
    fqi = report["fqi_question_totals"]
    fqi_total = int(fqi["total"])
    marking = report["marking_question_totals"]
    question_types: list[str] = list(report.get("question_types") or [])
    lines = [
        f"# Marked completion × FQI stats — {report['student_slug']} / {report['subject_context']}",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "## Scope",
        "",
        f"- Marking results prefixes: `{json.dumps(report.get('marking_results_prefixes') or [report.get('marking_results_prefix')], ensure_ascii=False)}`",
        f"- Include FQI schema prefixes: `{json.dumps(report.get('include_fqi_schema_prefixes') or [], ensure_ascii=False)}`",
        f"- Exclude FQI schema prefixes: `{json.dumps(report.get('exclude_fqi_schema_prefixes') or [], ensure_ascii=False)}`",
        f"- Active marking results in scope: **{report['marking_result_count']}**",
        f"- Included in totals: **{report.get('included_marking_result_count', report['templates_with_fqi'])}**",
        f"- Excluded completions (FQI schema filter): **{report.get('excluded_completion_count', 0)}**",
        f"- Templates with FQI (included): **{report['templates_with_fqi']}**",
        f"- Missing template file id: {report['missing_template_file_id_count']}",
        f"- Missing FQI: {report['missing_fqi_count']}",
        f"- Excluded/disqualified question rows (not in marks totals): {report.get('excluded_disqualified_question_count', 0)}",
        f"- FQI schema versions: `{json.dumps(report['fqi_schema_versions'], ensure_ascii=False)}`",
        "",
        "## FQI question totals",
        "",
        "Each row is one `question_info` entry (sub-parts such as `Q1(a)` count separately).",
        "",
        "| Type | Count | Share |",
        "|------|------:|------:|",
    ]
    for qtype in question_types:
        count = int(fqi["by_type"].get(qtype, 0))
        lines.append(f"| {qtype} | {count} | {_pct(count, fqi_total)} |")
    lines.append(f"| **Total** | **{fqi_total}** | 100% |")

    per_file = report["fqi_per_file"]
    lines.extend(
        [
            "",
            f"Per file (FQI): min {per_file['min']}, max {per_file['max']}, avg {per_file['avg']}",
            "",
            "## Files by question-type mix",
            "",
            "| Types present | Files |",
            "|---------------|------:|",
        ]
    )
    for row in report["files_by_type_mix"]:
        lines.append(f"| {', '.join(row['types'])} | {row['count']} |")

    lines.extend(
        [
            "",
            "## Marking question_results (mapped via FQI `question_index`)",
            "",
            "| Type | Marked rows | FQI rows |",
            "|------|------------:|---------:|",
        ]
    )
    for qtype in question_types:
        marked = int(marking["by_type"].get(qtype, 0))
        fqi_count = int(fqi["by_type"].get(qtype, 0))
        lines.append(f"| {qtype} | {marked} | {fqi_count} |")
    unknown = int(marking["by_type"].get("UNKNOWN", 0))
    if unknown:
        lines.append(f"| UNKNOWN | {unknown} | — |")
    lines.append(f"| **Total** | **{marking['total']}** | **{fqi_total}** |")

    marks = report.get("marking_marks_by_type") or {}
    marks_by_type = marks.get("by_type") or {}
    if marks_by_type:
        lines.extend(
            [
                "",
                "## Marks by question type",
                "",
                "Sums `earned_marks` and `max_marks` from marking rows with `scoring_status=counted`, "
                "mapped to FQI `question_type`.",
                "",
                "| Type | Questions | Earned | Max | % |",
                "|------|----------:|-------:|----:|--:|",
            ]
        )
        marks_types_ordered = _ordered_question_types(
            Counter({k: int(v.get("question_count", 0)) for k, v in marks_by_type.items()})
        )
        for qtype in marks_types_ordered:
            row = marks_by_type[qtype]
            lines.append(
                f"| {qtype} | {row['question_count']} | {row['earned_marks']} | {row['max_marks']} | {_fmt_pct(row.get('percentage'))} |"
            )
        if "UNKNOWN" in marks_by_type and "UNKNOWN" not in marks_types_ordered:
            row = marks_by_type["UNKNOWN"]
            lines.append(
                f"| UNKNOWN | {row['question_count']} | {row['earned_marks']} | {row['max_marks']} | {_fmt_pct(row.get('percentage'))} |"
            )
        lines.append(
            f"| **Total** | **{marks.get('question_count', 0)}** | **{marks.get('earned_marks', 0)}** | **{marks.get('max_marks', 0)}** | **{_fmt_pct(marks.get('percentage'))}** |"
        )

    mismatches = report["fqi_vs_marking_mismatches"]
    lines.extend(
        [
            "",
            f"## FQI vs marking count mismatches ({len(mismatches)})",
            "",
        ]
    )
    if mismatches:
        lines.extend(
            [
                "| Artifact | Marked | FQI | Δ |",
                "|----------|-------:|----:|--:|",
            ]
        )
        for row in mismatches:
            lines.append(
                f"| {row['artifact_stem']} | {row['marking_count']} | {row['fqi_count']} | {row['delta']} |"
            )
    else:
        lines.append("None.")

    if report["unknown_result_id_count"]:
        lines.extend(
            [
                "",
                f"## Unmapped marking `result_id`s ({report['unknown_result_id_count']})",
                "",
            ]
        )
        for row in report["unknown_result_ids"][:20]:
            lines.append(f"- `{row['artifact_path']}` → `{row['result_id']}`")

    excluded = report.get("excluded_completions") or []
    if excluded:
        lines.extend(
            [
                "",
                f"## Excluded completions ({len(excluded)})",
                "",
                "| Artifact | FQI schema | Reason |",
                "|----------|------------|--------|",
            ]
        )
        for row in excluded:
            reason = row.get("exclude_reason") or "schema_excluded"
            if reason == "schema_not_included":
                detail = f"not in include: {row.get('include_fqi_schema_prefixes', '')}"
            else:
                detail = f"matches exclude: {row.get('exclude_fqi_schema_prefix', '')}"
            lines.append(f"| {row['artifact_stem']} | {row['fqi_schema_version']} | {detail} |")

    return "\n".join(lines) + "\n"


def _print_human(report: dict[str, Any]) -> None:
    fqi = report["fqi_question_totals"]
    marking = report["marking_question_totals"]
    question_types: list[str] = list(report.get("question_types") or [])
    print(f"student_slug: {report['student_slug']}")
    print(f"subject_context: {report['subject_context']}")
    print(f"marking_result_count: {report['marking_result_count']}")
    print(f"included_marking_result_count: {report.get('included_marking_result_count', report['templates_with_fqi'])}")
    if report.get("excluded_completion_count"):
        print(f"excluded_completions: {report['excluded_completion_count']}")
    print(f"templates_with_fqi: {report['templates_with_fqi']}")
    print(f"fqi_schema_versions: {report['fqi_schema_versions']}")
    print("\nFQI question totals:")
    for qtype in question_types:
        count = fqi["by_type"].get(qtype, 0)
        print(f"  {qtype}: {count}")
    print(f"  total: {fqi['total']}")
    per_file = report["fqi_per_file"]
    print(f"  per-file min/max/avg: {per_file['min']}/{per_file['max']}/{per_file['avg']}")
    print("\nFiles by type mix:")
    for row in report["files_by_type_mix"]:
        print(f"  {', '.join(row['types'])}: {row['count']}")
    print("\nMarking question_results:")
    for qtype in (*question_types, "UNKNOWN"):
        if marking["by_type"].get(qtype):
            print(f"  {qtype}: {marking['by_type'][qtype]}")
    print(f"  total: {marking['total']}")
    marks = report.get("marking_marks_by_type") or {}
    if marks.get("by_type"):
        print("\nMarks by question type (counted rows):")
        for qtype, row in marks["by_type"].items():
            print(
                f"  {qtype}: {row['earned_marks']}/{row['max_marks']} marks "
                f"({row['question_count']} questions, {_fmt_pct(row.get('percentage'))})"
            )
        print(
            f"  total: {marks.get('earned_marks')}/{marks.get('max_marks')} "
            f"({_fmt_pct(marks.get('percentage'))})"
        )
    excluded = report.get("excluded_disqualified_question_count", 0)
    if excluded:
        print(f"  excluded/disqualified rows (omitted from marks): {excluded}")
    print(f"\nFQI vs marking mismatches: {len(report['fqi_vs_marking_mismatches'])}")
    for row in report["fqi_vs_marking_mismatches"]:
        print(
            f"  {row['artifact_stem']}: marking={row['marking_count']} fqi={row['fqi_count']}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report marked-completion and FQI question stats for one student × subject."
    )
    parser.add_argument(
        "--student-slug",
        required=True,
        help="Student folder slug under context/marking_results/ (e.g. winston, emma, abigail)",
    )
    parser.add_argument(
        "--subject-context",
        action="append",
        required=True,
        metavar="SUBJECT",
        help=(
            "Subject folder slug under marking_results/ (repeat for multiple; "
            "e.g. singapore_primary_chinese and singapore_primary_higher_chinese)"
        ),
    )
    parser.add_argument("--study-db-path", type=Path, default=None)
    parser.add_argument("--context-root", type=Path, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory for artifact writes (default: student_understandings/<student>/<subject>/)",
    )
    parser.add_argument(
        "--write-artifacts",
        action="store_true",
        help="Write marked_completion_fqi_stats.json and .md under --output-dir",
    )
    parser.add_argument("--json", action="store_true", help="Print full JSON report to stdout")
    parser.add_argument(
        "--include-fqi-schema-prefix",
        action="append",
        default=[],
        metavar="PREFIX",
        help=(
            "When set, only include completions whose FQI schema_version starts with PREFIX "
            "(repeatable; use with singapore_primary_chinese to keep 高华 only)"
        ),
    )
    parser.add_argument(
        "--exclude-fqi-schema-prefix",
        action="append",
        default=[],
        metavar="PREFIX",
        help=(
            "Exclude completions whose template FQI schema_version starts with PREFIX "
            "(repeatable; e.g. high-chinese for 高华 under singapore_primary_chinese)"
        ),
    )
    args = parser.parse_args()

    study_db = (args.study_db_path or default_db_path()).expanduser().resolve()
    context_root = (args.context_root or default_context_root()).expanduser().resolve()
    subject_contexts = tuple(s.strip() for s in args.subject_context if s.strip())
    include_prefixes = tuple(p.strip() for p in args.include_fqi_schema_prefix if p.strip())
    exclude_prefixes = tuple(p.strip() for p in args.exclude_fqi_schema_prefix if p.strip())

    report = build_marked_completion_fqi_stats(
        student_slug=args.student_slug,
        subject_contexts=subject_contexts,
        study_db=study_db,
        context_root=context_root,
        include_fqi_schema_prefixes=include_prefixes,
        exclude_fqi_schema_prefixes=exclude_prefixes,
    )

    if args.write_artifacts:
        out_dir = (
            args.output_dir.expanduser().resolve()
            if args.output_dir
            else default_output_dir(
                student_slug=args.student_slug,
                subject_context=subject_contexts[-1],
            )
        )
        out_dir.mkdir(parents=True, exist_ok=True)
        json_path = out_dir / "marked_completion_fqi_stats.json"
        md_path = out_dir / "marked_completion_fqi_stats.md"
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        md_path.write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote {json_path}")
        print(f"wrote {md_path}")

    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    elif not args.write_artifacts:
        _print_human(report)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
