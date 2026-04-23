from __future__ import annotations

from pathlib import Path
import sys
import types

import pytest

from ai_study_buddy.marking.assets.render import (
    render_answers_pdf_pages_to_bundle,
    render_attempt_pdf_to_bundle,
)


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


def test_render_attempt_pdf_to_bundle_writes_standardized_page_names(tmp_path, monkeypatch):
    _install_fake_fitz(monkeypatch, page_count=3)
    pdf_path = tmp_path / "attempt.pdf"
    pdf_path.write_bytes(b"%PDF fake\n")

    written = render_attempt_pdf_to_bundle(pdf_path, tmp_path / "bundle", dpi_scale=2.0)
    assert [path.name for path in written] == ["page-01.png", "page-02.png", "page-03.png"]
    assert written[0].read_bytes() == b"page-1"


def test_render_attempt_pdf_to_bundle_cleans_existing_standardized_images(tmp_path, monkeypatch):
    _install_fake_fitz(monkeypatch, page_count=1)
    pdf_path = tmp_path / "attempt.pdf"
    pdf_path.write_bytes(b"%PDF fake\n")

    attempt_dir = tmp_path / "bundle" / "attempt"
    attempt_dir.mkdir(parents=True, exist_ok=True)
    (attempt_dir / "page-99.png").write_bytes(b"stale")
    (attempt_dir / "note.txt").write_text("keep", encoding="utf-8")

    render_attempt_pdf_to_bundle(pdf_path, tmp_path / "bundle", dpi_scale=2.0, clean_existing=True)

    assert not (attempt_dir / "page-99.png").exists()
    assert (attempt_dir / "note.txt").exists()
    assert (attempt_dir / "page-01.png").is_file()


def test_render_answers_pdf_pages_to_bundle_uses_mapping_order_indices(tmp_path, monkeypatch):
    _install_fake_fitz(monkeypatch, page_count=8)
    pdf_path = tmp_path / "answers.pdf"
    pdf_path.write_bytes(b"%PDF fake\n")

    written = render_answers_pdf_pages_to_bundle(
        pdf_path,
        tmp_path / "bundle",
        pages_1_based=[7, 5],
        image_format="jpg",
    )
    assert [path.name for path in written] == ["page-01.jpg", "page-02.jpg"]
    assert written[0].read_bytes() == b"page-7"
    assert written[1].read_bytes() == b"page-5"


def test_render_answers_pdf_pages_to_bundle_rejects_out_of_range_page(tmp_path, monkeypatch):
    _install_fake_fitz(monkeypatch, page_count=2)
    pdf_path = tmp_path / "answers.pdf"
    pdf_path.write_bytes(b"%PDF fake\n")

    with pytest.raises(ValueError, match="out of range"):
        render_answers_pdf_pages_to_bundle(
            pdf_path,
            tmp_path / "bundle",
            pages_1_based=[3],
        )
