"""Unit tests for Workspaces hardening, Caddy routing, admission control and restic backups."""

import uuid

import pytest
from pydantic import ValidationError

from app.modules.system.backups import build_restic_env, validate_backup_repository
from app.modules.system.monitoring import HostMetrics, evaluate_admission
from app.modules.system.schemas import BackupConfigUpdateRequest
from app.modules.workspaces.orchestrator import (
    WORKSPACES_NETWORK_NAME,
    build_caddy_workspace_route,
    build_workspace_container_spec,
)
from app.modules.workspaces.schemas import WorkspaceCreateRequest


def test_workspace_container_spec_enforces_isolation_and_no_docker_sock() -> None:
    spec = build_workspace_container_spec(
        workspace_id="ws-1",
        organization_id="org-1",
        project_id="proj-1",
        container_name="ol-ws-1234",
        volume_name="ol_ws_1234_data",
        workspace_class="standard",
        env_vars={"APP_ENV": "dev"},
    )
    assert spec["user"] == "1000:1000"
    assert spec["cap_drop"] == ["ALL"]
    assert spec["security_opt"] == ["no-new-privileges:true"]
    assert spec["network"] == WORKSPACES_NETWORK_NAME
    assert spec["nano_cpus"] == 2_000_000_000
    assert spec["mem_limit"] == "4096m"
    assert spec["pids_limit"] == 512
    assert all("docker.sock" not in k for k in spec["volumes"])


def test_caddy_workspace_route_uses_forward_auth() -> None:
    route = build_caddy_workspace_route(
        workspace_id="abc",
        host="ws-abc.panel.example.com",
        container_name="ol-ws-abc",
    )
    assert route["@id"] == "originlabs-ws-abc"
    assert route["match"] == [{"host": ["ws-abc.panel.example.com"]}]
    handlers = route["handle"][0]["routes"][0]["handle"]
    assert handlers[0]["rewrite"]["uri"] == "/api/v1/internal/forward-auth"
    assert handlers[1]["upstreams"] == [{"dial": "ol-ws-abc:8080"}]


def test_admission_control_blocks_low_disk_and_high_ram() -> None:
    healthy = HostMetrics(
        hostname="vps-1",
        os_name="Linux",
        arch="x86_64",
        cpu_cores=4,
        load_avg_1m=0.4,
        ram_total_mb=16384,
        ram_available_mb=12000,
        ram_used_pct=26.8,
        disk_total_gb=100.0,
        disk_free_gb=65.0,
        disk_used_pct=35.0,
        docker_available=True,
        running_workspaces=1,
        allocated_cpu_cores=2.0,
        allocated_ram_mb=4096,
    )
    assert evaluate_admission(healthy, "standard").allowed is True

    low_disk = HostMetrics(
        hostname="vps-1",
        os_name="Linux",
        arch="x86_64",
        cpu_cores=4,
        load_avg_1m=0.4,
        ram_total_mb=16384,
        ram_available_mb=12000,
        ram_used_pct=26.8,
        disk_total_gb=100.0,
        disk_free_gb=3.2,
        disk_used_pct=96.8,
        docker_available=True,
        running_workspaces=1,
        allocated_cpu_cores=2.0,
        allocated_ram_mb=4096,
    )
    assert evaluate_admission(low_disk, "light").allowed is False

    high_ram = HostMetrics(
        hostname="vps-1",
        os_name="Linux",
        arch="x86_64",
        cpu_cores=4,
        load_avg_1m=1.2,
        ram_total_mb=4096,
        ram_available_mb=512,
        ram_used_pct=87.5,
        disk_total_gb=80.0,
        disk_free_gb=40.0,
        disk_used_pct=50.0,
        docker_available=True,
        running_workspaces=1,
        allocated_cpu_cores=2.0,
        allocated_ram_mb=2048,
    )
    assert evaluate_admission(high_ram, "standard").allowed is False


def test_backup_repository_validation_and_env_builder() -> None:
    assert validate_backup_repository("local", "/var/backups/originlabs") == (
        "/var/backups/originlabs"
    )
    assert validate_backup_repository("s3", "s3:https://s3.example.com/ol-backups") == (
        "s3:https://s3.example.com/ol-backups"
    )

    for bad_repo in ["/tmp/a;rm -rf /", "/var/backups $(whoami)", "relative/path"]:
        with pytest.raises(ValueError):
            validate_backup_repository("local", bad_repo)

    with pytest.raises(ValueError):
        validate_backup_repository("s3", "/var/backups/local")

    env = build_restic_env(
        repository="/var/backups/originlabs",
        password="secret-password",
        s3_access_key="key-id",
        s3_secret_key="secret-val",
    )
    assert env["RESTIC_PASSWORD"] == "secret-password"
    assert env["AWS_ACCESS_KEY_ID"] == "key-id"


def test_workspace_and_backup_schemas() -> None:
    ws = WorkspaceCreateRequest(
        project_id=uuid.uuid4(),
        name="Backend Sandbox",
        slug="backend-sandbox",
        workspace_class="light",
        idle_timeout_minutes=45,
    )
    assert ws.auto_start is False

    with pytest.raises(ValidationError):
        BackupConfigUpdateRequest(provider="local", repository="bad;cmd")
