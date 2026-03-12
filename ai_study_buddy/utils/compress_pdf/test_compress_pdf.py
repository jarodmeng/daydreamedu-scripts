import sys
import tempfile
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image

_UTIL_DIR = Path(__file__).resolve().parent
if str(_UTIL_DIR) not in sys.path:
    sys.path.insert(0, str(_UTIL_DIR))

from compress_pdf import compress_pdf


def _make_rotated_scan_pdf(path: Path) -> Path:
    portrait_img = path.with_name("portrait.png")
    landscape_img = path.with_name("landscape.png")
    portrait = Image.new("RGB", (1200, 1700), "white")
    portrait.paste((255, 0, 0), (0, 0, 220, 220))
    portrait.paste((0, 255, 0), (980, 0, 1200, 220))
    portrait.paste((0, 0, 255), (0, 1480, 220, 1700))
    portrait.save(portrait_img)

    landscape = Image.new("RGB", (1700, 1200), "white")
    landscape.paste((255, 255, 0), (0, 0, 260, 220))
    landscape.paste((255, 0, 255), (1440, 0, 1700, 220))
    landscape.paste((0, 255, 255), (0, 980, 260, 1200))
    landscape.save(landscape_img)

    doc = pymupdf.open()

    page1 = doc.new_page(width=595, height=842)
    page1.insert_image(page1.rect, filename=str(portrait_img))
    page1.insert_text((72, 120), "page 1", fontsize=24)

    page2 = doc.new_page(width=842, height=595)
    page2.insert_image(page2.rect, filename=str(landscape_img))
    page2.insert_text((72, 120), "page 2 rotated", fontsize=24)
    page2.set_rotation(90)

    doc.save(str(path))
    doc.close()

    portrait_img.unlink(missing_ok=True)
    landscape_img.unlink(missing_ok=True)
    return path
def _render_signature(page: pymupdf.Page) -> np.ndarray:
    pix = page.get_pixmap(matrix=pymupdf.Matrix(0.2, 0.2), alpha=False)
    img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples).convert("L")
    return np.asarray(img, dtype=np.float32)


def test_compress_pdf_preserves_rotated_page_geometry():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        input_path = _make_rotated_scan_pdf(tmpdir / "input.pdf")
        output_path = tmpdir / "output.pdf"

        compress_pdf(input_path, output_path=output_path, force=True)

        src = pymupdf.open(str(input_path))
        out = pymupdf.open(str(output_path))
        try:
            assert [(p.rect.width, p.rect.height) for p in out] == [
                (p.rect.width, p.rect.height) for p in src
            ]
            assert all(page.rotation == 0 for page in out)

            for src_page, out_page in zip(src, out):
                src_pix = src_page.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False)
                out_pix = out_page.get_pixmap(matrix=pymupdf.Matrix(1, 1), alpha=False)
                assert (out_pix.width, out_pix.height) == (src_pix.width, src_pix.height)

                diff = np.abs(_render_signature(src_page) - _render_signature(out_page)).mean()
                assert diff < 25
        finally:
            src.close()
            out.close()
