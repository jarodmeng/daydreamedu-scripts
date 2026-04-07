# Low-Learning-Value Unit Cleanup

This folder now keeps the minimal long-term artifacts and scripts needed for the completed low-learning-value unit cleanup.

The original AI review workflow was a one-time operator process. Its transient candidate-generation, batch-submission, and manual-review scripts are not kept here anymore. What remains is:

- the confirmed-removals artifact
- the source-data apply summary
- the learning-history cleanup summary
- the two reusable apply scripts used for the rollout

It does **not** disable units automatically. The retained scripts apply permanent source-data/history cleanup against already confirmed units.

## Folder layout

```text
review_low_learning_value_units_using_ai/
├── README.md
├── prompts/
│   └── low_learning_value_polyphonic_units_review_prompt.md
├── scripts/
│   ├── apply_confirmed_low_learning_value_unit_removals.py
│   ├── remove_confirmed_units_from_learning_history.py
│   └── common.py
└── batch_artifacts/
    └── ...
```

## Retained provenance artifacts

- `batch_artifacts/low_learning_value_units.confirmed_true_positives.json`
  Operator-confirmed units to remove permanently.
- `batch_artifacts/low_learning_value_units.applied_removals.json`
  Summary of the HWXNet source-data removal step.
- `batch_artifacts/low_learning_value_units.learning_history_cleanup.json`
  Summary of the user-history cleanup step.

Pilot runs, raw batch transport files, candidate snapshots, AI-selected intermediates, and review-process artifacts are intentionally not kept once the final confirmed-removals artifact and apply summaries exist.

## Apply workflow

### 7. Remove confirmed units from HWXNet source data

Dry-run first:

```bash
python3 chinese_chr_app/review_low_learning_value_units_using_ai/scripts/apply_confirmed_low_learning_value_unit_removals.py --dry-run
```

Write a preview JSON without touching the source file:

```bash
python3 chinese_chr_app/review_low_learning_value_units_using_ai/scripts/apply_confirmed_low_learning_value_unit_removals.py \
  --output /tmp/extracted_characters_hwxnet.cleaned.json
```

Apply in place with an automatic local backup:

```bash
python3 chinese_chr_app/review_low_learning_value_units_using_ai/scripts/apply_confirmed_low_learning_value_unit_removals.py --in-place
```

Apply in place and sync the changed rows back to Supabase:

```bash
python3 chinese_chr_app/review_low_learning_value_units_using_ai/scripts/apply_confirmed_low_learning_value_unit_removals.py \
  --in-place \
  --sync-hwxnet-table
```

When `--in-place` is used, the script first creates a timestamped backup under `chinese_chr_app/data/backups/`. When `--sync-hwxnet-table` is used, it first creates a timestamped `hwxnet_characters_backup_<timestamp>` table in Supabase before upserting the changed rows.

### 8. Remove confirmed units from users' learning history

Dry-run first:

```bash
python3 chinese_chr_app/review_low_learning_value_units_using_ai/scripts/remove_confirmed_units_from_learning_history.py
```

Apply with mandatory Supabase table backups:

```bash
python3 chinese_chr_app/review_low_learning_value_units_using_ai/scripts/remove_confirmed_units_from_learning_history.py --apply
```

Before deleting anything, the script creates timestamped backup tables for every mutated Supabase table:

- `pinyin_recall_unit_bank`
- `pinyin_recall_item_presented`
- `pinyin_recall_item_answered`
- `user_prioritized_characters`

This cleanup removes explicit matching `unit_id` rows from the learning-state/event tables and removes matching reading-specific rows from `user_prioritized_characters`. It intentionally leaves `pinyin_recall_report_error` and `pinyin_recall_disabled_units` intact as audit history.

## Historical note

The removed one-time workflow used AI review prompts seeded with 7 real gameplay-reported examples (`搂|lou1`, `殉|xun4`, `瘪|bie3`, `杉|sha1`, `雀|qiao3`, `眯|mi2`, `王|wang4`) before operator confirmation. The resulting confirmed-removals artifact is the retained source of truth for this cleanup.
