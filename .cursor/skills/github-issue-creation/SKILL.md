---
name: github-issue-creation
description: Creates GitHub issues using the gh CLI with --body-file for the body and a label. Use when the user asks to create a GitHub issue, file an issue, or open an issue. Prefer this over the GitHub MCP server for issue creation.
---

# GitHub Issue Creation (gh CLI)

Create GitHub issues using **gh CLI only** (do not use the GitHub MCP server for this). Always pass the issue body via `--body-file`. Every issue must have at least one label; if you cannot choose one, ask the user.

## Prerequisites

- `gh` CLI installed and authenticated (`gh auth status`).
- Repo in `owner/repo` form (e.g. from current git remote or user says which repo).

## Workflow

### 1. Repo

- If the user specified a repo, use it.
- If you're in a git repo and they didn't specify, use that repo: `gh repo view --json nameWithOwner -q .nameWithOwner` or infer from git remote.
- If still unknown, ask: "Which repo? (owner/repo)"

### 2. Body file

**Always** use `--body-file`. Never pass the body inline with `-b` or `--body` for the main content.

- If the user pointed to a file (e.g. a proposal or doc), use that path as the body file.
- Otherwise, write the body to a temporary file (e.g. `issue-body.md` or a path in the repo), then pass that path to `--body-file`.

### 3. Label

- Pick a label that fits: e.g. `enhancement`, `bug`, `documentation`, `question`, `good first issue`. Use the repo's existing labels when possible (`gh label list -R owner/repo`).
- **If you cannot confidently choose a label**, ask the user: "Which label should this issue have? (e.g. enhancement, bug, documentation)"

### 4. Create

```bash
gh issue create -R OWNER/REPO -t "Issue title" --body-file PATH_TO_BODY_FILE -l LABEL
```

- Add more labels with extra `-l` flags: `-l enhancement -l good first issue`.
- If the repo is the current directory and default remote is correct, you can omit `-R OWNER/REPO`.

## Example

User says: "Create an issue for the profile three-categories idea, use the proposal file as the body."

1. Repo: current repo (or ask).
2. Body file: path to the proposal file they mentioned.
3. Label: e.g. `enhancement`; if unclear, ask.
4. Run:

```bash
gh issue create -R jarodmeng/daydreamedu-scripts -t "Profile: show 未学字 / 在学字 / 已学字" --body-file path/to/PROPOSAL_Profile_Three_Categories.md -l enhancement
```

## Summary

| Step    | Rule |
|---------|------|
| Tool    | Use **gh CLI** only; do not use GitHub MCP for creating issues. |
| Body    | **Always** use `--body-file`; do not use `-b`/`--body` for the main body. |
| Label   | Assign at least one label; if unsure, **ask the user** to provide one. |
