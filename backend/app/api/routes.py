"""Aggregate API router.

Mounts every endpoint group under a single router that main.py includes at
/api. The setup/unlock and auth login routes are public; everything else sits
behind the unlock gate and JWT auth via per-router dependencies.
"""
from fastapi import APIRouter

from backend.app.api.endpoints import (
    accounts,
    auth,
    categories,
    exports,
    reports,
    settings,
    setup,
    transactions,
    users,
)

api_router = APIRouter()


@api_router.get("/health", tags=["health"])
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


api_router.include_router(setup.router)
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(accounts.router)
api_router.include_router(categories.router)
api_router.include_router(transactions.router)
api_router.include_router(reports.router)
api_router.include_router(exports.router)
api_router.include_router(settings.router)
