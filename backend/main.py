"""OPLedger — FastAPI application entry point.

Serves the REST API and the static vanilla JS frontend from a single image.
The frontend talks to the backend exclusively through the REST API, so this
same app works unchanged behind a reverse proxy or in a hosted deployment.
"""
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import api_router
from backend.app.core.config import settings
from backend.app.core.runtime import runtime
from backend.app.db import database

logger = logging.getLogger("opledger")

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "frontend"
ASSETS_DIR = ROOT / "assets"


def _load_jwt_secret() -> None:
    from backend.app.models.models import Setting

    db = database.new_session()
    try:
        secret = db.get(Setting, "jwt_secret")
        runtime.jwt_secret = secret.value if secret else None
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Ensure the data dir/config exist and connect/unlock the DB at boot."""
    settings.ensure_data_dir()
    if database.is_external():
        # External database (e.g. PostgreSQL): connect immediately; no unlock.
        database.open_external()
        runtime.unlocked = True
        _load_jwt_secret()
        logger.info("Connected to external database")
    elif settings.passphrase and database.database_exists():
        # Convenience path for unattended restarts (OPLEDGER_PASSPHRASE set).
        if database.open_database(settings.passphrase, create=False):
            _load_jwt_secret()
            runtime.unlocked = True
            logger.info("Database auto-unlocked from OPLEDGER_PASSPHRASE")
        else:
            logger.warning("OPLEDGER_PASSPHRASE did not unlock the database")
    yield


app = FastAPI(
    title="OPLedger",
    description="Self-hosted bookkeeping: QFX in, Schedule C out.",
    version="0.1.0",
    lifespan=lifespan,
)

# REST API — the same surface a cloud deployment would expose.
app.include_router(api_router, prefix="/api")

# Project icon used by the frontend. Mounted before the catch-all.
if ASSETS_DIR.is_dir():
    app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")

# Static frontend (vanilla JS, no build step). Mounted last so /api wins.
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
