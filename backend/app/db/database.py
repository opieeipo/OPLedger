"""Encrypted SQLAlchemy engine and unlock lifecycle.

The local database is encrypted at rest with AES-256-GCM via the ``cryptography``
library (key derived from the user's passphrase with scrypt) — see crypto_store.
We chose this over SQLCipher because ``cryptography`` ships wheels for macOS,
Linux, and Windows, so the app bundles natively on all three; SQLCipher's C
extension has no Windows wheel. The passphrase is never stored, and a wrong
passphrase fails the GCM auth tag (same unlock contract SQLCipher gave us).

Mechanics: the encrypted blob on disk is decrypted into an in-memory SQLite
database on unlock; the image is re-sealed and written back atomically after
every commit (and on dispose). Because the key isn't known until the user
supplies the passphrase, the engine is created lazily by ``open_database``.

Swapping SQLite for PostgreSQL is a connection-string change (see
config/settings.yaml) — the models below are unaffected.
"""
from __future__ import annotations

import os
import sqlite3

from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.db import crypto_store

Base = declarative_base()

# Lazily initialized on a successful unlock; None means the DB is locked.
_engine: Engine | None = None
_SessionLocal: sessionmaker | None = None
# For the local encrypted store: the shared in-memory connection + passphrase,
# used to re-seal the database image to disk after writes.
_raw_conn: sqlite3.Connection | None = None
_passphrase: str | None = None


def is_external() -> bool:
    """True when configured for an external DB (e.g. PostgreSQL, or a plain
    unencrypted SQLite file) rather than the local encrypted store. The
    ``sqlite+pysqlcipher`` URL is the marker for the local encrypted store (kept
    for config compatibility; storage is now AES-256-GCM, not SQLCipher).
    External databases need no passphrase/unlock — encryption at rest is their
    responsibility."""
    url = settings.database_url
    return bool(url) and not url.startswith("sqlite+pysqlcipher")


def database_exists() -> bool:
    """Whether an encrypted database file is already present on disk."""
    return settings.db_path.exists()


def _persist() -> None:
    """Re-seal the in-memory database image to disk (atomic write)."""
    if _raw_conn is None or _passphrase is None:
        return
    blob = crypto_store.encrypt(_raw_conn.serialize(), _passphrase)
    path = settings.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_bytes(blob)
    os.replace(tmp, path)


@event.listens_for(Session, "after_commit")
def _seal_after_commit(_session: Session) -> None:
    # Fires for every ORM commit; no-op for the external (non-local) backend.
    _persist()


def _migrate(engine: Engine) -> None:
    """Idempotent additive migrations for ledgers created before a column existed.

    ``create_all`` adds new tables but never alters existing ones, and this app
    ships no migration framework — so we add late-arriving columns by hand. Each
    statement is guarded: a duplicate-column error just means it's already there.
    """
    additions = [
        "ALTER TABLE transactions ADD COLUMN personal_category VARCHAR",
    ]
    for stmt in additions:
        try:
            with engine.begin() as conn:
                conn.execute(text(stmt))
        except Exception:
            pass  # column already present (SQLite/Postgres raise on duplicate)


def open_external() -> None:
    """Connect to the configured external database and ensure the schema."""
    global _engine, _SessionLocal
    from backend.app import models  # noqa: F401  (register models on Base)

    engine = create_engine(settings.database_url, future=True)
    Base.metadata.create_all(engine)
    _migrate(engine)
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


def open_database(passphrase: str, *, create: bool) -> bool:
    """Open and unlock the encrypted database with the given passphrase.

    Returns True on success. Returns False if the passphrase is wrong for an
    existing database (the GCM auth tag won't verify) or no database exists and
    ``create`` is False. When ``create`` is True a new encrypted database is
    initialized with this passphrase and the schema is created.

    The encrypted image is decrypted into an in-memory SQLite database; writes
    are re-sealed to disk after each commit (see _seal_after_commit) and on
    dispose. A single shared connection (StaticPool) holds the live image.
    """
    global _engine, _SessionLocal, _raw_conn, _passphrase

    image: bytes | None = None
    if settings.db_path.exists():
        image = crypto_store.decrypt(settings.db_path.read_bytes(), passphrase)
        if image is None:
            return False  # wrong passphrase / tampered
    elif not create:
        return False

    conn = sqlite3.connect(":memory:", check_same_thread=False)
    if image is not None:
        conn.deserialize(image)

    engine = create_engine("sqlite://", creator=lambda: conn, poolclass=StaticPool, future=True)

    # create_all is idempotent (new schema on first run, new tables on upgrades);
    # _migrate adds late-arriving columns. Import models so they register on Base.
    from backend.app import models  # noqa: F401

    Base.metadata.create_all(engine)
    _migrate(engine)

    _engine = engine
    _SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)
    _raw_conn = conn
    _passphrase = passphrase
    _persist()  # write the encrypted image (initial create, or after a migration)
    return True


def new_session():
    """Create a new ORM session. Raises if the database is locked."""
    if _SessionLocal is None:
        raise RuntimeError("Database is locked")
    return _SessionLocal()


def dispose() -> None:
    """Seal the latest image to disk, close the engine, and re-lock the DB."""
    global _engine, _SessionLocal, _raw_conn, _passphrase
    try:
        _persist()
    except Exception:
        pass
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
    _raw_conn = None
    _passphrase = None
