#!/usr/bin/env python3
"""Phase 0 spike: Cursor SDK local agent + context/ file access.

One-off — not part of the shipped buddy_console runtime.

Usage (from repo root, after sourcing .env.local):

    set -a && source ai_study_buddy/buddy_console/backend/.env.local && set +a
    python3 ai_study_buddy/buddy_console/backend/_spike_cursor_sdk_context.py

Optional:

    python3 .../_spike_cursor_sdk_context.py --marking-json <path-under-repo>
    python3 .../_spike_cursor_sdk_context.py --skip-follow-up
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Callable


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _default_marking_json(repo_root: Path) -> Path:
    directory = repo_root / "ai_study_buddy" / "context" / "marking_results" / "winston" / "singapore_primary_math"
    candidates = sorted(directory.glob("*.json"))
    if not candidates:
        raise FileNotFoundError("no marking_results JSON under winston/singapore_primary_math")
    return candidates[0]


def _run_timed(label: str, fn: Callable[[], Any]) -> tuple[Any, float]:
    started = time.perf_counter()
    result = fn()
    elapsed = time.perf_counter() - started
    print(f"[timing] {label}: {elapsed:.1f}s")
    return result, elapsed


def _execute_turn(agent: Any, prompt: str, label: str) -> tuple[str, float]:
    def _run() -> str:
        run = agent.send(prompt)
        print(f"[ok] {label} run.id={run.id}")
        result = run.wait()
        if result.status == "error":
            raise RuntimeError(f"{label} failed: run_id={run.id}")
        text = ""
        if hasattr(run, "text"):
            try:
                text = run.text() or ""
            except Exception:
                text = ""
        if not text and isinstance(result.result, str):
            text = result.result
        return text.strip()

    text, elapsed = _run_timed(label, _run)
    return text, elapsed


def main() -> int:
    parser = argparse.ArgumentParser(description="Cursor SDK local agent context spike")
    parser.add_argument(
        "--marking-json",
        type=Path,
        help="Marking result JSON path (absolute or relative to repo root)",
    )
    parser.add_argument("--skip-follow-up", action="store_true", help="Skip second in-session turn")
    args = parser.parse_args()

    api_key = os.environ.get("CURSOR_API_KEY", "").strip()
    if not api_key:
        print("ERROR: CURSOR_API_KEY not set. Source backend/.env.local first.", file=sys.stderr)
        return 1

    repo_root = _repo_root()
    context_root = repo_root / "ai_study_buddy" / "context"
    pedagogy_path = (
        context_root / "subject_understandings" / "singapore_primary_math" / "math_error_types.md"
    )
    marking_path = args.marking_json or _default_marking_json(repo_root)
    if not marking_path.is_absolute():
        marking_path = (repo_root / marking_path).resolve()

    for label, path in (("pedagogy", pedagogy_path), ("marking_json", marking_path)):
        if not path.is_file():
            print(f"ERROR: {label} file missing: {path}", file=sys.stderr)
            return 1

    marking_rel = marking_path.relative_to(repo_root).as_posix()
    pedagogy_rel = pedagogy_path.relative_to(repo_root).as_posix()

    print(f"repo_root: {repo_root}")
    print(f"pedagogy:  {pedagogy_rel}")
    print(f"marking:   {marking_rel}")

    try:
        from cursor_sdk import Agent, Cursor, CursorAgentError, LocalAgentOptions
    except ImportError:
        print("ERROR: cursor-sdk not installed. Run: pip3 install cursor-sdk", file=sys.stderr)
        return 1

    try:
        models = Cursor.models.list(api_key=api_key)
        print(f"[ok] Cursor.models.list -> {len(models)} models")
    except CursorAgentError as err:
        print(f"ERROR: models.list failed: {err.message} (retryable={err.is_retryable})", file=sys.stderr)
        return 1

    first_prompt = (
        "Spike test only. Do not modify any files.\n\n"
        f"1) Read `{pedagogy_rel}` and name the first three [tag] prefixes defined for review notes "
        "(one short phrase each).\n"
        f"2) Read `{marking_rel}` and report question_results[0] result_id, outcome, "
        "and earned_marks/max_marks.\n"
        "Reply in under 120 words."
    )
    follow_prompt = "Without re-reading files: what subject_context is in that marking JSON context block?"

    first_elapsed = 0.0
    second_elapsed = 0.0

    try:
        with Agent.create(
            model="auto",
            api_key=api_key,
            local=LocalAgentOptions(cwd=repo_root),
        ) as agent:
            print(f"[ok] Agent.create -> agent_id={agent.agent_id}")

            first_text, first_elapsed = _execute_turn(agent, first_prompt, "first_turn")
            print("[first_turn excerpt]")
            print(first_text[:500] + ("…" if len(first_text) > 500 else ""))

            if not args.skip_follow_up:
                second_text, second_elapsed = _execute_turn(agent, follow_prompt, "follow_up_turn")
                print("[follow_up_turn excerpt]")
                print(second_text[:300] + ("…" if len(second_text) > 300 else ""))

    except CursorAgentError as err:
        print(f"ERROR: SDK failed: {err.message} (retryable={err.is_retryable})", file=sys.stderr)
        return 1
    except RuntimeError as err:
        print(f"ERROR: {err}", file=sys.stderr)
        return 1

    try:
        payload = json.loads(marking_path.read_text(encoding="utf-8"))
        ctx = payload.get("context", {})
        print(f"[local] marking subject_context={ctx.get('subject_context')!r}")
    except Exception as err:
        print(f"WARN: local JSON read failed: {err}", file=sys.stderr)

    summary = f"SPIKE SUMMARY: ok | first_turn={first_elapsed:.1f}s"
    if not args.skip_follow_up:
        summary += f" follow_up_turn={second_elapsed:.1f}s"
    print(f"\n{summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
