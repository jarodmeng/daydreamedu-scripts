"""Tests for path confinement under configured roots."""

from pathlib import Path

import pytest

from ai_study_buddy.root_pdf_browser.serve import (
    _content_disposition_inline,
    _pdf_blocked_not_under_leaf_folder,
    list_dir_children,
    safe_resolve_under_root,
)


def test_safe_resolve_normal_child(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    sub = root / "a"
    sub.mkdir()
    got = safe_resolve_under_root(root, "a")
    assert got == sub.resolve()


def test_safe_resolve_empty_rel_is_root(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    assert safe_resolve_under_root(root, "") == root.resolve()
    assert safe_resolve_under_root(root, "  ") == root.resolve()


def test_safe_resolve_rejects_dotdot(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    (root / "inside").mkdir()
    assert safe_resolve_under_root(root, "..") is None
    assert safe_resolve_under_root(root, "inside/../..") is None
    assert safe_resolve_under_root(root, "inside/..") == root.resolve()


def test_safe_resolve_rejects_absolute(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    assert safe_resolve_under_root(root, "/etc/passwd") is None


def test_safe_resolve_rejects_escape_after_resolve(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    trap = tmp_path / "outside"
    trap.mkdir()
    link = root / "evil"
    try:
        link.symlink_to(trap, target_is_directory=True)
    except OSError:
        pytest.skip("symlinks not supported")
    assert safe_resolve_under_root(root, "evil") is None


def test_list_dir_children_none_when_not_dir(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    f = root / "x.pdf"
    f.write_bytes(b"%PDF-1.4")
    assert list_dir_children(root, "x.pdf", leaf_rels=frozenset()) is None


def test_leaf_prefix_hides_orphan_dirs_without_leaf_descendant(tmp_path: Path) -> None:
    """Dirs like stray top-level ``db`` with no leaf folder underneath are omitted."""
    root = tmp_path / "r"
    root.mkdir()
    (root / "db").mkdir()
    ok = root / "ok"
    ok.mkdir()
    (ok / "z.pdf").write_bytes(b"%PDF-1.4")
    leaf = frozenset({"ok"})
    dirs, pdfs = list_dir_children(root, "", leaf_rels=leaf)
    assert dirs == ["ok"]
    assert pdfs == []
    assert "db" not in dirs


def test_leaf_prefix_nested_paths(tmp_path: Path) -> None:
    root = tmp_path / "r"
    (root / "a" / "b").mkdir(parents=True)
    (root / "a" / "b" / "doc.pdf").write_bytes(b"%PDF-1.4")
    leaf = frozenset({"a/b"})
    d0, p0 = list_dir_children(root, "", leaf_rels=leaf)
    assert d0 == ["a"]
    assert p0 == []
    d1, p1 = list_dir_children(root, "a", leaf_rels=leaf)
    assert d1 == ["b"]
    assert p1 == []
    d2, p2 = list_dir_children(root, "a/b", leaf_rels=leaf)
    assert d2 == []
    assert p2 == ["doc.pdf"]


def test_leaf_prefix_not_completed_subtree(tmp_path: Path) -> None:
    root = tmp_path / "g"
    u1 = root / "Math" / "Not completed" / "Unit 1"
    u1.mkdir(parents=True)
    (u1 / "c.pdf").write_bytes(b"%PDF-1.4")
    leaf = frozenset({"Math/Not completed/Unit 1"})
    dirs, _ = list_dir_children(root, "Math", leaf_rels=leaf)
    assert "Not completed" in dirs
    d2, _ = list_dir_children(root, "Math/Not completed", leaf_rels=leaf)
    assert "Unit 1" in d2
    _, pdf_u1 = list_dir_children(root, "Math/Not completed/Unit 1", leaf_rels=leaf)
    assert pdf_u1 == ["c.pdf"]


def test_leaf_prefix_x_prefix_not_in_leaf_set(tmp_path: Path) -> None:
    """x-prefix dirs are omitted when no leaf paths traverse them."""
    root = tmp_path / "g"
    (root / "keep").mkdir(parents=True)
    (root / "keep" / "a.pdf").write_bytes(b"%PDF-1.4")
    (root / "xWork").mkdir()
    (root / "xWork" / "b.pdf").write_bytes(b"%PDF-1.4")
    leaf = frozenset({"keep"})
    dirs, pdfs = list_dir_children(root, "", leaf_rels=leaf)
    assert dirs == ["keep"]
    assert pdfs == []
    dirs_d, pdfs_d = list_dir_children(root, "keep", leaf_rels=leaf)
    assert dirs_d == []
    assert pdfs_d == ["a.pdf"]


def test_leaf_prefix_pdf_at_sync_root_requires_empty_rel_in_leaf_set(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    (root / "d").mkdir()
    (root / "a.PDF").write_bytes(b"%PDF")
    (root / "readme.txt").write_text("x", encoding="utf-8")
    leaf = frozenset({""})
    dirs, pdfs = list_dir_children(root, "", leaf_rels=leaf)
    assert dirs == []
    assert pdfs == ["a.PDF"]


def test_list_dir_children_rejects_path_off_leaf_prefix_tree(tmp_path: Path) -> None:
    root = tmp_path / "r"
    (root / "only" / "leaf" / "here").mkdir(parents=True)
    (root / "only" / "leaf" / "here" / "p.pdf").write_bytes(b"%PDF")
    leaf = frozenset({"only/leaf/here"})
    assert list_dir_children(root, "nope", leaf_rels=leaf) is None


def test_pdf_parent_must_be_listed_leaf_folder(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    good = root / "leaf"
    good.mkdir()
    (good / "f.pdf").write_bytes(b"%PDF-1.4")
    bad = root / "other"
    bad.mkdir()
    (bad / "oops.pdf").write_bytes(b"%PDF-1.4")
    leaf = frozenset({"leaf"})
    assert not _pdf_blocked_not_under_leaf_folder(root, leaf, "leaf/f.pdf")
    assert _pdf_blocked_not_under_leaf_folder(root, leaf, "other/oops.pdf")


def test_content_disposition_ascii_filename_roundtrips() -> None:
    got = _content_disposition_inline("worksheet.pdf")
    assert got == 'inline; filename="worksheet.pdf"; filename*=UTF-8\'\'worksheet.pdf'


def test_content_disposition_chinese_filename_is_utf8_encoded() -> None:
    got = _content_disposition_inline("华文 测验1.pdf")
    assert 'filename="?? ??1.pdf"' in got
    assert "filename*=UTF-8''%E5%8D%8E%E6%96%87%20%E6%B5%8B%E9%AA%8C1.pdf" in got
