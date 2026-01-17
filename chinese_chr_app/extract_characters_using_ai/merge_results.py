#!/usr/bin/env python3
"""
Merge multiple JSONL result files into a single file.

This script merges multiple JSONL files (typically from different batches)
into a single output file, with optional deduplication and append mode.

Usage:
    # Merge multiple files
    python3 merge_results.py \
      --inputs jsonl/results_001.jsonl jsonl/results_002.jsonl jsonl/results_003.jsonl \
      --output jsonl/results.jsonl

    # Append to existing file
    python3 merge_results.py \
      --inputs jsonl/results_004.jsonl \
      --output jsonl/results.jsonl \
      --append
"""

import argparse
from pathlib import Path
from typing import Set, Optional


def count_lines(file_path: Path) -> int:
    """Count non-empty lines in a file."""
    count = 0
    if file_path.exists():
        with file_path.open('r', encoding='utf-8') as f:
            count = sum(1 for line in f if line.strip())
    return count


def merge_jsonl_files(
    input_files: list[Path],
    output_file: Path,
    append: bool = False,
    deduplicate: bool = False,
) -> tuple[int, int]:
    """
    Merge multiple JSONL files into one.
    
    Returns:
        tuple: (total_lines, new_lines_added)
    """
    # Count existing entries if appending
    existing_count = 0
    seen_lines: Optional[Set[str]] = None
    
    if append and output_file.exists():
        existing_count = count_lines(output_file)
        if deduplicate:
            # Load existing lines for deduplication
            seen_lines = set()
            with output_file.open('r', encoding='utf-8') as f:
                for line in f:
                    if line.strip():
                        seen_lines.add(line.strip())
    
    # Open output file
    mode = "a" if (append and output_file.exists()) else "w"
    new_lines_added = 0
    
    with output_file.open(mode, encoding='utf-8') as f_out:
        for input_file in input_files:
            if not input_file.exists():
                print(f"⚠️  Skipping non-existent file: {input_file}")
                continue
            
            print(f"   Reading: {input_file.name}")
            lines_in_file = 0
            lines_added_from_file = 0
            
            with input_file.open('r', encoding='utf-8') as f_in:
                for line in f_in:
                    if not line.strip():
                        continue
                    
                    lines_in_file += 1
                    
                    # Check for duplicates if deduplication is enabled
                    if deduplicate:
                        line_key = line.strip()
                        if seen_lines is not None:
                            if line_key in seen_lines:
                                continue
                            seen_lines.add(line_key)
                    
                    f_out.write(line)
                    lines_added_from_file += 1
                    new_lines_added += 1
            
            print(f"      Added {lines_added_from_file} lines (from {lines_in_file} total)")
    
    total_lines = existing_count + new_lines_added
    return total_lines, new_lines_added


def main():
    parser = argparse.ArgumentParser(
        description="Merge multiple JSONL result files into a single file."
    )
    parser.add_argument(
        "--inputs",
        nargs="+",
        type=Path,
        required=True,
        help="List of input JSONL files to merge (e.g., results_001.jsonl results_002.jsonl)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        required=True,
        help="Path to output JSONL file (e.g., results.jsonl)",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Append to existing output file instead of overwriting",
    )
    parser.add_argument(
        "--deduplicate",
        action="store_true",
        help="Remove duplicate lines (based on exact line content)",
    )

    args = parser.parse_args()

    # Create output directory
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Check if input files exist
    missing_files = [f for f in args.inputs if not f.exists()]
    if missing_files:
        print(f"⚠️  Warning: {len(missing_files)} input file(s) not found:")
        for f in missing_files:
            print(f"   - {f}")
        print()

    # Count existing entries if appending
    existing_count = 0
    if args.append and args.output.exists():
        existing_count = count_lines(args.output)
        if existing_count > 0:
            print(f"📋 Existing entries in {args.output.name}: {existing_count}")

    print(f"🔀 Merging {len(args.inputs)} file(s) into {args.output.name}...")
    print(f"{'='*60}")

    total_lines, new_lines_added = merge_jsonl_files(
        args.inputs,
        args.output,
        append=args.append,
        deduplicate=args.deduplicate,
    )

    print(f"{'='*60}")
    if args.append and existing_count > 0:
        print(f"✅ Appended {new_lines_added} new entries to {args.output.resolve()}")
        print(f"   Total entries: {total_lines} (was {existing_count}, added {new_lines_added})")
    else:
        print(f"✅ Merged results saved to: {args.output.resolve()}")
        print(f"   Total entries: {total_lines}")


if __name__ == "__main__":
    main()
