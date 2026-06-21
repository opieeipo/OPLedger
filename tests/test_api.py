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


def _qfx(*txns: str) -> str:
    body = "\n".join(txns)
    return (
        "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\n\n"
        "<OFX><BANKMSGSRSV1><STMTTRNRS><STMTRS>"
        "<CURDEF>USD<BANKACCTFROM><BANKID>123<ACCTID>999<ACCTTYPE>CHECKING</BANKACCTFROM>"
        f"<BANKTRANLIST>{body}</BANKTRANLIST>"
        "</STMTRS></STMTTRNRS></BANKMSGSRSV1></OFX>\n"
    )


def _stmttrn(fitid: str, amount: str, name: str, dtposted: str = "20260115") -> str:
    return (
        f"<STMTTRN><TRNTYPE>DEBIT<DTPOSTED>{dtposted}<TRNAMT>{amount}"
        f"<FITID>{fitid}<NAME>{name}</STMTTRN>"
    )


SAMPLE_QFX = _qfx(
    _stmttrn("T1", "-12.50", "COFFEE", "20260115"),
    _stmttrn("T2", "-30.00", "FUEL", "20260116"),
)


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
    assert r1.json() == {"parsed": 2, "imported": 2, "duplicates": 0, "auto_tagged": 0}

    # Re-importing the overlapping window imports nothing new.
    r2 = client.post("/api/transactions/import", headers=auth,
                     files={"file": ("stmt.qfx", SAMPLE_QFX, "application/x-ofx")}, data=data)
    assert r2.json() == {"parsed": 2, "imported": 0, "duplicates": 2, "auto_tagged": 0}

    assert len(client.get("/api/transactions", headers=auth).json()) == 2


def test_schedule_c_categories_listed_and_validated(client):
    auth = {"Authorization": f"Bearer {_setup(client).json()['access_token']}"}
    account_id = client.get("/api/accounts", headers=auth).json()[0]["id"]

    cats = client.get("/api/categories", headers=auth).json()["categories"]
    assert "Office expenses" in cats and "Advertising" in cats

    client.post("/api/transactions/import", headers=auth,
                files={"file": ("a.qfx", _qfx(_stmttrn("C1", "-9.00", "STAPLES")), "x")},
                data={"account_id": str(account_id)})
    txn_id = client.get("/api/transactions", headers=auth).json()[0]["id"]

    # A configured category is accepted; an unknown one is rejected.
    ok = client.post(f"/api/transactions/{txn_id}/tag", headers=auth,
                     json={"txn_type": "business", "schedule_c_category": "Office expenses"})
    assert ok.status_code == 200
    bad = client.post(f"/api/transactions/{txn_id}/tag", headers=auth,
                      json={"txn_type": "business", "schedule_c_category": "Yacht maintenance"})
    assert bad.status_code == 400


def test_reports_pnl_schedule_c_and_yoy(client):
    auth = {"Authorization": f"Bearer {_setup(client).json()['access_token']}"}
    account_id = client.get("/api/accounts", headers=auth).json()[0]["id"]

    qfx = _qfx(
        _stmttrn("R1", "1000.00", "CLIENT PAYMENT", "20260201"),  # income
        _stmttrn("R2", "-200.00", "OFFICE DEPOT", "20260205"),    # expense
        _stmttrn("R3", "-50.00", "DELTA AIR", "20260210"),        # expense
    )
    client.post("/api/transactions/import", headers=auth,
                files={"file": ("r.qfx", qfx, "x")}, data={"account_id": str(account_id)})

    txns = {t["fitid"]: t for t in client.get("/api/transactions", headers=auth).json()}
    client.post(f"/api/transactions/{txns['R1']['id']}/tag", headers=auth,
                json={"txn_type": "business"})
    client.post(f"/api/transactions/{txns['R2']['id']}/tag", headers=auth,
                json={"txn_type": "business", "schedule_c_category": "Office expenses"})
    client.post(f"/api/transactions/{txns['R3']['id']}/tag", headers=auth,
                json={"txn_type": "business", "schedule_c_category": "Travel"})

    pnl = client.get("/api/reports/pnl", headers=auth,
                     params={"start": "2026-01-01", "end": "2026-12-31"}).json()
    assert float(pnl["income"]) == 1000 and float(pnl["expenses"]) == 250
    assert float(pnl["net"]) == 750
    cats = {c["category"]: float(c["amount"]) for c in pnl["by_category"]}
    assert cats == {"Office expenses": 200, "Travel": 50}

    sc = client.get("/api/reports/schedule-c", headers=auth, params={"year": 2026}).json()
    assert float(sc["gross_receipts"]) == 1000 and float(sc["net_profit"]) == 750

    yoy = client.get("/api/reports/year-over-year", headers=auth,
                     params={"start_year": 2025, "end_year": 2026}).json()
    by_year = {y["year"]: float(y["net"]) for y in yoy["years"]}
    assert by_year == {2025: 0, 2026: 750}


def test_multi_account_ledger_filter(client):
    auth = {"Authorization": f"Bearer {_setup(client).json()['access_token']}"}
    checking = client.get("/api/accounts", headers=auth).json()[0]["id"]
    card = client.post("/api/accounts", headers=auth, json={"nickname": "Card"}).json()["id"]

    client.post("/api/transactions/import", headers=auth,
                files={"file": ("a.qfx", _qfx(_stmttrn("M1", "-5.00", "A")), "x")},
                data={"account_id": str(checking)})
    client.post("/api/transactions/import", headers=auth,
                files={"file": ("b.qfx", _qfx(_stmttrn("M2", "-9.00", "B")), "x")},
                data={"account_id": str(card)})

    # Combined ledger shows both; filtering narrows to one account.
    assert len(client.get("/api/transactions", headers=auth).json()) == 2
    only_card = client.get("/api/transactions", headers=auth, params={"account_id": card}).json()
    assert [t["fitid"] for t in only_card] == ["M2"]


def test_external_database_mode_skips_passphrase(tmp_path, monkeypatch):
    # A non-SQLCipher database_url selects external mode (same code path as
    # PostgreSQL): connect at startup, no passphrase, no unlock screen.
    monkeypatch.setenv("OPLEDGER_DATABASE_URL", f"sqlite:///{tmp_path/'ext.db'}")
    settings.data_dir = tmp_path
    settings.passphrase = None
    database.dispose()
    runtime.lock()
    with TestClient(app) as c:
        assert c.get("/api/setup/status").json() == {"initialized": False, "unlocked": True}

        r = c.post("/api/setup", json={
            "owner_username": "owner", "owner_password": "supersecret",
            "ledger_name": "Acme",  # note: no passphrase
        })
        assert r.status_code == 201
        auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
        assert c.get("/api/me", headers=auth).json()["role"] == "owner"

        assert c.post("/api/unlock", json={"passphrase": "x"}).status_code == 400
        assert c.get("/api/setup/status").json()["initialized"] is True
    database.dispose()
    runtime.lock()


def test_recurring_detection(client):
    auth = {"Authorization": f"Bearer {_setup(client).json()['access_token']}"}
    account_id = client.get("/api/accounts", headers=auth).json()[0]["id"]
    qfx = _qfx(
        _stmttrn("N1", "-15.99", "NETFLIX", "20260115"),
        _stmttrn("N2", "-15.99", "NETFLIX", "20260215"),
        _stmttrn("N3", "-15.99", "NETFLIX", "20260315"),
        _stmttrn("Z1", "-4.00", "ONE OFF", "20260101"),  # not recurring
    )
    client.post("/api/transactions/import", headers=auth,
                files={"file": ("n.qfx", qfx, "x")}, data={"account_id": str(account_id)})

    series = client.get("/api/transactions/recurring", headers=auth).json()
    assert len(series) == 1
    assert series[0]["payee"] == "NETFLIX"
    assert series[0]["cadence"] == "monthly"
    assert series[0]["occurrences"] == 3


def test_exports_csv_txf_pdf(client):
    auth = {"Authorization": f"Bearer {_setup(client).json()['access_token']}"}
    account_id = client.get("/api/accounts", headers=auth).json()[0]["id"]
    qfx = _qfx(
        _stmttrn("X1", "1000.00", "CLIENT", "20260301"),
        _stmttrn("X2", "-200.00", "OFFICE DEPOT", "20260305"),
    )
    client.post("/api/transactions/import", headers=auth,
                files={"file": ("x.qfx", qfx, "x")}, data={"account_id": str(account_id)})
    txns = {t["fitid"]: t for t in client.get("/api/transactions", headers=auth).json()}
    client.post(f"/api/transactions/{txns['X1']['id']}/tag", headers=auth,
                json={"txn_type": "business"})
    client.post(f"/api/transactions/{txns['X2']['id']}/tag", headers=auth,
                json={"txn_type": "business", "schedule_c_category": "Office expenses"})

    csv_res = client.get("/api/export/csv", headers=auth)
    assert csv_res.status_code == 200
    assert csv_res.headers["content-type"].startswith("text/csv")
    body = csv_res.text
    assert "date,account,payee" in body and "OFFICE DEPOT" in body and "Checking" in body

    txf = client.get("/api/export/txf", headers=auth, params={"year": 2026})
    assert txf.status_code == 200
    assert "V042" in txf.text and "$200.00" in txf.text and "N301" in txf.text  # Office expenses
    assert "N287" in txf.text  # gross receipts

    pdf = client.get("/api/export/pdf", headers=auth, params={"year": 2026})
    assert pdf.status_code == 200
    assert pdf.headers["content-type"] == "application/pdf"
    assert pdf.content[:5] == b"%PDF-"


def test_tagging_is_remembered_and_applied_on_next_import(client):
    auth = {"Authorization": f"Bearer {_setup(client).json()['access_token']}"}
    account_id = client.get("/api/accounts", headers=auth).json()[0]["id"]

    # Import a transaction from STARBUCKS and tag it business/Office expenses.
    client.post("/api/transactions/import", headers=auth,
                files={"file": ("a.qfx", _qfx(_stmttrn("S1", "-5.00", "STARBUCKS")), "x")},
                data={"account_id": str(account_id)})
    txn = client.get("/api/transactions", headers=auth).json()[0]
    client.post(f"/api/transactions/{txn['id']}/tag", headers=auth,
                json={"txn_type": "business", "schedule_c_category": "Office expenses"})

    # A new transaction from the same payee imports pre-tagged.
    r = client.post("/api/transactions/import", headers=auth,
                    files={"file": ("b.qfx", _qfx(_stmttrn("S2", "-6.00", "STARBUCKS")), "x")},
                    data={"account_id": str(account_id)})
    assert r.json()["auto_tagged"] == 1

    s2 = [t for t in client.get("/api/transactions", headers=auth).json() if t["fitid"] == "S2"][0]
    assert s2["txn_type"] == "business"
    assert s2["schedule_c_category"] == "Office expenses"
