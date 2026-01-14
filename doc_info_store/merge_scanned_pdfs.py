#!/usr/bin/env python3
"""
Merge raw scanned PDFs in a folder into a single PDF, ordered by filename index.

Assumptions / conventions (aligned with doc_info_store):
- Only include "raw scanned files" whose basename starts with 'p' (case-insensitive)
- Ignore derived variants like 'c.p5.math.001....pdf'
- Ignore hidden files like '.DS_Store'
- Filename convention typically: <grade>.<subject>.<index>.<title>.pdf

Logging:
- Each run writes a JSON log next to the output PDF: <output_pdf>.log.json
- The output PDF name includes a run id so you can locate the matching log easily.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

try:
    import fitz  # PyMuPDF
except Exception as e:  # pragma: no cover
    fitz = None
    _FITZ_IMPORT_ERR = e


_INDEX_RE = re.compile(r"^(?P<prefix>[pP][^.]*)\.(?P<subject>[^.]*)\.(?P<index>\d{3})\..+\.pdf$")


def _iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _run_id(now_utc: datetime) -> str:
    # Example: 20260113T091530Z
    return now_utc.strftime("%Y%m%dT%H%M%SZ")


def _guess_child_from_path(input_dir: Path) -> str:
    # .../<child> Primary School documents/<grade>/<subject>
    for p in input_dir.parts:
        m = re.match(r"^(?P<child>.+?)\s+Primary School documents?$", p, flags=re.IGNORECASE)
        if m:
            child = m.group("child").strip()
            return child if child else "unknown"
    return "unknown"


def _guess_grade_subject_from_path(input_dir: Path) -> tuple[str, str]:
    if len(input_dir.parts) < 2:
        return "", ""
    grade = input_dir.parts[-2].upper()
    subject = input_dir.parts[-1]
    subject = subject[:1].upper() + subject[1:].lower() if subject else subject
    return grade, subject


@dataclass(frozen=True)
class InputPdf:
    path: Path
    index: Optional[int]


def _is_raw_scanned_pdf(p: Path) -> bool:
    if not p.is_file():
        return False
    if p.name.startswith("."):
        return False
    if not p.name.lower().endswith(".pdf"):
        return False
    return p.name.lower().startswith("p")


def _extract_index(filename: str) -> Optional[int]:
    m = _INDEX_RE.match(filename)
    if not m:
        return None
    try:
        return int(m.group("index"))
    except Exception:
        return None


def _list_inputs(input_dir: Path) -> list[InputPdf]:
    inputs: list[InputPdf] = []
    for p in sorted(input_dir.iterdir()):
        if not _is_raw_scanned_pdf(p):
            continue
        inputs.append(InputPdf(path=p, index=_extract_index(p.name)))
    inputs.sort(key=lambda x: (x.index is None, x.index if x.index is not None else 10**9, x.path.name.lower()))
    return inputs


def _ensure_fitz() -> None:
    if fitz is None:
        raise SystemExit(
            "Missing dependency PyMuPDF. Install with:\n"
            "  pip install -r question_splitter/requirements.txt\n"
            "or\n"
            "  pip install -r doc_info_store/requirements.txt\n"
            f"\nOriginal import error: {_FITZ_IMPORT_ERR}"
        )


def merge_pdfs(inputs: list[InputPdf], output_pdf: Path) -> dict:
    """
    Merge PDFs using PyMuPDF, returning summary stats.
    """
    _ensure_fitz()
    output_pdf.parent.mkdir(parents=True, exist_ok=True)

    out_doc = fitz.open()
    included = []
    total_pages = 0
    for item in inputs:
        src = item.path
        try:
            src_doc = fitz.open(str(src))
            n_pages = int(src_doc.page_count)
            out_doc.insert_pdf(src_doc)
            included.append(
                {
                    "filename": src.name,
                    "index": item.index if item.index is not None else "",
                    "pages": n_pages,
                }
            )
            total_pages += n_pages
        except Exception as e:
            included.append(
                {
                    "filename": src.name,
                    "index": item.index if item.index is not None else "",
                    "pages": "",
                    "error": str(e),
                }
            )

    out_doc.save(str(output_pdf))
    out_doc.close()
    return {"included": included, "total_pages": total_pages}


def main() -> int:
    ap = argparse.ArgumentParser(description="Merge raw scanned PDFs in a folder into one PDF, ordered by index.")
    ap.add_argument("input_dir", help="Folder containing PDFs, e.g. '.../Winston .../P5/Math'")
    ap.add_argument(
        "-o",
        "--output-dir",
        default="doc_info_store/out",
        help="Output directory (default: doc_info_store/out)",
    )
    ap.add_argument(
        "--output-name",
        default=None,
        help="Optional output PDF filename. If omitted, a name is generated.",
    )
    args = ap.parse_args()

    run_started = datetime.now(timezone.utc)
    rid = _run_id(run_started)

    input_dir = Path(args.input_dir).expanduser()
    if not input_dir.exists() or not input_dir.is_dir():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 2

    child = _guess_child_from_path(input_dir)
    grade, subject = _guess_grade_subject_from_path(input_dir)

    inputs = _list_inputs(input_dir)
    if not inputs:
        print("No raw scanned PDFs found (expected basenames starting with 'p').", file=sys.stderr)
        return 3

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_name = args.output_name or f"merged_{child}_{grade}_{subject}__{rid}.pdf".replace(" ", "_")
    output_pdf = output_dir / output_name

    print(f"Merging {len(inputs)} PDFs -> {output_pdf}", file=sys.stderr)
    summary = merge_pdfs(inputs, output_pdf=output_pdf)

    run_finished = datetime.now(timezone.utc)
    log_path = Path(str(output_pdf) + ".log.json")

    # Snapshot inputs for "what produced this output"
    snapshot = []
    for item in inputs:
        p = item.path
        try:
            st = p.stat()
            mtime = datetime.fromtimestamp(st.st_mtime, tz=timezone.utc)
            size = int(st.st_size)
        except Exception:
            mtime = None
            size = None
        snapshot.append(
            {
                "filename": p.name,
                "index": item.index if item.index is not None else "",
                "mtime_utc": _iso_utc(mtime) if mtime else "",
                "size_bytes": size if size is not None else "",
            }
        )

    log = {
        "run_id": rid,
        "run_started_at_utc": _iso_utc(run_started),
        "run_finished_at_utc": _iso_utc(run_finished),
        "input_dir": str(input_dir),
        "child": child,
        "grade": grade,
        "subject": subject,
        "included_files_count": len(inputs),
        "output_pdf": str(output_pdf),
        "output_pdf_log": str(log_path),
        "merge_summary": summary,
        "input_snapshot": snapshot,
        "ordering": "by filename index (.<index>.) ascending; ties by filename; files without index last",
    }
    log_path.write_text(json.dumps(log, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote merged PDF -> {output_pdf}")
    print(f"Wrote log -> {log_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

