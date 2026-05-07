#!/usr/bin/env python3
"""Remove dangling raw/main relation rows from file_relations.

A dangling raw/main relation edge is one where source_id or target_id does not
exist in pdf_files. This script only repairs relation table consistency; it
does not delete any pdf_files rows.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager


def collect_dangling_raw_main_edges(mgr: PdfFileManager) -> tuple[list[dict], Counter]:
    conn = mgr._get_connection()
    files = conn.execute("SELECT id FROM pdf_files").fetchall()
    file_ids = {row["id"] for row in files}

    rel_rows = conn.execute(
        """
        SELECT id, source_id, target_id, relation_type
        FROM file_relations
        WHERE relation_type IN ('raw_source', 'main_version')
        ORDER BY relation_type, source_id, target_id
        """
    ).fetchall()

    dangling: list[dict] = []
    counts = Counter()
    for row in rel_rows:
        src_exists = row["source_id"] in file_ids
        tgt_exists = row["target_id"] in file_ids
        if src_exists and tgt_exists:
            continue
        reason = []
        if not src_exists:
            reason.append("missing_source")
        if not tgt_exists:
            reason.append("missing_target")
        reason_key = "+".join(reason)
        counts[f"{row['relation_type']}::{reason_key}"] += 1
        dangling.append(
            {
                "id": row["id"],
                "source_id": row["source_id"],
                "target_id": row["target_id"],
                "relation_type": row["relation_type"],
                "reason": reason_key,
            }
        )
    return dangling, counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Apply deletions (default: dry-run).")
    parser.add_argument("--preview-limit", type=int, default=20, help="Number of sample rows to print.")
    args = parser.parse_args()

    mgr = PdfFileManager()
    dangling, counts = collect_dangling_raw_main_edges(mgr)

    report = {
        "mode": "execute" if args.execute else "dry_run",
        "dangling_edge_count": len(dangling),
        "issue_breakdown": dict(counts),
        "preview": dangling[: args.preview_limit],
    }

    if args.execute and dangling:
        conn = mgr._get_connection()
        conn.executemany(
            "DELETE FROM file_relations WHERE id = ?",
            [(row["id"],) for row in dangling],
        )
        conn.commit()
        report["deleted_edge_count"] = len(dangling)

    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
