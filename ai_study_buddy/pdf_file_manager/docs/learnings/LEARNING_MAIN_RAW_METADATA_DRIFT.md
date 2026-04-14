### Overview

This learning documents a broader metadata integrity issue discovered during validation of the local `pdf_file_manager` registry in March 2026: linked raw/main file pairs can drift on metadata that should be invariant across both records.

**Main finding:** the utility currently allows document-level metadata to drift between linked raw/main records for the same logical document. The observed pattern was most clearly visible on `is_template`, where main files appeared to be updated while their raw counterparts were left stale.

The important context is that these pairs are not unrelated records. They represent the same logical document in two forms:

- raw archive: `_raw_*.pdf`
- compressed working/main file: `_c_*.pdf`

Because of that, document-level metadata should usually be treated as shared meaning across the pair, not file-representation meaning.

This learning is specifically about **raw/main inconsistency**. It should not be conflated with separate semantic questions, such as whether a file inside a student-scoped folder may legitimately have `is_template=True`.

### What was observed

Registry-wide validation of linked raw/main pairs looked for metadata that should describe the logical document rather than the specific file representation.

Examples of fields that should normally be invariant across a raw/main pair:

- `subject`
- `doc_type`
- `student_id`
- `is_template`
- `metadata.grade_or_scope`
- `metadata.content_folder`
- other document-level metadata like `metadata.chinese_variant` when present

The audit that triggered this learning found the clearest concrete problem on `is_template`:

- `801` raw/main pairs total
- `778` pairs with matching `is_template`
- `23` pairs with mismatched `is_template`

In every mismatched case:

- raw file had `is_template=False`
- main file had `is_template=True`

Representative examples:

- `.../Singapore Primary Math/P6/Exam/_raw_p6.math.wa2.1.pdf`
- `.../Singapore Primary Math/P6/Exam/_c_p6.math.wa2.1.pdf`

- `.../Singapore Primary English/<student email>/P6/Exam/_raw_P6 English Term 1 Weighted Review.pdf`
- `.../Singapore Primary English/<student email>/P6/Exam/_c_P6 English Term 1 Weighted Review.pdf`

- `.../Singapore Primary Science/<student email>/P6/Exam/_raw_P6 Science Weighted Review practice paper 1.pdf`
- `.../Singapore Primary Science/<student email>/P6/Exam/_c_P6 Science Weighted Review practice paper 1.pdf`

The `23` `is_template` mismatches split into two path buckets:

- `12` general-scope pairs under `.../Singapore Primary Math/P6/Exam/...`
- `11` pairs under Winston's student-scoped folders

The `11` Winston-folder examples are themselves two different semantic subcases:

- `4` are `(empty)` variants, which fit the recognized meaning of `is_template=True`
- `7` are non-`(empty)` files where `is_template=True` is being used to indicate that the file has a `(reviewed)` variant

That distinction matters because the Winston-folder main files are not necessarily wrong. The corruption signal in this learning is that their linked raw files disagree with them.

### Interpretation

This drift looks like stale or corrupted registry state rather than intentional modeling.

Reasoning:

- compression changes representation, not document meaning
- the linked raw and main files refer to the same logical source document
- the utility’s document metadata is mostly document-level in practice
- there is no strong domain reason for raw and compressed variants of the same file to disagree on invariant fields

The one theoretical alternative is to model some fields as file-record-level rather than document-level. But for fields like `subject`, `doc_type`, `student_id`, `grade_or_scope`, `content_folder`, and typically `is_template`, the current utility and surrounding workflows treat them as properties of the underlying document.

So the working assumption should be:

- raw/main linked pairs should normally have the same document-level metadata

And more specifically:

- `is_template` drift is the concrete symptom already observed
- other invariant fields could theoretically drift in the same way if update paths are not parity-aware

### Separate this from student-folder semantics

There are two subtly different `is_template` problems:

1. **Raw/main parity problem**

- the same logical document has different invariant metadata values on its linked raw and main records
- this is usually a registry inconsistency
- this learning note is about that problem

2. **Student-folder semantics problem**

- a file under a student-scoped folder has `is_template=True`
- that is not automatically wrong
- in the current workflow, some student-scoped main files intentionally use `is_template=True` to indicate they are the source for a `(reviewed)` variant
- in the current data discussed here, that overloaded reviewed-variant pattern appears on `7` files
- separately, `(empty)` variants remain a normal template case and account for `4` of the Winston-folder examples in this mismatch set

So the presence of `is_template=True` inside a student folder is a separate modeling/validation question. It should not be treated as evidence that the raw/main drift cases are intentional.

Concretely:

- student-folder `is_template=True` may be valid
- raw/main disagreement for the same logical document is still likely invalid

### Likely cause

The main finding above points to a specific failure mode: the system permits updates to one side of a linked raw/main pair without keeping the counterpart in sync.

The observed `is_template` mismatches are consistent with older partial workflows where:

- the main file was updated to `is_template=True`
- but the linked raw file was not updated in parallel

This is especially plausible for:

- manual `update_metadata(...)` repairs
- template-linking workflows
- legacy one-off scripts that modified main files only

The broader lesson is that any workflow that mutates document-level metadata on only one side of a raw/main pair could create the same kind of drift for other invariant fields.

### Fix proposal

#### 1. Backfill current mismatches

Repair existing raw/main pairs where invariant document metadata differs.

Recommended rule:

- treat the main file as canonical for current backfill purposes
- copy invariant document-level fields from main to raw where drift is detected

Why main should be the source of truth:

- the main file is the primary working record in the utility
- template/completion workflows already operate mainly on main files
- when drift exists today, the main file is the more likely intentional value

#### 2. Enforce parity in code

Strengthen the invariant that linked raw/main pairs share the same document-level metadata.

Implementation options:

- ensure `compress_and_register(...)` always writes identical invariant metadata values to both rows
- when scan/rescan logic repairs metadata on one side of a raw/main pair, normalize the paired file as well when appropriate
- optionally add a small validation/repair helper dedicated to raw/main parity checks

### Code surface area to update

The main surface area is small. The drift appears to happen when a public workflow updates invariant metadata on one file record without syncing its linked raw/main counterpart.

The most important code surfaces are:

- `update_metadata(...)`
  - this is the primary place where document-level metadata can be changed after registration
  - today it updates only the targeted file
  - this is the best place to enforce raw/main parity for invariant fields when they are provided

- `link_template_by_paths(...)`
  - this explicitly flips template/completed flags using `update_metadata(...)`
  - once parity is enforced in `update_metadata(...)`, this path should inherit the fix

- `link_goodnotes_template_for_file(...)`
  - this can auto-fix a resolved template to `is_template=True`
  - it should also inherit the parity fix if `update_metadata(...)` becomes parity-aware

- `compress_and_register(...)`
  - this already creates raw/main pairs with matching values copied from the source row
  - it should still be treated as an explicit invariant surface and covered by tests

Recommended supporting additions:

- a small helper to resolve linked raw/main counterparts for a file record
- a repair helper to backfill existing raw/main metadata drift in the registry
- regression tests verifying:
  - new raw/main pairs start with matching invariant metadata
  - metadata updates do not change only one side of a linked pair
  - existing drift can be repaired cleanly

### Implementation plan

1. Add a helper to resolve linked raw/main counterparts and to find raw/main pairs with mismatched `is_template`.
2. Generalize that helper so it can compare and synchronize invariant document-level fields across a pair.
3. Update `update_metadata(...)` so invariant metadata changes propagate across a linked raw/main pair.
4. Keep `compress_and_register(...)` explicitly covered as an invariant surface for matching document-level metadata.
5. Add a repair routine that updates raw to match main and records the change through normal metadata logging.
5. Add focused regression tests for:
   - parity on newly created raw/main pairs
   - parity preservation when metadata-changing workflows call `update_metadata(...)`
   - repair of existing drift
6. Start with `is_template` as the first concrete repaired field, since it is the drift already observed in production data.
7. Run the repair routine on the live registry.
8. Re-run the metadata validation audit and confirm the observed mismatch count drops from `23` to `0` for `is_template`, while keeping the broader parity machinery reusable for other fields.

### Status

Implemented for the current invariant metadata update path.

March 2026 implementation notes:

- `update_metadata(...)` now syncs invariant document metadata across linked raw/main pairs
- a repair helper was added to backfill existing raw/main metadata drift by copying main values onto raw
- the live registry backfill repaired the `23` observed `is_template` mismatch pairs
- after the backfill, the audited invariant fields showed `0` raw/main mismatches in the local registry:
  - `subject`
  - `doc_type`
  - `student_id`
  - `is_template`
  - `metadata.grade_or_scope`
  - `metadata.content_folder`
  - `metadata.chinese_variant`
