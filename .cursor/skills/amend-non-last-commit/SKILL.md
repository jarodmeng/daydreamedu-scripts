---
name: amend-non-last-commit
description: Amends the commit message of a commit that is not HEAD in a non-interactive way (no editor). Use when the user wants to reword an older commit, link a commit to a GitHub issue (e.g. add "Fixes #6"), or change a past commit message without opening an interactive rebase.
---

# Amend commit message of non-last commit (non-interactive)

Use this when you need to change the **message** of a commit that is not the most recent (e.g. to add "Fixes #6" or reword the subject). No interactive editor; everything is driven by env vars and one `amend -m`.

## 1. Identify the target commit

- **By hash:** e.g. `b03a092` (use `git log --oneline -n` to find it).
- **By position:** e.g. "oldest of the last 3 commits" → that commit is `HEAD~2`. So the rebase range is `HEAD~3` (three commits: the one to reword plus the two on top).

Confirm with:

```bash
git log --oneline -n   # replace n with how many commits to show
```

## 2. Run a non-interactive reword rebase

Use `git rebase -i` but automate the todo so the target commit is marked **reword** and no editor is opened for the todo list.

- **N** = number of commits in the range (e.g. 3 for "last 3 commits").
- To reword the **oldest** of those N commits, change the **first** line in the todo from `pick` to `reword`.

**macOS / BSD sed** (creates `*.bak`; safe to delete after):

```bash
GIT_SEQUENCE_EDITOR="sed -i.bak '1s/^pick /reword /'" git rebase -i HEAD~N
```

**GNU sed** (Linux):

```bash
GIT_SEQUENCE_EDITOR="sed -i '1s/^pick /reword /'" git rebase -i HEAD~N
```

Replace `N` with the actual number (e.g. `HEAD~3`).

## 3. Set the new message when rebase stops

When rebase stops at the target commit for reword, set the new message with `--amend -m` so no editor opens:

```bash
git commit --amend -m "Subject line

Body paragraph 1.

Body paragraph 2.

Fixes #6"

```

Use the **full** message you want (subject + body). To only append a line (e.g. "Fixes #6") to the existing message, you must pass the full message anyway (e.g. re-use the current subject and body and add the line at the end).

## 4. Finish the rebase

```bash
git rebase --continue
```

If there are conflicts, resolve them, `git add` the resolved files, then run `git rebase --continue` again.

## 5. Verify

```bash
git log --oneline -n
git log -1 --format=full <commit>   # optional: check full message of rewritten commit
```

Note: The rewritten commit gets a **new hash**; any refs or PRs that pointed at the old hash now need to use the new one (or force-push the branch).

## Reword a different position (not the oldest in the range)

If the commit to reword is not the first line in the rebase todo (e.g. you want to reword the **second** of the last 3 commits):

- Still use `git rebase -i HEAD~N`.
- In `GIT_SEQUENCE_EDITOR`, change the **second** line from `pick` to `reword` instead of the first, e.g. for macOS:
  `sed -i.bak '2s/^pick /reword /'`
- Then run `git commit --amend -m "..."` and `git rebase --continue` when it stops at that commit.

## Summary one-liner (oldest of last 3, new message in one go)

```bash
GIT_SEQUENCE_EDITOR="sed -i.bak '1s/^pick /reword /'" git rebase -i HEAD~3
git commit --amend -m "Full subject

Full body.

Fixes #6"
git rebase --continue
```

No separate shell script; `GIT_SEQUENCE_EDITOR` and `git commit --amend -m` are enough. The `gh` CLI does not perform this history rewrite; it is local Git only.
