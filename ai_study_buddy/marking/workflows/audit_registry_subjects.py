from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager

ALLOWED_SUBJECTS = {"english", "math", "science", "chinese"}


def run_subject_audit(*, manager: PdfFileManager) -> dict:
    files = manager.find_files()
    missing: list[dict[str, str]] = []
    invalid: list[dict[str, str]] = []

    for file in files:
        raw_subject = file.subject
        normalized = raw_subject.strip().casefold() if isinstance(raw_subject, str) else ""
        row = {
            "file_id": file.id,
            "path": file.path,
            "name": file.name,
            "subject": raw_subject,
        }
        if not normalized:
            missing.append(row)
            continue
        if normalized not in ALLOWED_SUBJECTS:
            invalid.append(row)

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "total_files": len(files),
        "allowed_subjects": sorted(ALLOWED_SUBJECTS),
        "missing_subject_count": len(missing),
        "invalid_subject_count": len(invalid),
        "missing_subject_rows": missing,
        "invalid_subject_rows": invalid,
    }


def _default_output_path() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d")
    return Path("ai_study_buddy/context/marking_audits") / f"pdf_subject_audit_{stamp}.json"


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit pdf_files.subject coverage in PDF registry.")
    parser.add_argument("--db-path", type=str, default=None, help="Optional registry SQLite path.")
    parser.add_argument("--output", type=str, default=None, help="Optional JSON output path.")
    args = parser.parse_args()

    manager = PdfFileManager(db_path=args.db_path) if args.db_path else PdfFileManager()
    payload = run_subject_audit(manager=manager)

    output_path = Path(args.output) if args.output else _default_output_path()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    print(str(output_path))
    print(f"total_files={payload['total_files']}")
    print(f"missing_subject_count={payload['missing_subject_count']}")
    print(f"invalid_subject_count={payload['invalid_subject_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
