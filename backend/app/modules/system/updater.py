"""Detached Docker Compose self-updater launcher for 1-click instance upgrades."""

import re
import socket
import uuid
from dataclasses import dataclass
from typing import Any

import docker
from docker.errors import DockerException, ImageNotFound

from app.core.config import get_settings

DEFAULT_IMAGE_REPO = "ghcr.io/sushell-app/originlabs"
UPDATER_CLI_IMAGE = "docker:27-cli"

_VERSION_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$")
_IMAGE_REPO_RE = re.compile(r"^[a-z0-9][a-z0-9./_-]{1,180}$")
_PROJECT_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_FORBIDDEN_PATH_CHARS = set(";&|`$><\n\r\t\0'\" ")

_UPDATER_SCRIPT = """sleep 2
docker pull "$ORIGINLABS_TARGET_IMAGE"
ENV_FILE="$ORIGINLABS_WORK_DIR/.env"
if [ -f "$ENV_FILE" ]; then
  if grep -q '^ORIGINLABS_IMAGE=' "$ENV_FILE"; then
    sed -i "s|^ORIGINLABS_IMAGE=.*|ORIGINLABS_IMAGE=$ORIGINLABS_TARGET_IMAGE|" "$ENV_FILE"
  else
    printf '\\nORIGINLABS_IMAGE=%s\\n' "$ORIGINLABS_TARGET_IMAGE" >> "$ENV_FILE"
  fi
  if ! grep -q '^DOCKER_HOST=' "$ENV_FILE"; then
    printf 'DOCKER_HOST=%s\\n' "$DOCKER_HOST" >> "$ENV_FILE"
  fi
fi
docker compose -p "$ORIGINLABS_PROJECT" --project-directory "$ORIGINLABS_WORK_DIR" \\
  -f "$ORIGINLABS_COMPOSE_FILE" stop api worker || true
docker compose -p "$ORIGINLABS_PROJECT" --project-directory "$ORIGINLABS_WORK_DIR" \\
  -f "$ORIGINLABS_COMPOSE_FILE" rm -f api worker || true
docker compose -p "$ORIGINLABS_PROJECT" --project-directory "$ORIGINLABS_WORK_DIR" \\
  -f "$ORIGINLABS_COMPOSE_FILE" up -d --no-build --no-deps --force-recreate api worker
docker compose -p "$ORIGINLABS_PROJECT" --project-directory "$ORIGINLABS_WORK_DIR" \\
  -f "$ORIGINLABS_COMPOSE_FILE" restart caddy || true
docker compose -p "$ORIGINLABS_PROJECT" --project-directory "$ORIGINLABS_WORK_DIR" \\
  -f "$ORIGINLABS_COMPOSE_FILE" ps
"""


@dataclass(frozen=True, slots=True)
class SelfUpdateLaunchResult:
    """Metadata returned when the detached updater helper container starts."""

    target_version: str
    target_image: str
    updater_container_id: str
    project_name: str
    working_dir: str


def validate_target_version(version: str) -> str:
    """Normalize and strictly validate a target release version string."""
    cleaned = version.strip().lstrip("v")
    if not _VERSION_RE.match(cleaned):
        raise ValueError("La versión objetivo no cumple el formato semver válido.")
    return cleaned


def _validate_safe_path(value: str, label: str) -> str:
    cleaned = value.strip()
    if not cleaned.startswith("/") or any(ch in _FORBIDDEN_PATH_CHARS for ch in cleaned):
        raise ValueError(f"Ruta inválida para {label}.")
    return cleaned


def build_updater_container_spec(
    *,
    target_version: str,
    working_dir: str,
    compose_file: str,
    project_name: str,
    image_repo: str = DEFAULT_IMAGE_REPO,
    docker_host: str = "tcp://docker-proxy:2375",
    nonce: str | None = None,
) -> dict[str, Any]:
    """Build hardened detached Docker Compose updater container specification."""
    clean_version = validate_target_version(target_version)
    clean_repo = image_repo.strip().lower()
    if not _IMAGE_REPO_RE.match(clean_repo):
        raise ValueError("Repositorio de imagen inválido para actualización.")

    clean_workdir = _validate_safe_path(working_dir, "working_dir")
    clean_compose = _validate_safe_path(compose_file, "compose_file")
    clean_project = project_name.strip().lower()
    if not _PROJECT_RE.match(clean_project):
        raise ValueError("Nombre de proyecto Docker Compose inválido.")

    short_nonce = (nonce or uuid.uuid4().hex[:8]).lower()
    target_image = f"{clean_repo}:{clean_version}"

    return {
        "image": UPDATER_CLI_IMAGE,
        "name": f"originlabs-updater-{short_nonce}",
        "detach": True,
        "auto_remove": True,
        "network": "originlabs_net",
        "volumes": {clean_workdir: {"bind": clean_workdir, "mode": "rw"}},
        "environment": {
            "DOCKER_HOST": docker_host,
            "ORIGINLABS_TARGET_IMAGE": target_image,
            "ORIGINLABS_WORK_DIR": clean_workdir,
            "ORIGINLABS_COMPOSE_FILE": clean_compose,
            "ORIGINLABS_PROJECT": clean_project,
        },
        "command": ["sh", "-eu", "-c", _UPDATER_SCRIPT],
    }


def _discover_compose_context(client: Any) -> tuple[str, str, str]:
    """Discover active Compose project, working dir and compose file from API container labels."""
    api_container = None
    hostname = socket.gethostname()
    try:
        api_container = client.containers.get(hostname)
    except DockerException:
        matches = client.containers.list(filters={"label": "com.docker.compose.service=api"})
        if matches:
            api_container = matches[0]

    labels: dict[str, str] = {}
    if api_container is not None:
        raw_labels = api_container.attrs.get("Config", {}).get("Labels")
        if isinstance(raw_labels, dict):
            labels = {str(k): str(v) for k, v in raw_labels.items()}

    project_name = labels.get("com.docker.compose.project", "originlabs").strip() or "originlabs"
    working_dir = (
        labels.get("com.docker.compose.project.working_dir", "/opt/originlabs").strip()
        or "/opt/originlabs"
    )
    raw_configs = labels.get("com.docker.compose.project.config_files", "")
    compose_file = raw_configs.split(",")[0].strip() if raw_configs else ""
    if not compose_file:
        compose_file = f"{working_dir}/compose.prod.yml"

    return project_name, working_dir, compose_file


def trigger_self_update(
    target_version: str,
    *,
    image_repo: str = DEFAULT_IMAGE_REPO,
) -> SelfUpdateLaunchResult:
    """Pull helper CLI image and launch detached container to upgrade OriginLabs."""
    settings = get_settings()
    clean_version = validate_target_version(target_version)

    try:
        client = docker.from_env()
        client.ping()
    except DockerException as exc:
        raise RuntimeError(
            f"Docker daemon no disponible para ejecutar auto-actualización: {exc}"
        ) from exc

    project_name, working_dir, compose_file = _discover_compose_context(client)
    spec = build_updater_container_spec(
        target_version=clean_version,
        working_dir=working_dir,
        compose_file=compose_file,
        project_name=project_name,
        image_repo=image_repo,
        docker_host=settings.docker_host,
    )

    try:
        try:
            client.images.get(UPDATER_CLI_IMAGE)
        except ImageNotFound:
            client.images.pull(UPDATER_CLI_IMAGE)
        container = client.containers.run(**spec)
    except DockerException as exc:
        raise RuntimeError(f"No se pudo lanzar el contenedor updater: {exc}") from exc

    return SelfUpdateLaunchResult(
        target_version=clean_version,
        target_image=str(spec["environment"]["ORIGINLABS_TARGET_IMAGE"]),
        updater_container_id=str(container.id),
        project_name=project_name,
        working_dir=working_dir,
    )
