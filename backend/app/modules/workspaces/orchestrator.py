"""Docker orchestration, cgroups limits, network isolation and Caddy dynamic routing."""

from dataclasses import dataclass
from typing import Any, Literal

import docker
import httpx
from docker.errors import DockerException, NotFound

WorkspaceClass = Literal["light", "standard", "heavy"]

WORKSPACES_NETWORK_NAME = "originlabs_workspaces"
DEFAULT_WORKSPACE_IMAGE = "codercom/code-server:4.96.2"
WORKSPACE_MOUNT_PATH = "/home/coder/project"


@dataclass(frozen=True, slots=True)
class WorkspaceClassSpec:
    """Resource quotas enforced via Docker cgroups for each workspace class."""

    cpu_cores: float
    ram_mb: int
    disk_gb: int
    pids_limit: int


WORKSPACE_CLASS_SPECS: dict[WorkspaceClass, WorkspaceClassSpec] = {
    "light": WorkspaceClassSpec(cpu_cores=1.0, ram_mb=2048, disk_gb=10, pids_limit=256),
    "standard": WorkspaceClassSpec(cpu_cores=2.0, ram_mb=4096, disk_gb=30, pids_limit=512),
    "heavy": WorkspaceClassSpec(cpu_cores=4.0, ram_mb=8192, disk_gb=30, pids_limit=1024),
}


def build_workspace_url(subdomain: str, domain: str, *, secure: bool) -> str:
    """Build external workspace IDE URL for a subdomain and instance base domain."""
    clean_host = domain.split(":")[0].strip().lower() or "localhost"
    scheme = "https" if secure else "http"
    return f"{scheme}://{subdomain}.{clean_host}"


def build_workspace_container_spec(
    *,
    workspace_id: str,
    organization_id: str,
    project_id: str,
    container_name: str,
    volume_name: str,
    workspace_class: WorkspaceClass,
    image: str = DEFAULT_WORKSPACE_IMAGE,
    env_vars: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Build hardened non-root Docker container spec without host Docker socket access."""
    spec = WORKSPACE_CLASS_SPECS[workspace_class]
    volumes: dict[str, dict[str, str]] = {
        volume_name: {"bind": WORKSPACE_MOUNT_PATH, "mode": "rw"},
    }
    for src, cfg in volumes.items():
        if "docker.sock" in src or "docker.sock" in cfg.get("bind", ""):
            raise ValueError("Está prohibido montar el socket Docker dentro de un workspace.")

    environment = {"HOME": "/home/coder", **(env_vars or {})}
    return {
        "image": image,
        "name": container_name,
        "detach": True,
        "user": "1000:1000",
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges:true"],
        "pids_limit": spec.pids_limit,
        "nano_cpus": int(spec.cpu_cores * 1_000_000_000),
        "mem_limit": f"{spec.ram_mb}m",
        "network": WORKSPACES_NETWORK_NAME,
        "volumes": volumes,
        "environment": environment,
        "command": ["--auth", "none", "--bind-addr", "0.0.0.0:8080", WORKSPACE_MOUNT_PATH],
        "labels": {
            "originlabs.managed": "true",
            "originlabs.workspace_id": workspace_id,
            "originlabs.organization_id": organization_id,
            "originlabs.project_id": project_id,
            "originlabs.workspace_class": workspace_class,
        },
    }


def build_caddy_workspace_route(
    *,
    workspace_id: str,
    host: str,
    container_name: str,
) -> dict[str, Any]:
    """Build Caddy JSON route guarded by internal forward_auth session validation."""
    return {
        "@id": f"originlabs-ws-{workspace_id}",
        "match": [{"host": [host]}],
        "handle": [
            {
                "handler": "subroute",
                "routes": [
                    {
                        "handle": [
                            {
                                "handler": "reverse_proxy",
                                "upstreams": [{"dial": "api:8000"}],
                                "rewrite": {"uri": "/api/v1/internal/forward-auth"},
                                "handle_response": [
                                    {
                                        "match": {"status_code": [2]},
                                        "routes": [],
                                    }
                                ],
                            },
                            {
                                "handler": "reverse_proxy",
                                "upstreams": [{"dial": f"{container_name}:8080"}],
                            },
                        ]
                    }
                ],
            }
        ],
    }


class WorkspaceOrchestrator:
    """Docker SDK + Caddy Admin API client for starting and stopping workspaces."""

    def __init__(self, *, caddy_admin_url: str) -> None:
        self.caddy_admin_url = caddy_admin_url.rstrip("/")

    def _docker_client(self) -> Any:
        try:
            return docker.from_env()
        except DockerException as exc:
            raise RuntimeError(
                f"Docker daemon no disponible para orquestar workspaces: {exc}"
            ) from exc

    def _ensure_network(self, client: Any) -> None:
        try:
            client.networks.get(WORKSPACES_NETWORK_NAME)
        except NotFound:
            client.networks.create(WORKSPACES_NETWORK_NAME, driver="bridge", check_duplicate=True)

    def start_container(
        self,
        *,
        workspace_id: str,
        organization_id: str,
        project_id: str,
        container_name: str,
        volume_name: str,
        workspace_class: WorkspaceClass,
        image: str,
        env_vars: dict[str, str],
    ) -> str:
        """Create or start an isolated workspace container and return its container ID."""
        client = self._docker_client()
        self._ensure_network(client)

        try:
            existing = client.containers.get(container_name)
            if existing.status != "running":
                existing.start()
            return str(existing.id)
        except NotFound:
            pass
        except DockerException as exc:
            raise RuntimeError(f"Error iniciando contenedor existente: {exc}") from exc

        spec = build_workspace_container_spec(
            workspace_id=workspace_id,
            organization_id=organization_id,
            project_id=project_id,
            container_name=container_name,
            volume_name=volume_name,
            workspace_class=workspace_class,
            image=image,
            env_vars=env_vars,
        )
        try:
            client.volumes.get(volume_name)
        except NotFound:
            client.volumes.create(
                name=volume_name,
                labels={"originlabs.managed": "true", "originlabs.workspace_id": workspace_id},
            )

        try:
            container = client.containers.run(**spec)
            return str(container.id)
        except DockerException as exc:
            raise RuntimeError(f"No se pudo iniciar el contenedor del workspace: {exc}") from exc

    def stop_container(self, container_name: str) -> None:
        """Stop a running workspace container while preserving its persistent volume."""
        client = self._docker_client()
        try:
            container = client.containers.get(container_name)
            if container.status == "running":
                container.stop(timeout=15)
        except NotFound:
            return
        except DockerException as exc:
            raise RuntimeError(f"Error deteniendo workspace: {exc}") from exc

    def remove_container(
        self,
        *,
        container_name: str,
        volume_name: str,
        purge_volume: bool = False,
    ) -> None:
        """Remove a workspace container and optionally delete its persistent volume."""
        client = self._docker_client()
        try:
            container = client.containers.get(container_name)
            container.remove(force=True)
        except NotFound:
            pass
        except DockerException as exc:
            raise RuntimeError(f"Error eliminando contenedor: {exc}") from exc

        if purge_volume:
            try:
                vol = client.volumes.get(volume_name)
                vol.remove(force=True)
            except NotFound:
                pass
            except DockerException as exc:
                raise RuntimeError(f"Error eliminando volumen del workspace: {exc}") from exc

    def exec_command(self, container_name: str, command: str) -> tuple[int, str]:
        """Run a shell command inside a running workspace container."""
        client = self._docker_client()
        try:
            container = client.containers.get(container_name)
            if container.status != "running":
                return 1, "El workspace está detenido. Inícialo para usar la terminal."
            result = container.exec_run(
                cmd=["/bin/sh", "-c", command],
                workdir=WORKSPACE_MOUNT_PATH,
                user="1000:1000",
            )
            output = result.output.decode("utf-8", errors="replace") if result.output else ""
            return int(result.exit_code or 0), output
        except NotFound:
            return 1, "Contenedor del workspace no encontrado en Docker."
        except DockerException as exc:
            return 1, f"Error ejecutando comando en contenedor: {exc}"

    async def register_caddy_route(
        self,
        *,
        workspace_id: str,
        host: str,
        container_name: str,
    ) -> None:
        """Best-effort registration of ws-<id>.domain route in Caddy Admin API."""
        route = build_caddy_workspace_route(
            workspace_id=workspace_id,
            host=host,
            container_name=container_name,
        )
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                await client.put(
                    f"{self.caddy_admin_url}/id/originlabs-ws-{workspace_id}",
                    json=route,
                )
        except httpx.HTTPError:
            return

    async def remove_caddy_route(self, *, workspace_id: str) -> None:
        """Best-effort removal of a workspace route from Caddy Admin API."""
        try:
            async with httpx.AsyncClient(timeout=4.0) as client:
                await client.delete(f"{self.caddy_admin_url}/id/originlabs-ws-{workspace_id}")
        except httpx.HTTPError:
            return
