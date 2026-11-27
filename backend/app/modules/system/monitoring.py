"""Host resource telemetry and admission control for preventing VPS saturation."""

import os
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import docker
from docker.errors import DockerException

from app.modules.workspaces.orchestrator import WORKSPACE_CLASS_SPECS, WorkspaceClass


@dataclass(frozen=True, slots=True)
class HostMetrics:
    """Snapshot of host CPU, memory, disk and active workspace allocation."""

    hostname: str
    os_name: str
    arch: str
    cpu_cores: int
    load_avg_1m: float
    ram_total_mb: int
    ram_available_mb: int
    ram_used_pct: float
    disk_total_gb: float
    disk_free_gb: float
    disk_used_pct: float
    docker_available: bool
    running_workspaces: int
    allocated_cpu_cores: float
    allocated_ram_mb: int


@dataclass(frozen=True, slots=True)
class AdmissionDecision:
    """Admission control verdict before starting a workspace of a given class."""

    workspace_class: WorkspaceClass
    allowed: bool
    severity: str
    reason: str


def _read_linux_meminfo_mb() -> tuple[int, int]:
    """Read MemTotal and MemAvailable in MB from /proc/meminfo on Linux."""
    meminfo = Path("/proc/meminfo")
    if not meminfo.is_file():
        return 0, 0
    total_kb = 0
    avail_kb = 0
    free_kb = 0
    for line in meminfo.read_text(encoding="utf-8", errors="ignore").splitlines():
        if line.startswith("MemTotal:"):
            total_kb = int(line.split()[1])
        elif line.startswith("MemAvailable:"):
            avail_kb = int(line.split()[1])
        elif line.startswith("MemFree:"):
            free_kb = int(line.split()[1])
    effective_avail = avail_kb or free_kb
    return total_kb // 1024, effective_avail // 1024


def _check_docker_daemon() -> bool:
    try:
        client = docker.from_env()
        client.ping()
        return True
    except DockerException:
        return False


def collect_host_metrics(
    *,
    running_workspaces: int = 0,
    allocated_cpu_cores: float = 0.0,
    allocated_ram_mb: int = 0,
) -> HostMetrics:
    """Collect current host telemetry safely across Linux and non-Linux dev hosts."""
    cpu_cores = os.cpu_count() or 1
    load_1m = 0.0
    if sys.platform != "win32":
        try:
            load_1m = round(os.getloadavg()[0], 2)
        except OSError:
            load_1m = 0.0

    ram_total_mb, ram_avail_mb = _read_linux_meminfo_mb()
    ram_used_pct = (
        round(((ram_total_mb - ram_avail_mb) / ram_total_mb) * 100.0, 1)
        if ram_total_mb > 0
        else 0.0
    )

    usage = shutil.disk_usage("/")
    gb = 1024.0**3
    disk_total_gb = round(usage.total / gb, 1)
    disk_free_gb = round(usage.free / gb, 1)
    disk_used_pct = (
        round(((usage.total - usage.free) / usage.total) * 100.0, 1)
        if usage.total > 0
        else 0.0
    )

    return HostMetrics(
        hostname=platform.node() or "originlabs-host",
        os_name=platform.system(),
        arch=platform.machine() or "unknown",
        cpu_cores=cpu_cores,
        load_avg_1m=load_1m,
        ram_total_mb=ram_total_mb,
        ram_available_mb=ram_avail_mb,
        ram_used_pct=ram_used_pct,
        disk_total_gb=disk_total_gb,
        disk_free_gb=disk_free_gb,
        disk_used_pct=disk_used_pct,
        docker_available=_check_docker_daemon(),
        running_workspaces=running_workspaces,
        allocated_cpu_cores=allocated_cpu_cores,
        allocated_ram_mb=allocated_ram_mb,
    )


_STARTUP_RAM_REQUIRED_MB: dict[WorkspaceClass, int] = {
    "light": 384,
    "standard": 768,
    "heavy": 1536,
}


def evaluate_admission(metrics: HostMetrics, workspace_class: WorkspaceClass) -> AdmissionDecision:
    """Decide whether the host can safely start another workspace of the given class."""
    if metrics.disk_free_gb < 5.0:
        return AdmissionDecision(
            workspace_class=workspace_class,
            allowed=False,
            severity="blocked",
            reason=(
                f"Disco crítico: solo quedan {metrics.disk_free_gb} GB libres "
                "(mínimo requerido: 5.0 GB)."
            ),
        )

    if metrics.ram_total_mb > 0:
        required_mb = _STARTUP_RAM_REQUIRED_MB[workspace_class]
        if metrics.ram_available_mb < required_mb or metrics.ram_used_pct >= 90.0:
            return AdmissionDecision(
                workspace_class=workspace_class,
                allowed=False,
                severity="blocked",
                reason=(
                    f"RAM insuficiente: iniciar clase '{workspace_class}' requiere ~{required_mb} "
                    f"MB libres (disponibles: {metrics.ram_available_mb} MB, "
                    f"uso actual: {metrics.ram_used_pct:.1f}%)."
                ),
            )
        remaining_mb = metrics.ram_available_mb - required_mb
        if remaining_mb < 768 or metrics.disk_used_pct > 80.0:
            return AdmissionDecision(
                workspace_class=workspace_class,
                allowed=True,
                severity="warning",
                reason=(
                    f"Carga elevada: quedarían {remaining_mb} MB libres "
                    f"y disco al {metrics.disk_used_pct:.1f}%."
                ),
            )

    return AdmissionDecision(
        workspace_class=workspace_class,
        allowed=True,
        severity="ok",
        reason="Capacidad suficiente en el servidor.",
    )
