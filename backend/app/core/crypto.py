"""Symmetric encryption at rest for Git tokens, project env vars and secrets."""

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _build_fernet() -> Fernet:
    """Derive a 32-byte Fernet key from ORIGINLABS_ENCRYPTION_KEY (or secret_key in dev)."""
    settings = get_settings()
    raw_key = settings.originlabs_encryption_key
    if not raw_key:
        if settings.originlabs_env == "production":
            raise RuntimeError(
                "ORIGINLABS_ENCRYPTION_KEY es obligatoria en producción para cifrar secretos."
            )
        raw_key = f"dev-encryption::{settings.originlabs_secret_key}"

    digest = hashlib.sha256(raw_key.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(digest)
    return Fernet(fernet_key)


def encrypt_secret(plaintext: str) -> str:
    """Encrypt a plaintext secret into a URL-safe Fernet token string."""
    token = _build_fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("utf-8")


def decrypt_secret(ciphertext: str) -> str:
    """Decrypt a Fernet-encrypted secret string."""
    try:
        raw = _build_fernet().decrypt(ciphertext.encode("utf-8"))
    except InvalidToken as exc:
        raise ValueError("No se pudo descifrar el secreto con la clave actual.") from exc
    return raw.decode("utf-8")


def mask_secret(value: str) -> str:
    """Return a fixed-length mask without leaking plaintext characters."""
    if not value:
        return ""
    return "••••••••"
