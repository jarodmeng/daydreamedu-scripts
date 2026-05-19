# Student File Browser

**Version: v0.1.1**

Filter-first **operator** inventory for on-disk **main** PDFs under DaydreamEdu and GoodNotes. Uses [`ai_study_buddy.files`](../files/) **v0.3.0+** (v0.3.1 recommended) for path facets, registry correlation, and marking/review health flags (`marking` v0.3.8+ shared workflow loader). GoodNotes leaf folders match [goodnotes-leaf-registry-report](../../.cursor/commands/goodnotes-leaf-registry-report.md) (registration-ready set; WIP `Not completed` subtrees are out of scope). Completion **activity** and **note** files are excluded from the index (same as [`completion_template_link_gap_report`](../pdf_file_manager/scripts/completion_template_link_gap_report.py)); templates are still listed.

Default URL: `http://127.0.0.1:8771/`

## Quick start

```bash
cd /path/to/daydreamedu-scripts
python3 -m ai_study_buddy.student_file_browser.serve
```

Background:

```bash
python3 -m ai_study_buddy.student_file_browser.spawn_background
```

## Requirements

- Configured `DAYDREAMEDU_ROOT` and/or `GOODNOTES_ROOT` (see [`ai_study_buddy/files`](../files/README.md))
- `pdf_registry.db` for registration enrichment (optional `PDF_REGISTRY_PATH`)
- `ai_study_buddy/context` for marking/review flags (`AI_STUDY_BUDDY_CONTEXT_ROOT` to override)

## Sibling tools

| Port | Tool |
|------|------|
| 8770 | [`root_pdf_browser`](../root_pdf_browser/README.md) v0.1.6+ — tree browse; **View PDF** deep links (`?id=` + `rel=`) |
| 8771 | **Student File Browser** (this app) |
| 5178 | [`review_workspace`](../review_workspace/README.md) v0.1.4+ — marking review; **Review Workspace** deep links (`?attempt_id=` + `student_id=`) |

## Docs

- [ARCHITECTURE.md](./ARCHITECTURE.md)
- [SPEC.md](./SPEC.md)
- [CHANGELOG.md](./CHANGELOG.md)
- [TESTING.md](./TESTING.md)
- [docs/proposal/](./docs/proposal/) — design proposals (e.g. [1-root-id-filter.md](./docs/proposal/1-root-id-filter.md) for [TODO P0-1](../TODO.md); [review_workspace attempt deep links](../review_workspace/docs/proposal/2-attempt-deep-links.md) shipped in v0.1.1)

## Rollback

Stop the server and remove this package directory. No registry or database changes. `files` v0.3.0 may remain for other consumers.
