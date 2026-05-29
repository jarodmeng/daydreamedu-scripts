#!/usr/bin/env python3
"""Orchestrate template FQI detector batches (queue slice → Task specs → apply results).

Typical full run (operator or parent chat):

1. ``status`` — pending count
2. ``prepare-batch`` — emit detector Task specs (batch_size=5, sidecars)
3. Parent spawns detector Tasks from ``tasks[]``
4. ``apply-batch`` — update queue from results JSON
5. Repeat until ``pending_total`` is 0
6. ``finalize-run`` — optional import_context_json for file_question_info
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

DEFAULT_BATCH_SIZE = 5
_SESSION_RESULTS = _SCRIPT_DIR / "queues" / "_fqi_detector_batch_session.json"


def _run_json_capture(argv: list[str]) -> dict[str, Any]:
    proc = subprocess.run(
        argv,
        cwd=str(_REPO_ROOT),
        check=False,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            "command failed\n"
            f"  argv: {' '.join(argv)}\n"
            f"  exit: {proc.returncode}\n"
            f"  stderr: {proc.stderr.strip()}\n"
            f"  stdout: {proc.stdout.strip()}"
        )
    payload = json.loads(proc.stdout)
    if not isinstance(payload, dict):
        raise ValueError("expected JSON object on stdout")
    return payload


def cmd_status(*, queue: Path) -> dict[str, Any]:
    from next_priority_detector_batch import _load_queue, _pending_items

    payload = _load_queue(queue)
    pending = _pending_items(payload)
    items = payload.get("items") or []
    status_counts: dict[str, int] = {}
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("status") or "unknown")
        status_counts[key] = status_counts.get(key, 0) + 1
    return {
        "queue": str(queue),
        "item_total": len(items),
        "pending_total": len(pending),
        "status_counts": status_counts,
        "next_pending_ords": [int(i.get("ord") or 0) for i in pending[:10]],
    }


def cmd_prepare_batch(
    *,
    queue: Path,
    batch_size: int,
    offset: int,
    context_root: Path,
    write_sidecars: bool,
    output_task_spec: Path | None,
) -> dict[str, Any]:
    argv = [
        sys.executable,
        str(_SCRIPT_DIR / "next_priority_detector_batch.py"),
        "--queue",
        str(queue),
        "--batch-size",
        str(batch_size),
        "--offset",
        str(offset),
        "--context-root",
        str(context_root),
        "--json",
    ]
    if write_sidecars:
        argv.append("--write-marking-reference-sidecars")
    if output_task_spec is not None:
        argv.extend(["--output-task-spec-json", str(output_task_spec)])
    return _run_json_capture(argv)


def cmd_apply_batch(*, queue: Path, results_json: Path, append_session: bool) -> dict[str, Any]:
    argv = [
        sys.executable,
        str(_SCRIPT_DIR / "_apply_priority_detector_batch_results.py"),
        "--queue",
        str(queue),
        "--results-json",
        str(results_json),
    ]
    proc = subprocess.run(argv, cwd=str(_REPO_ROOT), check=False, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or f"exit {proc.returncode}")
    stats = json.loads(proc.stdout)
    if append_session and results_json.is_file():
        session: list[Any] = []
        if _SESSION_RESULTS.is_file():
            session = json.loads(_SESSION_RESULTS.read_text(encoding="utf-8"))
            if not isinstance(session, list):
                session = []
        batch_rows = json.loads(results_json.read_text(encoding="utf-8"))
        if isinstance(batch_rows, list):
            session.extend(batch_rows)
        _SESSION_RESULTS.parent.mkdir(parents=True, exist_ok=True)
        _SESSION_RESULTS.write_text(json.dumps(session, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        stats["session_results_path"] = str(_SESSION_RESULTS)
    return stats


def cmd_finalize_run(*, dry_run: bool) -> dict[str, Any]:
    argv = [
        sys.executable,
        "-m",
        "ai_study_buddy.learning_db.ingest.import_context_json",
        "--artifact-family",
        "file_question_info",
    ]
    if dry_run:
        argv.append("--dry-run")
    proc = subprocess.run(argv, cwd=str(_REPO_ROOT), check=False, capture_output=True, text=True)
    return {
        "exit_code": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
        "dry_run": dry_run,
    }


def cmd_plan_full_run(*, queue: Path, batch_size: int) -> dict[str, Any]:
    status = cmd_status(queue=queue)
    pending = int(status["pending_total"])
    batches = (pending + batch_size - 1) // batch_size if pending else 0
    return {
        "queue": str(queue),
        "pending_total": pending,
        "batch_size": batch_size,
        "batches_needed": batches,
        "offsets": [i * batch_size for i in range(batches)],
    }


def _add_queue_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--queue",
        type=Path,
        required=True,
        help="Template FQI detector queue JSON",
    )
    parser.add_argument(
        "--context-root",
        type=Path,
        default=_REPO_ROOT / "ai_study_buddy" / "context",
        help="Context root for FQI sidecars",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p_status = sub.add_parser("status", help="Print pending counts and next ords")
    _add_queue_args(p_status)

    p_prepare = sub.add_parser("prepare-batch", help="Emit next detector Task specs JSON on stdout")
    _add_queue_args(p_prepare)
    p_prepare.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    p_prepare.add_argument("--offset", type=int, default=0)
    p_prepare.add_argument(
        "--no-marking-reference-sidecars",
        action="store_true",
        help="Skip writing prior_marking_reference.json sidecars",
    )
    p_prepare.add_argument("--output-task-spec-json", type=Path, default=None)

    p_apply = sub.add_parser("apply-batch", help="Apply detector results list to queue")
    _add_queue_args(p_apply)
    p_apply.add_argument("--results-json", type=Path, required=True)
    p_apply.add_argument("--append-session", action="store_true", default=True)
    p_apply.add_argument("--no-append-session", action="store_true")

    p_fin = sub.add_parser("finalize-run", help="Import file_question_info family into study_buddy.db")
    _add_queue_args(p_fin)
    p_fin.add_argument("--dry-run", action="store_true")

    p_plan = sub.add_parser("plan-full-run", help="How many batches of N for current pending count")
    _add_queue_args(p_plan)
    p_plan.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)

    return parser


def main() -> int:
    args = build_parser().parse_args()
    queue = args.queue.expanduser().resolve()

    if args.command == "status":
        print(json.dumps(cmd_status(queue=queue), indent=2, ensure_ascii=False))
        return 0

    if args.command == "prepare-batch":
        write_sidecars = not getattr(args, "no_marking_reference_sidecars", False)
        out = cmd_prepare_batch(
            queue=queue,
            batch_size=args.batch_size,
            offset=args.offset,
            context_root=args.context_root.expanduser().resolve(),
            write_sidecars=write_sidecars,
            output_task_spec=args.output_task_spec_json,
        )
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    if args.command == "apply-batch":
        stats = cmd_apply_batch(
            queue=queue,
            results_json=args.results_json.expanduser().resolve(),
            append_session=not args.no_append_session,
        )
        print(json.dumps(stats, indent=2, ensure_ascii=False))
        return 0

    if args.command == "finalize-run":
        result = cmd_finalize_run(dry_run=args.dry_run)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0 if result["exit_code"] == 0 else 1

    if args.command == "plan-full-run":
        print(json.dumps(cmd_plan_full_run(queue=queue, batch_size=args.batch_size), indent=2, ensure_ascii=False))
        return 0

    raise AssertionError(f"unknown command: {args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
