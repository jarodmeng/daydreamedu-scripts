"""Tests for path confinement under configured roots."""

from pathlib import Path

import pytest

from ai_study_buddy.root_pdf_browser.serve import (
    _content_disposition_inline,
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
    assert list_dir_children(root, "x.pdf") is None


def test_list_dir_children_lists_pdf_only(tmp_path: Path) -> None:
    root = tmp_path / "r"
    root.mkdir()
    (root / "d").mkdir()
    (root / "a.PDF").write_bytes(b"%PDF")
    (root / "readme.txt").write_text("x", encoding="utf-8")
    dirs, pdfs = list_dir_children(root, "")
    assert dirs == ["d"]
    assert pdfs == ["a.PDF"]


def test_content_disposition_ascii_filename_roundtrips() -> None:
    got = _content_disposition_inline("worksheet.pdf")
    assert got == 'inline; filename="worksheet.pdf"; filename*=UTF-8\'\'worksheet.pdf'


def test_content_disposition_chinese_filename_is_utf8_encoded() -> None:
    got = _content_disposition_inline("华文 测验1.pdf")
    assert 'filename="?? ??1.pdf"' in got
    assert "filename*=UTF-8''%E5%8D%8E%E6%96%87%20%E6%B5%8B%E9%AA%8C1.pdf" in got
