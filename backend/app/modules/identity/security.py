"""Cryptographic helpers for password hashing and opaque tokens."""

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2id."""
    return str(_password_hasher.hash(password))


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against an Argon2id hash."""
    try:
        return bool(_password_hasher.verify(password_hash, password))
    except (VerifyMismatchError, InvalidHashError):
        return False


def generate_opaque_token() -> str:
    """Generate a URL-safe 256-bit opaque token."""
    return secrets.token_urlsafe(32)


def hash_token(raw_token: str) -> str:
    """Return SHA-256 hex digest for storing opaque session/invite tokens."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def verify_bootstrap_token(provided: str | None, expected: str | None) -> bool:
    """Validate optional bootstrap setup token in constant time."""
    if not expected:
        return True
    if not provided:
        return False
    return hmac.compare_digest(provided.strip(), expected.strip())
