# Add AI Study Buddy TODO bullet

Append or insert a **new open item** into [`ai_study_buddy/TODO.md`](../../ai_study_buddy/TODO.md) exactly per **Rules of engagement** at the top of that file.

## What the user provides

1. **Priority:** one of **`P0`**, **`P1`**, or **`P2`** (same meanings as in the Rules of engagement).
2. **Short description:** a rough phrase or jot — can be sloppy; you **wordsmith** it into crisp backlog prose consistent with neighbouring bullets (`…`/`…`/`…`/`…`/`…`‑style specificity, **`backticks`** for paths/commands/modules where helpful, sparing **bold** for emphasis).

## What you supply

- **Truthful Singapore timestamp:** `YYYY-MM-DD HH:MM SGT` **for row creation/editing**.
  - Prefer a **deterministic anchor** via shell (repository root):

    ```bash
    TZ=Asia/Singapore date '+%Y-%m-%d %H:%M SGT'
    ```

    Use today’s calendar date unless the row is knowingly backdated/edited historically (only when the user says so).

- **No fictional “later today”** relative to wall-clock Singapore time when logging **new** bullets.

## Where to edit

- **Open work only:** target the matching heading:

  - `## P0 — require immediate attention`
  - `## P1 — require attention within 7 days`
  - `## P2 — require attention when there's free time`

- **Do not** add new open bullets under **`## Completed`**.

### Empty section placeholder

If the chosen tier shows only **`_No open items._`** (currently **P0**), **remove that italic line** and replace it with the new `- [ ]` bullet (still leave extra blank lines if the surrounding document already uses them for readability).

## Row format & ordering

- Use this shape (replace `Pn-m` **after** renumber — see below):

  ```markdown
  - [ ] **Pn-m** · <timestamp>: <polished prose>
  ```

- **Sort** all **open** bullets in **that tier’s section** strictly by **timestamp ascending** (**oldest at the top**). Place the **new row in sort order**.

- Preserve **nested** sub-bullets (indented `-` lines): they belong to their parent checklist item — **never** split those blocks or reorder nested lines away from their parent top-level `- [ ]` bullet.

- **Renumber** every open bullet’s **`Pn-m`** in **that tier** so **`m`** is contiguous **after sort** (**`1`** … **`N`** matches final list order).

- **Leave** headings, **Rules of engagement**, and **Completed › P\*** untouched except as required by placeholders above.

## After editing

1. **`read_lints`/eyeball:** the edited file should stay valid Markdown and keep section boundaries (`## Completed` stays at the bottom of open tiers).
2. Tell the user the **assigned id** (**`Pn-m`**), the **stamp** you used, and the **tier** heading so they can cite it externally.
