# Proposal 2: Scan CLI subcommand

**Happy path item:** [Scan CLI] — Use `scan_for_new_files` in a dry‑run‑then‑real pattern whenever you add new PDFs, ideally via a `scan` CLI with `--root`, `--dry-run`, and `--progress`.

---

## Motivation

All `_scan_*.py` and `_bootstrap_*_exam.py` scripts in `scripts/archive/` implement the same flow: ensure roots, dry run, then real scan with per‑file progress. This logic is duplicated many times. A first‑class `scan` subcommand would:

- Standardize the dry‑run‑then‑real pattern.
- Allow scanning from the command line without writing Python.
- Centralize progress reporting and options (e.g. `--min-savings-pct`).

---

## Current code / functions

- **API**
  - `scan_for_new_files(self, roots=None, min_savings_pct=10, dry_run=False, on_file_start=None) -> list[ScanResult]`
  - If `roots` is None, uses all configured scan roots from `list_scan_roots()`.
  - If `roots` is provided, uses only those paths (each resolved).
  - Skips paths already in `pdf_files`; for new PDFs: registers `_raw_`/`_c_` or calls `compress_and_register` for unknown files.
  - `on_file_start: Callable[[Path], None]` is invoked before processing each new file (e.g. for progress).
- **CLI**
  - `_cli_main()` currently only has a `log` subcommand; no `scan` subcommand.

---

## Gap

- No CLI to run a scan: users must write a small script that calls `scan_for_new_files` with dry run then real run and an `on_file_start` progress callback.
- Dry run vs real run and progress reporting are implemented ad hoc in each script.

---

## Implementation plan

1. **Add `scan` subparser in `_cli_main`**
   - `pdf_file_manager scan [--root PATH ...] [--dry-run] [--min-savings-pct N] [--progress] [--db PATH]`
   - `--root`: optional, repeatable; if present, scan only these paths (resolved). If absent, scan all configured scan roots.
   - `--dry-run`: only list what would be processed; do not register or compress.
   - `--min-savings-pct`: passed through to `scan_for_new_files` (default e.g. 10).
   - `--progress`: when set (and not dry run), print per‑file progress (e.g. `[1/N] filename.pdf ...`).

2. **CLI behavior**
   - Create `PdfFileManager(db_path=args.db)`.
   - If `--root` is used, pass `roots=[...]` to `scan_for_new_files`; otherwise pass `roots=None`.
   - If `--dry-run`: call `scan_for_new_files(..., dry_run=True)`, print each `r.file.path` as “would process: …”.
   - If not dry run and `--progress`: build an `on_file_start` that prints `[n/total] path.name ...` (total from a preliminary dry run or from counting results as we go).
   - Call `scan_for_new_files(..., dry_run=False, on_file_start=...)` and print each result (e.g. `-> name (compressed=True|False)`).

3. **Docs**
   - Update CLI help and any user-facing docs to describe `scan` and recommend dry run before real run.

---

## Test plan

- **CLI tests**
  - `scan --dry-run` with no roots (and no scan roots in DB): exits 0, prints “No scan roots” or empty list (per existing `ConfigError` when roots is None and list is empty).
  - `scan --dry-run --root /some/path`: with empty or non‑existent path: exits 0, no crash; with path containing no PDFs: “would process” list empty or “No new PDFs”.
  - `scan --dry-run --root <dir_with_pdfs>`: output includes “would process: …” for each new PDF (and not for already registered paths).
  - `scan --root <dir_with_pdfs>` (no dry run): files get registered/compressed; running again with same root yields no new work.
  - `scan --progress --root <dir_with_pdfs>`: progress lines appear in order; final summary matches count of processed files.
  - `scan --min-savings-pct 5`: ensure value is passed through (e.g. compress when savings >= 5%).
- **Regression**
  - Existing tests for `scan_for_new_files` (if any) still pass.
  - Ensure `--db` is respected and used for both `log` and `scan` when provided.
