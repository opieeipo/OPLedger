"""SQLCipher-backed SQLAlchemy engine.

The database file is encrypted at rest with AES-256. The key is supplied at
runtime (derived from the user's passphrase, see core.security) via SQLCipher's
PRAGMA key. Swapping SQLite for PostgreSQL is a connection-string change in
settings.yaml — no model code changes required.
"""
from sqlalchemy import create_engine, event
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.app.core.config import settings

Base = declarative_base()

# pysqlcipher3 driver; the engine is created locked and unlocked per-connection
# with the runtime-derived key.
engine = create_engine(f"sqlite+pysqlcipher://:@/{settings.db_path}", future=True)

SessionLocal = sessionmaker(bind=engine, autoflush=False, future=True)


def unlock(key_hex: str) -> None:
    """Register the SQLCipher key applied to every new connection."""

    @event.listens_for(engine, "connect")
    def _set_key(dbapi_conn, _record):  # noqa: ANN001
        dbapi_conn.execute(f"PRAGMA key=\"x'{key_hex}'\"")
