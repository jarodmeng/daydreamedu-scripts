#!/usr/bin/env python3
"""Apply detector batch results to priority_template_fqi_detector_queue.json."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def _resolve_output_path(raw: str) -> Path:
    p = Path(raw.strip())
    if not p.is_absolute():
        p = (REPO_ROOT / p).resolve()
    return p


def _extract_output_path(text: str) -> str | None:
    if not text:
        return None
    patterns = [
        r"\*\*Output path\*\*:\s*`([^`]+)`",
        r"\*\*Output:\*\*\s*`([^`]+)`",
        r"Output path[`\s:]+\s*`?([^\s`]+question_sections\.json)`?",
        r"`([^`]+question_sections\.json)`",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return m.group(1).strip()
    return None


def apply_batch(queue_path: Path, results: list[dict[str, Any]]) -> dict[str, Any]:
    payload = json.loads(queue_path.read_text(encoding="utf-8"))
    by_ord = {
        int(item.get("ord") or 0): item
        for item in payload.get("items", [])
        if isinstance(item, dict)
    }
    stats: dict[str, Any] = {"succeeded": 0, "failed": []}
    for r in results:
        ord_num = int(r["ord"])
        item = by_ord.get(ord_num)
        if item is None:
            stats["failed"].append({"ord": ord_num, "reason": "ord_not_in_queue"})
            continue
        success = bool(r.get("success"))
        if success:
            out = str(r.get("output_path") or _extract_output_path(str(r.get("raw") or "")) or "")
            if not out:
                item["status"] = "failed"
                item["error"] = "missing_output_path"
                stats["failed"].append({"ord": ord_num, "reason": "missing_output_path"})
                continue
            p = _resolve_output_path(out)
            if not p.is_file():
                item["status"] = "failed"
                item["error"] = "output_missing_after_success"
                stats["failed"].append({"ord": ord_num, "reason": "output_missing_after_success"})
                continue
            item["status"] = "done"
            item["needs_detection"] = False
            item["detector_completed_at"] = _now_iso()
            item["error"] = None
            stats["succeeded"] += 1
        else:
            err = str(r.get("error") or r.get("reason") or "detector_failed")[:200]
            item["status"] = "failed"
            item["error"] = err
            stats["failed"].append({"ord": ord_num, "reason": err})
    tmp = queue_path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    tmp.replace(queue_path)
    return stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument(
        "--results-json",
        type=Path,
        required=True,
        help="JSON file: list of {ord, success, output_path?, error?, raw?}",
    )
    args = parser.parse_args()
    results = json.loads(args.results_json.read_text(encoding="utf-8"))
    if not isinstance(results, list):
        raise SystemExit("results-json must be a JSON list")
    stats = apply_batch(args.queue.expanduser().resolve(), results)
    print(json.dumps(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
