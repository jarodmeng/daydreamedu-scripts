from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ai_study_buddy.buddy_console.backend.goodnotes_airdrop import (
    GoodnotesAirDropError,
    GoodnotesAirDropUnavailableError,
    launch_goodnotes_airdrop,
)

router = APIRouter(tags=["goodnotes-airdrop"])


class AirDropShareLinkRequest(BaseModel):
    url: str = Field(..., min_length=1)


@router.post("/api/goodnotes/airdrop-share-link")
def airdrop_share_link(body: AirDropShareLinkRequest) -> dict[str, Any]:
    try:
        launch_goodnotes_airdrop(body.url)
    except GoodnotesAirDropUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except GoodnotesAirDropError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "launched"}
