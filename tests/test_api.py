"""End-to-end API tests for setup, encryption unlock, auth/roles, and QFX import.

Skipped automatically when the runtime dependencies (FastAPI, SQLCipher, etc.)
are not installed, so the pure-logic tests can still run in a bare environment.
"""
import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlcipher3")
pytest.importorskip("ofxparse")

from fastapi.testclient import TestClient  # noqa: E402

from backend.app.core.config import settings  # noqa: E402
from backend.app.core.runtime import runtime  # noqa: E402
from backend.app.db import database  # noqa: E402
from backend.main import app  # noqa: E402


SAMPLE_QFX = """OFXHEADER:100
DATA:OFXSGML
VERSION:102

<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>
<CURDEF>USD<BANKACCTFROM><BANKID>123<ACCTID>999<ACCTTYPE>CHECKING</BANKACCTFROM>
<BANKTRANLIST>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260115<TRNAMT>-12.50<FITID>T1<NAME>COFFEE</STMTTRN>
<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>20260116<TRNAMT>-30.00<FITID>T2<NAME>FUEL</STMTTRN>
</BANKTRANLIST></STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>
"""


@pytest.fixture()
def client(tmp_path):
    # Point the app at a fresh, empty data dir and reset runtime/DB state — this
    # exercises the real lock/unlock lifecycle without reloading modules.
    settings.data_dir = tmp_path
    settings.passphrase = None
    database.dispose()
    runtime.lock()
    with TestClient(app) as c:  # context manager runs the startup lifespan
        yield c
    database.dispose()
    runtime.lock()


def _setup(client):
    return client.post("/api/setup", json={
        "owner_username": "owner", "owner_password": "supersecret",
        "passphrase": "correct horse battery", "ledger_name": "Acme LLC",
        "first_account": {"nickname": "Checking"},
    })


def test_setup_creates_owner_and_returns_usable_token(client):
    assert client.get("/api/setup/status").json() == {"initialized": False, "unlocked": False}

    r = _setup(client)
    assert r.status_code == 201
    token = r.json()["access_token"]

    me = client.get("/api/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "owner"

    # Setup is one-time: a second attempt is rejected.
    assert _setup(client).status_code == 409


def test_wrong_passphrase_rejected_after_restart(client):
    _setup(client)
    # Simulate a restart: the key is gone from memory and the DB relocks.
    database.dispose()
    runtime.lock()

    assert client.get("/api/setup/status").json()["unlocked"] is False
    assert client.post("/api/unlock", json={"passphrase": "wrong"}).status_code == 401
    assert client.post("/api/unlock", json={"passphrase": "correct horse battery"}).status_code == 204
    # Locked state blocks data access until unlocked.


def test_locked_database_blocks_data_endpoints(client):
    _setup(client)
    database.dispose()
    runtime.lock()
    # 503 while locked, regardless of token.
    assert client.get("/api/transactions").status_code == 503


def test_roles_enforced(client):
    owner_token = _setup(client).json()["access_token"]
    auth = {"Authorization": f"Bearer {owner_token}"}

    r = client.post("/api/users", headers=auth,
                    json={"username": "v", "password": "viewerpass", "role": "viewer"})
    assert r.status_code == 201

    viewer_token = client.post("/api/auth/login",
                               json={"username": "v", "password": "viewerpass"}).json()["access_token"]
    vauth = {"Authorization": f"Bearer {viewer_token}"}

    # Viewer cannot manage users or create accounts, but can read.
    assert client.get("/api/users", headers=vauth).status_code == 403
    assert client.post("/api/accounts", headers=vauth, json={"nickname": "X"}).status_code == 403
    assert client.get("/api/accounts", headers=vauth).status_code == 200


def test_qfx_import_dedupes_on_reimport(client):
    owner_token = _setup(client).json()["access_token"]
    auth = {"Authorization": f"Bearer {owner_token}"}
    account_id = client.get("/api/accounts", headers=auth).json()[0]["id"]

    data = {"account_id": str(account_id)}
    r1 = client.post("/api/transactions/import", headers=auth,
                     files={"file": ("stmt.qfx", SAMPLE_QFX, "application/x-ofx")}, data=data)
    assert r1.status_code == 201
    assert r1.json() == {"parsed": 2, "imported": 2, "duplicates": 0}

    # Re-importing the overlapping window imports nothing new.
    r2 = client.post("/api/transactions/import", headers=auth,
                     files={"file": ("stmt.qfx", SAMPLE_QFX, "application/x-ofx")}, data=data)
    assert r2.json() == {"parsed": 2, "imported": 0, "duplicates": 2}

    assert len(client.get("/api/transactions", headers=auth).json()) == 2
