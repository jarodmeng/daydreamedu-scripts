"""Compare marking amendment overrides against base marking results for obsolescence."""

from __future__ import annotations

import json
import math
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Literal

from ai_study_buddy.marking.review.amendment_service import (
    _normalize_field_value,
    _normalize_nullable_text,
    _normalize_summary_overrides,
)

Source = Literal["db", "json", "both"]
FieldStatus = Literal["obsolete", "active", "missing_row", "error"]


def _finite_mark(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return float(value) if value >= 0 else None
    if isinstance(value, float) and math.isfinite(value) and value >= 0:
        return value
    return None


def marks_equal(a: Any, b: Any) -> bool:
    fa, fb = _finite_mark(a), _finite_mark(b)
    if fa is None or fb is None:
        return fa is fb
    return math.isclose(fa, fb, rel_tol=0, abs_tol=1e-9)


def skill_tags_equal(a: Any, b: Any) -> bool:
    def norm(v: Any) -> list[str] | None:
        if not isinstance(v, list):
            return None
        return sorted(tag for tag in v if isinstance(tag, str))

    return norm(a) == norm(b)


def field_values_equal(field_key: str, amendment_val: Any, current_val: Any) -> bool:
    av = _normalize_field_value(field_key, amendment_val)
    cv = _normalize_field_value(field_key, current_val)
    if field_key in {"earned_marks", "max_marks"}:
        return marks_equal(av, cv)
    if field_key == "skill_tags":
        return skill_tags_equal(av, cv)
    return av == cv


def get_question_field(row: dict[str, Any], key: str) -> Any:
    if key == "diagnosis.mistake_type":
        diagnosis = row.get("diagnosis")
        if isinstance(diagnosis, dict):
            return diagnosis.get("mistake_type")
        return row.get("diagnosis_mistake_type")
    if key == "diagnosis.reasoning":
        diagnosis = row.get("diagnosis")
        if isinstance(diagnosis, dict):
            return diagnosis.get("reasoning")
        return row.get("diagnosis_reasoning")
    if key == "skill_tags":
        value = row.get("skill_tags")
        if value is None and row.get("skill_tags_json"):
            try:
                value = json.loads(row["skill_tags_json"])
            except Exception:
                pass
        return value
    return row.get(key)


def question_row_from_db(r: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    out = dict(r)
    if out.get("diagnosis_json"):
        try:
            out["diagnosis"] = json.loads(out["diagnosis_json"])
        except Exception:
            pass
    if out.get("raw_json"):
        try:
            raw = json.loads(out["raw_json"])
            if isinstance(raw, dict):
                for key, value in raw.items():
                    if key not in out or out[key] is None:
                        out[key] = value
        except Exception:
            pass
    return out


def page_row_from_db(r: sqlite3.Row | dict[str, Any]) -> dict[str, Any]:
    out = dict(r)
    if out.get("raw_json"):
        try:
            raw = json.loads(out["raw_json"])
            if isinstance(raw, dict):
                out.update({k: v for k, v in raw.items() if k not in out})
        except Exception:
            pass
    return out


def question_rows_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = payload.get("question_results") if isinstance(payload.get("question_results"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("result_id"), str):
            out[row["result_id"]] = row
    return out


def page_rows_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    rows = context.get("question_page_map") if isinstance(context.get("question_page_map"), list) else []
    out: dict[str, dict[str, Any]] = {}
    for row in rows:
        if isinstance(row, dict) and isinstance(row.get("result_id"), str):
            out[row["result_id"]] = row
    return out


@dataclass
class FieldItem:
    kind: str
    amendment_id: str
    amendment_path: str
    marking_result_path: str
    student_id: str | None
    subject_context: str | None
    result_id: str | None
    field_key: str
    amendment_value: Any
    current_value: Any
    status: FieldStatus


@dataclass
class AuditReport:
    source: Source
    db_path: str | None
    context_root: str | None
    items: list[FieldItem] = field(default_factory=list)
    db_json_mismatch_count: int = 0

    @property
    def status_counts(self) -> Counter[str]:
        return Counter(item.status for item in self.items)

    @property
    def kind_counts(self) -> Counter[str]:
        return Counter(item.kind for item in self.items)

    def items_by_amendment_path(self) -> dict[str, list[FieldItem]]:
        grouped: dict[str, list[FieldItem]] = defaultdict(list)
        for item in self.items:
            grouped[item.amendment_path].append(item)
        return dict(grouped)

    def fully_obsolete_amendment_paths(self) -> list[str]:
        out: list[str] = []
        for path, group in sorted(self.items_by_amendment_path().items()):
            if group and all(item.status == "obsolete" for item in group):
                out.append(path)
        return out

    def partially_obsolete_amendment_paths(self) -> list[str]:
        out: list[str] = []
        for path, group in sorted(self.items_by_amendment_path().items()):
            obs = sum(1 for item in group if item.status == "obsolete")
            act = sum(1 for item in group if item.status == "active")
            if obs and act:
                out.append(path)
        return out

    def to_dict(self, *, sample_limit: int = 10) -> dict[str, Any]:
        def sample(items: list[str]) -> list[str]:
            return items[: max(sample_limit, 0)]

        by_field: Counter[tuple[str, str, str]] = Counter(
            (item.kind, item.field_key, item.status) for item in self.items if item.status in {"obsolete", "active"}
        )
        field_breakdown = [
            {"kind": kind, "field_key": fk, "status": status, "count": count}
            for (kind, fk, status), count in sorted(by_field.items(), key=lambda x: (-x[1], x[0][0], x[0][1], x[0][2]))
        ]

        by_student_subject: Counter[tuple[str | None, str | None, str]] = Counter(
            (item.student_id, item.subject_context, item.status)
            for item in self.items
            if item.kind == "question_field" and item.status in {"obsolete", "active"}
        )
        student_subject = []
        for (student_id, subject_context, status), count in sorted(
            by_student_subject.items(), key=lambda x: (x[0][0] or "", x[0][1] or "", x[0][2])
        ):
            student_subject.append(
                {
                    "student_id": student_id,
                    "subject_context": subject_context,
                    "status": status,
                    "count": count,
                }
            )

        return {
            "source": self.source,
            "db_path": self.db_path,
            "context_root": self.context_root,
            "db_json_mismatch_count": self.db_json_mismatch_count,
            "counts": {
                "total_field_items": len(self.items),
                **dict(self.status_counts),
            },
            "kind_counts": dict(self.kind_counts),
            "field_breakdown": field_breakdown,
            "student_subject_breakdown": student_subject,
            "amendment_file_rollup": {
                "fully_obsolete": len(self.fully_obsolete_amendment_paths()),
                "partially_obsolete": len(self.partially_obsolete_amendment_paths()),
                "no_obsolete_items": len(
                    [
                        path
                        for path, group in self.items_by_amendment_path().items()
                        if group and not any(item.status == "obsolete" for item in group)
                    ]
                ),
            },
            "samples": {
                "fully_obsolete_amendment_paths": sample(self.fully_obsolete_amendment_paths()),
                "partially_obsolete_amendment_paths": sample(self.partially_obsolete_amendment_paths()),
                "obsolete_field_items": sample(
                    [
                        {
                            "amendment_path": item.amendment_path,
                            "result_id": item.result_id,
                            "field_key": item.field_key,
                            "kind": item.kind,
                        }
                        for item in self.items
                        if item.status == "obsolete"
                    ]
                ),
                "active_field_items": sample(
                    [
                        {
                            "amendment_path": item.amendment_path,
                            "result_id": item.result_id,
                            "field_key": item.field_key,
                            "kind": item.kind,
                        }
                        for item in self.items
                        if item.status == "active"
                    ]
                ),
            },
        }


def _audit_amendment_payload(
    *,
    amendment_id: str,
    amendment_path: str,
    marking_result_path: str,
    student_id: str | None,
    subject_context: str | None,
    amendment_payload: dict[str, Any],
    marking_payload: dict[str, Any],
) -> list[FieldItem]:
    items: list[FieldItem] = []
    qrows = question_rows_by_id(marking_payload)
    pmrows = page_rows_by_id(marking_payload)
    summary = marking_payload.get("summary") if isinstance(marking_payload.get("summary"), dict) else {}

    for amendment in amendment_payload.get("question_amendments", []):
        if not isinstance(amendment, dict):
            continue
        result_id = amendment.get("result_id")
        fields = amendment.get("fields")
        if not isinstance(result_id, str) or not isinstance(fields, dict):
            continue
        base_row = qrows.get(result_id)
        if base_row is None:
            for field_key, amendment_value in fields.items():
                items.append(
                    FieldItem(
                        kind="question_field",
                        amendment_id=amendment_id,
                        amendment_path=amendment_path,
                        marking_result_path=marking_result_path,
                        student_id=student_id,
                        subject_context=subject_context,
                        result_id=result_id,
                        field_key=field_key,
                        amendment_value=amendment_value,
                        current_value=None,
                        status="missing_row",
                    )
                )
            continue
        for field_key, amendment_value in fields.items():
            current_value = get_question_field(base_row, field_key)
            status: FieldStatus = (
                "obsolete" if field_values_equal(field_key, amendment_value, current_value) else "active"
            )
            items.append(
                FieldItem(
                    kind="question_field",
                    amendment_id=amendment_id,
                    amendment_path=amendment_path,
                    marking_result_path=marking_result_path,
                    student_id=student_id,
                    subject_context=subject_context,
                    result_id=result_id,
                    field_key=field_key,
                    amendment_value=amendment_value,
                    current_value=current_value,
                    status=status,
                )
            )

    for amendment in amendment_payload.get("question_page_map_amendments", []):
        if not isinstance(amendment, dict):
            continue
        result_id = amendment.get("result_id")
        if not isinstance(result_id, str):
            continue
        base_row = pmrows.get(result_id)
        for field_key in ("attempt_page_start", "confidence"):
            if field_key not in amendment:
                continue
            amendment_value = amendment[field_key]
            current_value = base_row.get(field_key) if base_row else None
            if base_row is None:
                status = "missing_row"
            else:
                status = "obsolete" if amendment_value == current_value else "active"
            items.append(
                FieldItem(
                    kind="page_map",
                    amendment_id=amendment_id,
                    amendment_path=amendment_path,
                    marking_result_path=marking_result_path,
                    student_id=student_id,
                    subject_context=subject_context,
                    result_id=result_id,
                    field_key=field_key,
                    amendment_value=amendment_value,
                    current_value=current_value,
                    status=status,
                )
            )

    overrides = _normalize_summary_overrides(amendment_payload.get("summary_overrides"))
    for field_key, amendment_value in overrides.items():
        current_value = summary.get(field_key)
        av = _normalize_nullable_text(amendment_value) if field_key == "human_note" else amendment_value
        cv = _normalize_nullable_text(current_value) if field_key == "human_note" else current_value
        status = "obsolete" if av == cv else "active"
        items.append(
            FieldItem(
                kind="summary",
                amendment_id=amendment_id,
                amendment_path=amendment_path,
                marking_result_path=marking_result_path,
                student_id=student_id,
                subject_context=subject_context,
                result_id=None,
                field_key=field_key,
                amendment_value=av,
                current_value=cv,
                status=status,
            )
        )

    return items


def audit_from_json(*, context_root: Path) -> AuditReport:
    context_root = context_root.expanduser().resolve()
    items: list[FieldItem] = []

    for amend_path in sorted((context_root / "marking_amendments").rglob("*.json")):
        rel_amend = amend_path.relative_to(context_root).as_posix()
        try:
            amendment_payload = json.loads(amend_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(amendment_payload, dict):
            continue
        context = amendment_payload.get("context") if isinstance(amendment_payload.get("context"), dict) else {}
        marking_result_path = context.get("marking_result_path")
        if not isinstance(marking_result_path, str):
            continue
        mark_path = context_root / marking_result_path
        if not mark_path.is_file():
            continue
        try:
            marking_payload = json.loads(mark_path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(marking_payload, dict):
            continue

        items.extend(
            _audit_amendment_payload(
                amendment_id=rel_amend,
                amendment_path=rel_amend,
                marking_result_path=marking_result_path,
                student_id=context.get("student_id") if isinstance(context.get("student_id"), str) else None,
                subject_context=context.get("subject_context") if isinstance(context.get("subject_context"), str) else None,
                amendment_payload=amendment_payload,
                marking_payload=marking_payload,
            )
        )

    return AuditReport(
        source="json",
        db_path=None,
        context_root=str(context_root),
        items=items,
    )


def audit_from_db(*, db_path: Path, context_root: Path | None = None) -> AuditReport:
    db_path = db_path.expanduser().resolve()
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        amendments = conn.execute(
            """
            SELECT amendment_id, artifact_id, amendment_path, marking_result_path,
                   summary_overrides_json, context_json
            FROM marking_amendments
            WHERE is_deleted = 0
            ORDER BY amendment_path
            """
        ).fetchall()

        qr_by_artifact: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in conn.execute(
            """
            SELECT artifact_id, result_id, outcome, max_marks, earned_marks, student_answer, correct_answer,
                   diagnosis_mistake_type, diagnosis_reasoning, human_note, skill_tags_json, diagnosis_json, raw_json
            FROM marking_question_results
            """
        ):
            qr_by_artifact[row["artifact_id"]][row["result_id"]] = question_row_from_db(row)

        pm_by_artifact: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
        for row in conn.execute(
            "SELECT artifact_id, result_id, attempt_page_start, confidence, raw_json FROM marking_question_page_map"
        ):
            pm_by_artifact[row["artifact_id"]][row["result_id"]] = page_row_from_db(row)

        artifact_summary: dict[str, dict[str, Any]] = {}
        for row in conn.execute(
            "SELECT artifact_id, summary_human_note, summary_json, raw_json FROM marking_artifacts WHERE is_deleted = 0"
        ):
            summary: dict[str, Any] = {}
            if row["summary_json"]:
                try:
                    summary = json.loads(row["summary_json"]) or {}
                except Exception:
                    pass
            if row["raw_json"]:
                try:
                    raw = json.loads(row["raw_json"])
                    if isinstance(raw, dict) and isinstance(raw.get("summary"), dict):
                        summary = {**summary, **raw["summary"]}
                except Exception:
                    pass
            if row["summary_human_note"] is not None:
                summary.setdefault("human_note", row["summary_human_note"])
            artifact_summary[row["artifact_id"]] = summary

        items: list[FieldItem] = []
        for amendment in amendments:
            amendment_id = amendment["amendment_id"]
            artifact_id = amendment["artifact_id"]
            amendment_path = amendment["amendment_path"]
            marking_result_path = amendment["marking_result_path"]
            ctx = json.loads(amendment["context_json"] or "{}")
            student_id = ctx.get("student_id") if isinstance(ctx.get("student_id"), str) else None
            subject_context = ctx.get("subject_context") if isinstance(ctx.get("subject_context"), str) else None
            qrows = qr_by_artifact.get(artifact_id, {})
            pmrows = pm_by_artifact.get(artifact_id, {})
            summary = artifact_summary.get(artifact_id, {})

            for qa in conn.execute(
                "SELECT result_id, fields_json FROM marking_question_amendments WHERE amendment_id = ?",
                (amendment_id,),
            ):
                result_id = qa["result_id"]
                try:
                    fields = json.loads(qa["fields_json"] or "{}")
                except Exception:
                    fields = {}
                if not isinstance(fields, dict):
                    continue
                base_row = qrows.get(result_id)
                if base_row is None:
                    for field_key, amendment_value in fields.items():
                        items.append(
                            FieldItem(
                                kind="question_field",
                                amendment_id=amendment_id,
                                amendment_path=amendment_path,
                                marking_result_path=marking_result_path,
                                student_id=student_id,
                                subject_context=subject_context,
                                result_id=result_id,
                                field_key=field_key,
                                amendment_value=amendment_value,
                                current_value=None,
                                status="missing_row",
                            )
                        )
                    continue
                for field_key, amendment_value in fields.items():
                    current_value = get_question_field(base_row, field_key)
                    status: FieldStatus = (
                        "obsolete" if field_values_equal(field_key, amendment_value, current_value) else "active"
                    )
                    items.append(
                        FieldItem(
                            kind="question_field",
                            amendment_id=amendment_id,
                            amendment_path=amendment_path,
                            marking_result_path=marking_result_path,
                            student_id=student_id,
                            subject_context=subject_context,
                            result_id=result_id,
                            field_key=field_key,
                            amendment_value=amendment_value,
                            current_value=current_value,
                            status=status,
                        )
                    )

            for pa in conn.execute(
                """
                SELECT result_id, attempt_page_start, confidence
                FROM marking_page_map_amendments
                WHERE amendment_id = ?
                """,
                (amendment_id,),
            ):
                result_id = pa["result_id"]
                base_row = pmrows.get(result_id)
                for field_key in ("attempt_page_start", "confidence"):
                    if pa[field_key] is None:
                        continue
                    amendment_value = pa[field_key]
                    current_value = base_row.get(field_key) if base_row else None
                    if base_row is None:
                        status = "missing_row"
                    else:
                        status = "obsolete" if amendment_value == current_value else "active"
                    items.append(
                        FieldItem(
                            kind="page_map",
                            amendment_id=amendment_id,
                            amendment_path=amendment_path,
                            marking_result_path=marking_result_path,
                            student_id=student_id,
                            subject_context=subject_context,
                            result_id=result_id,
                            field_key=field_key,
                            amendment_value=amendment_value,
                            current_value=current_value,
                            status=status,
                        )
                    )

            try:
                overrides = _normalize_summary_overrides(json.loads(amendment["summary_overrides_json"] or "{}"))
            except Exception:
                overrides = {}
            for field_key, amendment_value in overrides.items():
                current_value = summary.get(field_key)
                av = _normalize_nullable_text(amendment_value) if field_key == "human_note" else amendment_value
                cv = _normalize_nullable_text(current_value) if field_key == "human_note" else current_value
                status = "obsolete" if av == cv else "active"
                items.append(
                    FieldItem(
                        kind="summary",
                        amendment_id=amendment_id,
                        amendment_path=amendment_path,
                        marking_result_path=marking_result_path,
                        student_id=student_id,
                        subject_context=subject_context,
                        result_id=None,
                        field_key=field_key,
                        amendment_value=av,
                        current_value=cv,
                        status=status,
                    )
                )
    finally:
        conn.close()

    report = AuditReport(
        source="db",
        db_path=str(db_path),
        context_root=str(context_root.expanduser().resolve()) if context_root else None,
        items=items,
    )
    return report


def build_report(
    *,
    source: Source,
    db_path: Path,
    context_root: Path,
) -> AuditReport:
    db_path = db_path.expanduser().resolve()
    context_root = context_root.expanduser().resolve()

    if source == "db":
        return audit_from_db(db_path=db_path, context_root=context_root)
    if source == "json":
        return audit_from_json(context_root=context_root)

    db_report = audit_from_db(db_path=db_path, context_root=context_root)
    json_report = audit_from_json(context_root=context_root)

    def item_key(item: FieldItem) -> tuple[Any, ...]:
        return (
            item.amendment_path,
            item.kind,
            item.result_id,
            item.field_key,
            json.dumps(item.amendment_value, sort_keys=True, ensure_ascii=True),
        )

    db_keys = {item_key(item): item.status for item in db_report.items}
    json_keys = {item_key(item): item.status for item in json_report.items}
    mismatch = 0
    for key, db_status in db_keys.items():
        json_status = json_keys.get(key)
        if json_status != db_status:
            mismatch += 1
    for key in json_keys:
        if key not in db_keys:
            mismatch += 1

    merged = AuditReport(
        source="both",
        db_path=str(db_path),
        context_root=str(context_root),
        items=db_report.items,
        db_json_mismatch_count=mismatch,
    )
    return merged
