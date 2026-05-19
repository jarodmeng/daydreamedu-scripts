from __future__ import annotations

import copy
import json
import subprocess
import sys
import types
from pathlib import Path

import pytest

from ai_study_buddy.marking.core.artifact_schema import validate_marking_artifact_dict
from ai_study_buddy.marking.file_question_info.api import (
    _grade_segment_from_pdf_file,
    _slug_from_pdf_file,
    _subject_scope_from_pdf_file,
    assert_unique_detector_question_ids,
    build_detector_question_id_list,
    file_question_info_run_dir_for_pdf,
    get_latest_question_sections_for_file_id,
    get_latest_question_sections_for_pdf_file,
    iter_questions_ordered,
    iter_sections_ordered,
    load_question_sections_json,
    question_page_map_from_question_sections,
    render_file_question_info_pages_for_pdf,
    section_hint_strings_for_context,
    validate_question_sections_dict,
)
from ai_study_buddy.marking.file_question_info.errors import (
    InvalidGradeOrScopeError,
    MissingGradeOrScopeError,
    QuestionSectionsDuplicateQuestionIdError,
    QuestionSectionsLookupError,
    QuestionSectionsNotFoundError,
    QuestionSectionsValidationError,
    UnknownQuestionSectionsSchemaVersionError,
)
from ai_study_buddy.learning_db.core.connection import get_connection
from ai_study_buddy.learning_db.core.migrate import apply_migrations
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


def _find_payload_for_schema_version(
    schema_version: str,
    *,
    expected_question_count: int | None = None,
    expected_first3_page_map: tuple[tuple[str, int], tuple[str, int], tuple[str, int]] | None = None,
) -> dict:
    root = Path("ai_study_buddy/context/file_question_info")
    matches: list[tuple[Path, dict]] = []
    for candidate in sorted(root.rglob("question_sections.json")):
        payload = json.loads(candidate.read_text(encoding="utf-8"))
        if payload.get("schema_version") != schema_version:
            continue
        if expected_question_count is None:
            return payload
        n = len(iter_questions_ordered(payload))
        matches.append((candidate, payload))
        if n != expected_question_count:
            continue
        if expected_first3_page_map is not None:
            page_map = question_page_map_from_question_sections(payload)
            keys = list(page_map.keys())[:3]
            got = tuple((qid, page_map[qid]["attempt_page_start"]) for qid in keys)
            if got != expected_first3_page_map:
                continue
        return payload
    if expected_question_count is not None and matches:
        counts = ", ".join(
            f"{p.relative_to(root)}:{len(iter_questions_ordered(pl))}" for p, pl in matches[:12]
        )
        raise AssertionError(
            f"No question_sections.json for {schema_version=} with "
            f"{expected_question_count} questions (candidates: {counts})"
        )
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


def _page_range(start: int, end: int) -> dict:
    return {
        "start_page": start,
        "end_page": end,
        "start_mid_page": False,
        "end_mid_page": False,
    }


def test_math_multi_page_question_info_start_pages_accepted():
    payload = _minimal_math_v1_1_payload()
    payload["sections"][0]["questions_page_range"] = _page_range(2, 5)
    payload["sections"][0]["question_info"] = [
        {"question_index": "Q1", "question_mark": 1, "start_page": 2},
        {"question_index": "Q2", "question_mark": 1, "start_page": 3},
        {"question_index": "Q3", "question_mark": 1, "start_page": 5},
    ]
    validate_question_sections_dict(payload)


@pytest.mark.parametrize("builder", [_minimal_math_v1_1_payload, _minimal_science_v1_1_payload])
def test_start_page_outside_questions_page_range_rejected(builder):
    payload = builder()
    payload["sections"][0]["questions_page_range"] = _page_range(1, 3)
    payload["sections"][0]["question_info"] = [
        {"question_index": "Q1", "question_mark": 1, "start_page": 4},
    ]
    with pytest.raises(QuestionSectionsValidationError, match="outside questions_page_range"):
        validate_question_sections_dict(payload)


@pytest.mark.parametrize("builder", [_minimal_math_v1_1_payload, _minimal_science_v1_1_payload])
def test_start_page_must_be_non_decreasing_in_reading_order(builder):
    payload = builder()
    payload["sections"][0]["questions_page_range"] = _page_range(1, 5)
    payload["sections"][0]["question_info"] = [
        {"question_index": "Q1", "question_mark": 1, "start_page": 3},
        {"question_index": "Q2", "question_mark": 1, "start_page": 2},
    ]
    with pytest.raises(QuestionSectionsValidationError, match="non-decreasing"):
        validate_question_sections_dict(payload)


@pytest.mark.parametrize("builder", [_minimal_math_v1_1_payload, _minimal_science_v1_1_payload])
def test_strict_layout_questions_page_range_start_must_match_min_question_start(builder):
    payload = builder()
    payload["sections"][0]["questions_page_range"] = _page_range(1, 5)
    payload["sections"][0]["question_info"] = [
        {"question_index": "Q1", "question_mark": 1, "start_page": 2},
    ]
    with pytest.raises(
        QuestionSectionsValidationError,
        match="questions_page_range.start_page must equal min\\(question_info.start_page\\)",
    ):
        validate_question_sections_dict(payload)


def test_english_without_stem_allows_questions_page_range_start_before_first_question():
    payload = copy.deepcopy(_find_payload_for_schema_version("english-v1.3"))
    section = next(s for s in payload["sections"] if "stem_page_range" not in s)
    section["questions_page_range"] = _page_range(1, 10)
    section["question_info"] = [
        {"question_index": "Q1", "question_mark": 1, "start_page": 2},
        {"question_index": "Q2", "question_mark": 1, "start_page": 3},
    ]
    validate_question_sections_dict(payload)


def test_english_with_stem_requires_questions_page_range_start_to_match_min_question_start():
    payload = copy.deepcopy(_find_payload_for_schema_version("english-v1.3"))
    section = next(s for s in payload["sections"] if "stem_page_range" in s)
    min_start = min(item["start_page"] for item in section["question_info"])
    section["questions_page_range"]["start_page"] = min_start + 1
    with pytest.raises(
        QuestionSectionsValidationError,
        match="questions_page_range.start_page must equal min\\(question_info.start_page\\)",
    ):
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


def test_consumer_iterators_and_map_helpers():
    payload = _minimal_math_v1_1_payload()
    validate_question_sections_dict(payload)

    sections = iter_sections_ordered(payload)
    assert len(sections) == 1
    assert sections[0]["question_type"] == "SAQ"
    assert sections[0]["questions_page_range"]["start_page"] == 1

    questions = iter_questions_ordered(payload)
    assert [q["question_index"] for q in questions] == ["Q19", "Q20(a)", "Q6(a)(i)"]

    assert build_detector_question_id_list(payload) == ("Q19", "Q20(a)", "Q6(a)(i)")
    assert_unique_detector_question_ids(payload)

    page_map = question_page_map_from_question_sections(payload)
    assert page_map["Q19"]["attempt_page_start"] == 1
    assert page_map["Q20(a)"]["attempt_page_start"] == 1
    assert page_map["Q6(a)(i)"]["attempt_page_start"] == 1
    assert page_map["Q19"]["source"] == "script_inferred"
    assert page_map["Q19"]["confidence"] == "high"

    assert section_hint_strings_for_context(payload) == ("S1: SAQ",)


def test_duplicate_question_ids_hard_fail():
    payload = _minimal_math_v1_1_payload()
    payload["sections"][0]["question_info"].append({"question_index": "Q19", "question_mark": 1, "start_page": 1})
    validate_question_sections_dict(payload)
    with pytest.raises(QuestionSectionsDuplicateQuestionIdError, match="duplicate question_index"):
        assert_unique_detector_question_ids(payload)
    with pytest.raises(QuestionSectionsDuplicateQuestionIdError):
        question_page_map_from_question_sections(payload)


def test_section_hint_includes_trimmed_title():
    payload = _minimal_math_v1_1_payload()
    payload["sections"][0]["printed_section_title"] = "  Open   Ended  "
    validate_question_sections_dict(payload)
    assert section_hint_strings_for_context(payload) == ("S1: SAQ: Open Ended",)


def test_get_latest_question_sections_for_file_id_db_and_divergence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    payload = _minimal_math_v1_1_payload()
    file_id = str(payload["input_context"]["files"][0]["file_id"])
    context_root = tmp_path / "context"
    source_rel_path = "file_question_info/singapore_primary_math/P6/sample/question_sections.json"
    fs_path = context_root / source_rel_path
    fs_path.parent.mkdir(parents=True, exist_ok=True)
    fs_path.write_text(json.dumps(payload), encoding="utf-8")

    db_path = tmp_path / "study_buddy.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO file_question_info_runs(
                run_id, schema_version, subject_scope, grade, slug, primary_file_id, primary_file_path,
                source_rel_path, source_content_hash, raw_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run-1",
                payload["schema_version"],
                "singapore_primary_math",
                "P6",
                "sample",
                file_id,
                "/tmp/smoke_math.pdf",
                source_rel_path,
                "h1",
                json.dumps(payload),
                payload["created_at"],
                payload["updated_at"],
            ),
        )
        conn.commit()
    finally:
        conn.close()

    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "1")
    monkeypatch.setenv("LEARNING_DB_READ_FALLBACK_FILESYSTEM", "0")
    src = get_latest_question_sections_for_file_id(file_id, context_root=context_root)
    assert src["source_kind"] == "db"
    assert src["template_file_id"] == file_id
    assert src["validated_at_runtime"] is True

    # Introduce divergence and verify hard fail when detection is on.
    bad = dict(payload)
    bad["schema_version"] = "math-v1.0"
    fs_path.write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(QuestionSectionsLookupError, match="divergence detected"):
        get_latest_question_sections_for_file_id(file_id, context_root=context_root, detect_divergence=True)


def test_get_latest_question_sections_read_flags_and_pdf_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    payload = _minimal_science_v1_1_payload()
    file_id = str(payload["input_context"]["files"][0]["file_id"])
    context_root = tmp_path / "context"
    path = context_root / "file_question_info" / "singapore_primary_science" / "P6" / "s1" / "question_sections.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")

    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    monkeypatch.setenv("LEARNING_DB_READ_FALLBACK_FILESYSTEM", "0")
    src = get_latest_question_sections_for_file_id(file_id, context_root=context_root)
    assert src["source_kind"] == "filesystem"

    # reads enabled + no fallback and no DB rows should hard fail not found
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "1")
    monkeypatch.setenv("LEARNING_DB_READ_FALLBACK_FILESYSTEM", "0")
    db_path = tmp_path / "study_buddy.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    apply_migrations(db_path=db_path)
    with pytest.raises(QuestionSectionsNotFoundError):
        get_latest_question_sections_for_file_id(file_id, context_root=context_root, detect_divergence=False)

    # Same lookup through PdfFile wrapper
    pdf = _pdf_file(subject="science")
    pdf.id = file_id
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "0")
    src2 = get_latest_question_sections_for_pdf_file(pdf, context_root=context_root)
    assert src2["template_file_id"] == file_id


def test_get_latest_question_sections_invalid_payload_raises_typed_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    payload = _minimal_math_v1_1_payload()
    file_id = str(payload["input_context"]["files"][0]["file_id"])

    bad_payload = {"schema_version": "math-v1.2", "input_context": {"files": [{"file_id": file_id}]}}

    db_path = tmp_path / "study_buddy.db"
    monkeypatch.setenv("STUDY_BUDDY_DB_PATH", str(db_path))
    monkeypatch.setenv("LEARNING_DB_ENABLE_READS", "1")
    monkeypatch.setenv("LEARNING_DB_READ_FALLBACK_FILESYSTEM", "0")
    apply_migrations(db_path=db_path)
    conn = get_connection(db_path)
    try:
        conn.execute(
            """
            INSERT INTO file_question_info_runs(
                run_id, schema_version, subject_scope, grade, slug, primary_file_id, primary_file_path,
                source_rel_path, source_content_hash, raw_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "run-bad",
                "math-v1.2",
                "singapore_primary_math",
                "P6",
                "bad",
                file_id,
                "/tmp/bad.pdf",
                "file_question_info/singapore_primary_math/P6/bad/question_sections.json",
                "hbad",
                json.dumps(bad_payload),
                "2026-01-01T00:00:00+08:00",
                "2026-01-01T00:00:00+08:00",
            ),
        )
        conn.commit()
    finally:
        conn.close()

    with pytest.raises(QuestionSectionsValidationError):
        get_latest_question_sections_for_file_id(file_id, context_root=tmp_path / "context", require_valid=True)


@pytest.mark.parametrize(
    ("schema_version", "expected_count", "expected_first3"),
    [
        (
            "chinese-v1.4",
            40,
            (
                ("Q1", 2),
                ("Q2", 2),
                ("Q3", 2),
            ),
        ),
        (
            "high-chinese-v1.2",
            11,
            (
                ("Q1", 3),
                ("Q2", 3),
                ("Q3", 3),
            ),
        ),
        (
            "english-v1.3",
            75,
            (
                ("Q1", 2),
                ("Q2", 2),
                ("Q3", 2),
            ),
        ),
        (
            "math-v1.2",
            38,
            (
                ("Q1", 1),
                ("Q2", 1),
                ("Q3", 1),
            ),
        ),
        (
            "science-v1.2",
            22,
            (
                ("Q1(a)", 2),
                ("Q1(b)", 2),
                ("Q2(a)", 3),
            ),
        ),
    ],
)
def test_question_page_map_golden_by_subject_family(schema_version, expected_count, expected_first3):
    payload = _find_payload_for_schema_version(
        schema_version,
        expected_question_count=expected_count,
        expected_first3_page_map=expected_first3,
    )
    validate_question_sections_dict(payload)
    page_map = question_page_map_from_question_sections(payload)
    keys = list(page_map.keys())
    assert len(keys) == expected_count
    assert tuple((qid, page_map[qid]["attempt_page_start"]) for qid in keys[:3]) == expected_first3
    for qid, row in page_map.items():
        assert row["result_id"] == qid
        assert row["confidence"] == "high"
        assert row["source"] == "script_inferred"


def test_generated_page_map_is_compatible_with_marking_result_consumers():
    payload = _minimal_math_v1_1_payload()
    validate_question_sections_dict(payload)
    page_map = question_page_map_from_question_sections(payload)

    fixture = Path("ai_study_buddy/marking/tests/fixtures/marking_result_v1_5/valid_minimal.json")
    artifact_payload = json.loads(fixture.read_text(encoding="utf-8"))
    artifact_payload["context"]["question_page_map"] = list(page_map.values())
    artifact_payload["question_results"] = [
        {
            "result_id": qid,
            "scoring_status": "counted",
            "outcome": "correct",
            "max_marks": 1,
            "earned_marks": 1,
            "student_answer": None,
            "correct_answer": None,
            "error_tags": [],
            "skill_tags": [],
            "diagnosis": {"mistake_type": None, "reasoning": None, "confidence": None},
            "human_note": None,
        }
        for qid in page_map.keys()
    ]
    artifact_payload["summary"]["total_marks"] = len(page_map)
    artifact_payload["summary"]["earned_marks"] = len(page_map)
    artifact_payload["summary"]["percentage"] = 100.0

    validate_marking_artifact_dict(artifact_payload)
