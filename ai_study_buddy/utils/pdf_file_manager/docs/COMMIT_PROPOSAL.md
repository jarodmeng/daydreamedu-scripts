# Proposal: Git commits for current changes

Suggested way to commit the current (uncommitted) changes in logical chunks. Assumes you are in the repo root.

---

## Commit 1 — Docs and scripts layout

**Purpose:** Add learnings + proposals and ignore archived one-off scripts.

**Stage and commit:**
```bash
git add ai_study_buddy/utils/pdf_file_manager/docs/
git add .gitignore
git commit -m "pdf_file_manager: add docs (learnings, proposals), ignore scripts/archive

- docs/learnings/LEARNING_FROM_FIRST_RUN.md: patterns and native-feature ideas
- docs/proposals/01–04: ensure helpers, scan CLI, coverage, link-template
- .gitignore: scripts/archive/ (one-off scripts moved out of tree)"
```

---

## Commit 2 — Implementation (v0.1.1 code and tests)

**Purpose:** All new API/CLI and tests for inference + proposals 1–4.

**Stage and commit:**
```bash
git add ai_study_buddy/utils/pdf_file_manager/pdf_file_manager.py
git add ai_study_buddy/utils/pdf_file_manager/tests/test_config.py
git add ai_study_buddy/utils/pdf_file_manager/tests/test_cli.py
git add ai_study_buddy/utils/pdf_file_manager/tests/test_coverage.py
git add ai_study_buddy/utils/pdf_file_manager/tests/test_relations.py
git commit -m "pdf_file_manager: implement inference + proposals 1–4 (API and CLI)

- Inference: is_template and chinese_variant in _infer_from_path (existing)
- P1: ensure_student, ensure_scan_root
- P2: scan CLI (--root, --dry-run, --min-savings-pct, --progress)
- P3: find_leaf_dirs, report_coverage, coverage CLI
- P4: link_template_by_paths, link-template CLI
- Tests: test_config, test_cli, test_coverage, test_relations"
```

---

## Commit 3 — Release v0.1.1

**Purpose:** Declare version and changelog.

**Stage and commit:**
```bash
git add ai_study_buddy/utils/pdf_file_manager/CHANGELOG.md
git add ai_study_buddy/utils/pdf_file_manager/README.md
git commit -m "pdf_file_manager: release v0.1.1

- CHANGELOG: v0.1.1 (inference + proposals 1–4), drop empty Unreleased
- README: version 0.1.1"
```

---

## Summary

| # | Focus              | Files                                                                 |
|---|--------------------|-----------------------------------------------------------------------|
| 1 | Docs + scripts     | `docs/**`, `.gitignore`                                               |
| 2 | Implementation     | `pdf_file_manager.py`, `tests/test_config.py`, `tests/test_cli.py`, `tests/test_coverage.py`, `tests/test_relations.py` |
| 3 | Release            | `CHANGELOG.md`, `README.md`                                           |

After commit 3 you can delete this file if you no longer need it: `docs/COMMIT_PROPOSAL.md`.
