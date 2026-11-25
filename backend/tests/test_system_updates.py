"""Unit tests for release semver comparison, Ed25519 verification and webhook schema."""

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from app.modules.system.schemas import UpdateSettingsRequest
from app.modules.system.updates import (
    canonical_manifest_bytes,
    is_newer_version,
    verify_manifest_signature,
)


def test_semver_comparison_handles_prereleases() -> None:
    assert is_newer_version("0.1.0-alpha", "0.1.0") is True
    assert is_newer_version("0.1.0-alpha", "0.2.0") is True
    assert is_newer_version("0.2.0", "0.2.0-beta.1") is False
    assert is_newer_version("0.2.0", "0.2.0") is False


def test_ed25519_manifest_signature_verification() -> None:
    private_key = Ed25519PrivateKey.generate()
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    pub_b64 = base64.b64encode(pub_bytes).decode("ascii")

    manifest = {
        "schema_version": 1,
        "channels": {
            "stable": {"version": "0.2.0", "severity": "security"},
        },
    }
    signature_b64 = base64.b64encode(
        private_key.sign(canonical_manifest_bytes(manifest))
    ).decode("ascii")

    assert verify_manifest_signature(manifest, signature_b64, pub_b64) is True

    tampered = {
        "schema_version": 1,
        "channels": {
            "stable": {"version": "9.9.9", "severity": "normal"},
        },
    }
    assert verify_manifest_signature(tampered, signature_b64, pub_b64) is False


def test_webhook_url_requires_https() -> None:
    valid = UpdateSettingsRequest(webhook_url="https://hooks.example.com/originlabs")
    assert valid.webhook_url == "https://hooks.example.com/originlabs"

    with pytest.raises(ValidationError):
        UpdateSettingsRequest(webhook_url="http://insecure.example.com/hook")
