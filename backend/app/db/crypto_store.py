"""Cross-platform encryption-at-rest for the local SQLite database.

Replaces SQLCipher (a C extension with no Windows wheel) with the `cryptography`
library, which ships wheels for macOS, Linux, and Windows — so the app bundles
natively on all three. The whole SQLite database image is sealed with
AES-256-GCM; the key is derived from the user's passphrase with scrypt. The
passphrase is never stored; a wrong passphrase fails the GCM auth tag (no
decrypt), preserving the same unlock contract SQLCipher gave us.

On-disk format:  MAGIC(8) | version(1) | salt(16) | nonce(12) | ciphertext+tag
"""
from __future__ import annotations

import os

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.scrypt import Scrypt

_MAGIC = b"OPLCRYPT"
_VERSION = 1
_SALT_LEN = 16
_NONCE_LEN = 12
# scrypt work factor (CPU/memory hard). 2**15 keeps unlock well under a second.
_N, _R, _P = 2 ** 15, 8, 1


def _derive_key(passphrase: str, salt: bytes) -> bytes:
    kdf = Scrypt(salt=salt, length=32, n=_N, r=_R, p=_P)
    return kdf.derive(passphrase.encode("utf-8"))


def encrypt(plaintext: bytes, passphrase: str) -> bytes:
    """Seal a database image with a fresh salt + nonce."""
    salt = os.urandom(_SALT_LEN)
    nonce = os.urandom(_NONCE_LEN)
    key = _derive_key(passphrase, salt)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, _MAGIC)
    return _MAGIC + bytes([_VERSION]) + salt + nonce + ciphertext


def decrypt(blob: bytes, passphrase: str) -> bytes | None:
    """Return the database image, or None if the passphrase is wrong / data is
    tampered (GCM auth failure) or the header is unrecognized."""
    header = len(_MAGIC) + 1 + _SALT_LEN + _NONCE_LEN
    if len(blob) < header or blob[: len(_MAGIC)] != _MAGIC:
        return None
    i = len(_MAGIC) + 1  # skip magic + version
    salt = blob[i : i + _SALT_LEN]
    nonce = blob[i + _SALT_LEN : i + _SALT_LEN + _NONCE_LEN]
    ciphertext = blob[i + _SALT_LEN + _NONCE_LEN :]
    key = _derive_key(passphrase, salt)
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, _MAGIC)
    except Exception:
        return None
