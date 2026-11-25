"""Unit tests for encryption at rest, Projects sanitization schemas and internal Git."""

from pydantic import ValidationError
import pytest

from app.core.crypto import decrypt_secret, encrypt_secret, mask_secret
from app.modules.projects.git_providers import InternalGitProvider, build_ephemeral_git_env
from app.modules.projects.schemas import ProjectCreateRequest, ProjectEnvVarUpsertRequest


def test_encrypt_decrypt_roundtrip_and_mask() -> None:
    secret = "test_example_secret_token_123456"
    ciphertext = encrypt_secret(secret)
    assert ciphertext != secret
    assert decrypt_secret(ciphertext) == secret
    assert mask_secret(secret) == "••••••••"


def test_project_schema_blocks_unsafe_branch_and_urls() -> None:
    valid = ProjectCreateRequest(
        name="OriginLabs Core",
        slug="originlabs-core",
        repo_clone_url="https://github.com/sushell/originlabs.git",
        default_branch="feature/module-4",
    )
    assert valid.default_branch == "feature/module-4"

    for bad_branch in ["-c", "--upload-pack=evil", "main..dev", "feature//bad"]:
        with pytest.raises(ValidationError):
            ProjectCreateRequest(
                name="Bad Branch",
                slug="bad-branch",
                default_branch=bad_branch,
            )

    for bad_url in [
        "http://github.com/org/repo.git",
        "https://user:pass@github.com/org/repo.git",
        "file:///etc/passwd",
    ]:
        with pytest.raises(ValidationError):
            ProjectCreateRequest(
                name="Bad URL",
                slug="bad-url",
                repo_clone_url=bad_url,
            )


def test_env_var_key_validation() -> None:
    valid = ProjectEnvVarUpsertRequest(key="DATABASE_URL", value="postgres://...", is_secret=True)
    assert valid.key == "DATABASE_URL"

    for bad_key in ["lowercase", "1STARTS_NUM", "BAD-KEY", "SPACE KEY"]:
        with pytest.raises(ValidationError):
            ProjectEnvVarUpsertRequest(key=bad_key, value="val")


async def test_internal_git_provider_contract_and_ephemeral_env() -> None:
    provider = InternalGitProvider(base_url="http://originlabs-git.internal")
    verification = await provider.verify_credentials()
    assert verification.ok is True
    assert verification.account_login == "originlabs-git"
    assert await provider.list_repositories() == []

    env = build_ephemeral_git_env(provider="github", token="test_provider_token")
    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert env["ORIGINLABS_GIT_USER"] == "x-access-token"
