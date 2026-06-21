"""Schedule C category list (config-driven)."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from backend.app.api.deps import get_current_user
from backend.app.services import categories as categories_service

router = APIRouter(tags=["categories"])


@router.get("/categories")
def list_categories(_=Depends(get_current_user)) -> dict:
    """Return the configured business (Schedule C) and personal categories."""
    return {
        "categories": categories_service.load_categories(),
        "personal_categories": categories_service.load_personal_categories(),
    }
