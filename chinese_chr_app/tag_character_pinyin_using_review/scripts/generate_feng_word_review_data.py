#!/usr/bin/env python3
"""
Generate review data for polyphonic Feng characters.

Run from repo root:
  python3 chinese_chr_app/tag_character_pinyin_using_ai/scripts/generate_feng_word_review_data.py

Requires DATABASE_URL or SUPABASE_DB_URL. Loads backend/.env.local if present.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv

    ENV_FILE = (
        Path(__file__).resolve().parents[2]
        / "chinese_chr_app"
        / "backend"
        / ".env.local"
    )
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE)
except ImportError:
    pass

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    print("psycopg is required. Install with: pip3 install 'psycopg[binary]>=3.1'")
    sys.exit(1)


SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parent
OUTPUT_PATH = ROOT / "review" / "feng_word_review_data.json"


def get_connection():
    url = os.environ.get("DATABASE_URL") or os.environ.get("SUPABASE_DB_URL")
    if not url:
        print("DATABASE_URL or SUPABASE_DB_URL is not set.")
        sys.exit(1)
    return psycopg.connect(url, row_factory=dict_row)


def fetch_rows() -> list[dict]:
    conn = get_connection()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT character, index, pinyin, words
                FROM feng_characters
                WHERE jsonb_array_length(pinyin) > 1
                ORDER BY index
                """
            )
            return cur.fetchall()
    finally:
        conn.close()


def main() -> None:
    rows = fetch_rows()
    review_data = []
    for row in rows:
      words = [
          word.strip()
          for word in (row.get("words") or [])
          if isinstance(word, str) and word.strip()
      ]
      review_data.append(
          {
              "character": (row.get("character") or "").strip(),
              "index": row.get("index"),
              "allowed_readings": [
                  reading.strip()
                  for reading in (row.get("pinyin") or [])
                  if isinstance(reading, str) and reading.strip()
              ],
              "words": [
                  {
                      "position": i,
                      "text": word,
                      "previous_word": words[i - 2] if i > 1 else None,
                      "next_word": words[i] if i < len(words) else None,
                  }
                  for i, word in enumerate(words, start=1)
              ],
          }
      )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(review_data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote review data to {OUTPUT_PATH}")
    print(f"Characters: {len(review_data)}")
    print(f"Words: {sum(len(item['words']) for item in review_data)}")


if __name__ == "__main__":
    main()
