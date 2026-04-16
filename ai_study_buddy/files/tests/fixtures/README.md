# `ai_study_buddy.files` test fixtures

Small on-disk directory trees copied into `tmp_path` by `conftest.py` fixtures. They stay tiny and text-only so Git can track them; leaf detection only checks filename suffixes.

| Tree | Purpose |
|------|---------|
| `minimal_sorted_tree/` | Generic `list_leaf_folders_under_root`: suffix filter + sorted order |
| `goodnotes_profile_tree/` | `list_goodnotes_leaf_folders_under_root` exclusions |
| `daydreamedu_profile_tree/` | `list_daydreamedu_leaf_folders_under_root` exclusions |
