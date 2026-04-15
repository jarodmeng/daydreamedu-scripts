#!/usr/bin/env python3
"""
Assemble unit answer-page ranges from continuation-aware page-segments output.

This variant expects:
- page_segments[].visible_unit_indices
- page_segments[].continued_unit_index
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _as_int_list(value: object) -> list[int]:
    if not isinstance(value, list):
        return []
    out: list[int] = []
    for v in value:
        try:
            out.append(int(v))
        except (TypeError, ValueError):
            continue
    return out


def _dedupe_keep_order(values: list[int]) -> list[int]:
    seen: set[int] = set()
    out: list[int] = []
    for v in values:
        if v in seen:
            continue
        seen.add(v)
        out.append(v)
    return out


def _build_manifest_order(result: dict) -> tuple[list[int], dict[int, int], dict[int, int | None]]:
    """
    Preferred source: result["unit_manifest_indices"] (if present).
    Fallback: numeric ordering from all indices observed in page_segments.
    """
    manifest = _as_int_list(result.get("unit_manifest_indices"))
    if not manifest:
        observed: set[int] = set()
        for item in result.get("page_segments") or []:
            observed.update(_as_int_list(item.get("visible_unit_indices")))
            c = item.get("continued_unit_index")
            if c is not None:
                try:
                    observed.add(int(c))
                except (TypeError, ValueError):
                    pass
        manifest = sorted(observed)

    order_map = {idx: pos for pos, idx in enumerate(manifest)}
    predecessor_map: dict[int, int | None] = {}
    for pos, idx in enumerate(manifest):
        predecessor_map[idx] = manifest[pos - 1] if pos > 0 else None
    return manifest, order_map, predecessor_map


def main() -> None:
    parser = argparse.ArgumentParser(description="Assemble page ranges from continuation-aware page segments")
    parser.add_argument("--processed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--custom-id", required=True)
    args = parser.parse_args()

    data = json.loads(args.processed.read_text(encoding="utf-8"))
    result = (data.get("results") or {}).get(args.custom_id)
    if not result:
        print(f"Error: No processed result found for {args.custom_id}", file=sys.stderr)
        sys.exit(1)

    page_segments = sorted(result.get("page_segments") or [], key=lambda item: int(item["answer_page"]))
    if not page_segments:
        print("Error: No page_segments found", file=sys.stderr)
        sys.exit(1)

    manifest, order_map, predecessor_map = _build_manifest_order(result)
    manifest_set = set(manifest)

    continuation_rule_violations: list[dict] = []
    # Warnings: structural hints that may be false positives when manifest order
    # includes units with no answer section (prompt v0.1.1 continuation semantics).
    continuation_rule_warnings: list[dict] = []
    continuation_substitution_suspicions: list[dict] = []
    per_page_units: dict[int, list[int]] = {}
    ordered_seen: list[int] = []
    ordered_seen_set: set[int] = set()

    unit_pages: dict[int, list[int]] = {}
    first_position: dict[int, tuple[int, int]] = {}
    last_position: dict[int, tuple[int, int]] = {}

    for item in page_segments:
        page = int(item["answer_page"])
        visible = _as_int_list(item.get("visible_unit_indices"))
        continued_raw = item.get("continued_unit_index")
        continued: int | None
        if continued_raw is None:
            continued = None
        else:
            try:
                continued = int(continued_raw)
            except (TypeError, ValueError):
                continued = None
                continuation_rule_violations.append(
                    {
                        "answer_page": page,
                        "reason": "continued_unit_index_non_integer",
                        "value": continued_raw,
                    }
                )

        if len(visible) != len(set(visible)):
            continuation_rule_violations.append(
                {
                    "answer_page": page,
                    "reason": "duplicate_visible_unit_indices",
                    "visible_unit_indices": visible,
                }
            )

        # Strictly increasing in manifest order.
        last_order = -1
        for idx in visible:
            if idx not in manifest_set:
                continuation_rule_violations.append(
                    {
                        "answer_page": page,
                        "reason": "visible_unit_not_in_manifest",
                        "unit_index": idx,
                    }
                )
                continue
            current_order = order_map[idx]
            if current_order <= last_order:
                continuation_rule_violations.append(
                    {
                        "answer_page": page,
                        "reason": "visible_unit_indices_not_strictly_increasing",
                        "visible_unit_indices": visible,
                    }
                )
                break
            last_order = current_order

        if continued is not None and continued not in manifest_set:
            continuation_rule_violations.append(
                {
                    "answer_page": page,
                    "reason": "continued_unit_not_in_manifest",
                    "continued_unit_index": continued,
                }
            )

        if continued is not None and continued in set(visible):
            continuation_rule_violations.append(
                {
                    "answer_page": page,
                    "reason": "continued_unit_also_listed_visible",
                    "continued_unit_index": continued,
                    "visible_unit_indices": visible,
                }
            )

        # Continuation-only pages are valid: a page can continue one unit without
        # introducing any new visible registry heading.

        if visible and continued is not None:
            first_visible = visible[0]
            expected = predecessor_map.get(first_visible)
            if continued != expected:
                # Strict manifest predecessor often disagrees with "last identified
                # answer unit before first visible heading" (e.g. unit 09 absent from
                # answer key). Downgrade to warning, not error.
                continuation_rule_warnings.append(
                    {
                        "severity": "warning",
                        "answer_page": page,
                        "reason": "continued_unit_not_manifest_predecessor_of_first_visible",
                        "continued_unit_index": continued,
                        "first_visible_unit_index": first_visible,
                        "manifest_immediate_predecessor": expected,
                        "note": (
                            "Manifest-order predecessor may not match continuation when "
                            "intermediate manifest units have no answer section; compare "
                            "to model page_segments and prompt v0.1.1 continuation rules."
                        ),
                    }
                )

        page_units = []
        if continued is not None:
            page_units.append(continued)
        page_units.extend(visible)
        page_units = _dedupe_keep_order(page_units)
        per_page_units[page] = page_units

        for idx in page_units:
            if idx not in ordered_seen_set:
                ordered_seen_set.add(idx)
                ordered_seen.append(idx)

        for pos, idx in enumerate(page_units):
            unit_pages.setdefault(idx, []).append(page)
            if idx not in first_position or (page, pos) < first_position[idx]:
                first_position[idx] = (page, pos)
            if idx not in last_position or (page, pos) > last_position[idx]:
                last_position[idx] = (page, pos)

    # Heuristic suspicion for "continuation substitution" between adjacent pages.
    for i in range(1, len(page_segments)):
        curr = page_segments[i]
        prev = page_segments[i - 1]
        curr_page = int(curr["answer_page"])
        prev_page = int(prev["answer_page"])
        curr_cont = curr.get("continued_unit_index")
        if curr_cont is None:
            continue
        try:
            curr_cont_i = int(curr_cont)
        except (TypeError, ValueError):
            continue
        prev_units = per_page_units.get(prev_page) or []
        if not prev_units:
            continue
        prev_last = prev_units[-1]
        if prev_last == curr_cont_i:
            continue
        if prev_last in order_map and curr_cont_i in order_map and order_map[prev_last] == order_map[curr_cont_i] + 1:
            continuation_substitution_suspicions.append(
                {
                    "answer_page": curr_page,
                    "previous_page": prev_page,
                    "continued_unit_index": curr_cont_i,
                    "previous_page_last_unit": prev_last,
                    "reason": "possible_continuation_owner_substitution",
                }
            )

    mappings = []
    for unit_index in sorted(unit_pages):
        pages = sorted(set(unit_pages[unit_index]))
        first_page, first_pos = first_position[unit_index]
        last_page, last_pos = last_position[unit_index]
        first_page_units = per_page_units.get(first_page, [])
        last_page_units = per_page_units.get(last_page, [])
        mappings.append(
            {
                "unit_index": unit_index,
                "answer_page_start": min(pages),
                "answer_page_end": max(pages),
                "starts_mid_page": first_pos > 0,
                "ends_mid_page": last_pos < len(last_page_units) - 1,
            }
        )

    if ordered_seen and manifest:
        if all(idx in order_map for idx in ordered_seen):
            seen_positions = sorted(order_map[idx] for idx in ordered_seen)
            start_pos = seen_positions[0]
            end_pos = seen_positions[-1]
            missing_in_span = [idx for idx in manifest[start_pos : end_pos + 1] if idx not in ordered_seen_set]
        else:
            missing_in_span = []
    else:
        missing_in_span = []

    non_monotonic = any(
        ordered_seen[i] in order_map
        and ordered_seen[i + 1] in order_map
        and order_map[ordered_seen[i]] > order_map[ordered_seen[i + 1]]
        for i in range(len(ordered_seen) - 1)
    )

    assembled = {
        "book_label": result.get("book_label"),
        "answer_file": result.get("answer_file"),
        "mappings": mappings,
        "global_notes": [
            "These ranges were assembled deterministically from continuation-aware per-page segments.",
            "starts_mid_page means the unit was not the first assembled unit on its first answer page.",
            "ends_mid_page means the unit was not the last assembled unit on its last answer page.",
        ],
        "validation": {
            "manifest_unit_indices": manifest,
            "ordered_seen_unit_indices": ordered_seen,
            "pages_with_no_registry_units": [
                int(item["answer_page"])
                for item in page_segments
                if not per_page_units.get(int(item["answer_page"]))
            ],
            "missing_unit_indices_within_detected_span": missing_in_span,
            "non_monotonic_jump_detected": non_monotonic,
            "continuation_rule_violations": continuation_rule_violations,
            "continuation_rule_warnings": continuation_rule_warnings,
            "continuation_substitution_suspicions": continuation_substitution_suspicions,
            "mapping_count": len(mappings),
        },
    }

    thought = result.get("_thought_summary")
    if thought:
        assembled["_thought_summary"] = thought

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(assembled, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote assembled ranges to {args.output}")


if __name__ == "__main__":
    main()
