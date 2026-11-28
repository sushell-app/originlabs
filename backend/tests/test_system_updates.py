"""Unit tests for release semver comparison, Ed25519 verification and webhook schema."""

import base64

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from app.modules.system.schemas import SmtpConfigUpdateRequest, UpdateSettingsRequest
from app.modules.system.smtp import build_email_message, validate_smtp_host
from app.modules.system.updater import (
    DEFAULT_IMAGE_REPO,
    build_updater_container_spec,
    validate_target_version,
)
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


def test_updater_container_spec_validation_and_security() -> None:
    assert validate_target_version("v0.1.1") == "0.1.1"
    spec = build_updater_container_spec(
        target_version="v0.1.1",
        working_dir="/opt/originlabs",
        compose_file="/opt/originlabs/compose.prod.yml",
        project_name="originlabs",
        nonce="deadbeef",
    )
    assert spec["name"] == "originlabs-updater-deadbeef"
    assert spec["auto_remove"] is True
    assert spec["environment"]["DOCKER_HOST"] == "tcp://docker-proxy:2375"
    assert spec["environment"]["ORIGINLABS_TARGET_IMAGE"] == f"{DEFAULT_IMAGE_REPO}:0.1.1"
    assert "--no-deps" in spec["command"][-1]

    with pytest.raises(ValueError):
        validate_target_version("0.1.1; rm -rf /")

    with pytest.raises(ValueError):
        build_updater_container_spec(
            target_version="0.1.1",
            working_dir="/opt/originlabs;id",
            compose_file="/opt/originlabs/compose.prod.yml",
            project_name="originlabs",
        )


def test_smtp_validation_and_message_builder() -> None:
    assert validate_smtp_host("smtp.gmail.com") == "smtp.gmail.com"
    with pytest.raises(ValueError):
        validate_smtp_host("smtp.example.com;id")

    with pytest.raises(ValidationError):
        SmtpConfigUpdateRequest(use_tls=True, use_ssl=True)

    msg = build_email_message(
        from_name="OriginLabs",
        from_email="noreply@example.com",
        to_email="admin@example.com",
        subject="Prueba SMTP",
        body_text="Hola mundo",
    )
    assert msg["Subject"] == "Prueba SMTP"
    with pytest.raises(ValueError):
        build_email_message(
            from_name="OriginLabs",
            from_email="noreply@example.com",
            to_email="admin@example.com",
            subject="Bad\r\nBcc: evil@example.com",
            body_text="Hola",
        )
