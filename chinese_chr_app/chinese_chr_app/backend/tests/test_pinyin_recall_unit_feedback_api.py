#!/usr/bin/env python3
"""Focused API checks for unit-specific pinyin-recall feedback behavior."""

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ["IMPORT_SMOKE_TEST"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent))

import app as app_module


def _load_hwxnet_entry(character: str):
    path = Path(__file__).resolve().parents[3] / "data" / "extracted_characters_hwxnet.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return data[character]


def _load_feng_entry(character: str):
    path = Path(__file__).resolve().parents[3] / "data" / "characters.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    return next(entry for entry in data if entry.get("Character") == character)


def test_answer_endpoint_returns_unit_specific_feedback_for_polyphonic_reading(monkeypatch):
    app_module.app.config["TESTING"] = True

    hwxnet_entry = _load_hwxnet_entry("行")
    feng_entry = _load_feng_entry("行")

    monkeypatch.setattr(
        app_module,
        "_get_profile_user",
        lambda: SimpleNamespace(user_id="test-user", user_metadata=None),
    )
    monkeypatch.setattr(app_module, "_get_pinyin_recall_dev_user", lambda: None)
    monkeypatch.setattr(app_module, "load_hwxnet", lambda: (None, app_module.hwxnet_lookup))
    monkeypatch.setattr(app_module, "load_characters", lambda: (None, app_module.character_lookup))
    monkeypatch.setattr(app_module, "hwxnet_lookup", {"行": hwxnet_entry})
    monkeypatch.setattr(app_module, "character_lookup", {"行": feng_entry})

    fake_db = SimpleNamespace(
        upsert_pinyin_recall_answer_and_log=lambda *args, **kwargs: (0, -10),
    )
    monkeypatch.setitem(sys.modules, "database", fake_db)

    client = app_module.app.test_client()
    response = client.post(
        "/api/games/pinyin-recall/answer",
        json={
            "session_id": "session-1",
            "character": "行",
            "unit_id": "行|hang2",
            "selected_choice": "xíng",
            "correct_pinyin": "háng",
            "i_dont_know": False,
            "latency_ms": 1234,
        },
        headers={"Authorization": "Bearer fake-token"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["correct"] is False

    missed = payload["missed_item"]
    assert missed["unit_id"] == "行|hang2"
    assert missed["correct_pinyin"] == "háng"
    assert missed["stem_words"][:3] == ["行列", "行业", "银行"]
    assert missed["meanings"] == [
        "line; row",
        "line of business; trade",
        "bank; commercial firm",
        "rank among siblings",
    ]
    assert missed["meaning_zh"] is None
    assert missed["all_pinyin"] == ["xíng", "háng"]
    assert missed["other_readings"] == ["xíng"]
