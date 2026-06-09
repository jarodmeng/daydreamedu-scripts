from __future__ import annotations

import hashlib
import json
from typing import Any


def fingerprint_resolved_question_row(row: dict[str, Any]) -> str:
    canonical = json.dumps(row, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def build_context_snapshot(
    *,
    marking_result_path: str,
    amendment_state: dict[str, Any] | None,
    review_state_updated_at: str | None,
    resolved_question_row: dict[str, Any],
) -> dict[str, Any]:
    amendment_meta = {}
    if isinstance(amendment_state, dict):
        amendment_meta = amendment_state.get("review_meta") if isinstance(amendment_state.get("review_meta"), dict) else {}
    return {
        "marking_result_path": marking_result_path,
        "amendment_updated_at": amendment_meta.get("updated_at") if isinstance(amendment_meta.get("updated_at"), str) else None,
        "review_state_updated_at": review_state_updated_at,
        "resolved_question_fingerprint": fingerprint_resolved_question_row(resolved_question_row),
    }


def compute_stale_context(
    *,
    snapshot: dict[str, Any] | None,
    live_snapshot: dict[str, Any],
) -> dict[str, bool]:
    if not isinstance(snapshot, dict):
        return {"marking": False, "review_notes": False}

    marking_stale = (
        snapshot.get("amendment_updated_at") != live_snapshot.get("amendment_updated_at")
        or snapshot.get("resolved_question_fingerprint") != live_snapshot.get("resolved_question_fingerprint")
    )
    review_stale = snapshot.get("review_state_updated_at") != live_snapshot.get("review_state_updated_at")
    return {"marking": marking_stale, "review_notes": review_stale}
