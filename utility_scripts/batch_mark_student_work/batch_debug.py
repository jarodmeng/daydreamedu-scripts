"""Shared helpers: persist batch marking traces under bundle/debug/."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Sequence

from ai_study_buddy.marking.workflows.v3_helpers import select_phase3_question_ids


def bundle_debug_dir(bundle_root: Path) -> Path:
    debug = bundle_root / "debug"
    debug.mkdir(parents=True, exist_ok=True)
    return debug


def bundle_debug_paths(bundle_root: Path) -> dict[str, str]:
    """Canonical debug artifact paths for batch orchestrator prompts."""
    d = bundle_debug_dir(bundle_root)
    return {
        "debug_dir": str(d.resolve()),
        "v3_batch_orchestration_trace": str((d / "v3_batch_orchestration_trace.json").resolve()),
        "phase2_section_pattern": str((d / "phase2_section_{section_index}.json").resolve()),
        "phase2_orchestrator_summary": str((d / "phase2_orchestrator_summary.json").resolve()),
        "phase3_deep_dive": str((d / "phase3_deep_dive.json").resolve()),
        "phase3_question_execution_trace": str(
            (d / "phase3_question_execution_trace.json").resolve()
        ),
    }


def write_debug_json(bundle_root: Path, filename: str, payload: Mapping[str, Any]) -> Path:
    out = bundle_debug_dir(bundle_root) / filename
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    return out


def write_v3_batch_prep_trace(*, bundle_root: Path, meta: Mapping[str, Any]) -> Path:
    sections = meta.get("sections") or []
    return write_debug_json(
        bundle_root,
        "v3_batch_prep_trace.json",
        {
            "ord": meta.get("ord"),
            "run_at": meta.get("run_at"),
            "bundle_root": meta.get("bundle_root"),
            "marking_mode": meta.get("marking_mode"),
            "section_count": len(sections),
            "expected_phase2_row_count": sum(len(s.get("question_ids") or []) for s in sections),
            "phase2_batch_wave_count": len(meta.get("phase2_batches") or []),
            "sections": sections,
        },
    )


def write_v3_batch_grade_spec(
    *,
    bundle_root: Path,
    spec: Mapping[str, Any],
) -> Path:
    slim = {k: v for k, v in spec.items() if k != "prompt"}
    slim["prompt_char_count"] = len(spec.get("prompt") or "")
    return write_debug_json(bundle_root, "v3_batch_grade_spec.json", slim)


def split_phase2_rows_by_section(
    *,
    phase2_rows: Sequence[Mapping[str, Any]],
    sections: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_qid: dict[str, Mapping[str, Any]] = {}
    for row in phase2_rows:
        if not isinstance(row, Mapping):
            continue
        qid = row.get("question_id")
        if isinstance(qid, str) and qid.strip():
            by_qid[qid.strip()] = row

    out: list[dict[str, Any]] = []
    for section in sections:
        qids = [
            q.strip()
            for q in (section.get("question_ids") or [])
            if isinstance(q, str) and q.strip()
        ]
        rows = [dict(by_qid[q]) for q in qids if q in by_qid]
        out.append(
            {
                "section_index": section.get("section_index"),
                "section_label": section.get("section_label"),
                "question_ids": qids,
                "row_count": len(rows),
                "rows": rows,
            }
        )
    return out


def write_phase2_section_execution_trace(
    *,
    bundle_root: Path,
    sections: Sequence[Mapping[str, Any]],
    phase2_rows: Sequence[Mapping[str, Any]],
) -> Path:
    split = split_phase2_rows_by_section(phase2_rows=phase2_rows, sections=sections)
    payload = {
        "sections": [
            {
                "section_index": block["section_index"],
                "succeeded": block["row_count"] == len(block["question_ids"]),
                "attempts": 1,
                "error": None
                if block["row_count"] == len(block["question_ids"])
                else f"row_count {block['row_count']} != expected {len(block['question_ids'])}",
                "row_count": block["row_count"],
            }
            for block in split
        ]
    }
    return write_debug_json(bundle_root, "phase2_section_execution_trace.json", payload)


def write_phase2_section_files(
    *,
    bundle_root: Path,
    sections: Sequence[Mapping[str, Any]],
    phase2_rows: Sequence[Mapping[str, Any]],
) -> list[Path]:
    paths: list[Path] = []
    for block in split_phase2_rows_by_section(phase2_rows=phase2_rows, sections=sections):
        idx = block.get("section_index")
        if idx is None:
            continue
        name = f"phase2_section_{int(idx)}.json"
        paths.append(write_debug_json(bundle_root, name, block))
    return paths


def write_phase2_phase3_routing(
    *,
    bundle_root: Path,
    phase2_rows: Sequence[Mapping[str, Any]],
    phase3_enabled: bool,
    phase3_skipped_reason: str | None = None,
) -> Path:
    targets = select_phase3_question_ids(phase2_rows)
    return write_debug_json(
        bundle_root,
        "phase2_phase3_routing.json",
        {
            "phase3_enabled": phase3_enabled,
            "phase3_skipped_reason": phase3_skipped_reason,
            "would_escalate_question_ids": list(targets),
            "would_escalate_count": len(targets),
        },
    )


def persist_post_grade_debug(
    *,
    bundle_root: Path,
    meta: Mapping[str, Any],
    phase2_rows: Sequence[Mapping[str, Any]],
    phase3_enabled: bool = False,
    validate_summary: Mapping[str, Any] | None = None,
    grade_spec: Mapping[str, Any] | None = None,
) -> dict[str, str]:
    """Copy phase2 into bundle/debug and write routing + section traces."""
    debug = bundle_debug_dir(bundle_root)
    sections = meta.get("sections") or []

    fast_pass_path = debug / "phase2_fast_pass.json"
    fast_pass_path.write_text(
        json.dumps(list(phase2_rows), indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )

    write_phase2_section_files(
        bundle_root=bundle_root, sections=sections, phase2_rows=phase2_rows
    )
    write_phase2_section_execution_trace(
        bundle_root=bundle_root, sections=sections, phase2_rows=phase2_rows
    )
    write_phase2_phase3_routing(
        bundle_root=bundle_root,
        phase2_rows=phase2_rows,
        phase3_enabled=phase3_enabled,
        phase3_skipped_reason=None
        if phase3_enabled
        else "batch default (phase2-only); enable via orchestrator --with-phase3",
    )

    if validate_summary:
        write_debug_json(bundle_root, "phase2_validate_gate.json", validate_summary)

    if grade_spec:
        write_v3_batch_grade_spec(bundle_root=bundle_root, spec=grade_spec)

    summary_path = debug / "phase2_orchestrator_summary.json"
    if not summary_path.is_file():
        write_debug_json(
            bundle_root,
            "phase2_orchestrator_summary.json",
            {
                "source": "batch_item_persist_grade_debug.py",
                "section_count": len(sections),
                "phase2_row_count": len(phase2_rows),
                "phase2_fast_pass_path": str(fast_pass_path.resolve()),
            },
        )

    return {
        "phase2_fast_pass": str(fast_pass_path.resolve()),
        "debug_dir": str(debug.resolve()),
    }
