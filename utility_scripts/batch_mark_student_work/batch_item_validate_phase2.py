#!/usr/bin/env python3
"""Gate before batch_item_finalize: section count and phase2 row coverage."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
for p in (_REPO_ROOT, _SCRIPT_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meta-json", type=Path, required=True)
    parser.add_argument("--phase2-json", type=Path, required=True)
    args = parser.parse_args()

    meta = json.loads(args.meta_json.read_text(encoding="utf-8"))
    rows = json.loads(args.phase2_json.read_text(encoding="utf-8"))
    if not isinstance(rows, list):
        print("ERROR: phase2 JSON must be an array", file=sys.stderr)
        return 1

    sections = meta.get("sections") or []
    if not sections:
        print("ERROR: meta has no sections[]", file=sys.stderr)
        return 1

    expected_ids: list[str] = []
    for section in sections:
        for qid in section.get("question_ids") or []:
            if isinstance(qid, str) and qid.strip():
                expected_ids.append(qid.strip())

    got_ids = [
        r.get("question_id")
        for r in rows
        if isinstance(r, dict) and isinstance(r.get("question_id"), str)
    ]
    missing = [q for q in expected_ids if q not in got_ids]
    extra = [q for q in got_ids if q not in expected_ids]

    if len(rows) != len(expected_ids):
        print(
            f"ERROR: phase2 rows {len(rows)} != expected {len(expected_ids)} "
            f"from {len(sections)} section(s)",
            file=sys.stderr,
        )
        if missing:
            print(f"  missing question_ids: {missing}", file=sys.stderr)
        if extra:
            print(f"  unexpected question_ids: {extra}", file=sys.stderr)
        return 1

    if missing or extra:
        print("ERROR: question_id mismatch", file=sys.stderr)
        if missing:
            print(f"  missing: {missing}", file=sys.stderr)
        if extra:
            print(f"  extra: {extra}", file=sys.stderr)
        return 1

    print(
        json.dumps(
            {
                "ok": True,
                "sections": len(sections),
                "phase2_rows": len(rows),
                "question_ids": expected_ids,
            },
            indent=2,
            ensure_ascii=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
