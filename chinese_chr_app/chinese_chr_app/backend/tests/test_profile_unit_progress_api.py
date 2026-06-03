#!/usr/bin/env python3
"""Focused API checks for unit-level profile/progress reporting."""

import os
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

os.environ["IMPORT_SMOKE_TEST"] = "1"

sys.path.insert(0, str(Path(__file__).parent.parent))

import app as app_module
import database as database_module


def test_build_pinyin_recall_practice_summary_returns_empty_for_no_rows():
    assert database_module._build_pinyin_recall_practice_summary([], today_utc=date(2026, 4, 7)) == []


def test_build_pinyin_recall_practice_summary_aggregates_rolling_windows():
    rows = [
        {
            "date": date(2026, 4, 7),
            "answered": 5,
            "correct": 4,
            "新字_answered": 2,
            "新字_correct": 1,
            "巩固_answered": 2,
            "巩固_correct": 2,
            "重测_answered": 1,
            "重测_correct": 1,
        },
        {
            "date": date(2026, 4, 3),
            "answered": 4,
            "correct": 3,
            "新字_answered": 1,
            "新字_correct": 1,
            "巩固_answered": 0,
            "巩固_correct": 0,
            "重测_answered": 3,
            "重测_correct": 2,
        },
        {
            "date": date(2026, 3, 15),
            "answered": 3,
            "correct": 2,
            "新字_answered": 0,
            "新字_correct": 0,
            "巩固_answered": 3,
            "巩固_correct": 2,
            "重测_answered": 0,
            "重测_correct": 0,
        },
        {
            "date": date(2026, 1, 15),
            "answered": 6,
            "correct": 5,
            "新字_answered": 4,
            "新字_correct": 3,
            "巩固_answered": 2,
            "巩固_correct": 2,
            "重测_answered": 0,
            "重测_correct": 0,
        },
    ]

    summary = database_module._build_pinyin_recall_practice_summary(rows, today_utc=date(2026, 4, 7))

    assert [item["key"] for item in summary] == [
        "last_7_days",
        "last_30_days",
        "last_90_days",
        "lifetime",
    ]

    last_7_days = summary[0]
    assert last_7_days["label"] == "最近7天"
    assert last_7_days["active_days"] == 2
    assert last_7_days["answered"] == 9
    assert last_7_days["correct"] == 7
    assert last_7_days["accuracy_pct"] == 78
    assert last_7_days["by_category"]["新字"] == {"answered": 3, "correct": 2}
    assert last_7_days["by_category"]["巩固"] == {"answered": 2, "correct": 2}
    assert last_7_days["by_category"]["重测"] == {"answered": 4, "correct": 3}

    last_30_days = summary[1]
    assert last_30_days["active_days"] == 3
    assert last_30_days["answered"] == 12
    assert last_30_days["correct"] == 9
    assert last_30_days["accuracy_pct"] == 75

    last_90_days = summary[2]
    assert last_90_days["active_days"] == 4
    assert last_90_days["answered"] == 18
    assert last_90_days["correct"] == 14

    lifetime = summary[3]
    assert lifetime["active_days"] == 4
    assert lifetime["answered"] == 18
    assert lifetime["correct"] == 14
    assert lifetime["accuracy_pct"] == 78
    assert lifetime["by_category"]["新字"] == {"answered": 7, "correct": 5}
    assert lifetime["by_category"]["巩固"] == {"answered": 7, "correct": 6}
    assert lifetime["by_category"]["重测"] == {"answered": 4, "correct": 3}


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
        get_pinyin_recall_practice_summary=lambda user_id: [
            {
                "key": "last_7_days",
                "label": "最近7天",
                "active_days": 2,
                "answered": 9,
                "correct": 7,
                "accuracy_pct": 78,
                "by_category": {
                    "新字": {"answered": 3, "correct": 2},
                    "巩固": {"answered": 2, "correct": 2},
                    "重测": {"answered": 4, "correct": 3},
                },
            }
        ],
        _get_enabled_recall_unit_ids=lambda: {"u1", "u2"},
        get_pinyin_recall_category_daily_trend=lambda user_id, days=None, **kwargs: [],
        get_pinyin_recall_category_counts=lambda user_id, **kwargs: {
            "total_units": 904,
            "learned": 200,
            "learning": 50,
            "not_tested": 654,
            "learning_hard": 10,
            "learning_normal": 40,
            "learned_mastered": 65,
            "learned_memorized": 15,
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
    practice_summary = payload["practice_summary"]
    assert proficiency["total_units"] == 904
    assert proficiency["total_characters"] == 904
    assert proficiency["description"] == "200 / 904"
    assert proficiency["learned_count"] == 200
    assert proficiency["learning_count"] == 50
    assert proficiency["not_tested_count"] == 654
    assert proficiency["learned_mastered"] == 65
    assert proficiency["learned_memorized"] == 15
    assert practice_summary[0]["label"] == "最近7天"
    assert practice_summary[0]["active_days"] == 2
    assert practice_summary[0]["accuracy_pct"] == 78


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


def test_profile_category_accepts_learned_memorized(monkeypatch):
    app_module.app.config["TESTING"] = True
    _set_auth(monkeypatch)

    fake_units = [
        {
            "unit_id": "好|hao3",
            "character": "好",
            "reading_key": "hao3",
            "reading_display": "hǎo",
            "score": 45,
            "last_answered_at": "2026-06-01T12:00:00+00:00",
        },
    ]
    captured = {}

    def _by_category(user_id, category):
        captured["category"] = category
        return fake_units

    fake_db = SimpleNamespace(get_pinyin_recall_characters_by_category=_by_category)
    monkeypatch.setitem(sys.modules, "database", fake_db)

    client = app_module.app.test_client()
    response = client.get(
        "/api/profile/progress/category/learned_memorized",
        headers={"Authorization": "Bearer fake-token"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["category"] == "learned_memorized"
    assert captured["category"] == "learned_memorized"
    assert payload["units"] == fake_units


def test_profile_sub_band_for_score_matches_table_thresholds():
    assert database_module._profile_sub_band_for_score(-25) == "难字"
    assert database_module._profile_sub_band_for_score(0) == "普通在学字"
    assert database_module._profile_sub_band_for_score(9) == "普通在学字"
    assert database_module._profile_sub_band_for_score(10) == "普通已学字"
    assert database_module._profile_sub_band_for_score(19) == "普通已学字"
    assert database_module._profile_sub_band_for_score(20) == "掌握字"
    assert database_module._profile_sub_band_for_score(39) == "掌握字"
    assert database_module._profile_sub_band_for_score(40) == "精通字"
    assert database_module._profile_sub_band_for_score(100) == "精通字"


def test_category_trend_point_includes_memorized():
    point = database_module._category_trend_point_from_counts(
        {
            "learning_hard": 1,
            "learning_normal": 2,
            "learned_normal": 3,
            "learned_mastered": 4,
            "learned_memorized": 5,
        },
        date(2026, 6, 3),
    )
    assert point == {
        "date": "2026-06-03",
        "hard": 1,
        "learning_normal": 2,
        "learned_normal": 3,
        "mastered": 4,
        "memorized": 5,
    }


def test_sync_category_trend_replaces_today_with_live_counts(monkeypatch):
    today = date(2026, 5, 26)
    monkeypatch.setattr(database_module, "_profile_trend_today_utc_date", lambda: today)
    monkeypatch.setattr(
        database_module,
        "get_pinyin_recall_category_counts",
        lambda user_id: {
            "learning_hard": 1,
            "learning_normal": 22,
            "learned_normal": 249,
            "learned_mastered": 3537,
        },
    )

    replayed = [
        {
            "date": "2026-05-26",
            "hard": 2,
            "learning_normal": 22,
            "learned_normal": 250,
            "mastered": 3537,
        }
    ]
    live = {
        "learning_hard": 1,
        "learning_normal": 22,
        "learned_normal": 249,
        "learned_mastered": 3537,
    }
    synced = database_module._sync_category_trend_with_live_counts(
        "user-1", list(replayed), live_counts=live
    )

    assert synced[-1]["date"] == today.isoformat()
    assert synced[-1]["hard"] == 1
    assert synced[-1]["learned_normal"] == 249


def test_sync_category_trend_appends_today_when_replay_ends_yesterday(monkeypatch):
    monkeypatch.setattr(
        database_module,
        "_profile_trend_today_utc_date",
        lambda: date(2026, 5, 26),
    )
    monkeypatch.setattr(
        database_module,
        "get_pinyin_recall_category_counts",
        lambda user_id: {
            "learning_hard": 1,
            "learning_normal": 22,
            "learned_normal": 249,
            "learned_mastered": 3537,
        },
    )

    live = {
        "learning_hard": 1,
        "learning_normal": 22,
        "learned_normal": 249,
        "learned_mastered": 3537,
    }
    synced = database_module._sync_category_trend_with_live_counts(
        "user-1",
        [{"date": "2026-05-25", "hard": 2, "learning_normal": 22, "learned_normal": 250, "mastered": 3537}],
        live_counts=live,
    )

    assert len(synced) == 2
    assert synced[-1]["date"] == "2026-05-26"
    assert synced[-1]["learned_normal"] == 249
    assert synced[-1]["hard"] == 1
