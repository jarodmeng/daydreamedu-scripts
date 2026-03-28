#!/usr/bin/env python3
"""Focused invariants for Feng character source data."""

import json
from pathlib import Path


CHARACTERS_JSON = Path(__file__).resolve().parents[3] / "data" / "characters.json"


def test_all_feng_words_contain_their_character():
    data = json.loads(CHARACTERS_JSON.read_text(encoding="utf-8"))

    offenders = []
    for entry in data:
        character = entry.get("Character")
        for phrase in entry.get("Words") or []:
            if character and character not in phrase:
                offenders.append((entry.get("Index"), character, phrase))

    assert offenders == []


def test_feng_index_2328_is_the_qian_card_not_qianze():
    data = json.loads(CHARACTERS_JSON.read_text(encoding="utf-8"))

    entry = next(row for row in data if row.get("Index") == "2328")

    assert entry["Character"] == "遣"
    assert entry["zibiao_index"] == 2921
    assert entry["Radical"] == "辶"
    assert entry["Words"] == ["遣返", "遣散", "遣送", "差遣", "派遣", "消遣", "调兵遣将"]
