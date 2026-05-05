from __future__ import annotations

import argparse
from pathlib import Path

from ai_study_buddy.marking.file_question_info.api import (
    load_question_sections_json,
    validate_question_sections_dict,
)
from ai_study_buddy.marking.file_question_info.errors import FileQuestionInfoError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate file_question_info question_sections.json")
    parser.add_argument("path", help="Path to question_sections.json")
    args = parser.parse_args(argv)

    path = Path(args.path)
    try:
        payload = load_question_sections_json(path)
        validate_question_sections_dict(payload)
    except (FileQuestionInfoError, OSError, ValueError) as exc:
        print(f"validation failed: {exc}")
        return 1

    print(f"validation passed: {path}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())

