#!/usr/bin/env python3
"""
Batch derive target-character reading tags for HWXNet 常用词组.

This script:
- queries the live hwxnet_characters table to find polyphonic characters that
  have at least one common_phrases entry
- runs extract_common_phrase_character_readings.py logic for each character
- saves a merged JSON artifact keyed by character
- supports parallel workers and resumable progress

Usage:
  python3 batch_extract_common_phrase_character_readings.py
  python3 batch_extract_common_phrase_character_readings.py --workers 8
  python3 batch_extract_common_phrase_character_readings.py --limit 20 --workers 4
  python3 batch_extract_common_phrase_character_readings.py --overwrite
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    from dotenv import load_dotenv

    ENV_FILE = Path(__file__).resolve().parent.parent / "chinese_chr_app" / "backend" / ".env.local"
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
except ImportError:
    pass

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

from extract_common_phrase_character_readings import extract_common_phrase_character_readings


SCRIPT_DIR = Path(__file__).resolve().parent
BASE_DIR = SCRIPT_DIR.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_JSON = DATA_DIR / "extracted_hwxnet_common_phrase_character_readings.json"
BACKUP_DIR = DATA_DIR / "backups"
PROGRESS_JSON = SCRIPT_DIR / "progress_common_phrase_character_readings.json"


class RateLimiter:
    """Thread-safe fixed-interval rate limiter."""

    def __init__(self, requests_per_second: float):
        self.min_interval = 0.0 if requests_per_second <= 0 else 1.0 / requests_per_second
        self.last_request_time = 0.0
        self.lock = threading.Lock()

    def acquire(self):
        if self.min_interval <= 0:
            return
        with self.lock:
            now = time.time()
            elapsed = now - self.last_request_time
            if elapsed < self.min_interval:
                time.sleep(self.min_interval - elapsed)
            self.last_request_time = time.time()


def _db_url() -> str:
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        raise RuntimeError("DATABASE_URL or SUPABASE_DB_URL is not set.")
    if psycopg is None:
        raise RuntimeError("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
    return url


def load_target_characters(limit: Optional[int] = None) -> List[str]:
    """
    Load the exact target batch:
    polyphonic characters with at least one common_phrases entry.
    """
    query = """
    WITH per_char AS (
        SELECT
            character,
            zibiao_index,
            (
                SELECT COUNT(DISTINCT BTRIM(elem))
                FROM jsonb_array_elements_text(COALESCE(pinyin, '[]'::jsonb)) AS e(elem)
                WHERE BTRIM(elem) <> ''
            ) AS reading_count,
            jsonb_array_length(COALESCE(common_phrases, '[]'::jsonb)) AS common_phrase_count
        FROM hwxnet_characters
    )
    SELECT character
    FROM per_char
    WHERE reading_count > 1
      AND common_phrase_count > 0
    ORDER BY zibiao_index ASC NULLS LAST, character ASC
    """
    if limit:
        query += " LIMIT %s"

    with psycopg.connect(_db_url(), row_factory=dict_row) as conn:
        with conn.cursor() as cur:
            if limit:
                cur.execute(query, (limit,))
            else:
                cur.execute(query)
            rows = cur.fetchall()
    return [row["character"] for row in rows if row.get("character")]


def load_existing_output() -> Dict[str, Any]:
    if not OUTPUT_JSON.exists():
        return {}
    try:
        return json.loads(OUTPUT_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {}


def load_progress() -> Dict[str, Any]:
    if not PROGRESS_JSON.exists():
        return {"processed": {}, "failed": {}, "last_updated": None}
    try:
        return json.loads(PROGRESS_JSON.read_text(encoding="utf-8"))
    except Exception:
        return {"processed": {}, "failed": {}, "last_updated": None}


def save_progress(progress: Dict[str, Any]) -> None:
    progress["last_updated"] = datetime.now().isoformat()
    PROGRESS_JSON.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS_JSON.write_text(json.dumps(progress, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


_did_backup_output = False


def ensure_output_backup() -> None:
    global _did_backup_output
    if _did_backup_output:
        return
    if not OUTPUT_JSON.exists():
        _did_backup_output = True
        return
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIR / f"{OUTPUT_JSON.stem}.{ts}.json"
    if backup_path.exists():
        ts = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = BACKUP_DIR / f"{OUTPUT_JSON.stem}.{ts}.json"
    backup_path.write_bytes(OUTPUT_JSON.read_bytes())
    print(f"Backed up existing output to: {backup_path}", flush=True)
    _did_backup_output = True


def save_results(results: Dict[str, Any]) -> None:
    ensure_output_backup()
    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    merged = load_existing_output()
    merged.update(results)
    OUTPUT_JSON.write_text(json.dumps(merged, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def extract_one(character: str, limiter: RateLimiter) -> Dict[str, Any]:
    limiter.acquire()
    return extract_common_phrase_character_readings(character)


def batch_extract(
    characters: List[str],
    *,
    workers: int = 4,
    requests_per_second: float = 1.0,
    overwrite: bool = False,
) -> Dict[str, Any]:
    progress = load_progress()
    processed = progress.get("processed", {})
    failed = progress.get("failed", {})

    existing_output = load_existing_output()
    if existing_output:
        for ch, payload in existing_output.items():
            if ch not in processed and isinstance(payload, dict):
                processed[ch] = {
                    "status": "done",
                    "timestamp": datetime.now().isoformat(),
                }

    if overwrite:
        remaining = list(characters)
    else:
        remaining = [c for c in characters if c not in processed and c not in failed]

    print(f"Target characters: {len(characters)}", flush=True)
    print(f"Already processed: {len(processed)}", flush=True)
    print(f"Already failed: {len(failed)}", flush=True)
    print(f"Remaining: {len(remaining)}", flush=True)
    print(f"Workers: {workers}", flush=True)
    print(f"Request rate: {requests_per_second} req/s", flush=True)
    print("=" * 70, flush=True)

    if not remaining:
        return {
            "total": len(characters),
            "processed": len(processed),
            "failed": len(failed),
            "results_written": len(load_existing_output()),
        }

    limiter = RateLimiter(requests_per_second)
    results_to_write: Dict[str, Any] = {}
    new_failed: Dict[str, Any] = {}
    start_time = time.time()
    completed_count = 0

    with ThreadPoolExecutor(max_workers=max(1, workers)) as executor:
        future_to_char = {
            executor.submit(extract_one, char, limiter): char
            for char in remaining
        }
        try:
            for future in as_completed(future_to_char):
                char = future_to_char[future]
                completed_count += 1
                try:
                    payload = future.result()
                    results_to_write[char] = payload
                    failed.pop(char, None)
                    processed[char] = {
                        "status": "done",
                        "timestamp": datetime.now().isoformat(),
                        "common_phrase_count": len(payload.get("common_phrase_readings", [])),
                    }
                    print(
                        f"[{completed_count}/{len(remaining)}] {char} ✓ {len(payload.get('common_phrase_readings', []))} phrase tags",
                        flush=True,
                    )
                except Exception as exc:
                    new_failed[char] = {
                        "status": "failed",
                        "timestamp": datetime.now().isoformat(),
                        "error": str(exc),
                        "traceback": traceback.format_exc(),
                    }
                    failed[char] = new_failed[char]
                    print(f"[{completed_count}/{len(remaining)}] {char} ✗ {exc}", flush=True)

                if completed_count % 10 == 0:
                    progress["processed"] = processed
                    progress["failed"] = failed
                    save_progress(progress)
                    if results_to_write:
                        save_results(results_to_write)
                        results_to_write = {}
        except KeyboardInterrupt:
            print("\nInterrupted. Saving progress...", flush=True)
            progress["processed"] = processed
            progress["failed"] = failed
            save_progress(progress)
            if results_to_write:
                save_results(results_to_write)
            raise

    progress["processed"] = processed
    progress["failed"] = failed
    save_progress(progress)
    if results_to_write:
        save_results(results_to_write)

    total_time = time.time() - start_time
    return {
        "total": len(characters),
        "new_processed": len(results_to_write),
        "new_failed": len(new_failed),
        "processed": len(processed),
        "failed": len(failed),
        "results_written": len(load_existing_output()),
        "timing": {
            "total_seconds": total_time,
            "formatted": str(timedelta(seconds=int(total_time))),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Batch derive target-character reading tags for HWXNet 常用词组.",
    )
    parser.add_argument(
        "--characters",
        nargs="+",
        default=None,
        help="Optional explicit character list to process instead of loading the full DB-derived target set.",
    )
    parser.add_argument("--limit", type=int, default=None, help="Process only the first N target characters.")
    parser.add_argument("--workers", type=int, default=4, help="Number of parallel worker threads (default: 4).")
    parser.add_argument(
        "--requests-per-second",
        type=float,
        default=1.0,
        help="Shared request rate across workers (default: 1.0 req/s).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Reprocess characters already marked processed in progress/output.",
    )
    args = parser.parse_args()

    if args.characters:
        characters = list(dict.fromkeys(args.characters))
    else:
        try:
            characters = load_target_characters(limit=args.limit)
        except Exception as exc:
            print(f"Failed to load target characters: {exc}", file=sys.stderr, flush=True)
            sys.exit(1)

    stats = batch_extract(
        characters,
        workers=args.workers,
        requests_per_second=args.requests_per_second,
        overwrite=args.overwrite,
    )
    print("\nDone.", flush=True)
    print(json.dumps(stats, ensure_ascii=False, indent=2), flush=True)


if __name__ == "__main__":
    main()
