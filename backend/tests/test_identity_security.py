"""Unit tests for identity cryptographic helpers and strict Pydantic schemas."""

import pytest
from pydantic import ValidationError

from app.modules.identity.schemas import CreateOrganizationRequest, SetupRequest
from app.modules.identity.security import (
    generate_opaque_token,
    hash_password,
    hash_token,
    verify_bootstrap_token,
    verify_password,
)


def test_argon2_password_hash_and_verify() -> None:
    hashed = hash_password("super-secret-pass-2026")
    assert hashed != "super-secret-pass-2026"
    assert verify_password("super-secret-pass-2026", hashed) is True
    assert verify_password("wrong-password", hashed) is False


def test_opaque_token_and_sha256_hash() -> None:
    token_a = generate_opaque_token()
    token_b = generate_opaque_token()
    assert token_a != token_b
    assert len(hash_token(token_a)) == 64
    assert hash_token(token_a) == hash_token(token_a)


def test_bootstrap_token_verification() -> None:
    assert verify_bootstrap_token(None, None) is True
    assert verify_bootstrap_token(None, "expected-secret") is False
    assert verify_bootstrap_token("wrong", "expected-secret") is False
    assert verify_bootstrap_token("expected-secret", "expected-secret") is True


def test_organization_slug_validation_rejects_invalid_values() -> None:
    valid = CreateOrganizationRequest(name="Sushell Core", slug="sushell-core")
    assert valid.slug == "sushell-core"

    for bad_slug in ["A", "-leading", "trailing-", "Upper_Case", "space slug"]:
        with pytest.raises(ValidationError):
            CreateOrganizationRequest(name="Bad Org", slug=bad_slug)


def test_setup_request_enforces_password_length() -> None:
    with pytest.raises(ValidationError):
        SetupRequest(
            full_name="Admin User",
            email="admin@example.com",
            password="short",
            organization_name="Sushell",
            organization_slug="sushell",
        )
