"""Security primitives: passphrase-derived encryption key, password hashing,
and JWT session tokens.

- The database encryption key is derived from the user's passphrase via PBKDF2
  and held only in memory. The passphrase itself is never stored.
- User account passwords are hashed with bcrypt.
- Sessions are stateless JWTs with a configurable expiration.
"""
import hashlib

from passlib.context import CryptContext

from backend.app.core.config import settings

_pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# PBKDF2 parameters for deriving the SQLCipher key from the passphrase.
_PBKDF2_ITERATIONS = 256_000
_KEY_LENGTH = 32  # 256-bit key for AES-256


def hash_password(password: str) -> str:
    """Bcrypt-hash a user account password."""
    return _pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _pwd_context.verify(password, hashed)


def derive_db_key(passphrase: str, salt: bytes) -> bytes:
    """Derive the AES-256 database key from the passphrase via PBKDF2.

    The result unlocks the SQLCipher database and exists only in memory.
    """
    return hashlib.pbkdf2_hmac(
        "sha256", passphrase.encode("utf-8"), salt, _PBKDF2_ITERATIONS, _KEY_LENGTH
    )


def create_session_token(subject: str) -> str:
    """Issue a JWT session token for the given user, honoring the timeout."""
    raise NotImplementedError  # uses settings.jwt_secret + settings.session_timeout
