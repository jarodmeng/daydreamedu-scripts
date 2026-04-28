from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ai_study_buddy.marking.core.context_resolver import resolve_marking_context
from ai_study_buddy.marking.core.path_privacy import resolve_marking_artifact_paths, sanitize_marking_artifact_paths
from ai_study_buddy.marking.core.artifact_schema import validate_marking_artifact_dict
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

SOURCE_VERSION = "marking_result.v1.5"
TARGET_VERSION = "marking_result.v1.6"
REVIEW_QUEUE_DEFAULT = "ai_study_buddy/marking/docs/reports/context_resolution_v1_6_review_queue.json"

# Targeted manual replay overrides for known legacy outliers.
# Keyed by canonical artifact JSON relative path under context_root.
MANUAL_REPLAY_OVERRIDES: dict[str, dict[str, Any]] = {
    "marking_results/emma/singapore_primary_english/Grammar MCQs Explained Primary 1 - 01 Worksheet 1 Nouns__20260422_110006.json": {
        "marking_mode": "embedded_answer_override",
        "manual_answer_pages": (1, 1),
    },
}


@dataclass(frozen=True)
class CompareResult:
    ok: bool
    diffs: list[str]
    mode: str


def _now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _iter_marking_json_files(marking_root: Path) -> list[Path]:
    if not marking_root.is_dir():
        return []
    return sorted(marking_root.rglob("*.json"))


def _derive_mode(context: dict[str, Any]) -> str:
    source = str(context.get("answer_mapping_source") or "").lower()
    answer_start = context.get("answer_page_start")
    answer_end = context.get("answer_page_end")
    answer_file_path = str(context.get("answer_file_path") or "")
    attempt_file_path = str(context.get("attempt_file_path") or "")

    teacher_cues = (
        "teacher_annotated",
        "teacher-annotated",
        "mode b teacher-annotated",
        "green-ink",
        "red tick",
        "red cross",
        "manual visual solving",
        "inferred from",
    )
    if "self_answer_pages override" in source:
        return "embedded_answer_override"
    if any(cue in source for cue in teacher_cues):
        return "teacher_annotated"
    # Embedded/self answer keys often appear as direct-page extraction from completion/template.
    if isinstance(answer_start, int) and isinstance(answer_end, int):
        if "embedded answer key" in source or "taken directly from page" in source:
            return "embedded_answer_override"
        if answer_file_path and attempt_file_path and answer_file_path == attempt_file_path:
            return "embedded_answer_override"
    return "standard_mapped_answer"


def _make_resolve_kwargs(
    payload: dict[str, Any], *, manager: PdfFileManager, artifact_rel_path: str | None = None
) -> dict[str, Any]:
    resolved_payload = resolve_marking_artifact_paths(payload)
    context = resolved_payload.get("context") if isinstance(resolved_payload.get("context"), dict) else {}
    attempt_file_id = context.get("attempt_file_id")
    attempt_file_path = context.get("attempt_file_path")

    mode = _derive_mode(context)
    attempt_ref: str | None = None
    if isinstance(attempt_file_id, str) and attempt_file_id.strip():
        if manager.get_file(attempt_file_id) is not None:
            attempt_ref = attempt_file_id
    if attempt_ref is None:
        if not isinstance(attempt_file_path, str) or not attempt_file_path.strip():
            raise ValueError("missing attempt_file_path after path resolution")
        attempt_ref = attempt_file_path

    kwargs: dict[str, Any] = {"attempt_file_id_or_path": attempt_ref, "marking_mode": mode}
    if mode == "embedded_answer_override":
        start = context.get("answer_page_start")
        end = context.get("answer_page_end")
        if not isinstance(start, int) or not isinstance(end, int):
            raise ValueError("embedded_answer_override requires integer answer_page_start/answer_page_end")
        kwargs["self_answer_pages"] = (start, end)

    # Explicit manual overrides for known outliers.
    if artifact_rel_path:
        override = MANUAL_REPLAY_OVERRIDES.get(artifact_rel_path)
        if override:
            if "marking_mode" in override:
                kwargs["marking_mode"] = override["marking_mode"]
            if "manual_answer_pages" in override:
                kwargs.pop("self_answer_pages", None)
                kwargs["manual_answer_pages"] = tuple(override["manual_answer_pages"])
    return kwargs


def _compare_context(payload: dict[str, Any], resolved: Any, mode: str) -> CompareResult:
    context = payload.get("context") if isinstance(payload.get("context"), dict) else {}
    diff: list[str] = []

    def _eq(field: str, expected: Any, actual: Any) -> None:
        if expected != actual:
            diff.append(f"{field}: expected={expected!r} actual={actual!r}")

    # Compare using sanitized forms for path-bearing fields.
    candidate_ctx = {
        "attempt_file_path": resolved.attempt_file_path,
        "template_file_path": resolved.template_file_path,
        "unit_file_path": resolved.unit_file_path,
        "answer_file_path": resolved.answer_file_path,
    }
    sanitized = sanitize_marking_artifact_paths({"context": candidate_ctx}).get("context", {})

    _eq("student_id", context.get("student_id"), resolved.student_id)
    _eq("attempt_file_path", context.get("attempt_file_path"), sanitized.get("attempt_file_path"))
    _eq("template_file_path", context.get("template_file_path"), sanitized.get("template_file_path"))
    _eq("unit_file_path", context.get("unit_file_path"), sanitized.get("unit_file_path"))
    _eq("unit_label", context.get("unit_label"), resolved.unit_label)
    _eq("book_group_id", context.get("book_group_id"), resolved.book_group_id)
    _eq("book_label", context.get("book_label"), resolved.book_label)

    if mode == "teacher_annotated":
        src = str(context.get("answer_mapping_source") or "").lower()
        if "teacher_annotated" not in src and "teacher-annotated" not in src and "mode b teacher-annotated" not in src:
            diff.append(f"answer_mapping_source: expected teacher-annotated family, actual={context.get('answer_mapping_source')!r}")
    elif mode == "embedded_answer_override":
        if "self_answer_pages override" not in str(context.get("answer_mapping_source") or ""):
            diff.append("answer_mapping_source: missing self_answer_pages override marker")
        _eq("answer_page_start", context.get("answer_page_start"), resolved.answer_page_start)
        _eq("answer_page_end", context.get("answer_page_end"), resolved.answer_page_end)
    else:
        _eq("answer_file_path", context.get("answer_file_path"), sanitized.get("answer_file_path"))
        _eq("answer_page_start", context.get("answer_page_start"), resolved.answer_page_start)
        _eq("answer_page_end", context.get("answer_page_end"), resolved.answer_page_end)

    return CompareResult(ok=not diff, diffs=diff, mode=mode)


def _apply_resolution(payload: dict[str, Any], *, mode: str) -> dict[str, Any]:
    out = dict(payload)
    context = dict(out.get("context") or {})
    context["context_resolution"] = {
        "method": "resolve_marking_context",
        "resolver_version": "1",
        "resolved_at": _now_iso_utc(),
        "mode": mode,
        "invariants": {
            "unit_label_normalized": True,
            "mode_explicit": True,
        },
    }
    out["context"] = context
    out["schema_version"] = TARGET_VERSION
    return out


def _overwrite_context_from_resolved(payload: dict[str, Any], resolved: Any) -> dict[str, Any]:
    out = dict(payload)
    context = dict(out.get("context") or {})
    context["attempt_file_id"] = resolved.attempt_file_id
    context["attempt_file_path"] = resolved.attempt_file_path
    context["template_file_id"] = resolved.template_file_id
    context["template_file_path"] = resolved.template_file_path
    context["book_group_id"] = resolved.book_group_id
    context["book_label"] = resolved.book_label
    context["unit_file_id"] = resolved.unit_file_id
    context["unit_file_path"] = resolved.unit_file_path
    context["unit_label"] = resolved.unit_label
    context["answer_file_id"] = resolved.answer_file_id
    context["answer_file_path"] = resolved.answer_file_path
    context["answer_page_start"] = resolved.answer_page_start
    context["answer_page_end"] = resolved.answer_page_end
    context["starts_mid_page"] = resolved.starts_mid_page
    context["ends_mid_page"] = resolved.ends_mid_page
    context["answer_mapping_source"] = resolved.answer_mapping_source
    context["answer_mapping_notes"] = resolved.answer_mapping_notes
    out["context"] = sanitize_marking_artifact_paths({"context": context}).get("context", context)
    return out


def run(
    *,
    context_root: str | Path = "ai_study_buddy/context",
    dry_run: bool = True,
    review_queue_path: str | Path = REVIEW_QUEUE_DEFAULT,
    overwrite_mismatches: bool = False,
) -> dict[str, Any]:
    root = Path(context_root)
    marking_root = root / "marking_results"
    files = _iter_marking_json_files(marking_root)
    manager = PdfFileManager()
    review_queue: list[dict[str, Any]] = []

    summary = {
        "scanned_files": len(files),
        "source_version_files": 0,
        "upgraded_files": 0,
        "already_target_version": 0,
        "queued_for_review": 0,
        "resolve_errors": 0,
        "validation_errors": 0,
        "mismatches_overwritten": 0,
        "dry_run": int(dry_run),
    }

    for path in files:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue

        schema_version = payload.get("schema_version")
        if schema_version == TARGET_VERSION:
            summary["already_target_version"] += 1
            continue
        if schema_version != SOURCE_VERSION:
            continue
        summary["source_version_files"] += 1

        try:
            rel_path = path.relative_to(root).as_posix()
            kwargs = _make_resolve_kwargs(payload, manager=manager, artifact_rel_path=rel_path)
            resolved = resolve_marking_context(manager=manager, **kwargs)
            mode = kwargs["marking_mode"]
            cmp = _compare_context(payload, resolved, mode)
        except Exception as exc:
            summary["resolve_errors"] += 1
            review_queue.append(
                {
                    "artifact_path": str(path),
                    "reason": "resolve_error",
                    "error": str(exc),
                }
            )
            continue

        if not cmp.ok:
            if overwrite_mismatches:
                upgraded_payload = _overwrite_context_from_resolved(payload, resolved)
                upgraded_payload = _apply_resolution(upgraded_payload, mode=cmp.mode)
                try:
                    validate_marking_artifact_dict(upgraded_payload)
                except Exception as exc:
                    summary["validation_errors"] += 1
                    review_queue.append(
                        {
                            "artifact_path": str(path),
                            "reason": "validation_error_after_overwrite",
                            "mode": cmp.mode,
                            "diffs": cmp.diffs,
                            "error": str(exc),
                        }
                    )
                    continue
                summary["mismatches_overwritten"] += 1
                summary["upgraded_files"] += 1
                if not dry_run:
                    path.write_text(json.dumps(upgraded_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
                continue
            summary["queued_for_review"] += 1
            review_queue.append(
                {
                    "artifact_path": str(path),
                    "reason": "context_mismatch",
                    "mode": cmp.mode,
                    "diffs": cmp.diffs,
                }
            )
            continue

        upgraded = _apply_resolution(payload, mode=cmp.mode)
        try:
            validate_marking_artifact_dict(upgraded)
        except Exception as exc:
            summary["validation_errors"] += 1
            review_queue.append(
                {
                    "artifact_path": str(path),
                    "reason": "validation_error_after_upgrade",
                    "error": str(exc),
                }
            )
            continue

        summary["upgraded_files"] += 1
        if not dry_run:
            path.write_text(json.dumps(upgraded, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")

    queue_path = Path(review_queue_path)
    queue_path.parent.mkdir(parents=True, exist_ok=True)
    queue_payload = {
        "generated_at": _now_iso_utc(),
        "summary": summary,
        "items": review_queue,
    }
    queue_path.write_text(json.dumps(queue_payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    summary["review_queue_path"] = str(queue_path)
    summary["review_queue_items"] = len(review_queue)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Replay resolver and backfill context_resolution for v1.6 migration.")
    parser.add_argument("--context-root", default="ai_study_buddy/context")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--review-queue-path", default=REVIEW_QUEUE_DEFAULT)
    parser.add_argument("--overwrite-mismatches", action="store_true")
    args = parser.parse_args()
    summary = run(
        context_root=args.context_root,
        dry_run=args.dry_run,
        review_queue_path=args.review_queue_path,
        overwrite_mismatches=args.overwrite_mismatches,
    )
    print(json.dumps(summary, indent=2, ensure_ascii=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
