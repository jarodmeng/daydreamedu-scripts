from ai_study_buddy.pdf_file_manager.pdf_file_manager import (
    PdfFile,
    has_raw_pdf_prefix,
    normalize_pdf_display_name,
)


def test_normalize_pdf_display_name_strips_known_prefixes():
    assert normalize_pdf_display_name("c_example.pdf") == "example"
    assert normalize_pdf_display_name("_c_example.pdf") == "example"
    assert normalize_pdf_display_name("raw_example.pdf") == "example"
    assert normalize_pdf_display_name("_raw_example.pdf") == "example"


def test_normalize_pdf_display_name_strips_iteratively():
    assert normalize_pdf_display_name("_c_raw_example.pdf") == "example"
    assert normalize_pdf_display_name("_raw__c_example.pdf") == "example"


def test_pdf_file_normal_name_uses_canonical_helper():
    file = PdfFile(
        id="1",
        name="_raw_c_example.pdf",
        path="/tmp/_raw_c_example.pdf",
        file_type="main",
        doc_type="exam",
        student_id="winston",
        subject="science",
        is_template=False,
        size_bytes=1,
        page_count=1,
        has_raw=False,
        metadata=None,
        added_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        notes=None,
    )
    assert file.normal_name == "example"


def test_has_raw_pdf_prefix():
    assert has_raw_pdf_prefix("_raw_example.pdf")
    assert has_raw_pdf_prefix("raw_example.pdf")
    assert not has_raw_pdf_prefix("_c_example.pdf")
