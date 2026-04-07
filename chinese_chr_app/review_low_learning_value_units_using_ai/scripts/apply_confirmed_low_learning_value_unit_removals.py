#!/usr/bin/env python3
"""Remove confirmed low-learning-value readings from HWXNet source data."""

from __future__ import annotations

import argparse
import copy
import shutil
from collections import defaultdict
from pathlib import Path
from typing import Any

from common import (
    CONFIRMED_TRUE_POSITIVES_JSON,
    DATA_BACKUPS_DIR,
    DEFAULT_APPLIED_REMOVALS_SUMMARY,
    DEFAULT_CANDIDATE_ARTIFACT,
    HWXNET_JSON,
    ensure_import_paths,
    load_confirmed_units_with_candidates,
    read_json,
    save_json,
    utc_timestamp_slug,
)


def dedupe_preserving_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        cleaned = str(value or "").strip()
        if not cleaned or cleaned in seen:
            continue
        seen.add(cleaned)
        out.append(cleaned)
    return out


def _flatten_phrase_buckets(buckets: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(buckets, list):
        return out
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        phrases = bucket.get("Phrases") or []
        if not isinstance(phrases, list):
            continue
        for phrase in phrases:
            if not isinstance(phrase, str):
                continue
            for piece in phrase.split(","):
                cleaned = piece.strip()
                if cleaned:
                    out.append(cleaned)
    return dedupe_preserving_order(out)


def _flatten_gloss_buckets(buckets: Any) -> list[str]:
    out: list[str] = []
    if not isinstance(buckets, list):
        return out
    for bucket in buckets:
        if not isinstance(bucket, dict):
            continue
        glosses = bucket.get("Glosses") or []
        if not isinstance(glosses, list):
            continue
        for gloss in glosses:
            cleaned = str(gloss or "").strip()
            if cleaned:
                out.append(cleaned)
    return dedupe_preserving_order(out)


def prune_hwxnet_entry(
    entry: dict[str, Any],
    reading_displays_to_remove: set[str],
) -> tuple[dict[str, Any], dict[str, int]]:
    updated = copy.deepcopy(entry)
    stats = {
        "removed_pinyin_entries": 0,
        "removed_basic_meanings": 0,
        "removed_phrase_buckets": 0,
        "removed_gloss_buckets": 0,
    }

    pinyin = updated.get("拼音") or []
    if isinstance(pinyin, list):
        kept_pinyin = [value for value in pinyin if value not in reading_displays_to_remove]
        stats["removed_pinyin_entries"] = len(pinyin) - len(kept_pinyin)
        updated["拼音"] = kept_pinyin

    basic_meanings = updated.get("基本字义解释") or []
    if isinstance(basic_meanings, list):
        kept_basic = [
            item
            for item in basic_meanings
            if str(item.get("读音") or "").strip() not in reading_displays_to_remove
        ]
        stats["removed_basic_meanings"] = len(basic_meanings) - len(kept_basic)
        updated["基本字义解释"] = kept_basic

    phrase_buckets = updated.get("常用词组按拼音") or []
    if isinstance(phrase_buckets, list):
        kept_phrase_buckets = [
            item
            for item in phrase_buckets
            if str(item.get("Pinyin") or "").strip() not in reading_displays_to_remove
        ]
        stats["removed_phrase_buckets"] = len(phrase_buckets) - len(kept_phrase_buckets)
        updated["常用词组按拼音"] = kept_phrase_buckets
        updated["常用词组"] = _flatten_phrase_buckets(kept_phrase_buckets)

    gloss_buckets = updated.get("英文解释按拼音") or []
    if isinstance(gloss_buckets, list):
        kept_gloss_buckets = [
            item
            for item in gloss_buckets
            if str(item.get("Pinyin") or "").strip() not in reading_displays_to_remove
        ]
        stats["removed_gloss_buckets"] = len(gloss_buckets) - len(kept_gloss_buckets)
        updated["英文解释按拼音"] = kept_gloss_buckets
        updated["英文翻译"] = _flatten_gloss_buckets(kept_gloss_buckets)

    return updated, stats


def validate_pruned_entry(
    character: str,
    entry: dict[str, Any],
    removed_readings: set[str],
) -> None:
    pinyin = entry.get("拼音") or []
    if not isinstance(pinyin, list) or not pinyin:
        raise ValueError(f"{character}: removing readings would leave no 拼音 values")
    for removed in removed_readings:
        if removed in pinyin:
            raise ValueError(f"{character}: removed reading {removed!r} still present in 拼音")

    basic_meanings = entry.get("基本字义解释") or []
    seen_basic_readings: set[str] = set()
    if isinstance(basic_meanings, list):
        for item in basic_meanings:
            reading = str(item.get("读音") or "").strip()
            if not reading:
                continue
            if reading in removed_readings:
                raise ValueError(f"{character}: removed reading {reading!r} still present in 基本字义解释")
            seen_basic_readings.add(reading)
    if not seen_basic_readings.issubset(set(pinyin)):
        raise ValueError(f"{character}: 基本字义解释 contains readings not in 拼音")

    for field_name, bucket_key in (("常用词组按拼音", "Pinyin"), ("英文解释按拼音", "Pinyin")):
        buckets = entry.get(field_name) or []
        if not isinstance(buckets, list):
            continue
        for bucket in buckets:
            reading = str(bucket.get(bucket_key) or "").strip()
            if reading in removed_readings:
                raise ValueError(f"{character}: removed reading {reading!r} still present in {field_name}")


def build_removals_by_character(confirmed_units: list[dict[str, Any]]) -> dict[str, set[str]]:
    removals: dict[str, set[str]] = defaultdict(set)
    for row in confirmed_units:
        character = str(row.get("character") or "").strip()
        reading_display = str(row.get("reading_display") or "").strip()
        if not character or not reading_display:
            raise ValueError(f"Confirmed unit missing character/reading_display: {row}")
        removals[character].add(reading_display)
    return removals


def apply_removals_to_dataset(
    data: dict[str, Any],
    removals_by_character: dict[str, set[str]],
) -> tuple[dict[str, Any], dict[str, Any], dict[str, dict[str, Any]]]:
    updated_data = copy.deepcopy(data)
    changed_entries: dict[str, dict[str, Any]] = {}
    per_character: list[dict[str, Any]] = []
    totals = {
        "characters_changed": 0,
        "removed_pinyin_entries": 0,
        "removed_basic_meanings": 0,
        "removed_phrase_buckets": 0,
        "removed_gloss_buckets": 0,
    }

    for character, removed_readings in sorted(removals_by_character.items()):
        entry = updated_data.get(character)
        if not isinstance(entry, dict):
            raise ValueError(f"Character {character!r} not found in HWXNet JSON")
        updated_entry, stats = prune_hwxnet_entry(entry, removed_readings)
        validate_pruned_entry(character, updated_entry, removed_readings)
        updated_data[character] = updated_entry
        changed_entries[character] = updated_entry
        totals["characters_changed"] += 1
        for key in ("removed_pinyin_entries", "removed_basic_meanings", "removed_phrase_buckets", "removed_gloss_buckets"):
            totals[key] += stats[key]
        per_character.append(
            {
                "character": character,
                "removed_readings": sorted(removed_readings),
                **stats,
            }
        )

    return updated_data, {"totals": totals, "characters": per_character}, changed_entries


def backup_local_json(source_json: Path, backup_dir: Path) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup_path = backup_dir / f"{source_json.stem}.{utc_timestamp_slug()}-low-learning-value-removals-backup{source_json.suffix}"
    shutil.copy2(source_json, backup_path)
    return backup_path


def sync_changed_hwxnet_rows_to_db(changed_entries: dict[str, dict[str, Any]]) -> dict[str, Any]:
    ensure_import_paths()
    from create_hwxnet_characters_table import CREATE_TABLE_SQL, get_connection, row_from_entry  # type: ignore

    if not changed_entries:
        return {"backup_table": None, "rows_upserted": 0}

    conn = get_connection()
    backup_table = f"hwxnet_characters_backup_{utc_timestamp_slug()}"
    try:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            conn.commit()

            cur.execute(f"CREATE TABLE {backup_table} AS SELECT * FROM hwxnet_characters")
            conn.commit()

            rows = [row_from_entry(entry) for entry in changed_entries.values()]
            cur.executemany(
                """
                INSERT INTO hwxnet_characters
                (character, zibiao_index, index, source_url, classification, pinyin, radical, strokes, basic_meanings, english_translations, english_translations_by_pinyin, common_phrases, common_phrases_by_pinyin)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (character, zibiao_index) DO UPDATE SET
                    index = EXCLUDED.index,
                    source_url = EXCLUDED.source_url,
                    classification = EXCLUDED.classification,
                    pinyin = EXCLUDED.pinyin,
                    radical = EXCLUDED.radical,
                    strokes = EXCLUDED.strokes,
                    basic_meanings = EXCLUDED.basic_meanings,
                    english_translations = EXCLUDED.english_translations,
                    english_translations_by_pinyin = EXCLUDED.english_translations_by_pinyin,
                    common_phrases = EXCLUDED.common_phrases,
                    common_phrases_by_pinyin = EXCLUDED.common_phrases_by_pinyin
                """,
                rows,
            )
            conn.commit()
        return {"backup_table": backup_table, "rows_upserted": len(changed_entries)}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Remove confirmed low-learning-value units from HWXNet source data.",
    )
    parser.add_argument("--confirmed-json", type=Path, default=CONFIRMED_TRUE_POSITIVES_JSON)
    parser.add_argument("--candidate-artifact", type=Path, default=DEFAULT_CANDIDATE_ARTIFACT)
    parser.add_argument("--source-json", type=Path, default=HWXNET_JSON)
    parser.add_argument("--output", type=Path, default=None, help="Write cleaned JSON to a separate path.")
    parser.add_argument("--in-place", action="store_true", help="Overwrite the source JSON after creating a backup.")
    parser.add_argument("--backup-dir", type=Path, default=DATA_BACKUPS_DIR)
    parser.add_argument("--summary-json", type=Path, default=DEFAULT_APPLIED_REMOVALS_SUMMARY)
    parser.add_argument("--sync-hwxnet-table", action="store_true", help="Also upsert the changed HWXNet rows to Supabase after creating a table backup.")
    parser.add_argument("--dry-run", action="store_true", help="Compute and validate changes without writing files or touching Supabase.")
    args = parser.parse_args()

    if args.in_place and args.output is not None:
        raise SystemExit("Use either --in-place or --output, not both.")
    if args.sync_hwxnet_table and args.dry_run:
        raise SystemExit("--sync-hwxnet-table cannot be used together with --dry-run.")

    confirmed_units = load_confirmed_units_with_candidates(args.confirmed_json, args.candidate_artifact)
    removals_by_character = build_removals_by_character(confirmed_units)
    original_data = read_json(args.source_json)
    if not isinstance(original_data, dict):
        raise SystemExit(f"Expected character-keyed JSON object at {args.source_json}")

    updated_data, apply_stats, changed_entries = apply_removals_to_dataset(original_data, removals_by_character)

    local_backup_path: str | None = None
    output_path: str | None = None
    if args.dry_run:
        output_path = None
    elif args.output is not None:
        save_json(args.output, updated_data)
        output_path = str(args.output)
    elif args.in_place:
        backup_path = backup_local_json(args.source_json, args.backup_dir)
        local_backup_path = str(backup_path)
        save_json(args.source_json, updated_data)
        output_path = str(args.source_json)

    db_sync_summary = {"backup_table": None, "rows_upserted": 0}
    if args.sync_hwxnet_table:
        db_sync_summary = sync_changed_hwxnet_rows_to_db(changed_entries)

    summary = {
        "confirmed_units_count": len(confirmed_units),
        "removed_unit_ids": [row["unit_id"] for row in confirmed_units],
        "source_json": str(args.source_json),
        "output_json": output_path,
        "local_json_backup": local_backup_path,
        "db_sync": db_sync_summary,
        **apply_stats,
    }
    save_json(args.summary_json, summary)
    print(
        f"Confirmed units: {len(confirmed_units)} | changed characters: {apply_stats['totals']['characters_changed']} | "
        f"summary: {args.summary_json}"
    )
    if local_backup_path:
        print(f"Local JSON backup: {local_backup_path}")
    if db_sync_summary.get("backup_table"):
        print(f"Supabase backup table: {db_sync_summary['backup_table']}")


if __name__ == "__main__":
    main()
