"""Security primitives: password hashing and JWT session tokens.

- The database encryption key is derived from the user's passphrase by
  SQLCipher's built-in KDF (PBKDF2-HMAC-SHA512) when the connection is keyed —
  see db/database.py. The passphrase is never stored.
- User account passwords are hashed with bcrypt.
- Sessions are stateless JWTs signed with a per-install secret (generated at
  setup, stored in the encrypted DB, held in memory after unlock) and a
  configurable expiration.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
from jose import JWTError, jwt

from backend.app.core.config import settings
from backend.app.core.runtime import runtime

_ALGORITHM = "HS256"


def _encode(password: str) -> bytes:
    # bcrypt hashes at most 72 bytes; truncate to stay within that limit.
    return password.encode("utf-8")[:72]


def hash_password(password: str) -> str:
    """Bcrypt-hash a user account password."""
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt()).decode("ascii")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(_encode(password), hashed.encode("ascii"))
    except ValueError:
        return False


def create_access_token(*, username: str, user_id: int, role: str) -> str:
    """Issue a JWT session token honoring the configured timeout."""
    if not runtime.jwt_secret:
        raise RuntimeError("JWT secret unavailable; database is locked")
    now = datetime.now(timezone.utc)
    claims = {
        "sub": username,
        "uid": user_id,
        "role": role,
        "iat": now,
        "exp": now + timedelta(seconds=settings.session_timeout),
    }
    return jwt.encode(claims, runtime.jwt_secret, algorithm=_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    """Decode and verify a session token. Returns claims, or None if invalid."""
    if not runtime.jwt_secret:
        return None
    try:
        return jwt.decode(token, runtime.jwt_secret, algorithms=[_ALGORITHM])
    except JWTError:
        return None
