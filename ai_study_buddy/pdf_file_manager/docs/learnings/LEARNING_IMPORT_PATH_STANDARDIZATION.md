# Learning: Package-standardized imports for `pdf_file_manager`

## Context

`PdfFileManager` usage had diverged into two patterns:

- package imports (for example `ai_study_buddy.pdf_file_manager...`)
- bare imports (for example `from pdf_file_manager import PdfFileManager`) supported by local `sys.path` mutation

The bare-import pattern made behavior depend on invocation context (cwd, script location, test path setup), which created avoidable fragility.

## Decision

Standardize all runtime and test imports on package paths:

```python
from ai_study_buddy.pdf_file_manager.pdf_file_manager import PdfFileManager
```

Package re-export form is also supported:

```python
from ai_study_buddy.pdf_file_manager import PdfFileManager
```

## Operational guidance

- Prefer module invocation from repo root for scripts and server startup:
  - `python3 -m ai_study_buddy.pdf_file_manager.pdf_file_manager_mcp_server ...`
  - `python3 -m ai_study_buddy.pdf_file_manager.scripts.backup_pdf_registry ...`
- Avoid `sys.path.insert(...)` for import resolution in normal usage.

## Troubleshooting

- `ModuleNotFoundError: No module named 'ai_study_buddy'`
  - Cause: command not run from repo root (or equivalent Python path context).
  - Fix: run from repo root with `python3 -m ...`.
- Old helper snippets that import `from pdf_file_manager import ...` fail
  - Fix: switch to package import style above.

## Outcome

Import behavior is now deterministic across scripts, tests, MCP tooling, and docs, reducing environment-dependent failures.
