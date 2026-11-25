"""Git provider integrations (GitHub, GitLab and headless OriginLabs Git)."""

from dataclasses import dataclass
from typing import Literal, Protocol

import httpx


@dataclass(frozen=True, slots=True)
class GitVerificationResult:
    """Result of verifying credentials against a Git provider."""

    ok: bool
    account_login: str | None = None
    error: str | None = None


@dataclass(frozen=True, slots=True)
class GitRepoSummary:
    """Normalized repository descriptor returned across providers."""

    full_name: str
    clone_url: str
    default_branch: str
    private: bool
    provider: Literal["github", "gitlab", "internal"]


class GitProviderClient(Protocol):
    """Unified contract for listing and verifying repositories."""

    async def verify_credentials(self) -> GitVerificationResult:
        """Verify provider token/connection."""
        ...

    async def list_repositories(
        self,
        *,
        query: str | None = None,
        limit: int = 50,
    ) -> list[GitRepoSummary]:
        """List accessible repositories."""
        ...


class GitHubProvider:
    """GitHub REST API v3 provider."""

    def __init__(self, *, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def verify_credentials(self) -> GitVerificationResult:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/user", headers=self._headers())
        except httpx.HTTPError as exc:
            return GitVerificationResult(ok=False, error=f"Error conectando a GitHub: {exc}")

        if resp.status_code != 200:
            return GitVerificationResult(
                ok=False,
                error=f"GitHub rechazó las credenciales (HTTP {resp.status_code}).",
            )
        data = resp.json()
        login = data.get("login") if isinstance(data, dict) else None
        return GitVerificationResult(ok=True, account_login=str(login) if login else None)

    async def list_repositories(
        self,
        *,
        query: str | None = None,
        limit: int = 50,
    ) -> list[GitRepoSummary]:
        per_page = min(max(limit, 1), 100)
        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                f"{self.base_url}/user/repos",
                headers=self._headers(),
                params={
                    "sort": "updated",
                    "per_page": per_page,
                    "affiliation": "owner,collaborator,organization_member",
                },
            )
            resp.raise_for_status()
            items = resp.json()

        q = query.strip().lower() if query else ""
        repos: list[GitRepoSummary] = []
        if not isinstance(items, list):
            return repos

        for item in items:
            if not isinstance(item, dict):
                continue
            full_name = str(item.get("full_name", ""))
            clone_url = str(item.get("clone_url", ""))
            if not full_name or not clone_url:
                continue
            if q and q not in full_name.lower():
                continue
            repos.append(
                GitRepoSummary(
                    full_name=full_name,
                    clone_url=clone_url,
                    default_branch=str(item.get("default_branch") or "main"),
                    private=bool(item.get("private", False)),
                    provider="github",
                )
            )
        return repos


class GitLabProvider:
    """GitLab REST API v4 provider (gitlab.com or self-hosted)."""

    def __init__(self, *, base_url: str, token: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict[str, str]:
        return {"PRIVATE-TOKEN": self.token}

    async def verify_credentials(self) -> GitVerificationResult:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/api/v4/user", headers=self._headers())
        except httpx.HTTPError as exc:
            return GitVerificationResult(ok=False, error=f"Error conectando a GitLab: {exc}")

        if resp.status_code != 200:
            return GitVerificationResult(
                ok=False,
                error=f"GitLab rechazó las credenciales (HTTP {resp.status_code}).",
            )
        data = resp.json()
        username = data.get("username") if isinstance(data, dict) else None
        return GitVerificationResult(ok=True, account_login=str(username) if username else None)

    async def list_repositories(
        self,
        *,
        query: str | None = None,
        limit: int = 50,
    ) -> list[GitRepoSummary]:
        per_page = min(max(limit, 1), 100)
        params: dict[str, str | int | bool] = {
            "membership": True,
            "order_by": "last_activity_at",
            "per_page": per_page,
        }
        if query and query.strip():
            params["search"] = query.strip()

        async with httpx.AsyncClient(timeout=12.0) as client:
            resp = await client.get(
                f"{self.base_url}/api/v4/projects",
                headers=self._headers(),
                params=params,
            )
            resp.raise_for_status()
            items = resp.json()

        repos: list[GitRepoSummary] = []
        if not isinstance(items, list):
            return repos

        for item in items:
            if not isinstance(item, dict):
                continue
            full_name = str(item.get("path_with_namespace", ""))
            clone_url = str(item.get("http_url_to_repo", ""))
            if not full_name or not clone_url:
                continue
            visibility = str(item.get("visibility", "private"))
            repos.append(
                GitRepoSummary(
                    full_name=full_name,
                    clone_url=clone_url,
                    default_branch=str(item.get("default_branch") or "main"),
                    private=visibility != "public",
                    provider="gitlab",
                )
            )
        return repos


class InternalGitProvider:
    """Headless OriginLabs Git adapter reserved for internal Forgejo/Gitea integration."""

    def __init__(self, *, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")

    async def verify_credentials(self) -> GitVerificationResult:
        return GitVerificationResult(ok=True, account_login="originlabs-git")

    async def list_repositories(
        self,
        *,
        query: str | None = None,
        limit: int = 50,
    ) -> list[GitRepoSummary]:
        _ = (query, limit)
        return []


def default_base_url_for_provider(provider: Literal["github", "gitlab", "internal"]) -> str:
    """Return canonical default API base URL for each Git provider."""
    if provider == "github":
        return "https://api.github.com"
    if provider == "gitlab":
        return "https://gitlab.com"
    return "http://originlabs-git.internal"


def get_git_provider(
    *,
    provider: Literal["github", "gitlab", "internal"],
    base_url: str,
    token: str | None,
) -> GitProviderClient:
    """Instantiate the appropriate Git provider client."""
    if provider == "github":
        if not token:
            raise ValueError("Se requiere un token para conectar GitHub.")
        return GitHubProvider(base_url=base_url, token=token)
    if provider == "gitlab":
        if not token:
            raise ValueError("Se requiere un token para conectar GitLab.")
        return GitLabProvider(base_url=base_url, token=token)
    return InternalGitProvider(base_url=base_url)


def build_ephemeral_git_env(
    *,
    provider: Literal["github", "gitlab", "internal"],
    token: str | None,
) -> dict[str, str]:
    """Build non-persistent environment hints for ephemeral Git clone/fetch in workspaces."""
    if not token:
        return {"GIT_TERMINAL_PROMPT": "0"}
    username = "x-access-token" if provider == "github" else "oauth2"
    return {
        "GIT_TERMINAL_PROMPT": "0",
        "ORIGINLABS_GIT_USER": username,
        "ORIGINLABS_GIT_TOKEN": token,
    }
