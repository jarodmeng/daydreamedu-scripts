#!/usr/bin/env python3
"""Remove empty directories under DAYDREAMEDU_ROOT (bottom-up).

Safe guards:
- Never removes the DaydreamEdu root itself.
- Never removes top-level ``template`` or ``completion`` branch roots.

With ``--evict-macos-metadata``, removes ``.DS_Store`` and ``.localized`` files
inside a directory when those are the only *files* present (subdirs must already
be gone). This lets legacy ``Singapore Primary …`` trees disappear after PDF
migration—Finder leaves metadata files that block plain ``rmdir``.

Default: dry-run (list only). Pass --execute to apply.

Does not use PdfFileManager; this is filesystem-only cleanup after file moves.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ai_study_buddy.files.roots import resolve_daydreamedu_root

_MACOS_METADATA_NAMES = frozenset({".DS_Store", ".localized"})


def prune_empty_dirs(
    d_root: Path,
    *,
    execute: bool,
    evict_macos_metadata: bool,
) -> tuple[list[str], list[str]]:
    """Return (removed_directory_paths, removed_junk_file_paths)."""
    d_root = d_root.resolve()
    removed_dirs: list[str] = []
    removed_junk: list[str] = []

    for dirpath_str, _dirnames, _filenames in os.walk(str(d_root), topdown=False):
        p = Path(dirpath_str).resolve()
        if p == d_root:
            continue
        try:
            rel = p.relative_to(d_root)
        except ValueError:
            continue
        if rel.parts and rel.parts[0] in {"template", "completion"} and len(rel.parts) == 1:
            continue

        try:
            children = list(p.iterdir())
        except OSError:
            continue

        subdirs = [c for c in children if c.is_dir()]
        if subdirs:
            continue

        files = [c for c in children if c.is_file()]
        if files:
            if not evict_macos_metadata:
                continue
            if not all(f.name in _MACOS_METADATA_NAMES for f in files):
                continue
            if execute:
                for f in files:
                    try:
                        f.unlink()
                        removed_junk.append(str(f))
                    except OSError as e:
                        sys.stderr.write(f"skip unlink {f}: {e}\n")

        if execute:
            try:
                p.rmdir()
            except OSError as e:
                sys.stderr.write(f"skip rmdir {p}: {e}\n")
                continue
        removed_dirs.append(str(p))

    return removed_dirs, removed_junk


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Delete metadata files (if --evict-macos-metadata) and remove empty directories.",
    )
    parser.add_argument(
        "--evict-macos-metadata",
        action="store_true",
        help="Remove .DS_Store / .localized when they are the only files in a leaf directory.",
    )
    parser.add_argument(
        "--output-json",
        help="Optional path to write full report JSON.",
    )
    args = parser.parse_args()

    root = resolve_daydreamedu_root()
    if root is None:
        print(
            "resolve_daydreamedu_root() returned None; set DAYDREAMEDU_ROOT or local_daydreamedu_root.txt",
            file=sys.stderr,
        )
        raise SystemExit(2)
    root = Path(root)

    removed_dirs, removed_junk = prune_empty_dirs(
        root,
        execute=args.execute,
        evict_macos_metadata=args.evict_macos_metadata,
    )
    out = {
        "d_root": str(root.resolve()),
        "mode": "execute" if args.execute else "dry_run",
        "evict_macos_metadata": args.evict_macos_metadata,
        "dirs_removed_or_would_remove": len(removed_dirs),
        "metadata_files_removed": len(removed_junk) if args.execute else 0,
        "dir_paths": removed_dirs,
        "junk_paths": removed_junk if args.execute else [],
    }
    print(json.dumps(out, indent=2))
    if args.output_json:
        Path(args.output_json).write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
