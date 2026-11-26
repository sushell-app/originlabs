#!/usr/bin/env bash
set -euo pipefail

# OriginLabs Installer (v0.1 — Base de pre-chequeos del Módulo 0/1)
# No requiere Python en el host; toda la plataforma corre en Docker.

MIN_CPU_CORES=2
MIN_RAM_MB=3500
MIN_DISK_GB=35
INSTALL_DIR="${ORIGINLABS_INSTALL_DIR:-/opt/originlabs}"
DRY_RUN="${ORIGINLABS_DRY_RUN:-0}"

log() { printf '[originlabs] %s\n' "$*"; }
err() { printf '[originlabs][ERROR] %s\n' "$*" >&2; }
die() { err "$*"; exit 1; }

require_root() {
  if [[ "${EUID}" -ne 0 ]] && [[ "${DRY_RUN}" != "1" ]]; then
    die "Ejecuta el instalador como root (o usando sudo). Para pruebas sin root usa ORIGINLABS_DRY_RUN=1."
  fi
}

check_os() {
  if [[ ! -r /etc/os-release ]]; then
    die "No se pudo leer /etc/os-release. SO no soportado."
  fi

  # shellcheck disable=SC1091
  source /etc/os-release
  local id="${ID:-}"
  local version="${VERSION_ID:-}"

  case "${id}:${version}" in
    ubuntu:22.04|ubuntu:24.04|debian:12)
      log "SO soportado detectado: ${PRETTY_NAME:-$id $version}"
      ;;
    *)
      die "SO no soportado (${id} ${version}). Solo se soporta Ubuntu 22.04 LTS, Ubuntu 24.04 LTS y Debian 12."
      ;;
  esac
}

check_arch() {
  local arch
  arch="$(uname -m)"
  case "${arch}" in
    x86_64|aarch64|arm64)
      log "Arquitectura soportada: ${arch}"
      ;;
    *)
      die "Arquitectura no soportada: ${arch}. Solo se soporta x86_64 y ARM64."
      ;;
  esac
}

check_resources() {
  local cpus ram_mb disk_gb
  cpus="$(nproc 2>/dev/null || echo 0)"
  ram_mb="$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo 0)"
  disk_gb="$(df -BG --output=avail / | tail -n 1 | tr -dc '0-9' || echo 0)"

  log "Recursos detectados (mínimos ESTIMADO): ${cpus} vCPU, ${ram_mb} MB RAM, ${disk_gb} GB libres en /"

  if (( cpus < MIN_CPU_CORES )); then
    if [[ "${DRY_RUN}" == "1" ]]; then
      log "[DRY_RUN][WARN] CPU inferior al mínimo recomendado (${cpus} < ${MIN_CPU_CORES} vCPU)."
    else
      die "CPU insuficiente: se requieren al menos ${MIN_CPU_CORES} vCPU (estimado)."
    fi
  fi
  if (( ram_mb < MIN_RAM_MB )); then
    if [[ "${DRY_RUN}" == "1" ]]; then
      log "[DRY_RUN][WARN] RAM inferior al mínimo recomendado (${ram_mb} MB < ${MIN_RAM_MB} MB)."
    else
      die "RAM insuficiente: se requieren al menos 4 GB (~${MIN_RAM_MB} MB útiles)."
    fi
  fi
  if (( disk_gb < MIN_DISK_GB )); then
    if [[ "${DRY_RUN}" == "1" ]]; then
      log "[DRY_RUN][WARN] Disco libre inferior al mínimo recomendado (${disk_gb} GB < ${MIN_DISK_GB} GB)."
    else
      die "Disco insuficiente: se requieren al menos 40 GB SSD (~${MIN_DISK_GB} GB libres)."
    fi
  fi
}

check_ports() {
  local port
  for port in 80 443; do
    if command -v ss >/dev/null 2>&1; then
      if ss -tuln | awk '{print $5}' | grep -qE "(^|:)${port}$"; then
        die "El puerto ${port} ya está en uso. Libera los puertos 80 y 443 antes de instalar OriginLabs."
      fi
    fi
  done
  log "Puertos 80 y 443 disponibles."
}

run_prechecks() {
  log "1/5 · Ejecutando chequeos del servidor..."
  check_os
  check_arch
  check_resources
  check_ports
}

install_docker() {
  log "2/5 · Verificando Docker + Compose..."
  if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
    log "Docker y Docker Compose ya están instalados."
    return 0
  fi

  if [[ "${DRY_RUN}" == "1" ]]; then
    log "[DRY_RUN] Se omitió la instalación automática de Docker."
    return 0
  fi

  log "Instalando Docker Engine y plugin Compose..."
  curl -fsSL https://get.docker.com | sh
  systemctl enable --now docker
}

deploy_stack() {
  log "3/5 · Desplegando núcleo, PostgreSQL, Redis y Caddy en ${INSTALL_DIR}..."
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "[DRY_RUN] Despliegue de compose.prod.yml pendiente de implementar en Módulo 1 completo."
    return 0
  fi
  mkdir -p "${INSTALL_DIR}"
  log "Base lista para descargar compose.prod.yml y generar secretos en Módulo 1."
}

main() {
  require_root
  run_prechecks
  install_docker
  deploy_stack
  log "Pre-chequeos completados. El flujo completo de SSL (4/5) y bootstrap admin (5/5) se completa en Módulo 1 y Módulo 2."
}

main "$@"
