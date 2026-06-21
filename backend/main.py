"""OPLedger — FastAPI application entry point.

Serves the REST API and the static vanilla JS frontend from a single image.
The frontend talks to the backend exclusively through the REST API, so this
same app works unchanged behind a reverse proxy or in a hosted deployment.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import api_router
from backend.app.core.config import settings

app = FastAPI(
    title="OPLedger",
    description="Self-hosted bookkeeping: QFX in, Schedule C out.",
    version="0.1.0",
)

# REST API — the same surface a cloud deployment would expose.
app.include_router(api_router, prefix="/api")

# Static frontend (vanilla JS, no build step). Mounted last so /api wins.
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")


@app.on_event("startup")
def on_startup() -> None:
    """Ensure the data dir + first-run config tree exist before serving."""
    settings.ensure_data_dir()
