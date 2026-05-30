import tempfile
from pathlib import Path

import pytest

from ai_study_buddy.pdf_file_manager.pdf_file_manager import InvalidDocTypeError, PdfFileManager


def test_normalize_doc_type_accepts_canonical_values():
    mgr = PdfFileManager(db_path=str(Path(tempfile.gettempdir()) / "tmp-registry.db"))
    for value in ("exam", "exercise", "book", "activity", "composition", "note"):
        assert mgr._normalize_doc_type(value) == value
        assert mgr._normalize_doc_type(value.upper()) == value


@pytest.mark.parametrize(
    "value",
    [
        None,
        "",
        " ",
        "worksheet",
        "notes",
        "book_exercise",
        "practice",
        "unknown",
    ],
)
def test_normalize_doc_type_rejects_legacy_and_invalid_values(value):
    mgr = PdfFileManager(db_path=str(Path(tempfile.gettempdir()) / "tmp-registry.db"))
    with pytest.raises(InvalidDocTypeError):
        mgr._normalize_doc_type(value)  # type: ignore[arg-type]

