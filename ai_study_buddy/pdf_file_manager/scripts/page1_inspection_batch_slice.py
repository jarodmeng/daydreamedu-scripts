#!/usr/bin/env python3
"""Print manifest slice for page-1 agent batches (operator helper)."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from ai_study_buddy.pdf_file_manager.completion_date.page1 import (
    default_page1_work_dir,
    manifest_path_for,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work-dir", default="", help="Batch work directory")
    parser.add_argument("--offset", type=int, default=0)
    parser.add_argument("--batch-size", type=int, default=10)
    parser.add_argument("--pending-only", action="store_true", help="Skip items with results JSON")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    work_dir = Path(args.work_dir) if args.work_dir else default_page1_work_dir()
    manifest = json.loads(manifest_path_for(work_dir).read_text(encoding="utf-8"))
    items = manifest.get("items") or []

    if args.pending_only:
        pending = []
        for item in items:
            fid = item["file_id"]
            if not (work_dir / "results" / f"{fid}.json").is_file():
                pending.append(item)
        items = pending

    batch = items[args.offset : args.offset + args.batch_size]
    if args.json:
        print(json.dumps(batch, ensure_ascii=False, indent=2))
    else:
        print(f"work_dir={work_dir.resolve()}")
        print(f"slice offset={args.offset} batch_size={args.batch_size} count={len(batch)}")
        print(f"pending_total={len(items) if not args.pending_only else 'n/a'}")
        for item in batch:
            page2 = item.get("page2_image_path") or ""
            print(
                f"{item['file_id']}\t{item['doc_type']}\t{item['normal_name'][:50]}\t"
                f"{item['page1_image_path']}\t{page2}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
