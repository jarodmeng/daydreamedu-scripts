# compress_pdf — Specification

> Status: **Implemented** (`compress_pdf.py`)
>
> Parent doc: [L4_INGESTION_PIPELINE](../../docs/L4_INGESTION_PIPELINE.md) — Utilities section.

**Purpose:** Reduce storage size of raw scanned PDFs before ingestion. Raw scans from mobile scanning apps can be 5–25 MB per paper. The compressed version is what the ingestion pipeline actually processes.

---

## Output naming

The caller is responsible for providing an explicit output path or filename. There is no default naming convention for the compressed file — this keeps naming decisions with the caller.

Originals are **never modified**.

| How to specify output | Parameter / flag | Example |
|-----------------------|-----------------|---------|
| Full output path | `output_path` / `--output` | `--output /dest/abc.pdf` |
| Filename only (same dir as input) | `output_name` / `--output-name` | `--output-name abc_compressed.pdf` |
| Batch mode (derived per file) | `--batch-prefix` (default `_c_`) | `--batch /scans/ --batch-prefix _c_` |

**Batch mode** is the only context that uses an auto-derived output name. The prefix is prepended to each input filename (`_c_` by default, configurable via `--batch-prefix`). Files already starting with the prefix are skipped.

---

## Observed PDF characteristics

Based on analysis of 6 real exam PDFs from Winston's archive:

| Paper | Pages | Raw size | KB/page | DPI | Format | Notes |
|-------|-------|----------|---------|-----|--------|-------|
| Math P6 WA1 | 8 | 3.6 MB | 460 | 300 | RGB JPEG | High-quality scan |
| Science P6 WR | 16 | 5.6 MB | 356 | 300 / 600 | JPEG + 1-bit PNG | Mixed: cover in color, b&w pages at 600 DPI |
| English P5 EoY Paper 2 | 26 | **23.4 MB** | 919 | 300 | RGB JPEG | Very high quality scan — worst case observed |
| Chinese EoY Answers | 10 | 1.0 MB | 105 | 150 | RGB JPEG | Already compressed by scanner app |
| Chinese EoY Questions | 17 | 3.2 MB | 190 | 150–200 | JPEG + PNG | Already compressed by scanner app |
| HC EoY Questions | 10 | 1.3 MB | 128 | 150 | RGB JPEG | Already compressed by scanner app |

Key observations:
- **No consistent DPI**: 150, 200, 300, 600 DPI all seen across papers from the same archive. Scanner app settings vary.
- **Two image formats within a single PDF**: JPEG (lossy, color/grayscale scans) and 1-bit PNG (lossless bilevel, black-and-white document mode). The Science paper mixes both.
- **Quality varies enormously**: English at 919 KB/page vs. pre-compressed Chinese at 105 KB/page — 9× difference. English was clearly saved at JPEG quality ≈ 90–95.
- **Color is sparse but semantically meaningful**: On color-scanned pages, only 0–5% of pixels carry actual color (teacher red/green marks). Color must always be preserved — it encodes the teacher/student/correction layer distinction.

---

## Compression algorithm

For each page in the PDF:

1. **Extract** the primary embedded image (scanned PDFs have exactly one image per page).
2. **Detect page image type:**
   - **Bilevel (1-bit PNG):** pure black-and-white document scan — always the highest-DPI pages.
   - **Grayscale JPEG:** grayscale photo scan.
   - **RGB JPEG:** color photo scan — contains teacher annotations in color.
3. **Downsample** if current DPI exceeds `target_dpi`:
   - Use `Image.NEAREST` for 1-bit images (preserves sharp text edges).
   - Use `Image.LANCZOS` for grayscale/color (antialiased).
4. **Re-encode** per type:

| Page type | Output format | Rationale |
|-----------|--------------|-----------|
| 1-bit (bilevel) | **1-bit PNG** | JPEG handles bilevel content extremely poorly (bloats 5–8×). 1-bit PNG with deflate is optimal. Downsampling 600 → 150 DPI alone gives ~16× per-page reduction. |
| Grayscale JPEG | **Grayscale JPEG** at `jpeg_quality` | Re-encode at lower quality. |
| RGB JPEG | **RGB JPEG** at `jpeg_quality` | Always preserve RGB — never convert to grayscale, even if color pixels are sparse. Color is semantically meaningful. |

5. **Guard:** if the compressed image is larger than the original for a page, keep the original bytes unchanged for that page.
6. **Assemble** a new PDF at the original page dimensions (points).
7. **Save** with `garbage=4, deflate=True` (PyMuPDF garbage collection + PDF-level deflate).

---

## Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `target_dpi` | `150` | Pages above this DPI are downsampled. 150 DPI matches Ghostscript's `/ebook` preset and the pre-compressed Chinese papers already in the archive. Produces ~1200×1700 px per A4 page — sufficient for Gemini Vision and human review. Use `300` for higher quality at ~4× larger file. |
| `jpeg_quality` | `72` | JPEG re-encoding quality. 72 is the Ghostscript `/ebook` equivalent — readable, significant savings vs. 90+ quality raw scans. |
| `skip_if_compressed` | `True` | Skip input files whose names start with `_c_`. Override with `force=True`. |
| `output_path` | `None` | Defaults to `_c_<filename>` next to the input. Explicit path overrides this. |

**Why 150 DPI, not 300 DPI?** Ghostscript's `/ebook` preset — the industry standard for readable document PDFs — targets 150 DPI. The pre-compressed Chinese papers in Winston's archive are already at 150 DPI and work well for both Vision LLM ingestion and human review. Gemini Flash resizes images internally at inference time, so a 300 DPI input provides no accuracy benefit over 150 DPI. The DPI change alone accounts for a 4× size reduction (¼ the pixels); combined with JPEG quality reduction this yields the full compression ratio.

---

## Observed compression benchmarks

| Paper | Raw | Compressed | Saved | Ratio | Dominant saving |
|-------|-----|------------|-------|-------|-----------------|
| Science P6 WR | 5.6 MB | 1.5 MB | 72% | 3.6× | Bilevel 600→150 DPI as 1-bit PNG (~16× per page) + color pages 300→150 DPI |
| English P5 EoY P2 | 23.4 MB | 2.9 MB | 88% | 8.1× | JPEG quality 90+ → 72 + 300→150 DPI downsampling |

Papers with **high-quality color JPEG scans** (Math, English) compress 6–8×. Papers with **mixed bilevel + color** compress 3–4×. Papers already at 150 DPI are essentially incompressible further without quality loss.

---

## Interface

### Python library

```python
from compress_pdf import compress_pdf

# Specify full output path
result = compress_pdf(
    input_path="/path/to/abc.pdf",
    output_path="/dest/abc.pdf",   # explicit full path
    target_dpi=150,
    jpeg_quality=72,
    force=False,
)

# Or specify output filename only (written next to the input)
result = compress_pdf(
    input_path="/path/to/abc.pdf",
    output_name="abc_compressed.pdf",   # same directory as input
)
```

Exactly one of `output_path` or `output_name` must be provided; passing neither (or both) raises `ValueError`.

`result` is a `CompressResult` dataclass:

```python
result.input_path       # str
result.output_path      # str
result.original_size    # int (bytes)
result.compressed_size  # int (bytes)
result.savings_pct      # float, e.g. 87.6
result.ratio            # float, e.g. 8.1
result.pages            # int
result.skipped          # bool
result.skip_reason      # str (empty if not skipped)
result.page_stats       # list[PageStat]

# Each PageStat:
stat.page               # int (1-based)
stat.image_type         # 'bilevel_png' | 'rgb_jpeg' | 'gray_jpeg' | 'no_image'
stat.original_kb        # int
stat.compressed_kb      # int
stat.original_dpi       # int
stat.output_dpi         # int
stat.color_fraction     # float (fraction of pixels with meaningful color)
```

### CLI — single file

`--output` or `--output-name` is required; there is no default output filename.

```bash
# Full output path
python compress_pdf.py abc.pdf --output /other/dir/abc.pdf

# Filename only (written next to input)
python compress_pdf.py abc.pdf --output-name abc_compressed.pdf

# Common flags
python compress_pdf.py abc.pdf --output out.pdf --target-dpi 300 --jpeg-quality 75
python compress_pdf.py abc.pdf --output out.pdf --force     # overwrite if output exists
python compress_pdf.py abc.pdf --output out.pdf --verbose   # per-page stats
python compress_pdf.py abc.pdf --output out.pdf --dry-run   # print savings without writing
```

### CLI — batch

```bash
python compress_pdf.py --batch /path/to/pdfs/
# → compresses all *.pdf files not already prefixed with _c_  (default --batch-prefix)
# → prints per-file and total summary

python compress_pdf.py --batch /path/to/pdfs/ --batch-prefix _compressed_
# → outputs _compressed_abc.pdf, _compressed_def.pdf, …
```

---

## Edge cases and guard rails

| Situation | Behaviour |
|-----------|-----------|
| Neither `output_path` nor `output_name` provided (Python API) | Raise `ValueError` |
| Both `output_path` and `output_name` provided | Raise `ValueError` |
| Single-file CLI with neither `--output` nor `--output-name` | Print error and exit |
| Output file already exists | Skip unless `--force`. |
| Batch: input filename starts with `--batch-prefix` | Skip (already processed). |
| PDF has no embedded images (digital PDF) | Copy as-is with a warning. |
| Page has multiple embedded images | Process each; warn if >1 per page. |
| Page already at or below `target_dpi` | Skip downsampling; still re-encode JPEG. |
| Compressed image larger than original | Keep original bytes for that page. |
| PDF is password-protected | Raise `ValueError` with clear message. |
| Input file not found | Raise `FileNotFoundError`. |

---

## Dependencies

`pymupdf`, `Pillow`, `numpy`

---

## Implementation status

| Step | Status |
|------|--------|
| `compress_pdf()` function | ✅ Done |
| `output_name` parameter (filename-only output) | ✅ Done |
| Require explicit output in single-file mode (no default naming) | ✅ Done |
| CLI: single file + `--batch` | ✅ Done |
| `--output-name` flag | ✅ Done |
| `--batch-prefix` flag (configurable batch prefix, default `_c_`) | ✅ Done |
| `--force`, `--verbose` flags | ✅ Done |
| Guard: per-page size regression | ✅ Done |
| `--dry-run` (write to temp file, report, delete) | ✅ Done |
| Verified on Science (mixed bilevel+color), English (all-color) | ✅ Done |
