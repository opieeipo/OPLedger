"""OPLedger REST API routes.

Stub surface mirroring the README's feature set: setup, auth, import, tagging,
reports, and exports. Handlers are placeholders — the wiring and contracts are
real, the business logic is not implemented yet.
"""
from fastapi import APIRouter, UploadFile

api_router = APIRouter()


@api_router.get("/health")
def health() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


@api_router.get("/setup/status")
def setup_status() -> dict:
    """Whether first-run setup (owner + passphrase + ledger) is complete."""
    return {"initialized": False}


@api_router.post("/setup")
def first_run_setup() -> dict:
    """Create the Owner account, derive the encryption key, name the ledger."""
    raise NotImplementedError


@api_router.post("/auth/login")
def login() -> dict:
    """Exchange credentials for a JWT session token."""
    raise NotImplementedError


@api_router.post("/transactions/import")
def import_qfx(file: UploadFile) -> dict:
    """Import a QFX file. Deduplicates on transaction ID across overlaps."""
    raise NotImplementedError


@api_router.get("/transactions")
def list_transactions() -> list:
    """List ledger transactions across all accounts."""
    raise NotImplementedError


@api_router.post("/transactions/{txn_id}/tag")
def tag_transaction(txn_id: str) -> dict:
    """Tag a transaction Personal/Business and assign a Schedule C category."""
    raise NotImplementedError


@api_router.get("/reports/pnl")
def pnl_report() -> dict:
    """Profit & loss report for a time period."""
    raise NotImplementedError


@api_router.get("/reports/schedule-c")
def schedule_c_summary() -> dict:
    """Schedule C summary by line item."""
    raise NotImplementedError


@api_router.get("/export/{fmt}")
def export(fmt: str) -> dict:
    """Export the ledger as TXF, CSV, or PDF."""
    raise NotImplementedError
