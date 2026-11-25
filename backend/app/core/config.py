"""Application configuration loaded from environment variables."""

from functools import lru_cache
import ipaddress
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for OriginLabs Core API and workers."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "OriginLabs Core API"
    app_version: str = "0.1.0-alpha"
    originlabs_env: str = "development"
    originlabs_domain: str = "localhost"
    originlabs_secret_key: str = "change-me-in-production"
    originlabs_encryption_key: str | None = None
    originlabs_bootstrap_token: str | None = None
    originlabs_release_channel: Literal["stable", "beta"] = "stable"
    originlabs_releases_url: str | None = None
    originlabs_releases_public_key: str | None = None

    database_url: str = (
        "postgresql+asyncpg://originlabs:originlabs_dev_password@postgres:5432/originlabs"
    )
    redis_url: str = "redis://redis:6379/0"
    caddy_admin_url: str = "http://caddy:2019"

    session_cookie_name: str = "originlabs_session"
    session_ttl_seconds: int = 60 * 60 * 24 * 7
    session_cookie_secure: bool | None = None
    session_cookie_domain: str | None = None

    cors_origins: list[str] = ["http://localhost", "http://localhost:5173"]

    @field_validator(
        "originlabs_bootstrap_token",
        "originlabs_encryption_key",
        "originlabs_releases_url",
        "originlabs_releases_public_key",
        "session_cookie_domain",
        mode="before",
    )
    @classmethod
    def _empty_str_to_none(cls, value: str | None) -> str | None:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def cookie_secure(self) -> bool:
        """Return whether session cookies must require HTTPS."""
        if self.session_cookie_secure is not None:
            return self.session_cookie_secure
        return self.originlabs_env == "production"

    @property
    def cookie_domain(self) -> str | None:
        """Return cookie domain enabling SSO across *.domain workspace subdomains."""
        if self.session_cookie_domain is not None:
            return self.session_cookie_domain
        host = self.originlabs_domain.split(":")[0].strip().lower()
        if not host or host == "localhost" or host.endswith(".localhost"):
            return None
        try:
            ipaddress.ip_address(host)
            return None
        except ValueError:
            return f".{host}"


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
