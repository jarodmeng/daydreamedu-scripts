# DaydreamEdu fixture (scaled-down)

A small copy of the real DaydreamEdu folder structure and two real PDFs, used by Phase 2+ tests for `register_file`, `compress_and_register`, and `scan_for_new_files` (with the real `compress_pdf` utility).

**Note:** The PDF files in this tree are listed in the repo `.gitignore` and are not committed. To populate the fixture locally, copy the two PDFs from the real drive into `Singapore Primary Science/winston.ry.meng@gmail.com/P5/Exam/` (see TESTING.md or the paths below).

## Layout

```
daydreamedu_fixture/
└── Singapore Primary Science/
    └── winston.ry.meng@gmail.com/
        └── P5/
            └── Exam/
                ├── p5.science.012.Primary 5 Science 2025 EOY.pdf
                └── p5.science.013.Primary 5 Science 2025 Booklet B.pdf
```

Mirrors: **L1** = subject (`Singapore Primary Science`), **L2** = student email, **L3** = grade (`P5`), **L4** = content type (`Exam`). The two PDFs are real files copied from the production drive so compression and registration behave like production.

## Usage in tests

- Use a **temporary DB** (never the real registry).
- Add the **absolute path** to `daydreamedu_fixture` (or to `daydreamedu_fixture/Singapore Primary Science/...`) as a scan root, or call `register_file` / `compress_and_register` with paths inside this tree.
- Tests that run `scan_for_new_files` or `compress_and_register` use these PDFs so the real `compress_pdf` runs on real content.

## Resolving the fixture path in code

```python
from pathlib import Path
FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "daydreamedu_fixture"
# or from a test file under tests/:
FIXTURE_ROOT = Path(__file__).resolve().parent.parent / "fixtures" / "daydreamedu_fixture"
```
