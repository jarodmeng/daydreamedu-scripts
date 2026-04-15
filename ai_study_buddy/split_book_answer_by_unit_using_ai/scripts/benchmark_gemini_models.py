#!/usr/bin/env python3
"""
Benchmark one book across multiple Gemini models.

Default flow submits all model batch jobs first, then processes each model:
build -> submit (all models) -> poll -> process -> assemble

Outputs a markdown summary table with:
- validation signals from assembled output
- optional ground-truth exact/range match counts
- token usage and rough cost estimate
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
BUILD_SCRIPT = SCRIPT_DIR / "build_gemini_page_segments_continuation_batch_input.py"
SUBMIT_SCRIPT = SCRIPT_DIR / "submit_gemini_batch.py"
CHECK_SCRIPT = SCRIPT_DIR / "check_gemini_batch_status.py"
PROCESS_SCRIPT = SCRIPT_DIR / "process_gemini_batch_output.py"
ASSEMBLE_SCRIPT = SCRIPT_DIR / "assemble_ranges_from_page_segments_continuation.py"

# Vertex AI Gemini 2.5 Flex/Batch rates (USD per 1M tokens, <=200k context tier)
# Source: cloud.google.com/vertex-ai/generative-ai/pricing
MODEL_RATES_PER_MTOK: dict[str, dict[str, float]] = {
    "models/gemini-2.5-pro": {"input": 0.625, "output": 5.0},
    "models/gemini-2.5-flash": {"input": 0.15, "output": 1.25},
    "models/gemini-2.5-flash-lite": {"input": 0.05, "output": 0.2},
}


def slugify_model(model: str) -> str:
    token = model.split("/")[-1].lower()
    token = re.sub(r"[^a-z0-9]+", "_", token).strip("_")
    return token or "model"


def run_cmd(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, check=False)


def read_jsonl_first_row(path: Path) -> dict[str, Any]:
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            return json.loads(line)
    raise ValueError(f"No non-empty row found in {path}")


def parse_usage_metadata(output_jsonl: Path) -> dict[str, int | None]:
    row = read_jsonl_first_row(output_jsonl)
    usage = ((row.get("response") or {}).get("usageMetadata")) or {}
    return {
        "prompt_tokens": usage.get("promptTokenCount"),
        "candidate_tokens": usage.get("candidatesTokenCount"),
        "thought_tokens": usage.get("thoughtsTokenCount"),
        "total_tokens": usage.get("totalTokenCount"),
    }


def estimate_usd(model: str, usage: dict[str, int | None]) -> float | None:
    rates = MODEL_RATES_PER_MTOK.get(model)
    prompt = usage.get("prompt_tokens")
    cand = usage.get("candidate_tokens")
    thought = usage.get("thought_tokens") or 0
    if not rates or prompt is None or cand is None:
        return None
    output_total = cand + thought
    return (prompt / 1_000_000.0) * rates["input"] + (output_total / 1_000_000.0) * rates["output"]


def index_mappings(items: list[dict[str, Any]]) -> dict[int, dict[str, Any]]:
    out: dict[int, dict[str, Any]] = {}
    for item in items:
        try:
            out[int(item["unit_index"])] = item
        except Exception:
            continue
    return out


def compare_to_ground_truth(assembled: dict[str, Any], ground_truth: dict[str, Any]) -> dict[str, int]:
    pred_map = index_mappings(assembled.get("mappings") or [])
    truth_map = index_mappings(ground_truth.get("mappings") or [])
    exact_matches = 0
    range_matches = 0
    for unit_index in sorted(truth_map):
        truth_item = truth_map[unit_index]
        pred_item = pred_map.get(unit_index)
        if not pred_item:
            continue
        same_range = (
            pred_item.get("answer_page_start") == truth_item.get("answer_page_start")
            and pred_item.get("answer_page_end") == truth_item.get("answer_page_end")
        )
        same_flags = (
            bool(pred_item.get("starts_mid_page")) == bool(truth_item.get("starts_mid_page"))
            and bool(pred_item.get("ends_mid_page")) == bool(truth_item.get("ends_mid_page"))
        )
        if same_range:
            range_matches += 1
        if same_range and same_flags:
            exact_matches += 1
    return {
        "truth_count": len(truth_map),
        "range_matches": range_matches,
        "exact_matches": exact_matches,
    }


def make_artifact_paths(artifacts_dir: Path, run_prefix: str, model: str) -> dict[str, Path]:
    stamp = slugify_model(model)
    base = f"{run_prefix}.{stamp}"
    return {
        "jsonl": artifacts_dir / f"{base}.jsonl",
        "job_info": artifacts_dir / f"{base}.job.json",
        "job_name": artifacts_dir / f"{base}.job_name.txt",
        "output_jsonl": artifacts_dir / f"{base}.output.jsonl",
        "processed_json": artifacts_dir / f"{base}.processed.json",
        "assembled_json": artifacts_dir / f"{base}.assembled.json",
    }


def build_and_submit_model(
    *,
    args: argparse.Namespace,
    model: str,
    run_prefix: str,
) -> dict[str, Any]:
    paths = make_artifact_paths(args.artifacts_dir, run_prefix, model)
    build_cmd = [
        sys.executable,
        str(BUILD_SCRIPT),
        "--book-label",
        args.book_label,
        "--output",
        str(paths["jsonl"]),
        "--dpi",
        str(args.dpi),
        "--jpeg-quality",
        str(args.jpeg_quality),
        "--max-output-tokens",
        str(args.max_output_tokens),
    ]
    if args.answer_page_start is not None:
        build_cmd.extend(["--answer-page-start", str(args.answer_page_start)])
    if args.answer_page_end is not None:
        build_cmd.extend(["--answer-page-end", str(args.answer_page_end)])
    if args.thinking_budget is not None:
        build_cmd.extend(["--thinking-budget", str(args.thinking_budget)])
    build_cmd.append("--include-thoughts" if args.include_thoughts else "--no-include-thoughts")

    submit_cmd = [
        sys.executable,
        str(SUBMIT_SCRIPT),
        str(paths["jsonl"]),
        "--job-info",
        str(paths["job_info"]),
        "--job-name-file",
        str(paths["job_name"]),
        "--model",
        model,
    ]

    build_result = run_cmd(build_cmd)
    if build_result.returncode != 0:
        raise RuntimeError(f"build failed for {model}:\n{build_result.stderr or build_result.stdout}")

    first_row = read_jsonl_first_row(paths["jsonl"])
    custom_id = first_row.get("key")
    if not custom_id:
        raise RuntimeError(f"Could not find custom key in {paths['jsonl']}")

    submit_result = run_cmd(submit_cmd)
    if submit_result.returncode != 0:
        raise RuntimeError(f"submit failed for {model}:\n{submit_result.stderr or submit_result.stdout}")

    return {
        "model": model,
        "custom_id": custom_id,
        "paths": {k: str(v) for k, v in paths.items()},
    }


def finalize_model_run(
    *,
    args: argparse.Namespace,
    submitted: dict[str, Any],
    ground_truth: dict[str, Any] | None,
) -> dict[str, Any]:
    model = submitted["model"]
    custom_id = submitted["custom_id"]
    paths = {k: Path(v) for k, v in (submitted.get("paths") or {}).items()}

    check_cmd = [
        sys.executable,
        str(CHECK_SCRIPT),
        "--job-info",
        str(paths["job_info"]),
        "--poll",
        "--poll-interval",
        str(args.poll_interval),
        "--output",
        str(paths["output_jsonl"]),
    ]
    process_cmd = [
        sys.executable,
        str(PROCESS_SCRIPT),
        "--input",
        str(paths["output_jsonl"]),
        "--output",
        str(paths["processed_json"]),
    ]

    check_result = run_cmd(check_cmd)
    if check_result.returncode != 0:
        raise RuntimeError(f"check/poll failed for {model}:\n{check_result.stderr or check_result.stdout}")

    process_result = run_cmd(process_cmd)
    if process_result.returncode != 0:
        raise RuntimeError(f"process failed for {model}:\n{process_result.stderr or process_result.stdout}")

    assemble_cmd = [
        sys.executable,
        str(ASSEMBLE_SCRIPT),
        "--custom-id",
        str(custom_id),
        "--processed",
        str(paths["processed_json"]),
        "--output",
        str(paths["assembled_json"]),
    ]
    assemble_result = run_cmd(assemble_cmd)
    if assemble_result.returncode != 0:
        raise RuntimeError(f"assemble failed for {model}:\n{assemble_result.stderr or assemble_result.stdout}")

    assembled = json.loads(paths["assembled_json"].read_text(encoding="utf-8"))
    validation = assembled.get("validation") or {}
    usage = parse_usage_metadata(paths["output_jsonl"])
    cost_estimate = estimate_usd(model, usage)

    gt = None
    if ground_truth is not None:
        gt = compare_to_ground_truth(assembled, ground_truth)

    return {
        "model": model,
        "custom_id": custom_id,
        "artifacts": {
            "jsonl": str(paths["jsonl"]),
            "job_info": str(paths["job_info"]),
            "job_name": str(paths["job_name"]),
            "output_jsonl": str(paths["output_jsonl"]),
            "processed_json": str(paths["processed_json"]),
            "assembled_json": str(paths["assembled_json"]),
        },
        "validation": {
            "mapping_count": validation.get("mapping_count"),
            "missing_within_span": len(validation.get("missing_unit_indices_within_detected_span") or []),
            "rule_violations": len(validation.get("continuation_rule_violations") or []),
            "rule_warnings": len(validation.get("continuation_rule_warnings") or []),
            "substitution_suspicions": len(validation.get("continuation_substitution_suspicions") or []),
            "non_monotonic_jump_detected": bool(validation.get("non_monotonic_jump_detected")),
        },
        "ground_truth": gt,
        "usage": usage,
        "estimated_cost_usd": cost_estimate,
    }


def format_ratio(value: int, total: int) -> str:
    if total <= 0:
        return "-"
    return f"{value}/{total}"


def markdown_table(rows: list[dict[str, Any]]) -> str:
    lines = []
    lines.append("| Model | Exact | Range | MapCt | Missing | Violations | Warnings | Suspicions | PromptTok | OutTok* | Est USD |")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|")
    for row in rows:
        gt = row.get("ground_truth") or {}
        truth_count = gt.get("truth_count", 0)
        exact = format_ratio(gt.get("exact_matches", 0), truth_count) if gt else "-"
        range_match = format_ratio(gt.get("range_matches", 0), truth_count) if gt else "-"
        usage = row.get("usage") or {}
        out_tok = (usage.get("candidate_tokens") or 0) + (usage.get("thought_tokens") or 0)
        cost = row.get("estimated_cost_usd")
        cost_str = "-" if cost is None else f"${cost:.4f}"
        v = row.get("validation") or {}
        lines.append(
            f"| `{row['model']}` | {exact} | {range_match} | {v.get('mapping_count', '-')} | "
            f"{v.get('missing_within_span', '-')} | {v.get('rule_violations', '-')} | "
            f"{v.get('rule_warnings', '-')} | {v.get('substitution_suspicions', '-')} | "
            f"{usage.get('prompt_tokens', '-')} | {out_tok} | {cost_str} |"
        )
    lines.append("")
    lines.append("*OutTok = candidates + thoughts tokens.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark split_book_answer pipeline across Gemini models")
    parser.add_argument("--book-label", required=True, help="Exact registry book label")
    parser.add_argument(
        "--models",
        default="models/gemini-2.5-pro,models/gemini-2.5-flash,models/gemini-2.5-flash-lite",
        help="Comma-separated model ids",
    )
    parser.add_argument("--run-prefix", default=None, help="Output stem prefix. Default: <timestamp>.<book-slug>")
    parser.add_argument("--artifacts-dir", type=Path, default=ROOT / "batch_artifacts")
    parser.add_argument("--summary-out", type=Path, default=None, help="Optional JSON summary output path")
    parser.add_argument("--ground-truth", type=Path, default=None, help="Optional ground-truth JSON path")
    parser.add_argument("--continue-on-error", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument(
        "--submit-all-first",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Submit all model jobs before polling/processing (recommended for long queues)",
    )

    parser.add_argument("--dpi", type=int, default=220)
    parser.add_argument("--jpeg-quality", type=int, default=90)
    parser.add_argument("--max-output-tokens", type=int, default=65536)
    parser.add_argument("--thinking-budget", type=int, default=None)
    parser.add_argument("--include-thoughts", action=argparse.BooleanOptionalAction, default=False)
    parser.add_argument("--answer-page-start", type=int, default=1)
    parser.add_argument("--answer-page-end", type=int, default=None)
    parser.add_argument("--poll-interval", type=int, default=30)
    args = parser.parse_args()

    args.artifacts_dir.mkdir(parents=True, exist_ok=True)
    models = [m.strip() for m in args.models.split(",") if m.strip()]
    if not models:
        raise SystemExit("Error: --models is empty")

    if args.run_prefix:
        run_prefix = args.run_prefix
    else:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        book_slug = re.sub(r"[^a-z0-9]+", "_", args.book_label.lower()).strip("_")
        run_prefix = f"{ts}.{book_slug}"

    ground_truth = None
    if args.ground_truth:
        ground_truth = json.loads(args.ground_truth.read_text(encoding="utf-8"))

    submitted_runs: list[dict[str, Any]] = []
    results: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []

    if args.submit_all_first:
        print("\n## Submit phase", flush=True)
        for model in models:
            print(f"\nSubmitting model: {model}", flush=True)
            try:
                submitted = build_and_submit_model(args=args, model=model, run_prefix=run_prefix)
                submitted_runs.append(submitted)
                print(f"Submitted: {model}", flush=True)
            except Exception as exc:
                msg = str(exc)
                errors.append({"model": model, "error": msg})
                print(f"Submit failed: {model}\n{msg}", file=sys.stderr, flush=True)
                if not args.continue_on_error:
                    break
    else:
        # Legacy sequential behavior: build+submit then finalize per model.
        for model in models:
            print(f"\nSubmitting model: {model}", flush=True)
            try:
                submitted = build_and_submit_model(args=args, model=model, run_prefix=run_prefix)
                submitted_runs.append(submitted)
                print(f"Submitted: {model}", flush=True)
            except Exception as exc:
                msg = str(exc)
                errors.append({"model": model, "error": msg})
                print(f"Submit failed: {model}\n{msg}", file=sys.stderr, flush=True)
                if not args.continue_on_error:
                    break
            if submitted_runs:
                latest = submitted_runs[-1]
                print(f"Processing model: {latest['model']}", flush=True)
                try:
                    result = finalize_model_run(args=args, submitted=latest, ground_truth=ground_truth)
                    results.append(result)
                    print(f"Completed: {latest['model']}", flush=True)
                except Exception as exc:
                    msg = str(exc)
                    errors.append({"model": latest["model"], "error": msg})
                    print(f"Failed: {latest['model']}\n{msg}", file=sys.stderr, flush=True)
                    if not args.continue_on_error:
                        break

    if args.submit_all_first:
        print("\n## Process phase", flush=True)
        for submitted in submitted_runs:
            model = submitted["model"]
            print(f"\nProcessing model: {model}", flush=True)
            try:
                result = finalize_model_run(args=args, submitted=submitted, ground_truth=ground_truth)
                results.append(result)
                print(f"Completed: {model}", flush=True)
            except Exception as exc:
                msg = str(exc)
                errors.append({"model": model, "error": msg})
                print(f"Failed: {model}\n{msg}", file=sys.stderr, flush=True)
                if not args.continue_on_error:
                    break

    summary = {
        "book_label": args.book_label,
        "run_prefix": run_prefix,
        "models": models,
        "submit_all_first": args.submit_all_first,
        "include_thoughts": args.include_thoughts,
        "ground_truth": str(args.ground_truth) if args.ground_truth else None,
        "submitted_runs": submitted_runs,
        "results": results,
        "errors": errors,
    }

    if args.summary_out:
        args.summary_out.parent.mkdir(parents=True, exist_ok=True)
        args.summary_out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nWrote summary JSON: {args.summary_out}")

    print("\n## Benchmark Summary\n")
    print(markdown_table(results))
    if errors:
        print("\n## Errors\n")
        for err in errors:
            print(f"- `{err['model']}`: {err['error']}")


if __name__ == "__main__":
    main()
