"""Tests for ai_study_buddy.files.main_pdfs."""

from dataclasses import dataclass
from pathlib import Path

from ai_study_buddy.files.main_pdfs import (
    build_main_pdf_index_for_roots,
    include_in_completion_operator_universe,
    is_inventory_main_pdf,
    is_main_pdf_basename,
    list_main_pdfs_in_leaf_folder,
)
from ai_study_buddy.files.path_facets import infer_path_facets
from ai_study_buddy.files.pdf_registry_paths import RegistryPathIndex


def test_is_main_pdf_basename() -> None:
    assert is_main_pdf_basename("_c_foo.pdf")
    assert not is_main_pdf_basename("_raw_foo.pdf")


def test_list_main_pdfs_in_leaf_folder(tmp_path: Path) -> None:
    leaf = tmp_path / "leaf"
    leaf.mkdir()
    (leaf / "_c_main.pdf").write_bytes(b"%PDF")
    (leaf / "_raw_main.pdf").write_bytes(b"%PDF")
    names = [p.name for p in list_main_pdfs_in_leaf_folder(leaf)]
    assert names == ["_c_main.pdf"]


def test_build_main_pdf_index_for_roots(tmp_path: Path) -> None:
    root = tmp_path / "DaydreamEdu"
    leaf = root / "completion" / "Singapore Primary Math" / "a@b.com" / "P4" / "Exam"
    leaf.mkdir(parents=True)
    (leaf / "_c_test.pdf").write_bytes(b"%PDF")

    rows = build_main_pdf_index_for_roots(daydreamedu_root=root, goodnotes_root=None)
    assert len(rows) == 1
    assert rows[0].basename == "_c_test.pdf"
    assert rows[0].facets.scope == "completion"
    assert rows[0].facets.doc_type == "exam"


def test_include_in_completion_operator_universe() -> None:
    exam = infer_path_facets(
        Path("/fake/DaydreamEdu/completion/Math/u@x.com/P4/Exam/a.pdf"),
        root_id="daydreamedu",
    )
    note = infer_path_facets(
        Path("/fake/DaydreamEdu/completion/Singapore Primary Chinese/u@x.com/P3/Note/n.pdf"),
        root_id="daydreamedu",
    )
    assert include_in_completion_operator_universe(exam)
    assert not include_in_completion_operator_universe(note)


@dataclass(frozen=True)
class _FakeRegistryRow:
    path: str
    file_type: str


def test_is_inventory_main_pdf_uses_registry_file_type(tmp_path: Path) -> None:
    main_pdf = tmp_path / "p6.chinese.wa1.1.pdf"
    raw_pdf = tmp_path / "_c_p6.chinese.wa1.1.pdf"
    main_pdf.write_bytes(b"%PDF")
    raw_pdf.write_bytes(b"%PDF")
    index = RegistryPathIndex(
        registered_resolved_paths=frozenset({str(main_pdf.resolve()), str(raw_pdf.resolve())}),
        scan_root_resolved_paths=frozenset(),
        pdf_files_row_count=2,
        scan_roots_row_count=0,
        file_by_resolved_path={
            str(main_pdf.resolve()): _FakeRegistryRow(str(main_pdf), "raw"),
            str(raw_pdf.resolve()): _FakeRegistryRow(str(raw_pdf), "main"),
        },
    )
    assert not is_inventory_main_pdf(main_pdf, registry_index=index)
    assert is_inventory_main_pdf(raw_pdf, registry_index=index)
    assert is_inventory_main_pdf(tmp_path / "unregistered.pdf", registry_index=index)


def test_build_main_pdf_index_respects_registry_file_type(tmp_path: Path) -> None:
    root = tmp_path / "DaydreamEdu"
    leaf = root / "completion" / "Singapore Primary Chinese" / "a@b.com" / "P6" / "Exam"
    leaf.mkdir(parents=True)
    raw_name = leaf / "p6.chinese.wa1.1.pdf"
    main_name = leaf / "_c_p6.chinese.wa1.1.pdf"
    raw_name.write_bytes(b"%PDF")
    main_name.write_bytes(b"%PDF")
    index = RegistryPathIndex(
        registered_resolved_paths=frozenset(
            {str(raw_name.resolve()), str(main_name.resolve())}
        ),
        scan_root_resolved_paths=frozenset(),
        pdf_files_row_count=2,
        scan_roots_row_count=0,
        file_by_resolved_path={
            str(raw_name.resolve()): _FakeRegistryRow(str(raw_name), "raw"),
            str(main_name.resolve()): _FakeRegistryRow(str(main_name), "main"),
        },
    )
    rows = build_main_pdf_index_for_roots(
        daydreamedu_root=root,
        goodnotes_root=None,
        registry_index=index,
    )
    assert len(rows) == 1
    assert rows[0].basename == "_c_p6.chinese.wa1.1.pdf"


def test_build_main_pdf_index_excludes_activity_note_completions(tmp_path: Path) -> None:
    root = tmp_path / "DaydreamEdu"
    exam_leaf = root / "completion" / "Singapore Primary Math" / "a@b.com" / "P4" / "Exam"
    note_leaf = root / "completion" / "Singapore Primary Chinese" / "a@b.com" / "P3" / "Note"
    exam_leaf.mkdir(parents=True)
    note_leaf.mkdir(parents=True)
    (exam_leaf / "_c_exam.pdf").write_bytes(b"%PDF")
    (note_leaf / "_c_note.pdf").write_bytes(b"%PDF")

    assert len(build_main_pdf_index_for_roots(daydreamedu_root=root, goodnotes_root=None)) == 2
    filtered = build_main_pdf_index_for_roots(
        daydreamedu_root=root,
        goodnotes_root=None,
        exclude_activity_note_completions=True,
    )
    assert len(filtered) == 1
    assert filtered[0].facets.doc_type == "exam"
