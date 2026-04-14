### Overview

This note captures a semantic modeling issue in `pdf_file_manager` that should be revisited later: the `is_template` flag is currently being used to mean two different things.

This is distinct from raw/main drift or other metadata corruption problems. Even when the data is internally consistent, the meaning of `is_template` can still be overloaded.

### The two meanings currently in use

#### 1. Empty template meaning

In the original and more straightforward sense, `is_template=True` means:

- the file is a blank exercise, exam, worksheet, or similar study material
- it is intended to be completed later
- it may be used by:
  - different students
  - the same student multiple times
  - a later reviewed workflow

Examples:

- general-scope files under folders like `.../P6/Exam/...`
- student-scoped files explicitly marked `(empty)`

This meaning is intuitive and aligns with the idea of a reusable source document.

#### 2. Reviewed-source meaning

In the current workflow, `is_template=True` is also being used to mean:

- the file is not blank
- it is a completed attempt or working copy
- it serves as the source for a `(reviewed)` variant of the same file

Examples discussed during the audit:

- `_c_P6 English Term 1 Weighted Review.pdf`
- `_c_EPO_Grammar_Cloze_01.pdf`
- `_c_EPO_Grammar_Cloze_02.pdf`
- `_c_P6 WA1 practice paper 1.pdf`
- `_c_P6 WA1 practice paper 3.pdf`
- `_c_P6 Science Weighted Review 1.pdf`
- `_c_P6 Science Weighted Review practice paper 1.pdf`

In these cases, `is_template=True` does not mean “blank reusable source.” It means something closer to “review base” or “pre-reviewed source file.”

### Why this matters

These two meanings are related, but not the same.

The first means:

- a blank source that can be completed

The second means:

- a completed source that can be reviewed

Both are “upstream” of another file, but they differ in an important way:

- one is incomplete/blank
- the other is already completed

Using the same boolean for both creates confusion in:

- validation
- reporting
- template/completion reasoning
- future feature design
- onboarding and mental model clarity

### Current known scope

From the March 2026 audit:

- the overloaded “has a `(reviewed)` variant” pattern was identified on `7` main files
- the recognized `(empty)` template pattern remained separate and accounted for `4` Winston-folder examples in the raw/main mismatch analysis

These numbers are useful examples, but the deeper issue is conceptual rather than just numeric.

### Questions to revisit later

1. Should `is_template` continue to mean “this file is upstream of another file” in a broad sense?
2. Should blank templates and reviewed-source files be modeled separately?
3. If they should be separate, should the distinction live in:
   - a new metadata field
   - a new relation type
   - a new enum-like field
   - a refinement of current workflow conventions
4. How should validation reason about student-scoped files with `is_template=True`?
5. How should UI and reporting present these two different concepts?

### Possible future directions

Some options to revisit later:

- keep `is_template` for the blank-template meaning only, and introduce a separate field for “has reviewed derivative”
- keep `is_template` as a broad upstream marker, but add another field that distinguishes `empty_template` vs `review_source`
- leave the schema unchanged, but formally document the overload and make validators relation-aware

This document does not recommend one answer yet. Its purpose is to preserve the context so the issue can be revisited deliberately later.

### Status

Open design question. Not yet addressed.
