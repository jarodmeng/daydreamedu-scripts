"""Tests for ai_study_buddy.files.pdf_registry_paths."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ai_study_buddy.files.pdf_registry_paths import (
    LeafFolderRegistryStatus,
    PdfFileRegistryStatus,
    RegistryPathIndex,
    ScanRootRegistrationBuckets,
    direct_pdf_paths_in_leaf_folder,
    is_pdf_registered,
    leaf_folder_registry_status,
    leaf_pdf_file_registry_statuses,
    leaf_registry_statuses_for_included_leaves,
    partition_daydreamedu_leaf_folders,
    pdf_file_registry_status,
    registration_buckets,
    resolved_path_from_registry_row,
    suspicious_all_leaves_marked_non_scan_root,
)


def test_resolved_path_from_registry_row_obj_and_dict(tmp_path: Path) -> None:
    f = tmp_path / "a.pdf"
    f.write_text("x", encoding="utf-8")
    obj = SimpleNamespace(path=str(f))
    assert resolved_path_from_registry_row(obj) == str(f.resolve())
    assert resolved_path_from_registry_row({"path": str(f)}) == str(f.resolve())


def test_resolved_path_from_registry_row_missing_path_raises() -> None:
    with pytest.raises(ValueError, match="no path"):
        resolved_path_from_registry_row(object())
    with pytest.raises(ValueError, match="no path"):
        resolved_path_from_registry_row({})


def test_registry_path_index_from_pdf_file_manager(tmp_path: Path) -> None:
    pdf_a = tmp_path / "a.pdf"
    pdf_a.write_text("%PDF", encoding="utf-8")
    scan = tmp_path / "scan"
    scan.mkdir()

    pfm = MagicMock()
    pfm.find_files.return_value = [SimpleNamespace(path=str(pdf_a))]
    pfm.list_scan_roots.return_value = [SimpleNamespace(path=str(scan.resolve()))]

    idx = RegistryPathIndex.from_pdf_file_manager(pfm)
    assert str(pdf_a.resolve()) in idx.registered_resolved_paths
    assert str(scan.resolve()) in idx.scan_root_resolved_paths
    assert idx.pdf_files_row_count == 1
    assert idx.scan_roots_row_count == 1


def test_registry_path_index_empty_find_files_ok() -> None:
    pfm = MagicMock()
    pfm.find_files.return_value = []
    pfm.list_scan_roots.return_value = []
    idx = RegistryPathIndex.from_pdf_file_manager(pfm)
    assert idx.registered_resolved_paths == frozenset()


def test_direct_pdf_paths_in_leaf_folder(tmp_path: Path) -> None:
    leaf = tmp_path / "leaf"
    leaf.mkdir()
    (leaf / "z.PDF").write_bytes(b"%PDF")
    (leaf / "a.pdf").write_bytes(b"%PDF")
    (leaf / "nope.txt").write_text("x", encoding="utf-8")
    got = direct_pdf_paths_in_leaf_folder(leaf)
    assert [p.name for p in got] == ["a.pdf", "z.PDF"]


def test_pdf_file_registry_status_and_is_pdf_registered(tmp_path: Path) -> None:
    root = tmp_path / "r"
    leaf = root / "leaf"
    leaf.mkdir(parents=True)
    reg_pdf = leaf / "in.pdf"
    reg_pdf.write_bytes(b"%PDF")
    txt = leaf / "note.txt"
    txt.write_text("x", encoding="utf-8")
    reg_key = str(reg_pdf.resolve())
    idx = RegistryPathIndex(
        registered_resolved_paths=frozenset({reg_key}),
        scan_root_resolved_paths=frozenset({str(leaf.resolve())}),
        pdf_files_row_count=1,
        scan_roots_row_count=1,
        file_by_resolved_path={reg_key: SimpleNamespace(path=str(reg_pdf))},
    )
    s_pdf = pdf_file_registry_status(reg_pdf, idx)
    assert s_pdf == PdfFileRegistryStatus(
        pdf_path=reg_pdf.resolve(),
        basename="in.pdf",
        is_pdf=True,
        is_registered=True,
        parent_is_scan_root=True,
    )
    s_txt = pdf_file_registry_status(txt, idx)
    assert s_txt.is_pdf is False
    assert s_txt.is_registered is False
    assert s_txt.parent_is_scan_root is True
    assert is_pdf_registered(reg_pdf, idx) is True
    assert is_pdf_registered(txt, idx) is False


def test_leaf_pdf_file_registry_statuses(tmp_path: Path) -> None:
    leaf = tmp_path / "leaf"
    leaf.mkdir()
    p1 = leaf / "a.pdf"
    p2 = leaf / "b.PDF"
    p1.write_bytes(b"%PDF")
    p2.write_bytes(b"%PDF")
    reg_key = str(p2.resolve())
    idx = RegistryPathIndex(
        registered_resolved_paths=frozenset({reg_key}),
        scan_root_resolved_paths=frozenset(),
        pdf_files_row_count=1,
        scan_roots_row_count=0,
        file_by_resolved_path={reg_key: SimpleNamespace(path=str(p2))},
    )
    rows = leaf_pdf_file_registry_statuses(leaf, idx)
    assert [r.basename for r in rows] == ["a.pdf", "b.PDF"]
    assert [r.is_registered for r in rows] == [False, True]


def test_leaf_folder_registry_status(tmp_path: Path) -> None:
    root = tmp_path / "root"
    leaf = root / "sub"
    leaf.mkdir(parents=True)
    reg_pdf = leaf / "in.pdf"
    unreg_pdf = leaf / "out.pdf"
    reg_pdf.write_bytes(b"%PDF")
    unreg_pdf.write_bytes(b"%PDF")

    reg_key = str(reg_pdf.resolve())
    idx = RegistryPathIndex(
        registered_resolved_paths=frozenset({reg_key}),
        scan_root_resolved_paths=frozenset({str(leaf.resolve())}),
        pdf_files_row_count=1,
        scan_roots_row_count=1,
        file_by_resolved_path={reg_key: SimpleNamespace(path=str(reg_pdf))},
    )

    st = leaf_folder_registry_status(leaf, root, idx)
    assert st.rel_posix_to_sync_root == "sub"
    assert st.direct_pdf_total == 2
    assert st.unregistered_total == 1
    assert st.unregistered_basenames == ("out.pdf",)
    assert st.is_scan_root is True
    assert st.all_direct_pdfs_registered is False


def test_registration_buckets() -> None:
    s1 = LeafFolderRegistryStatus(
        leaf_dir=Path("/x"),
        rel_posix_to_sync_root="a",
        direct_pdf_total=1,
        unregistered_total=0,
        unregistered_basenames=(),
        is_scan_root=True,
    )
    s2 = LeafFolderRegistryStatus(
        leaf_dir=Path("/y"),
        rel_posix_to_sync_root="b",
        direct_pdf_total=2,
        unregistered_total=1,
        unregistered_basenames=("u.pdf",),
        is_scan_root=True,
    )
    s3 = LeafFolderRegistryStatus(
        leaf_dir=Path("/z"),
        rel_posix_to_sync_root="c",
        direct_pdf_total=1,
        unregistered_total=0,
        unregistered_basenames=(),
        is_scan_root=False,
    )
    s4 = LeafFolderRegistryStatus(
        leaf_dir=Path("/w"),
        rel_posix_to_sync_root="d",
        direct_pdf_total=1,
        unregistered_total=1,
        unregistered_basenames=("y.pdf",),
        is_scan_root=False,
    )
    b = registration_buckets([s1, s2, s3, s4])
    assert b == ScanRootRegistrationBuckets(
        scan_root_all_registered=1,
        scan_root_some_unregistered=1,
        non_scan_root_all_registered=1,
        non_scan_root_some_unregistered=1,
    )


def test_suspicious_all_leaves_marked_non_scan_root() -> None:
    idx = RegistryPathIndex(
        registered_resolved_paths=frozenset(),
        scan_root_resolved_paths=frozenset({"/scan"}),
        pdf_files_row_count=0,
        scan_roots_row_count=1,
        file_by_resolved_path={},
    )
    st = LeafFolderRegistryStatus(
        leaf_dir=Path("/leaf"),
        rel_posix_to_sync_root="L",
        direct_pdf_total=0,
        unregistered_total=0,
        unregistered_basenames=(),
        is_scan_root=False,
    )
    assert suspicious_all_leaves_marked_non_scan_root(idx, [st]) is True
    assert suspicious_all_leaves_marked_non_scan_root(
        RegistryPathIndex(frozenset(), frozenset(), 0, 0, {}),
        [st],
    ) is False


def test_partition_daydreamedu_matches_profile(daydreamedu_profile_root: Path) -> None:
    inc, exc = partition_daydreamedu_leaf_folders(daydreamedu_profile_root)
    assert [p.name for p in inc] == ["Exam", "Note", "Notes"]
    root = daydreamedu_profile_root
    assert root.resolve() in exc


def test_leaf_registry_statuses_for_included_leaves(tmp_path: Path) -> None:
    root = tmp_path / "r"
    leaf = root / "L"
    leaf.mkdir(parents=True)
    p = leaf / "f.pdf"
    p.write_bytes(b"%PDF")
    reg_key = str(p.resolve())
    idx = RegistryPathIndex(
        registered_resolved_paths=frozenset({reg_key}),
        scan_root_resolved_paths=frozenset(),
        pdf_files_row_count=1,
        scan_roots_row_count=0,
        file_by_resolved_path={reg_key: SimpleNamespace(path=str(p))},
    )
    rows = leaf_registry_statuses_for_included_leaves([leaf], root, idx)
    assert len(rows) == 1
    assert rows[0].all_direct_pdfs_registered is True
