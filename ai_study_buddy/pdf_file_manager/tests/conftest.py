# Shared path setup, fixture root, and constants for pdf_file_manager tests.
# See TESTING.md. All tests use temporary DBs and (when needed) the DaydreamEdu fixture.

from pathlib import Path

_tests_dir = Path(__file__).resolve().parent

FIXTURE_ROOT = _tests_dir / "fixtures" / "daydreamedu_fixture"

EXPECTED_TABLES = [
    "book_answer_mappings",
    "file_completion_dates",
    "file_group_members",
    "file_groups",
    "file_relations",
    "operation_log",
    "pdf_files",
    "scan_roots",
    "students",
]

OPERATION_LOG_COLUMNS = {
    "id", "operation", "file_id", "group_id", "performed_at",
    "performed_by", "before_state", "after_state", "notes",
}

PDF_FILES_COLUMNS = {
    "id", "name", "path", "file_type", "doc_type", "student_id", "subject",
    "is_template", "size_bytes", "page_count", "has_raw", "metadata",
    "added_at", "updated_at", "notes",
}


def fixture_has_pdfs() -> bool:
    if not FIXTURE_ROOT.is_dir():
        return False
    pdfs = list(FIXTURE_ROOT.rglob("*.pdf"))
    return len(pdfs) >= 1
