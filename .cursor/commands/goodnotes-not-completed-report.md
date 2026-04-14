# GoodNotes Not completed report

When this command runs, produce a grouped report of **non-empty `Not completed` folders** under the GoodNotes root from environment variable:

`GOODNOTES_ROOT`

## Goal

Return results grouped by:

1. child (student email)
2. category in the format `<subject>-<grade>-<type>`
3. file names inside that `Not completed` subtree

## Scan rules

- Read root path from `GOODNOTES_ROOT`.
- If `GOODNOTES_ROOT` is missing, empty, or not a directory, stop and report a clear error.
- `GOODNOTES_ROOT` is expected to be defined in shell config (for example `~/.zshrc`).
- If needed, tell the user to check with `echo $GOODNOTES_ROOT` and reload via `source ~/.zshrc`.
- A folder qualifies only when:
  - its directory name is exactly `Not completed` (case-insensitive match is acceptable), and
  - it contains at least one non-hidden file in its subtree.
- Exclude hidden files and macOS metadata files (for example names starting with `.` such as `.DS_Store`).
- Do not query any database; this is a filesystem scan only.

## Path parsing rules

For a qualifying `Not completed` directory, derive fields from its path relative to GoodNotes root:

- `subject = parts[0]`
- `child = parts[1]`
- `grade = parts[2]`
- `type = parts[3]`
- `category = <subject>-<grade>-<type>`

Skip entries that do not have at least these 4 path components before `Not completed`.

## What to run

Run a short Python one-shot from repo root that:

- recursively finds `Not completed` directories,
- filters to non-hidden files only,
- groups into `child -> category -> filenames`,
- sorts child, category, and filenames alphabetically.

## Output format

Respond in this structure:

- `<child>`
  - `<subject>-<grade>-<type>`
    - `<filename1>`
    - `<filename2>`

Also include one compact line before the list:

- total number of qualifying `Not completed` folders
- total number of files across those folders

Keep output concise and scannable.
