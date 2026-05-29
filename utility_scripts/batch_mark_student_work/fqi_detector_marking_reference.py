"""Load prior marking question_page_map context for template FQI detector runs."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONTEXT_ROOT = _REPO_ROOT / "ai_study_buddy" / "context"

_PRIOR_MARKING_REFERENCE_FILENAME = "prior_marking_reference.json"
_REFERENCE_DISCLAIMER = (
    "Prior marking question_page_map is completion-oriented and non-binding. "
    "Ground FQI on the template PDF and rendered_pages; use marking only as context. "
    "Note discrepancies in input_context.hints and debug.notes when they differ."
)


def parse_student_grade_filters(specs: list[str]) -> list[tuple[str, set[str]]]:
    """Parse repeatable ``--student-grade 'Winston Meng:P6,PSLE'`` arguments."""
    out: list[tuple[str, set[str]]] = []
    for raw in specs:
        text = raw.strip()
        if not text or ":" not in text:
            raise ValueError(f"invalid --student-grade (expected Name:P4,P5): {raw!r}")
        name, grades_part = text.split(":", 1)
        name = name.strip()
        grades = {g.strip().upper() for g in grades_part.split(",") if g.strip()}
        if not name or not grades:
            raise ValueError(f"invalid --student-grade (empty name or grades): {raw!r}")
        out.append((name, grades))
    return out


def default_priority_filters() -> list[tuple[str, set[str]]]:
    return [
        ("Winston Meng", {"P6", "PSLE"}),
        ("Emma Meng", {"P4"}),
    ]


def remaining_p1_p5_filters() -> list[tuple[str, set[str]]]:
    """Filters for the 15 marked templates that still lack FQI (May 2026 gap slice)."""
    return [
        ("Abigail Meng", {"P1"}),
        ("Emma Meng", {"P1"}),
        ("Winston Meng", {"P5"}),
    ]


def _compact_page_map_row(row: Any) -> dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    result_id = row.get("result_id")
    if not isinstance(result_id, str) or not result_id.strip():
        return None
    compact: dict[str, Any] = {"result_id": result_id.strip()}
    page = row.get("attempt_page_start")
    if isinstance(page, int):
        compact["attempt_page_start"] = page
    for key in ("source", "confidence", "note"):
        value = row.get(key)
        if value is not None and value != "":
            compact[key] = value
    return compact


def _question_page_map_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    context = payload.get("context")
    if not isinstance(context, dict):
        return []
    raw_map = context.get("question_page_map")
    if not isinstance(raw_map, list):
        return []
    out: list[dict[str, Any]] = []
    for row in raw_map:
        compact = _compact_page_map_row(row)
        if compact is not None:
            out.append(compact)
    return out


def _load_latest_marking_row(sconn: sqlite3.Connection, attempt_file_id: str) -> sqlite3.Row | None:
    return sconn.execute(
        """
        SELECT artifact_id, artifact_path, is_partial, context_json, raw_json, created_at
        FROM marking_artifacts
        WHERE is_deleted=0 AND attempt_file_id=?
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (attempt_file_id,),
    ).fetchone()


def _question_result_ids(sconn: sqlite3.Connection, artifact_id: str) -> list[str]:
    rows = sconn.execute(
        """
        SELECT result_id FROM marking_question_results
        WHERE artifact_id=?
        ORDER BY result_id
        """,
        (artifact_id,),
    ).fetchall()
    return [str(row[0]) for row in rows if row[0] is not None]


def load_completion_marking_reference(
    sconn: sqlite3.Connection,
    *,
    completion_file_id: str,
    context_root: Path | None = None,
) -> dict[str, Any] | None:
    """Return a compact marking reference for one completion, or None if unmarked."""
    row = _load_latest_marking_row(sconn, completion_file_id)
    if row is None:
        return None

    context_payload: dict[str, Any] = {}
    raw_payload: dict[str, Any] = {}
    try:
        parsed = json.loads(str(row["context_json"] or "{}"))
        if isinstance(parsed, dict):
            context_payload = parsed
    except json.JSONDecodeError:
        pass
    try:
        parsed = json.loads(str(row["raw_json"] or "{}"))
        if isinstance(parsed, dict):
            raw_payload = parsed
    except json.JSONDecodeError:
        pass

    question_page_map = _question_page_map_from_payload(context_payload)
    if not question_page_map and raw_payload:
        question_page_map = _question_page_map_from_payload(raw_payload)

    artifact_id = str(row["artifact_id"])
    question_result_ids = _question_result_ids(sconn, artifact_id)

    artifact_path = str(row["artifact_path"] or "")
    rel_path = artifact_path
    root = (context_root or _DEFAULT_CONTEXT_ROOT).resolve()
    try:
        rel_path = str(Path(artifact_path).resolve().relative_to(root))
    except ValueError:
        pass

    return {
        "completion_file_id": completion_file_id,
        "marking_artifact_id": artifact_id,
        "marking_result_path": rel_path,
        "marking_created_at": str(row["created_at"] or ""),
        "is_partial": bool(row["is_partial"]),
        "question_page_map_count": len(question_page_map),
        "question_page_map": question_page_map,
        "question_result_ids": question_result_ids,
    }


def build_template_marking_reference(
    sconn: sqlite3.Connection,
    *,
    template_file_id: str,
    linked_completion_file_ids: list[str],
    context_root: Path | None = None,
) -> dict[str, Any]:
    linked: list[dict[str, Any]] = []
    for completion_id in linked_completion_file_ids:
        ref = load_completion_marking_reference(
            sconn,
            completion_file_id=completion_id,
            context_root=context_root,
        )
        if ref is not None:
            linked.append(ref)

    return {
        "template_file_id": template_file_id,
        "disclaimer": _REFERENCE_DISCLAIMER,
        "linked_completions": linked,
        "linked_completions_with_marking": len(linked),
        "linked_completions_total": len(linked_completion_file_ids),
    }


def marking_reference_prompt_section(reference: dict[str, Any] | None) -> str:
    if not reference:
        return ""
    linked = reference.get("linked_completions")
    if not isinstance(linked, list) or not linked:
        return ""

    lines = [
        "## Prior marking reference (non-binding)",
        reference.get("disclaimer") or _REFERENCE_DISCLAIMER,
        "",
        "Use this only for context (question ids, approximate pages). "
        "Template PDF + rendered_pages are authoritative. "
        "Record meaningful differences in input_context.hints and debug.notes.",
        "",
    ]
    for entry in linked:
        if not isinstance(entry, dict):
            continue
        lines.append(f"### completion_file_id={entry.get('completion_file_id')}")
        lines.append(f"- marking_result_path: {entry.get('marking_result_path')}")
        lines.append(f"- is_partial: {entry.get('is_partial')}")
        lines.append(f"- question_page_map_count: {entry.get('question_page_map_count')}")
        qids = entry.get("question_result_ids")
        if isinstance(qids, list) and qids:
            preview = ", ".join(str(x) for x in qids[:20])
            if len(qids) > 20:
                preview += f", … (+{len(qids) - 20} more)"
            lines.append(f"- question_result_ids: {preview}")
        qpm = entry.get("question_page_map")
        if isinstance(qpm, list) and qpm:
            lines.append("- question_page_map (JSON):")
            lines.append("```json")
            lines.append(json.dumps(qpm, indent=2, ensure_ascii=False))
            lines.append("```")
        lines.append("")

    return "\n".join(lines).rstrip() + "\n\n"


def write_prior_marking_reference_sidecar(
    reference: dict[str, Any],
    *,
    run_folder: Path,
) -> Path:
    """Write ``prior_marking_reference.json`` beside future ``question_sections.json``."""
    run_folder = run_folder.expanduser().resolve()
    run_folder.mkdir(parents=True, exist_ok=True)
    out_path = run_folder / _PRIOR_MARKING_REFERENCE_FILENAME
    out_path.write_text(json.dumps(reference, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return out_path
