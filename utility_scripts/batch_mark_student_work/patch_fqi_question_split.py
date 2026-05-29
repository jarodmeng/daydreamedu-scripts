#!/usr/bin/env python3
"""Split one FQI question_info row into multiple rows (same section, in place).

Validates and finalizes the snapshot to study_buddy.db when --finalize is set.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

_SCRIPT_DIR = Path(__file__).resolve().parent
_REPO_ROOT = _SCRIPT_DIR.parents[1]
_CONTEXT_ROOT = _REPO_ROOT / "ai_study_buddy" / "context"
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from ai_study_buddy.marking.file_question_info.api import (
    assert_unique_detector_question_ids,
    build_detector_question_id_list,
    load_question_sections_json,
)
from ai_study_buddy.marking.file_question_info.post_write import finalize_question_sections_snapshot
from ai_study_buddy.marking.file_question_info.validate import main as validate_main


def _find_question(payload: dict, question_index: str) -> tuple[int, int, dict]:
    for si, section in enumerate(payload.get("sections") or []):
        if not isinstance(section, dict):
            continue
        info = section.get("question_info")
        if not isinstance(info, list):
            continue
        for qi, row in enumerate(info):
            if isinstance(row, dict) and str(row.get("question_index")) == question_index:
                return si, qi, row
    raise ValueError(f"question_index not found: {question_index}")


def split_question(
    payload: dict,
    *,
    question_index: str,
    replacements: list[dict],
) -> list[str]:
    si, qi, row = _find_question(payload, question_index)
    base = copy.deepcopy(row)
    new_rows: list[dict] = []
    for spec in replacements:
        new_row = copy.deepcopy(base)
        new_row.update(spec)
        new_rows.append(new_row)
    section = payload["sections"][si]
    info = section["question_info"]
    info[qi : qi + 1] = new_rows
    assert_unique_detector_question_ids(payload)
    return list(build_detector_question_id_list(payload))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("json_path", type=Path, help="Path to question_sections.json")
    parser.add_argument("--question-index", required=True, help="Existing question_index to split")
    parser.add_argument(
        "--into",
        required=True,
        help='JSON array of replacement field objects, e.g. \'[{"question_index":"Q72(a)","question_mark":1}]\'',
    )
    parser.add_argument("--finalize", action="store_true", help="Run validate + finalize_question_sections_snapshot")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    replacements = json.loads(args.into)
    if not isinstance(replacements, list) or not replacements:
        raise SystemExit("--into must be a non-empty JSON array")

    path = args.json_path
    if not path.is_absolute():
        path = (_CONTEXT_ROOT / path).resolve() if not path.exists() else path.resolve()
    payload = load_question_sections_json(path)
    before = list(build_detector_question_id_list(payload))
    after = split_question(payload, question_index=args.question_index, replacements=replacements)

    print(f"split {args.question_index}: {len(before)} -> {len(after)} questions")
    print("new tail:", after[max(0, len(after) - 6) :])

    if args.dry_run:
        return 0

    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    if args.finalize:
        if validate_main([str(path)]) != 0:
            raise SystemExit("validate failed")
        finalize_question_sections_snapshot(snapshot_path=path, context_root=_CONTEXT_ROOT)
        print("finalize: OK")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
