"""SQLCipher-backed SQLAlchemy engine and unlock lifecycle.

The database file is encrypted at rest with AES-256 (SQLCipher). The encryption
key is derived from the user's passphrase by SQLCipher's own KDF
(PBKDF2-HMAC-SHA512, 256k iterations in SQLCipher 4) when the connection is
keyed. The passphrase is never stored; the derived key lives only inside the
open connection for the life of the process.

Because the key isn't known until the user supplies the passphrase (at first-run
setup or unlock), the engine is created lazily by ``open_database`` rather than
at import time. Until then the database is "locked" and no session can be made.

Swapping SQLite for PostgreSQL is a connection-string change (see
config/settings.yaml) — the models below are unaffected.
"""
from __future__ import annotations

import sqlcipher3

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings

Base = declarative_base()

# Lazily initialized on a successful unlock; None means the DB is locked.
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None


def is_external() -> bool:
    """True when configured for an external DB (e.g. PostgreSQL) rather than the
    local encrypted SQLCipher file. External databases need no passphrase/unlock;
    encryption at rest is the external store's responsibility."""
    url = settings.database_url
    return bool(url) and not url.startswith("sqlite+pysqlcipher")


def database_exists() -> bool:
    """Whether an encrypted database file is already present on disk."""
    return settings.db_path.exists()


def open_external() -> None:
    """Connect to the configured external database and ensure the schema."""
    global _engine, _SessionLocal
    from backend.app import models  # noqa: F401  (register models on Base)

    engine = create_engine(settings.database_url, future=True)
    Base.metadata.create_all(engine)
    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


def has_users() -> bool:
    """Whether any user exists (used to detect setup completion on external DBs)."""
    from backend.app.models.models import User

    session = new_session()
    try:
        return session.query(User).first() is not None
    finally:
        session.close()


def is_unlocked() -> bool:
    return _engine is not None


def _make_engine(passphrase: str) -> Engine:
    """Build an engine whose every connection is keyed with the passphrase.

    A single shared connection (StaticPool) keeps the derived key in one place
    and avoids SQLite write-lock contention at this app's scale.
    """
    db_path = str(settings.db_path)
    # Escape single quotes for the PRAGMA key string literal (SQLCipher derives
    # the key from this passphrase via PBKDF2 internally).
    escaped = passphrase.replace("'", "''")

    def _creator():
        conn = sqlcipher3.connect(db_path, check_same_thread=False)
        conn.execute(f"PRAGMA key = '{escaped}'")
        return conn

    return create_engine(
        "sqlite://",
        creator=_creator,
        poolclass=StaticPool,
        future=True,
    )


def open_database(passphrase: str, *, create: bool) -> bool:
    """Open and unlock the encrypted database with the given passphrase.

    Returns True on success. Returns False if the passphrase is wrong for an
    existing database (SQLCipher cannot decrypt the header). When ``create`` is
    True a new encrypted database is initialized with this passphrase and the
    schema is created.
    """
    global _engine, _SessionLocal

    engine = _make_engine(passphrase)
    try:
        # First access decrypts the header; a wrong key raises here.
        with engine.connect() as conn:
            conn.execute(text("SELECT count(*) FROM sqlite_master"))
    except Exception:
        engine.dispose()
        return False

    # create_all is idempotent: creates the schema on first run, and adds any
    # newly introduced tables on later upgrades. Import models so they register
    # on Base before create_all.
    from backend.app import models  # noqa: F401

    Base.metadata.create_all(engine)

    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)
    return True


def new_session():
    """Create a new ORM session. Raises if the database is locked."""
    if _SessionLocal is None:
        raise RuntimeError("Database is locked")
    return _SessionLocal()


def dispose() -> None:
    """Close the engine and drop the in-memory key, re-locking the database."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
