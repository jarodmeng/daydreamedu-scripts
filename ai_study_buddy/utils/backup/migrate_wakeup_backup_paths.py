#!/usr/bin/env python3
"""Rewrite ~/.wakeup lines from removed shim paths into ai_study_buddy/utils/backup/ canonical scripts.

Transforms:
  .../pdf_file_manager/scripts/run_backup_on_wake.sh   -> .../utils/backup/run_wake_all.sh
  .../learning_db/scripts/run_backup_on_wake.sh        -> .../utils/backup/run_learning_db_wake.sh

Then: if ~/.wakeup references run_wake_all.sh, drop redundant run_learning_db_wake.sh lines.

Use after removing per-package shim scripts from the repo. Default modifies ~/.wakeup; use --dry-run to preview."""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path

PDF_SUFFIX = Path("pdf_file_manager/scripts/run_backup_on_wake.sh").as_posix()
LEARN_SUFFIX = Path("learning_db/scripts/run_backup_on_wake.sh").as_posix()
CANON_W_ALL = Path("ai_study_buddy/utils/backup/run_wake_all.sh").as_posix()
CANON_LEARN = Path("ai_study_buddy/utils/backup/run_learning_db_wake.sh").as_posix()


def _rewrite_path(raw: Path) -> Path | None:
    p = raw.expanduser()
    parts = list(p.parts)
    try:
        i = parts.index("ai_study_buddy")
    except ValueError:
        return None
    repo_root = Path(*parts[:i])
    rel = Path(*parts[i:]).as_posix()
    if rel.endswith(PDF_SUFFIX):
        return repo_root / CANON_W_ALL
    if rel.endswith(LEARN_SUFFIX):
        return repo_root / CANON_LEARN
    return None


_QUOTED = re.compile(r'"([^"]*)"')


def _transform_line(line: str) -> str:
    def repl(m: re.Match[str]) -> str:
        inner = m.group(1)
        candidate = Path(inner)
        new = _rewrite_path(candidate)
        if new is None:
            return m.group(0)
        return f'"{new}"'

    return _QUOTED.sub(repl, line)


def _normalize_invoked_path(line: str) -> str | None:
    m = _QUOTED.search(line)
    if not m:
        return None
    return Path(m.group(1)).expanduser().resolve().as_posix()


def migrate(text: str) -> tuple[str, list[str]]:
    """Return (new_text, log lines)."""
    log: list[str] = []
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for line in lines:
        if line.strip() and not line.lstrip().startswith("#") and '"' in line:
            new_line = _transform_line(line)
            if new_line != line:
                log.append(f"rewrite: {line.strip()} -> {new_line.strip()}")
            line = new_line
        out.append(line)

    body = "".join(out)
    # Post-process: drop redundant learning-only hook if combined runner present
    non_empty = [ln for ln in body.splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
    has_wake_all = False
    has_learning = False
    for ln in non_empty:
        np = _normalize_invoked_path(ln)
        if np and np.endswith("/run_wake_all.sh"):
            has_wake_all = True
        if np and np.endswith("/run_learning_db_wake.sh"):
            has_learning = True

    if has_wake_all and has_learning:
        log.append("remove redundant run_learning_db_wake.sh (run_wake_all.sh already backs up study_buddy.db)")
        kept: list[str] = []
        for ln in body.splitlines(keepends=True):
            if not ln.strip() or ln.lstrip().startswith("#"):
                kept.append(ln)
                continue
            np = _normalize_invoked_path(ln)
            if np and np.endswith("/run_learning_db_wake.sh"):
                continue
            kept.append(ln)
        body = "".join(kept)

    # Dedupe identical quoted invocations (preserve shebang + comments order)
    seen_invoke: set[str] = set()
    final_lines: list[str] = []
    for ln in body.splitlines(keepends=True):
        if not ln.strip() or ln.lstrip().startswith("#"):
            final_lines.append(ln)
            continue
        np = _normalize_invoked_path(ln)
        if np and np in seen_invoke:
            log.append(f"drop duplicate invoke: {ln.strip()}")
            continue
        if np:
            seen_invoke.add(np)
        final_lines.append(ln)
    body = "".join(final_lines)

    if not body.endswith("\n") and body:
        body += "\n"
    return body, log


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dry-run", action="store_true", help="Print planned changes only.")
    ap.add_argument(
        "--wakeup",
        type=Path,
        default=Path.home() / ".wakeup",
        help="Path to sleepwatcher wake script (default: ~/.wakeup).",
    )
    args = ap.parse_args()
    w = Path(args.wakeup).expanduser()
    if not w.is_file():
        print(f"No {w}; nothing to migrate.", file=sys.stderr)
        return 0
    raw = w.read_text(encoding="utf-8")
    new_text, log = migrate(raw)
    if new_text == raw and not log:
        print(f"{w} already uses canonical utils/backup paths (no changes).")
        return 0
    for line in log:
        print(line)
    if args.dry_run:
        print(f"[dry-run] would write {len(new_text.splitlines())} lines to {w}")
        return 0
    fd, tmppath = tempfile.mkstemp(prefix="wakeup-", suffix=".tmp", dir=str(w.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as tf:
            tf.write(new_text)
        shutil.move(tmppath, w)
        os.chmod(w, 0o755)
        print(f"Updated {w}")
    finally:
        p = Path(tmppath)
        if p.exists():
            p.unlink(missing_ok=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
