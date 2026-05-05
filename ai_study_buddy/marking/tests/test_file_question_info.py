from __future__ import annotations

import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

from ai_study_buddy.marking.file_question_info.api import (
    _grade_segment_from_pdf_file,
    _slug_from_pdf_file,
    _subject_scope_from_pdf_file,
    file_question_info_run_dir_for_pdf,
    load_question_sections_json,
    render_file_question_info_pages_for_pdf,
    validate_question_sections_dict,
)
from ai_study_buddy.marking.file_question_info.errors import (
    InvalidGradeOrScopeError,
    MissingGradeOrScopeError,
    QuestionSectionsValidationError,
    UnknownQuestionSectionsSchemaVersionError,
)
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFile


class _FakePixmap:
    def __init__(self, marker: bytes):
        self._marker = marker

    def save(self, path: str) -> None:
        Path(path).write_bytes(self._marker)


class _FakePage:
    def __init__(self, index: int):
        self._index = index

    def get_pixmap(self, matrix, alpha: bool = False):
        _ = matrix
        _ = alpha
        return _FakePixmap(f"page-{self._index + 1}".encode("utf-8"))


class _FakeDoc:
    def __init__(self, page_count: int):
        self.page_count = page_count

    def __getitem__(self, index: int):
        return _FakePage(index)

    def close(self) -> None:
        return None


def _install_fake_fitz(monkeypatch: pytest.MonkeyPatch, page_count: int = 4) -> None:
    fake_module = types.SimpleNamespace(
        Matrix=lambda x, y: (x, y),
        open=lambda _path: _FakeDoc(page_count),
    )
    monkeypatch.setitem(sys.modules, "fitz", fake_module)


def _pdf_file(*, name: str = "p6.math.wa1.3.pdf", subject: str = "math", grade: str = "P6") -> PdfFile:
    return PdfFile(
        id="file-1",
        name=name,
        path=f"/tmp/{name}",
        file_type="main",
        doc_type="exam",
        student_id=None,
        subject=subject,
        is_template=False,
        size_bytes=123,
        page_count=5,
        has_raw=False,
        metadata={"grade_or_scope": grade},
        added_at="2026-01-01T00:00:00Z",
        updated_at="2026-01-01T00:00:00Z",
        notes=None,
    )


def test_slug_from_pdf_file_matches_normalization_prefix_rules():
    assert _slug_from_pdf_file(_pdf_file(name="_raw_demo.pdf")) == "demo"
    assert _slug_from_pdf_file(_pdf_file(name="_c_demo.pdf")) == "demo"
    assert _slug_from_pdf_file(_pdf_file(name="raw_demo.pdf")) == "demo"
    assert _slug_from_pdf_file(_pdf_file(name="c_demo.pdf")) == "demo"


def test_grade_segment_normalizes_and_restricts_allowlist():
    assert _grade_segment_from_pdf_file(_pdf_file(grade=" p6 ")) == "P6"
    assert _grade_segment_from_pdf_file(_pdf_file(grade="psle")) == "PSLE"

    with pytest.raises(MissingGradeOrScopeError):
        bad = _pdf_file()
        bad.metadata = {}
        _grade_segment_from_pdf_file(bad)

    with pytest.raises(InvalidGradeOrScopeError, match="Allowed values"):
        _grade_segment_from_pdf_file(_pdf_file(grade="Archive"))


def test_subject_scope_mapping():
    assert _subject_scope_from_pdf_file(_pdf_file(subject="math")) == "singapore_primary_math"
    assert _subject_scope_from_pdf_file(_pdf_file(subject="science")) == "singapore_primary_science"
    assert _subject_scope_from_pdf_file(_pdf_file(subject="english")) == "singapore_primary_english"
    assert _subject_scope_from_pdf_file(_pdf_file(subject="chinese")) == "singapore_primary_chinese"


def test_run_dir_for_pdf_uses_context_root_and_segments(tmp_path):
    path = file_question_info_run_dir_for_pdf(_pdf_file(), context_root=tmp_path / "context")
    assert path == (tmp_path / "context" / "file_question_info" / "singapore_primary_math" / "P6" / "p6.math.wa1.3")


def test_render_file_question_info_pages_full_and_subset_dense_names(tmp_path, monkeypatch):
    _install_fake_fitz(monkeypatch, page_count=4)
    pdf = _pdf_file()
    source_pdf = tmp_path / "input.pdf"
    source_pdf.write_bytes(b"%PDF fake\n")
    pdf.path = str(source_pdf)

    written = render_file_question_info_pages_for_pdf(pdf, context_root=tmp_path / "context")
    assert [p.name for p in written] == ["page_001.png", "page_002.png", "page_003.png", "page_004.png"]

    subset = render_file_question_info_pages_for_pdf(
        pdf,
        context_root=tmp_path / "context",
        pages_1_based=[4, 2],
        clean_existing=False,
        image_format="jpg",
    )
    assert [p.name for p in subset] == ["page_001.jpg", "page_002.jpg"]
    assert subset[0].read_bytes() == b"page-4"
    assert subset[1].read_bytes() == b"page-2"


def test_render_clean_existing_removes_all_existing_images(tmp_path, monkeypatch):
    _install_fake_fitz(monkeypatch, page_count=1)
    pdf = _pdf_file()
    source_pdf = tmp_path / "input.pdf"
    source_pdf.write_bytes(b"%PDF fake\n")
    pdf.path = str(source_pdf)

    target = file_question_info_run_dir_for_pdf(pdf, context_root=tmp_path / "context") / "rendered_pages"
    target.mkdir(parents=True, exist_ok=True)
    (target / "old.png").write_bytes(b"stale")
    (target / "old.jpg").write_bytes(b"stale")
    (target / "note.txt").write_text("keep", encoding="utf-8")

    render_file_question_info_pages_for_pdf(pdf, context_root=tmp_path / "context", clean_existing=True)

    assert not (target / "old.png").exists()
    assert not (target / "old.jpg").exists()
    assert (target / "note.txt").exists()
    assert (target / "page_001.png").is_file()


def _find_payload_for_schema_version(schema_version: str) -> dict:
    root = Path("ai_study_buddy/context/file_question_info")
    for candidate in root.rglob("question_sections.json"):
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        if payload.get("schema_version") == schema_version:
            return payload
    raise AssertionError(f"No question_sections.json found for schema version {schema_version}")


def _minimal_math_v1_1_payload() -> dict:
    rng = {"start_page": 1, "end_page": 1, "start_mid_page": False, "end_mid_page": False}
    sec_dbg = {"matched_header_text": "", "matched_instruction_text": "", "notes": ""}
    qrow = [{"question_index": "Q19", "question_mark": 2, "start_page": 1}]
    qrow_nested = [{"question_index": "Q20(a)", "question_mark": 1, "start_page": 1}]
    qrow_deep = [{"question_index": "Q6(a)(i)", "question_mark": 1, "start_page": 1}]
    return {
        "schema_version": "math-v1.2",
        "created_at": "2026-01-01T00:00:00+08:00",
        "updated_at": "2026-01-01T00:00:00+08:00",
        "input_context": {
            "files": [
                {
                    "path": "/tmp/smoke_math.pdf",
                    "file_id": "11111111-2222-4333-8444-555555555555",
                    "role": "question_booklet",
                    "notes": "",
                }
            ],
            "hints": "",
            "notes": "",
        },
        "debug": {"generation_model": "pytest", "confidence": "high", "notes": ""},
        "sections": [
            {
                "question_type": "SAQ",
                "questions_page_range": rng,
                "question_info": qrow + qrow_nested + qrow_deep,
                "debug": sec_dbg,
            }
        ],
    }


def _minimal_science_v1_1_payload() -> dict:
    rng = {"start_page": 1, "end_page": 1, "start_mid_page": False, "end_mid_page": False}
    sec_dbg = {"matched_header_text": "", "matched_instruction_text": "", "notes": ""}
    return {
        "schema_version": "science-v1.2",
        "created_at": "2026-01-01T00:00:00+08:00",
        "updated_at": "2026-01-01T00:00:00+08:00",
        "input_context": {
            "files": [
                {
                    "path": "/tmp/smoke_science.pdf",
                    "file_id": "22222222-3333-4444-8555-666666666666",
                    "role": "question_booklet",
                    "notes": "",
                }
            ],
            "hints": "",
            "notes": "",
        },
        "debug": {"generation_model": "pytest", "confidence": "high", "notes": ""},
        "sections": [
            {
                "question_type": "OEQ",
                "questions_page_range": rng,
                "question_info": [
                    {"question_index": "Q31", "question_mark": 3, "start_page": 1},
                    {"question_index": "Q31(a)", "question_mark": 2, "start_page": 1},
                    {"question_index": "Q6(a)(i)", "question_mark": 1, "start_page": 1},
                    {"question_index": "Q6(b)(ii)", "question_mark": 1, "start_page": 1},
                ],
                "debug": sec_dbg,
            }
        ],
    }


@pytest.mark.parametrize(
    "schema_version",
    ["chinese-v1.4", "high-chinese-v1.2", "english-v1.3", "math-v1.2", "science-v1.2"],
)
def test_validate_question_sections_dict_accepts_real_corpus_examples(schema_version):
    payload = _find_payload_for_schema_version(schema_version)
    validate_question_sections_dict(payload)


def test_validate_math_and_science_v1_2_smoke():
    validate_question_sections_dict(_minimal_math_v1_1_payload())
    validate_question_sections_dict(_minimal_science_v1_1_payload())


def test_math_v1_2_question_index_suffix_form_rejected():
    payload = _minimal_math_v1_1_payload()
    payload["sections"][0]["question_info"][1] = {"question_index": "Q20a", "question_mark": 1, "start_page": 1}
    with pytest.raises(QuestionSectionsValidationError, match="question_index"):
        validate_question_sections_dict(payload)


def test_science_v1_2_question_index_hyphen_inside_parens_rejected():
    payload = _minimal_science_v1_1_payload()
    payload["sections"][0]["question_info"][-1] = {
        "question_index": "Q6(a-i)",
        "question_mark": 1,
        "start_page": 1,
    }
    with pytest.raises(QuestionSectionsValidationError, match="question_index"):
        validate_question_sections_dict(payload)


def test_validate_question_sections_unknown_version():
    with pytest.raises(UnknownQuestionSectionsSchemaVersionError, match="Supported versions"):
        validate_question_sections_dict({"schema_version": "not-real"})


def test_validate_question_sections_enforces_single_input_file():
    payload = _find_payload_for_schema_version("math-v1.2")
    payload = dict(payload)
    input_context = dict(payload["input_context"])
    files = list(input_context["files"])
    input_context["files"] = files + [dict(files[0])]
    payload["input_context"] = input_context
    with pytest.raises(QuestionSectionsValidationError, match="exactly one entry"):
        validate_question_sections_dict(payload)


def test_load_question_sections_json_and_cli_validate(tmp_path):
    payload = _find_payload_for_schema_version("english-v1.3")
    path = tmp_path / "question_sections.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert load_question_sections_json(path)["schema_version"] == "english-v1.3"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_study_buddy.marking.file_question_info.validate",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "validation passed" in result.stdout


def test_load_question_sections_json_rejects_invalid_utf8_and_truncated_json(tmp_path):
    bad_utf8 = tmp_path / "bad_utf8.json"
    bad_utf8.write_bytes(b"\xff\xfe\xfd")
    with pytest.raises(UnicodeDecodeError):
        load_question_sections_json(bad_utf8)

    truncated = tmp_path / "truncated.json"
    truncated.write_text("{", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        load_question_sections_json(truncated)


def test_validate_question_sections_dict_accepts_all_real_corpus_files():
    root = Path("ai_study_buddy/context/file_question_info")
    candidates = sorted(root.rglob("question_sections.json"))
    assert candidates, f"No question_sections.json files found under {root}"

    for path in candidates:
        payload = load_question_sections_json(path)
        validate_question_sections_dict(payload)
