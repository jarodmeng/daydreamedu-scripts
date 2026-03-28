#!/usr/bin/env python3
"""Focused API checks for unit-level profile/progress reporting."""

import os
import sys
from pathlib import Path
from types import SimpleNamespace

os.environ["IMPORT_SMOKE_TEST"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent))

import app as app_module


def _set_auth(monkeypatch):
    monkeypatch.setattr(
        app_module,
        "_get_profile_user",
        lambda: SimpleNamespace(user_id="test-user", user_metadata=None),
    )
    monkeypatch.setattr(app_module, "_get_pinyin_recall_dev_user", lambda: None)


def test_profile_progress_returns_unit_level_denominator(monkeypatch):
    app_module.app.config["TESTING"] = True
    _set_auth(monkeypatch)

    fake_db = SimpleNamespace(
        get_character_views_count_for_user=lambda user_id: 12,
        get_character_views_recent_for_user=lambda user_id, limit=50: ["行", "和"],
        get_pinyin_recall_daily_stats=lambda user_id, days=30: [],
        get_pinyin_recall_category_daily_trend=lambda user_id, days=60: [],
        get_pinyin_recall_category_counts=lambda user_id: {
            "total_units": 904,
            "learned": 200,
            "learning": 50,
            "not_tested": 654,
            "learning_hard": 10,
            "learning_normal": 40,
            "learned_mastered": 80,
            "learned_normal": 120,
        },
        PROFILE_HWXNET_TOTAL=3664,
    )
    monkeypatch.setitem(sys.modules, "database", fake_db)

    client = app_module.app.test_client()
    response = client.get("/api/profile/progress", headers={"Authorization": "Bearer fake-token"})

    assert response.status_code == 200
    payload = response.get_json()
    proficiency = payload["proficiency"]
    assert proficiency["total_units"] == 904
    assert proficiency["total_characters"] == 904
    assert proficiency["description"] == "200 / 904"
    assert proficiency["learned_count"] == 200
    assert proficiency["learning_count"] == 50
    assert proficiency["not_tested_count"] == 654


def test_profile_category_returns_unit_entries(monkeypatch):
    app_module.app.config["TESTING"] = True
    _set_auth(monkeypatch)

    fake_units = [
        {
            "unit_id": "行|xing2",
            "character": "行",
            "reading_key": "xing2",
            "reading_display": "xíng",
            "score": 15,
            "last_answered_at": "2026-03-29T12:00:00+00:00",
        },
        {
            "unit_id": "行|hang2",
            "character": "行",
            "reading_key": "hang2",
            "reading_display": "háng",
            "score": 12,
            "last_answered_at": "2026-03-28T12:00:00+00:00",
        },
    ]
    fake_db = SimpleNamespace(
        get_pinyin_recall_characters_by_category=lambda user_id, category: fake_units,
    )
    monkeypatch.setitem(sys.modules, "database", fake_db)

    client = app_module.app.test_client()
    response = client.get(
        "/api/profile/progress/category/learned_normal",
        headers={"Authorization": "Bearer fake-token"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["category"] == "learned_normal"
    assert payload["units"] == fake_units
    assert payload["characters"] == fake_units
