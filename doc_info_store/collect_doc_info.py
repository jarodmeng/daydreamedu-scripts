#!/usr/bin/env python3
"""
Collect metadata for scanned school documents.

Outputs a flat table with columns:
- child
- grade
- subject
- scanned_file_name
- num_pages

Heuristics:
- Prefer inferring child/grade/subject from the directory structure:
  <child> Primary School documents/<grade>/<subject>/
- Also parses the filename convention:
  <grade>.<subject>.<index>.<title>.pdf

Example input:
  ".../My Drive/Winston Primary School documents/P5/Math/p5.math.001.P5 Term 1 Weekend Worksheet 1.pdf"
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional, Tuple

try:
    import fitz  # PyMuPDF
except Exception as e:  # pragma: no cover
    fitz = None
    _FITZ_IMPORT_ERR = e


_FILENAME_RE = re.compile(
    r"^(?P<grade>[pP]\d)\.(?P<subject>[a-zA-Z]+)\.(?P<index>\d{3})\.(?P<title>.+)\.pdf$"
)


@dataclass(frozen=True)
class DocRow:
    child: str
    grade: str
    subject: str
    scanned_file_name: str
    num_pages: str  # keep as string so CSV can have empty for non-pdf / failures


def _normalize_grade(s: str) -> str:
    s = s.strip()
    if re.fullmatch(r"[pP]\d", s):
        return s.upper()
    return s


def _normalize_subject(s: str) -> str:
    s = s.strip()
    if not s:
        return s
    return s[:1].upper() + s[1:].lower()


def _guess_child_from_path(input_dir: Path) -> str:
    """
    Given .../<child> Primary School documents/<grade>/<subject>, infer <child>.
    Falls back to 'unknown' if not detected.
    """
    parts = [p for p in input_dir.parts if p]
    for p in parts:
        m = re.match(r"^(?P<child>.+?)\s+Primary School documents?$", p, flags=re.IGNORECASE)
        if m:
            child = m.group("child").strip()
            return child if child else "unknown"
    return "unknown"


def _guess_grade_subject_from_path(input_dir: Path) -> Tuple[str, str]:
    grade = ""
    subject = ""
    # Expect .../<grade>/<subject>
    if len(input_dir.parts) >= 2:
        grade = _normalize_grade(Path(*input_dir.parts[-2:-1]).name)
        subject = _normalize_subject(Path(*input_dir.parts[-1:]).name)
    return grade, subject


def _parse_from_filename(filename: str) -> Tuple[Optional[str], Optional[str]]:
    m = _FILENAME_RE.match(filename)
    if not m:
        return None, None
    grade = _normalize_grade(m.group("grade"))
    subject = _normalize_subject(m.group("subject"))
    return grade, subject


def _safe_pdf_page_count(path: Path) -> Optional[int]:
    if path.suffix.lower() != ".pdf":
        return None
    if fitz is None:
        raise SystemExit(
            "Missing dependency PyMuPDF. Install with:\n"
            "  pip install -r question_splitter/requirements.txt\n"
            "or\n"
            "  pip install -r doc_info_store/requirements.txt\n"
            f"\nOriginal import error: {_FITZ_IMPORT_ERR}"
        )
    try:
        doc = fitz.open(str(path))
        return int(doc.page_count)
    except Exception:
        return None


def _iter_files(input_dir: Path, recursive: bool) -> Iterable[Path]:
    if recursive:
        for p in input_dir.rglob("*"):
            if not p.is_file():
                continue
            if p.name.startswith("."):
                continue
            yield p
    else:
        for p in input_dir.iterdir():
            if not p.is_file():
                continue
            if p.name.startswith("."):
                continue
            yield p


def collect_rows(input_dir: Path, recursive: bool) -> list[DocRow]:
    child = _guess_child_from_path(input_dir)
    grade_from_dir, subject_from_dir = _guess_grade_subject_from_path(input_dir)

    rows: list[DocRow] = []
    for p in sorted(_iter_files(input_dir, recursive=recursive)):
        filename = p.name
        # Only include "raw scanned files" which (per convention) always begin with "p".
        # This excludes derived variants like "c.p5.math.001....pdf".
        if not filename.lower().startswith("p"):
            continue
        g_from_name, s_from_name = _parse_from_filename(filename)

        grade = g_from_name or grade_from_dir
        subject = s_from_name or subject_from_dir

        n_pages = _safe_pdf_page_count(p)
        rows.append(
            DocRow(
                child=child,
                grade=grade,
                subject=subject,
                scanned_file_name=filename,
                num_pages=str(n_pages) if n_pages is not None else "",
            )
        )
    return rows


def write_csv(rows: list[DocRow], out_csv: Path) -> None:
    out_csv.parent.mkdir(parents=True, exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["child", "grade", "subject", "scanned_file_name", "num_pages"],
        )
        w.writeheader()
        for r in rows:
            w.writerow(asdict(r))


def write_json(rows: list[DocRow], out_json: Path) -> None:
    out_json.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(r) for r in rows]
    out_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def write_manifest(
    *,
    input_dir: Path,
    recursive: bool,
    rows: list[DocRow],
    included_files: list[Path],
    output_csv: Path,
    output_json: Optional[Path],
    run_started_at: datetime,
    run_finished_at: datetime,
    out_manifest: Path,
) -> None:
    out_manifest.parent.mkdir(parents=True, exist_ok=True)

    snapshot = []
    for p in included_files:
        try:
            st = p.stat()
            mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
            size = int(st.st_size)
        except Exception:
            mtime = None
            size = None
        snapshot.append(
            {
                "relative_path": str(p.relative_to(input_dir)),
                "scanned_file_name": p.name,
                "mtime_utc": _iso_utc(mtime) if mtime else "",
                "size_bytes": size if size is not None else "",
            }
        )

    manifest = {
        "run_started_at_utc": _iso_utc(run_started_at),
        "run_finished_at_utc": _iso_utc(run_finished_at),
        "input_dir": str(input_dir),
        "recursive": bool(recursive),
        "inclusion_rules": {
            "include_basename_prefix": "p",
            "exclude_basename_prefixes": ["."],
            "exclude_examples": ["c.p5.math.001....pdf"],
        },
        "outputs": {
            "csv": str(output_csv),
            "json": str(output_json) if output_json else "",
        },
        "row_count": len(rows),
        "file_snapshot": snapshot,
    }
    out_manifest.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description="Collect metadata for scanned docs in a folder.")
    ap.add_argument(
        "input_dir",
        help="Directory to scan, e.g. '.../My Drive/Winston Primary School documents/P5/Math'",
    )
    ap.add_argument(
        "-o",
        "--output-csv",
        default="doc_info_store/out/doc_info.csv",
        help="Output CSV path (default: doc_info_store/out/doc_info.csv)",
    )
    ap.add_argument("--json", dest="output_json", default=None, help="Optional output JSON path.")
    ap.add_argument(
        "--manifest",
        dest="output_manifest",
        default=None,
        help="Optional output manifest JSON path (default: <output-csv>.manifest.json).",
    )
    ap.add_argument("--recursive", action="store_true", help="Scan subfolders recursively.")
    args = ap.parse_args()

    input_dir = Path(args.input_dir).expanduser()
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 2

    run_started_at = datetime.now(timezone.utc)

    # Collect rows + list of included files (same filtering rules)
    included_files: list[Path] = []
    rows: list[DocRow] = []
    child = _guess_child_from_path(input_dir)
    grade_from_dir, subject_from_dir = _guess_grade_subject_from_path(input_dir)
    for p in sorted(_iter_files(input_dir, recursive=args.recursive)):
        filename = p.name
        if not filename.lower().startswith("p"):
            continue
        included_files.append(p)

        g_from_name, s_from_name = _parse_from_filename(filename)
        grade = g_from_name or grade_from_dir
        subject = s_from_name or subject_from_dir
        n_pages = _safe_pdf_page_count(p)
        rows.append(
            DocRow(
                child=child,
                grade=grade,
                subject=subject,
                scanned_file_name=filename,
                num_pages=str(n_pages) if n_pages is not None else "",
            )
        )

    out_csv = Path(args.output_csv)
    write_csv(rows, out_csv)
    out_json = Path(args.output_json) if args.output_json else None
    if out_json:
        write_json(rows, out_json)

    run_finished_at = datetime.now(timezone.utc)
    out_manifest = (
        Path(args.output_manifest)
        if args.output_manifest
        else Path(str(out_csv) + ".manifest.json")
    )
    write_manifest(
        input_dir=input_dir,
        recursive=args.recursive,
        rows=rows,
        included_files=included_files,
        output_csv=out_csv,
        output_json=out_json,
        run_started_at=run_started_at,
        run_finished_at=run_finished_at,
        out_manifest=out_manifest,
    )

    print(f"Wrote {len(rows)} rows -> {out_csv}")
    print(f"Wrote manifest -> {out_manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

