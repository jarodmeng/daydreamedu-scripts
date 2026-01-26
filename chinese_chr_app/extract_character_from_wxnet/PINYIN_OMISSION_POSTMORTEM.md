# Pinyin omission / partial-omission issue (HWXNet extractor)

## Summary

Some entries in `chinese_chr_app/data/extracted_characters_hwxnet.json` contain **incomplete pinyin lists** (missing one pronunciation for a multi‑pronunciation character) even though HWXNet shows multiple pronunciations.

This was not fully fixed by the “rerun only characters with empty pinyin” strategy, because the issue can be a **partial miss**: the extractor captured *one* pinyin reading but dropped another, leaving a non-empty `拼音` array.

## User-visible symptom

In the app’s “字典信息（来源：hwxnet）” panel, the character `写` showed only:

- `xiè`

…but HWXNet shows two pronunciations in the header line:

- `xiĕ` and `xiè`

## Concrete example (`写`)

At the time we investigated:

- The stored dataset entry had:
  - `拼音: ["xiè"]`
- HWXNet page header includes:
  - `拼音：xiĕ ... xiè ...`
- Re-running the current extractor (`extract_character_hwxnet.py`) on `写` now returns:
  - `["xiĕ", "xiè"]`

Why this matters:

- Because `拼音` was **not empty**, `写` was **not included** in the “rerun only empty-pinyin” backfill set, so it retained stale/incomplete pinyin.

## Root cause

This is a **data staleness + parser evolution** issue:

- An older iteration of `extract_character_hwxnet.py` failed to capture some third‑tone variants shown by HWXNet in the header (notably the **breve** style used in some places like `xiĕ`).
- That older logic therefore wrote incomplete `拼音` arrays into `extracted_characters_hwxnet.json`.
- A later fix improved pinyin extraction, but the batch backfill only reran characters where `拼音` was empty, not cases where `拼音` was merely incomplete.

Notes:

- HWXNet may present the third tone as **caron** (`xiě`) or **breve** (`xiĕ`) depending on the context/section. The header line for `写` uses `xiĕ`, while the “基本字义解释” section uses `xiě`.
- The app’s dictionary panel reads the stored `拼音` field directly, so if the stored file is stale/incomplete, the UI will also be incomplete.

## Why the “rerun only empty pinyin” remediation didn’t work

That remediation detects only total failures:

- **Total miss**: `拼音` is empty → gets rerun → fixed.
- **Partial miss**: `拼音` contains at least one value but is missing others → **not rerun** → stays wrong.

Multi-pronunciation characters are particularly likely to be partial-miss cases.

## Proposed full fix (do not execute yet)

The only reliable way to remove partial-miss staleness is to **re-extract all HWXNet entries** with the current parser and replace the dataset.

### Goals

- Ensure `extracted_characters_hwxnet.json` is consistent with the current extractor behavior.
- Eliminate both:
  - missing `拼音` (empty arrays), and
  - incomplete `拼音` (partial omissions).

### Approach

- Run the batch extractor over the full set of characters currently in the dataset (≈ 3664 entries).
- Write results to a **new output file** first (e.g., `extracted_characters_hwxnet.refreshed.json`) to avoid partially corrupting the canonical dataset if interrupted.
- Use **resume** support and conservative rate limiting to avoid overloading HWXNet and to handle transient network failures.

Suggested run shape (example):

- Prefer the existing batch script with overwrite + resume:
  - `python batch_extract_hwxnet.py --overwrite --resume`
- If parallelism is used, keep it conservative:
  - `--parallel --workers 2` (or similar)
- Ensure the batch script’s built-in rate limiting is enabled (or add a small inter-request delay).

### Validation / acceptance checks

Before swapping the refreshed file into `chinese_chr_app/data/extracted_characters_hwxnet.json`:

- **Structural checks**
  - JSON loads successfully
  - All entries have required keys (`character`, `source_url`, `拼音`, etc.)
- **Quality checks**
  - Run `validate_extracted_data.py` against the refreshed file
  - Count how many entries have empty `拼音` (should be near-zero; some rare edge cases may remain)
- **Diff checks**
  - Compare old vs new distributions:
    - number of entries with `len(拼音) > 1`
    - number of entries where `拼音` changed
  - Spot-check known multi-pronunciation characters (including `写`)

### Deployment plan

- After validation:
  - Replace `chinese_chr_app/data/extracted_characters_hwxnet.json` with the refreshed file.
  - Redeploy backend (if applicable) or restart the local backend so it reloads the updated JSON.

### Optional hardening (recommended)

To prevent this class of issue from recurring:

- **Add a “staleness detector” script**
  - Re-extract a small random sample and diff `拼音` vs stored values.
  - If drift exceeds a threshold, recommend a full refresh.
- **Make backfills detect partial omissions**
  - Instead of rerunning only empty `拼音`, rerun entries where:
    - `基本字义解释[].读音` includes a reading not present in `拼音`, or
    - the HWXNet header line implies multiple pronunciations (harder to infer without refetching).
  - Practical simplification: rerun any entry with `len(拼音) == 1` *and* known multi-pronunciation patterns, but this is still heuristic.

## Current status

- The extractor (`extract_character_hwxnet.py`) currently returns both pronunciations for `写`: `["xiĕ", "xiè"]`.
- The remaining risk is **other characters** still stored with partial omissions from older extraction runs.

