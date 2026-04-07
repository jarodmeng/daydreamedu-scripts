#!/usr/bin/env python3
"""Shared helpers for the low-learning-value unit AI review workflow."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
WORKFLOW_ROOT = SCRIPT_DIR.parent
OUTER_APP_DIR = WORKFLOW_ROOT.parent
BACKEND_DIR = OUTER_APP_DIR / "chinese_chr_app" / "backend"
CHARACTER_SCRIPTS_DIR = BACKEND_DIR / "scripts" / "characters"
READING_GLOSS_SCRIPTS_DIR = OUTER_APP_DIR / "generate_english_meaning_using_ai" / "scripts"
DATA_DIR = OUTER_APP_DIR / "data"
DATA_BACKUPS_DIR = DATA_DIR / "backups"
HWXNET_JSON = DATA_DIR / "extracted_characters_hwxnet.json"
BATCH_ARTIFACTS = WORKFLOW_ROOT / "batch_artifacts"
PROMPTS_DIR = WORKFLOW_ROOT / "prompts"
DEFAULT_PROMPT_MD = PROMPTS_DIR / "low_learning_value_polyphonic_units_review_prompt.md"
DEFAULT_CANDIDATE_ARTIFACT = BATCH_ARTIFACTS / "polyphonic_review_candidates.json"
DEFAULT_BATCH_INPUT = BATCH_ARTIFACTS / "review_batch_input.jsonl"
DEFAULT_CHUNK_MANIFEST = BATCH_ARTIFACTS / "review_chunk_manifest.json"
DEFAULT_BATCH_ID_FILE = BATCH_ARTIFACTS / "batch_id.txt"
DEFAULT_BATCH_OUTPUT = BATCH_ARTIFACTS / "batch_output.jsonl"
DEFAULT_BATCH_ERRORS = BATCH_ARTIFACTS / "batch_errors.jsonl"
DEFAULT_SELECTED_OUTPUT = BATCH_ARTIFACTS / "low_learning_value_units.selected.json"
CONFIRMED_TRUE_POSITIVES_JSON = BATCH_ARTIFACTS / "low_learning_value_units.confirmed_true_positives.json"
DEFAULT_APPLIED_REMOVALS_SUMMARY = BATCH_ARTIFACTS / "low_learning_value_units.applied_removals.json"
DEFAULT_HISTORY_CLEANUP_SUMMARY = BATCH_ARTIFACTS / "low_learning_value_units.learning_history_cleanup.json"

REVIEWED_LOW_VALUE_EXAMPLE_NOTES = {
    "搂|lou1": "Real gameplay-reported example of a technically valid reading that still caused learner confusion and looked like a poor fit for circulation.",
    "殉|xun4": "Real gameplay-reported example of a reading whose practical learner value appears too low for routine recall circulation.",
    "瘪|bie3": "Real gameplay-reported example where the reading may be valid but still felt low value and confusing in practice.",
    "杉|sha1": "Real gameplay-reported example of a low-value sibling reading that was not a good learner-facing recall target.",
    "雀|qiao3": "Real gameplay-reported example of a low-exposure reading that confused learners during play.",
    "眯|mi2": "Real gameplay-reported example where a technically valid reading still appeared unsuitable for ordinary learner recall circulation.",
    "王|wang4": "Real gameplay-reported example showing that even a familiar character can carry a low-learning-value reading for this game.",
}

SYNTHETIC_USERS = ("local-dev", "e2e-dev")
SYNTHETIC_PREFIXES = ("e2e-gha-",)


def load_env_local() -> None:
    """Load backend .env.local if python-dotenv is available."""
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    env_file = BACKEND_DIR / ".env.local"
    if env_file.exists():
        load_dotenv(env_file)


def ensure_import_paths() -> None:
    """Expose backend and existing reading-review helpers to this workflow."""
    for path in (str(BACKEND_DIR), str(READING_GLOSS_SCRIPTS_DIR), str(CHARACTER_SCRIPTS_DIR)):
        if path not in sys.path:
            sys.path.insert(0, path)


def load_runtime_modules():
    """Load the backend/database and reading-payload helpers."""
    load_env_local()
    ensure_import_paths()
    import database as db  # type: ignore
    import pinyin_recall  # type: ignore
    from run_single_reading_gloss_prompt import build_user_payload, extract_system_message  # type: ignore

    return db, pinyin_recall, build_user_payload, extract_system_message


def extract_system_prompt(prompt_md_path: Path) -> str:
    """Extract the system-message code block from a prompt markdown file."""
    text = prompt_md_path.read_text(encoding="utf-8")
    start_marker = "## 1. System message"
    idx = text.find(start_marker)
    if idx == -1:
        raise ValueError(f"Could not find '{start_marker}' in {prompt_md_path}")
    rest = text[idx + len(start_marker):]
    match = re.search(r"```(?:[^\n`]*)\n(.*?)```", rest, re.DOTALL)
    if not match:
        raise ValueError("Could not find system message code block in prompt .md")
    return match.group(1).strip()


def unique_display_readings(values: Any) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    if not isinstance(values, list):
        return out
    for value in values:
        if not isinstance(value, str):
            continue
        cleaned = value.strip()
        if cleaned and cleaned not in seen:
            seen.add(cleaned)
            out.append(cleaned)
    return out


def is_polyphonic_entry(hwxnet_entry: dict[str, Any]) -> bool:
    return len(unique_display_readings(hwxnet_entry.get("拼音") or [])) > 1


def normalize_selected_unit(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize one AI-selected unit row to the stable output contract."""
    confidence = item.get("confidence")
    if not isinstance(confidence, (int, float)):
        raise ValueError(f"Invalid confidence value: {confidence!r}")
    return {
        "unit_id": str(item.get("unit_id") or "").strip(),
        "decision_reason": str(item.get("decision_reason") or "").strip(),
        "confidence": float(confidence),
    }


def filter_real_user_rows_sql(table_alias: str = "") -> str:
    prefix = f"{table_alias}." if table_alias else ""
    parts = [
        f"{prefix}user_id NOT IN ('local-dev', 'e2e-dev')",
        f"{prefix}user_id NOT LIKE 'e2e-gha-%'",
    ]
    return " AND ".join(parts)


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def utc_timestamp_slug() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def split_unit_id(unit_id: str) -> tuple[str, str]:
    if "|" not in unit_id:
        raise ValueError(f"Invalid unit_id (missing '|'): {unit_id!r}")
    character, reading_key = unit_id.split("|", 1)
    character = character.strip()
    reading_key = reading_key.strip()
    if not character or not reading_key:
        raise ValueError(f"Invalid unit_id: {unit_id!r}")
    return character, reading_key


def build_candidate_lookup(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    return {
        row["unit_id"]: row
        for row in rows
        if isinstance(row, dict) and isinstance(row.get("unit_id"), str)
    }


def load_confirmed_units_with_candidates(
    confirmed_path: Path = CONFIRMED_TRUE_POSITIVES_JSON,
    candidate_path: Path = DEFAULT_CANDIDATE_ARTIFACT,
) -> list[dict[str, Any]]:
    confirmed_rows = read_json(confirmed_path)
    if not isinstance(confirmed_rows, list):
        raise ValueError(f"Expected list in confirmed units file: {confirmed_path}")
    candidate_payload = read_json(candidate_path)
    candidate_rows = candidate_payload.get("candidates") or []
    if not isinstance(candidate_rows, list):
        raise ValueError(f"Expected candidates list in artifact: {candidate_path}")
    candidates_by_id = build_candidate_lookup(candidate_rows)

    enriched: list[dict[str, Any]] = []
    missing: list[str] = []
    for row in confirmed_rows:
        if not isinstance(row, dict):
            continue
        unit_id = str(row.get("unit_id") or "").strip()
        if not unit_id:
            continue
        candidate = candidates_by_id.get(unit_id)
        if candidate is None:
            missing.append(unit_id)
            continue
        enriched.append(
            {
                **row,
                "character": candidate.get("character"),
                "reading_display": candidate.get("reading_display"),
                "reading_key": candidate.get("reading_key"),
            }
        )
    if missing:
        raise ValueError(
            "Confirmed units missing from candidate artifact: "
            + ", ".join(sorted(missing)[:10])
            + (" ..." if len(missing) > 10 else "")
        )
    return enriched
