# Human Review for Feng Word Readings on Polyphonic Characters

This folder now hosts the **human review workflow** for assigning a specific pinyin reading to Feng word examples used by the Chinese character app.

The main target is still issue `#32`: pinyin recall should eventually treat **`character + reading`** as the learning unit for polyphonic characters, instead of collapsing all readings into one character-level unit.

## Why This Exists

Many characters in the app are polyphonic. Today, the pinyin-recall game stores learning state by **character** and often assumes a single default reading. That breaks down when the Feng word shown to the learner points to a different pronunciation.

Examples:

- `行走` -> `行 = xíng`
- `银行` -> `行 = háng`
- `乐队` -> `乐 = yuè`
- `快乐` -> `乐 = lè`

If all of those are treated as generic stems for one character-level item, the app can ask for one reading while showing a word that cues another.

## Current Direction

For HWXNet `常用词组`, we already have a deterministic extractor in:

- `chinese_chr_app/extract_character_from_wxnet/`

That leaves Feng `Words` as the remaining source that still needs reading tags.

We previously explored an AI-assisted path for those Feng words. Since the remaining scope was only **163 polyphonic Feng characters**, we used a **human review tool** instead, and that review is now complete.

That means this folder should now be read as:

- review-data generation
- human review UI for Feng word readings
- exported decision artifacts
- merge/apply scripts for curated results
- completed review outputs for the 163 polyphonic Feng characters

Not:

- a live AI tagging pipeline
- a runtime app dependency

## Scope

Status:

- the review of all 163 polyphonic Feng characters is complete
- the generated review data, review page, and applied decision artifact in this folder are the completed outputs of that pass
- the reviewed results can be found in `review/feng_word_reading_decisions.applied.json`
- the source review data and local review page used for that pass are `review/feng_word_review_data.json` and `review/feng_word_reading_review.html`

In scope:

- generating review data for the 163 polyphonic Feng characters
- showing ordered Feng words together with the allowed Feng readings
- letting a reviewer choose the reading for contiguous Feng word groups
- letting a reviewer fine-tune individual Feng words when needed
- exporting the review decisions as JSON
- turning those decisions into a clean downstream artifact

Out of scope:

- tagging HWXNet `常用词组` in this folder
- changing the live pinyin-recall game directly
- changing search/dictionary behavior

## Review Workflow

This was the workflow used to complete the review:

1. Generate the review source data for the 163 polyphonic Feng characters.
2. Build a local review page from those generated files.
3. Review each character’s Feng words in original Feng order.
4. Assign one reading to a contiguous run of Feng words whenever the local Feng cluster clearly shares the same reading.
5. Fine-tune individual words only when needed.
6. Export the review decisions as JSON.
7. Apply those decisions into a clean curated artifact for downstream use.

## Design Principles

- The allowed reading list should come from `feng_characters.pinyin`, not the broader HWXNet reading set.
- Feng word order matters and should be visible during review.
- The reviewer should see one character’s word cluster at a time.
- The reviewer should be able to assign one reading to a contiguous block of words quickly.
- The tool should make it easy to leave `unknown` when needed.
- Decisions should be saved locally in the browser while reviewing.
- Exported decisions should be durable and easy to re-apply.

## Planned / Current Contents

- generated review data for the 163 polyphonic Feng characters
- a local human review page for choosing Feng word readings
- exported review decisions and applied downstream artifact for the completed 163-character review pass
- scripts to build that review page from generated data
- scripts to apply exported review decisions into a curated artifact

## Reviewed Results

The completed reviewed results for the 163 polyphonic Feng characters are in:

- `review/feng_word_reading_decisions.applied.json`

Related files in the same folder:

- `review/feng_word_review_data.json`: generated source data used to drive the review
- `review/feng_word_reading_review.html`: local review UI built from that source data

## Reviewed Results Structure

`review/feng_word_reading_decisions.applied.json` is the downstream artifact that readers and agents should use when they need the reviewed Feng word reading assignments.

Top-level structure:

- `character_count`: number of reviewed polyphonic Feng characters
- `total_words`: total number of Feng word rows in the artifact
- `decided_words`: number of Feng word rows with an assigned reading
- `undecided_words`: number of Feng word rows left undecided
- `characters`: array of per-character reviewed results

Each item in `characters` has:

- `character`: the Hanzi being reviewed
- `allowed_readings`: the canonical Feng reading set for that character
- `extra_readings`: extra readings preserved in the artifact when present
- `results`: ordered Feng word results for that character

Each item in `results` has:

- `text`: the Feng word text
- `reading`: the reviewed reading assigned to that word
- `notes`: reviewer notes, if any
- `source`: source label for the row

How to use it:

- treat `characters[].results[]` as the authoritative reviewed mapping from a Feng word to its reading for that character
- preserve the listed order of `results` when order matters, because the review was performed in original Feng order
- use `allowed_readings` to understand the intended reading inventory for that character
- use the top-level count fields for validation or sanity checks when regenerating downstream artifacts

## Validation

Use the validator script to sanity-check the applied reviewed results:

```bash
python3 chinese_chr_app/tag_character_pinyin_using_review/scripts/validate_feng_word_review_results.py
```

What it checks:

- top-level artifact counts against the actual per-character and per-word data
- duplicate or malformed character/result entries
- allowed readings that have no tagged Feng words
- characters that carry `extra_readings` beyond the main `allowed_readings` list
- result readings that are not declared in either `allowed_readings` or `extra_readings`

Use `--strict` if warnings should also cause a non-zero exit:

```bash
python3 chinese_chr_app/tag_character_pinyin_using_review/scripts/validate_feng_word_review_results.py --strict
```

## Relationship to the Main Proposal

This folder supports the proposal in:

- [PROPOSAL_Pinyin_Recall_Reading_Units_For_Polyphonic_Characters.md](/Users/jarodm/github/jarodmeng/daydreamedu-scripts/chinese_chr_app/chinese_chr_app/docs/archive/proposals/PROPOSAL_Pinyin_Recall_Reading_Units_For_Polyphonic_Characters.md)

That proposal describes the product and data-model reason for reading-level units. This folder is now focused on the practical **human review** machinery needed to make that proposal implementable for Feng words.

## Relationship to WordsByPinyin Migration

The completed reviewed artifact in this folder is now also the source of truth for the Feng `WordsByPinyin` transition field added to the main character bank.

Migration flow:

1. Review/export/apply Feng word readings in this folder.
2. Use `review/feng_word_reading_decisions.applied.json` as the authoritative reviewed mapping.
3. Build structured Feng buckets with:

```bash
python3 chinese_chr_app/tag_character_pinyin_using_review/scripts/build_feng_words_by_pinyin_transition.py
```

The script updates `data/characters.json` by:

- wrapping monophonic rows into one bucket
- grouping polyphonic Feng words by reviewed reading
- keeping legacy flat `Words` in place for backward compatibility during the transition

So while this folder is still not a runtime dependency, it now feeds a committed, reproducible migration step for the structured Feng word data model.
