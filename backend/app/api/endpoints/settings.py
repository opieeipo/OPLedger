"""Owner-configurable ledger settings (EIN, fiscal year, quarterly estimates).

Any authenticated user can read settings (reports and the UI need them); only an
Owner can change them.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.app.api.deps import get_current_user, get_db, require_role
from backend.app.models.models import Role
from backend.app.schemas import LedgerSettings, LedgerSettingsUpdate
from backend.app.services import settings_store

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=LedgerSettings)
def read_settings(db: Session = Depends(get_db), _=Depends(get_current_user)) -> LedgerSettings:
    return settings_store.get_settings(db)


@router.patch("/settings", response_model=LedgerSettings)
def update_settings(
    body: LedgerSettingsUpdate,
    db: Session = Depends(get_db),
    _=Depends(require_role(Role.owner)),
) -> LedgerSettings:
    settings_store.update_settings(db, body)
    return settings_store.get_settings(db)
