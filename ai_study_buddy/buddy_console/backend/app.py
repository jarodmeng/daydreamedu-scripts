from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ai_study_buddy.buddy_console.backend.inventory_api import router as inventory_router, warm_enriched_cache
from ai_study_buddy.marking.review.api_routes import CONTEXT_ROOT, router as review_router
from ai_study_buddy.marking.review.models import STATIC_ROUTE_PREFIX


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


REPO_ROOT = _repo_root()

app = FastAPI(
    title="AI Study Buddy Buddy Console Backend",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount(STATIC_ROUTE_PREFIX, StaticFiles(directory=str(CONTEXT_ROOT)), name="review-workspace-static")
app.include_router(inventory_router)
app.include_router(review_router)


@app.on_event("startup")
def _warm_inventory_on_startup() -> None:
    warm_enriched_cache(app)
