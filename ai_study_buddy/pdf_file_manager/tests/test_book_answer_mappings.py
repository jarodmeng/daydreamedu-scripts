import tempfile
import json
from pathlib import Path

import pytest

from ai_study_buddy.pdf_file_manager.pdf_file_manager import NotFoundError, PdfFileManager


def _make_pdf(path: Path) -> Path:
    path.write_bytes(b"%PDF-1.0\n")
    return path


def _register_book_file(mgr: PdfFileManager, path: Path, unit: str) -> str:
    record = mgr.register_file(
        _make_pdf(path),
        file_type="main",
        doc_type="book",
        subject="science",
        metadata={"unit": unit},
    )
    return record.id


def test_set_and_get_book_answer_mapping():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            group = mgr.create_file_group("Power Pack Science PSLE", group_type="book")
            unit_id = _register_book_file(mgr, root / "unit-1.pdf", "Unit 1")
            answer_id = _register_book_file(mgr, root / "answers.pdf", "Answers")
            mgr.add_to_file_group(group.id, unit_id)
            mgr.add_to_file_group(group.id, answer_id)

            mapping = mgr.set_book_answer_mapping(
                unit_id,
                answer_id,
                35,
                40,
                starts_mid_page=True,
                source="manual_verified",
                notes="validated",
            )
            fetched = mgr.get_book_answer_mapping(unit_id)

            assert mapping.unit_file_id == unit_id
            assert mapping.answer_file_id == answer_id
            assert mapping.answer_page_start == 35
            assert mapping.answer_page_end == 40
            assert mapping.starts_mid_page is True
            assert mapping.ends_mid_page is False
            assert mapping.source == "manual_verified"
            assert fetched is not None
            assert fetched.id == mapping.id
            assert fetched.unit_file.id == unit_id
            assert fetched.answer_file.id == answer_id
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_set_book_answer_mapping_upserts_by_unit():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            group = mgr.create_file_group("Power Pack Math PSLE", group_type="book")
            unit_id = _register_book_file(mgr, root / "unit-1.pdf", "Unit 1")
            answer_a = _register_book_file(mgr, root / "answers-a.pdf", "Answers A")
            answer_b = _register_book_file(mgr, root / "answers-b.pdf", "Answers B")
            for file_id in (unit_id, answer_a, answer_b):
                mgr.add_to_file_group(group.id, file_id)

            first = mgr.set_book_answer_mapping(unit_id, answer_a, 10, 12, source="manual_verified")
            second = mgr.set_book_answer_mapping(unit_id, answer_b, 13, 15, ends_mid_page=True, source="manual_corrected")

            assert first.id == second.id
            assert second.answer_file_id == answer_b
            assert second.answer_page_start == 13
            assert second.answer_page_end == 15
            assert second.ends_mid_page is True

            mappings = mgr.list_book_answer_mappings(book_group_id=group.id)
            assert len(mappings) == 1
            assert mappings[0].answer_file_id == answer_b

            log = mgr.get_operation_log(file_id=unit_id)
            operations = [entry.operation for entry in log]
            assert "book_answer_mapping_set" in operations
            assert "book_answer_mapping_update" in operations
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_list_book_answer_mappings_filters_by_group_answer_and_source():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            science_group = mgr.create_file_group("Science", group_type="book")
            math_group = mgr.create_file_group("Math", group_type="book")

            science_unit = _register_book_file(mgr, root / "science-unit.pdf", "Science Unit")
            science_answer = _register_book_file(mgr, root / "science-answers.pdf", "Science Answers")
            math_unit = _register_book_file(mgr, root / "math-unit.pdf", "Math Unit")
            math_answer = _register_book_file(mgr, root / "math-answers.pdf", "Math Answers")

            mgr.add_to_file_group(science_group.id, science_unit)
            mgr.add_to_file_group(science_group.id, science_answer)
            mgr.add_to_file_group(math_group.id, math_unit)
            mgr.add_to_file_group(math_group.id, math_answer)

            mgr.set_book_answer_mapping(science_unit, science_answer, 1, 2, source="manual_verified")
            mgr.set_book_answer_mapping(math_unit, math_answer, 5, 7, source="imported_ground_truth")

            science_only = mgr.list_book_answer_mappings(book_group_id=science_group.id)
            by_answer = mgr.list_book_answer_mappings(answer_file_id_or_path=math_answer)
            by_source = mgr.list_book_answer_mappings(source="manual_verified")

            assert [item.unit_file_id for item in science_only] == [science_unit]
            assert [item.unit_file_id for item in by_answer] == [math_unit]
            assert [item.unit_file_id for item in by_source] == [science_unit]
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_delete_book_answer_mapping_logs_and_removes_row():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            group = mgr.create_file_group("Power Pack English PSLE", group_type="book")
            unit_id = _register_book_file(mgr, root / "unit.pdf", "Unit")
            answer_id = _register_book_file(mgr, root / "answers.pdf", "Answers")
            mgr.add_to_file_group(group.id, unit_id)
            mgr.add_to_file_group(group.id, answer_id)
            mgr.set_book_answer_mapping(unit_id, answer_id, 20, 22, source="manual_verified")

            mgr.delete_book_answer_mapping(unit_id)

            assert mgr.get_book_answer_mapping(unit_id) is None
            log = mgr.get_operation_log(file_id=unit_id, operation="book_answer_mapping_delete")
            assert len(log) == 1
            assert log[0].before_state["answer_file_id"] == answer_id
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_set_book_answer_mapping_allows_cross_book_group_mapping_for_book_files():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            science_group = mgr.create_file_group("Science", group_type="book")
            math_group = mgr.create_file_group("Math", group_type="book")
            science_unit = _register_book_file(mgr, root / "science-unit.pdf", "Science Unit")
            math_answer = _register_book_file(mgr, root / "math-answers.pdf", "Math Answers")
            mgr.add_to_file_group(science_group.id, science_unit)
            mgr.add_to_file_group(math_group.id, math_answer)

            mapping = mgr.set_book_answer_mapping(science_unit, math_answer, 1, 2)
            assert mapping.unit_file_id == science_unit
            assert mapping.answer_file_id == math_answer

            notes_file = mgr.register_file(
                _make_pdf(root / "notes.pdf"),
                file_type="main",
                doc_type="notes",
                subject="science",
            )
            mgr.add_to_file_group(science_group.id, notes_file.id)

            with pytest.raises(ValueError, match="doc_type='book'"):
                mgr.set_book_answer_mapping(science_unit, notes_file.id, 1, 2)
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_delete_book_answer_mapping_missing_raises_not_found():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            unit_id = _register_book_file(mgr, root / "unit.pdf", "Unit")

            with pytest.raises(NotFoundError):
                mgr.delete_book_answer_mapping(unit_id)
    finally:
        Path(db_path).unlink(missing_ok=True)


def test_import_book_answer_mappings_from_json():
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name
    try:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            mgr = PdfFileManager(db_path=db_path)
            group = mgr.create_file_group("Power Pack Science PSLE", group_type="book")
            unit_id = _register_book_file(mgr, root / "_c_PP Science PSLE Topic 1.pdf", "Topic 1")
            answer_id = _register_book_file(mgr, root / "_c_PP Science PSLE Answers.pdf", "Answers")
            mgr.add_to_file_group(group.id, unit_id)
            mgr.add_to_file_group(group.id, answer_id)

            json_path = root / "ground_truth.json"
            json_path.write_text(json.dumps({
                "book_label": "Power Pack Science PSLE",
                "answer_file": "_c_PP Science PSLE Answers.pdf",
                "mappings": [
                    {
                        "unit_file": "_c_PP Science PSLE Topic 1.pdf",
                        "answer_page_start": 2,
                        "answer_page_end": 4,
                        "starts_mid_page": False,
                        "ends_mid_page": True,
                        "notes": "verified",
                    }
                ],
            }), encoding="utf-8")

            imported = mgr.import_book_answer_mappings_from_json(json_path)

            assert len(imported) == 1
            assert imported[0].unit_file_id == unit_id
            assert imported[0].answer_file_id == answer_id
            assert imported[0].source == "imported_ground_truth"
            assert imported[0].notes == "verified"
    finally:
        Path(db_path).unlink(missing_ok=True)
