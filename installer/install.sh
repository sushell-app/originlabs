#!/usr/bin/env bash
set -euo pipefail

# OriginLabs 1-Command Installer (v0.1.3)
# No requiere Python en el host; toda la plataforma corre en Docker.

MIN_CPU_CORES=2
MIN_RAM_MB=3500
MIN_DISK_GB=35

INSTALL_DIR="${ORIGINLABS_INSTALL_DIR:-/opt/originlabs}"
DRY_RUN="${ORIGINLABS_DRY_RUN:-0}"
DOMAIN="${ORIGINLABS_DOMAIN:-}"
HTTP_ONLY="${ORIGINLABS_HTTP_ONLY:-0}"
SKIP_RESOURCE_CHECK="${ORIGINLABS_SKIP_RESOURCE_CHECK:-0}"
IMAGE="${ORIGINLABS_IMAGE:-ghcr.io/sushell-app/originlabs:latest}"
REPO_REF="${ORIGINLABS_REPO_REF:-main}"
LOCAL_SOURCE="${ORIGINLABS_LOCAL_SOURCE:-}"

log() { printf '[originlabs] %s\n' "$*"; }
err() { printf '[originlabs][ERROR] %s\n' "$*" >&2; }
die() { err "$*"; exit 1; }

usage() {
  cat <<'EOF'
Uso: install.sh [opciones]
  --domain <dominio>       Dominio para HTTPS automático (ej: panel.tu-dominio.com)
  --http-only              Modo HTTP (:80) sin TLS (ideal para pruebas locales o por IP)
  --skip-resource-check    Solo advertir si CPU/RAM/disco están debajo del mínimo
  --install-dir <ruta>     Directorio de instalación (por defecto: /opt/originlabs)
  --image <imagen>         Imagen Docker unificada (por defecto: ghcr.io/sushell-app/originlabs:latest)
  --local-source <ruta>    Usar archivos locales del repositorio en lugar de descargar desde GitHub
  --dry-run                Ejecutar solo pre-chequeos del servidor sin instalar Docker ni levantar servicios
  -h, --help               Mostrar esta ayuda
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --domain)
        [[ $# -lt 2 ]] && die "Falta el valor para --domain"
        DOMAIN="$2"
        shift
        ;;
      --http-only)
        HTTP_ONLY="1"
        ;;
      --skip-resource-check)
        SKIP_RESOURCE_CHECK="1"
        ;;
      --install-dir)
        [[ $# -lt 2 ]] && die "Falta el valor para --install-dir"
        INSTALL_DIR="$2"
        shift
        ;;
      --image)
        [[ $# -lt 2 ]] && die "Falta el valor para --image"
        IMAGE="$2"
        shift
        ;;
      --repo-ref)
        [[ $# -lt 2 ]] && die "Falta el valor para --repo-ref"
        REPO_REF="$2"
        shift
        ;;
      --local-source)
        [[ $# -lt 2 ]] && die "Falta el valor para --local-source"
        LOCAL_SOURCE="$2"
        shift
        ;;
      --dry-run)
        DRY_RUN="1"
        ;;
      -h|--help)
        usage
        exit 0
        ;;
      *)
        die "Opción desconocida: $1"
        ;;
    esac
    shift
  done
}

require_root() {
  if [[ "${EUID}" -ne 0 ]] && [[ "${DRY_RUN}" != "1" ]]; then
    die "Ejecuta el instalador como root (o usando sudo). Para pruebas sin root usa --dry-run."
  fi
}

check_os() {
  if [[ ! -r /etc/os-release ]]; then
    die "No se pudo leer /etc/os-release. SO no soportado."
  fi

  # shellcheck source=/dev/null
  source /etc/os-release
  local id
  local version
  id="${ID:-}"
  version="${VERSION_ID:-}"

  case "${id}:${version}" in
    ubuntu:22.04|ubuntu:24.04|ubuntu:26.04|debian:12|debian:13)
      log "SO soportado detectado: ${PRETTY_NAME:-$id $version}"
      ;;
    *)
      die "SO no soportado (${id} ${version}). Solo se soporta Ubuntu 22.04/24.04/26.04 LTS y Debian 12/13."
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
  local cpus ram_mb disk_gb warn_only
  cpus="$(nproc 2>/dev/null || echo 0)"
  ram_mb="$(awk '/MemTotal/ {printf "%d", $2/1024}' /proc/meminfo 2>/dev/null || echo 0)"
  disk_gb="$(df -BG --output=avail / | tail -n 1 | tr -dc '0-9' || echo 0)"
  warn_only=0

  if [[ "${DRY_RUN}" == "1" ]] || [[ "${SKIP_RESOURCE_CHECK}" == "1" ]]; then
    warn_only=1
  fi

  log "Recursos detectados (mínimos ESTIMADO): ${cpus} vCPU, ${ram_mb} MB RAM, ${disk_gb} GB libres en /"

  if (( cpus < MIN_CPU_CORES )); then
    if (( warn_only == 1 )); then
      log "[WARN] CPU inferior al mínimo recomendado (${cpus} < ${MIN_CPU_CORES} vCPU)."
    else
      die "CPU insuficiente: se requieren al menos ${MIN_CPU_CORES} vCPU (estimado). Usa --skip-resource-check para continuar bajo tu responsabilidad."
    fi
  fi
  if (( ram_mb < MIN_RAM_MB )); then
    if (( warn_only == 1 )); then
      log "[WARN] RAM inferior al mínimo recomendado (${ram_mb} MB < ${MIN_RAM_MB} MB)."
    else
      die "RAM insuficiente: se requieren al menos 4 GB (~${MIN_RAM_MB} MB útiles). Usa --skip-resource-check para continuar bajo tu responsabilidad."
    fi
  fi
  if (( disk_gb < MIN_DISK_GB )); then
    if (( warn_only == 1 )); then
      log "[WARN] Disco libre inferior al mínimo recomendado (${disk_gb} GB < ${MIN_DISK_GB} GB)."
    else
      die "Disco insuficiente: se requieren al menos 40 GB SSD (~${MIN_DISK_GB} GB libres). Usa --skip-resource-check para continuar bajo tu responsabilidad."
    fi
  fi
}

check_ports() {
  if [[ -f "${INSTALL_DIR}/compose.prod.yml" ]]; then
    log "Instalación previa detectada en ${INSTALL_DIR}; omitiendo chequeo de puertos en uso."
    return 0
  fi

  local -a ports_to_check
  local port
  ports_to_check=(80)
  if [[ "${HTTP_ONLY}" != "1" ]]; then
    ports_to_check=(80 443)
  fi

  for port in "${ports_to_check[@]}"; do
    if command -v ss >/dev/null 2>&1; then
      if ss -tuln | awk '{print $5}' | grep -qE "(^|:)${port}$"; then
        die "El puerto ${port} ya está en uso. Libera los puertos 80/443 antes de instalar OriginLabs."
      fi
    fi
  done
  log "Puertos requeridos disponibles (${ports_to_check[*]})."
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
  systemctl enable --now docker >/dev/null 2>&1 || true
}

resolve_domain() {
  if [[ -z "${DOMAIN}" ]] && [[ "${HTTP_ONLY}" != "1" ]] && [[ -r /dev/tty ]]; then
    printf '[originlabs] Dominio para el panel (deja vacío para usar HTTP en puerto 80): ' >/dev/tty
    read -r DOMAIN </dev/tty || true
  fi

  if [[ -z "${DOMAIN}" ]] || [[ "${DOMAIN}" == "localhost" ]] || [[ "${DOMAIN}" =~ ^[0-9]+(\.[0-9]+){3}$ ]]; then
    HTTP_ONLY="1"
    if [[ -z "${DOMAIN}" ]]; then
      DOMAIN="localhost"
    fi
  fi
}

generate_secret() {
  local bytes
  bytes="${1:-32}"
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -hex "${bytes}"
  else
    od -An -N"${bytes}" -tx1 /dev/urandom | tr -d ' \n'
  fi
}

fetch_file() {
  local rel_path dest_path url
  rel_path="$1"
  dest_path="$2"

  if [[ -n "${LOCAL_SOURCE}" ]]; then
    [[ -r "${LOCAL_SOURCE}/${rel_path}" ]] || die "No se encontró ${LOCAL_SOURCE}/${rel_path}"
    cp "${LOCAL_SOURCE}/${rel_path}" "${dest_path}"
  else
    url="https://raw.githubusercontent.com/sushell-app/originlabs/${REPO_REF}/${rel_path}"
    curl -fsSL "${url}" -o "${dest_path}"
  fi
}

write_caddyfile() {
  local caddy_dest
  caddy_dest="${INSTALL_DIR}/infra/caddy/Caddyfile.prod"

  if [[ "${HTTP_ONLY}" == "1" ]]; then
    cat > "${caddy_dest}" <<'EOF'
{
	admin 0.0.0.0:2019
	auto_https off
}

:80 {
	encode gzip zstd

	@ws_noslash path_regexp wsnoslash ^/ws/(ws-[a-f0-9]{8})$
	redir @ws_noslash /ws/{re.wsnoslash.1}/ 308

	@workspace path_regexp ws ^/ws/ws-([a-f0-9]{8})(/.*)$
	handle @workspace {
		forward_auth api:8000 {
			uri /api/v1/internal/forward-auth
			copy_headers X-OriginLabs-User-Id X-OriginLabs-User-Email X-OriginLabs-Is-Admin
			header_up -Connection
			header_up -Upgrade
		}
		uri path_regexp ^/ws/ws-[a-f0-9]{8}(/.*)$ $1
		reverse_proxy ol-ws-{re.ws.1}:8080 {
			header_up Host {host}
			header_up X-Forwarded-Prefix /ws/ws-{re.ws.1}
		}
	}

	handle {
		reverse_proxy api:8000
	}
}
EOF
  else
    cat > "${caddy_dest}" <<'EOF'
{
	admin 0.0.0.0:2019
}

{$ORIGINLABS_DOMAIN} {
	encode gzip zstd

	@ws_noslash path_regexp wsnoslash ^/ws/(ws-[a-f0-9]{8})$
	redir @ws_noslash /ws/{re.wsnoslash.1}/ 308

	@workspace path_regexp ws ^/ws/ws-([a-f0-9]{8})(/.*)$
	handle @workspace {
		forward_auth api:8000 {
			uri /api/v1/internal/forward-auth
			copy_headers X-OriginLabs-User-Id X-OriginLabs-User-Email X-OriginLabs-Is-Admin
			header_up -Connection
			header_up -Upgrade
		}
		uri path_regexp ^/ws/ws-[a-f0-9]{8}(/.*)$ $1
		reverse_proxy ol-ws-{re.ws.1}:8080 {
			header_up Host {host}
			header_up X-Forwarded-Prefix /ws/ws-{re.ws.1}
		}
	}

	handle {
		reverse_proxy api:8000
	}
}
EOF
  fi
}

write_env_file() {
  local env_file pg_pass secret_key enc_key bootstrap_token cookie_secure
  env_file="${INSTALL_DIR}/.env"

  if [[ -f "${env_file}" ]]; then
    log "Archivo ${env_file} existente detectado; conservando secretos actuales."
    return 0
  fi

  pg_pass="$(generate_secret 16)"
  secret_key="$(generate_secret 32)"
  enc_key="$(generate_secret 32)"
  bootstrap_token="$(generate_secret 16)"

  cookie_secure="true"
  if [[ "${HTTP_ONLY}" == "1" ]]; then
    cookie_secure="false"
  fi

  cat > "${env_file}" <<EOF
# Generado automáticamente por OriginLabs installer
ORIGINLABS_ENV=production
ORIGINLABS_DOMAIN=${DOMAIN}
ORIGINLABS_IMAGE=${IMAGE}
ORIGINLABS_SECRET_KEY=${secret_key}
ORIGINLABS_ENCRYPTION_KEY=${enc_key}
ORIGINLABS_BOOTSTRAP_TOKEN=${bootstrap_token}
ORIGINLABS_AUTO_MIGRATE=true
SESSION_COOKIE_SECURE=${cookie_secure}
SESSION_TTL_SECONDS=604800

POSTGRES_DB=originlabs
POSTGRES_USER=originlabs
POSTGRES_PASSWORD=${pg_pass}
DATABASE_URL=postgresql+asyncpg://originlabs:${pg_pass}@postgres:5432/originlabs
REDIS_URL=redis://redis:6379/0
CADDY_ADMIN_URL=http://caddy:2019
DOCKER_HOST=tcp://docker-proxy:2375

ORIGINLABS_RELEASE_CHANNEL=stable
ORIGINLABS_RELEASES_URL=https://api.github.com/repos/sushell-app/originlabs/releases
ORIGINLABS_RELEASES_PUBLIC_KEY=
EOF
  chmod 600 "${env_file}"
}

deploy_stack() {
  log "3/5 · Desplegando OriginLabs en ${INSTALL_DIR}..."
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "[DRY_RUN] Pre-chequeos completados. No se escribieron archivos ni se levantaron contenedores."
    return 0
  fi

  resolve_domain
  mkdir -p "${INSTALL_DIR}/infra/caddy"

  fetch_file "compose.prod.yml" "${INSTALL_DIR}/compose.prod.yml"
  fetch_file "installer/uninstall.sh" "${INSTALL_DIR}/uninstall.sh"
  chmod +x "${INSTALL_DIR}/uninstall.sh"

  write_caddyfile
  write_env_file

  log "Descargando imagen (${IMAGE}) y levantando servicios..."
  if [[ "${IMAGE}" == */* ]]; then
    docker compose --project-directory "${INSTALL_DIR}" -f "${INSTALL_DIR}/compose.prod.yml" pull
  else
    docker compose --project-directory "${INSTALL_DIR}" -f "${INSTALL_DIR}/compose.prod.yml" pull postgres redis caddy docker-proxy
  fi
  if ! docker compose --project-directory "${INSTALL_DIR}" -f "${INSTALL_DIR}/compose.prod.yml" up -d --no-build --remove-orphans; then
    log "Recreación limpia tras actualización previa..."
    docker compose --project-directory "${INSTALL_DIR}" -f "${INSTALL_DIR}/compose.prod.yml" down --remove-orphans || true
    docker compose --project-directory "${INSTALL_DIR}" -f "${INSTALL_DIR}/compose.prod.yml" up -d --no-build
  fi
  docker compose --project-directory "${INSTALL_DIR}" -f "${INSTALL_DIR}/compose.prod.yml" restart caddy
}

wait_for_health() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    return 0
  fi

  log "4/5 · Verificando migraciones, Caddy y salud del servicio..."
  local i ready
  ready=0

  for ((i = 1; i <= 60; i++)); do
    if docker compose --project-directory "${INSTALL_DIR}" -f "${INSTALL_DIR}/compose.prod.yml" \
      exec -T api python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/health')" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 2
  done

  if (( ready != 1 )); then
    docker compose --project-directory "${INSTALL_DIR}" -f "${INSTALL_DIR}/compose.prod.yml" logs --tail=50 api caddy || true
    die "OriginLabs no respondió saludable en /api/v1/health tras 120 segundos."
  fi

  if [[ "${HTTP_ONLY}" == "1" ]]; then
    for ((i = 1; i <= 15; i++)); do
      if curl -fsS http://127.0.0.1/api/v1/health >/dev/null 2>&1; then
        break
      fi
      sleep 1
    done
    curl -fsS http://127.0.0.1/api/v1/health >/dev/null 2>&1 || die "Caddy no respondió en http://127.0.0.1/api/v1/health"
  fi
}

print_summary() {
  if [[ "${DRY_RUN}" == "1" ]]; then
    log "Dry-run completado correctamente."
    return 0
  fi

  local bootstrap_token scheme url_host
  bootstrap_token="$(grep -E '^ORIGINLABS_BOOTSTRAP_TOKEN=' "${INSTALL_DIR}/.env" | head -n 1 | cut -d= -f2- || true)"
  if [[ "${HTTP_ONLY}" == "1" ]]; then
    scheme="http"
    url_host="${DOMAIN}"
  else
    scheme="https"
    url_host="${DOMAIN}"
  fi

  log "5/5 · OriginLabs instalado y operativo."
  printf '\n'
  printf '  Panel web:         %s://%s\n' "${scheme}" "${url_host}"
  printf '  Bootstrap token:   %s\n' "${bootstrap_token}"
  printf '  Directorio:        %s\n' "${INSTALL_DIR}"
  printf '  Ver logs:          docker compose --project-directory %s -f %s/compose.prod.yml logs -f\n' "${INSTALL_DIR}" "${INSTALL_DIR}"
  printf '  Desinstalar:       sudo %s/uninstall.sh\n\n' "${INSTALL_DIR}"
}

main() {
  parse_args "$@"
  require_root
  run_prechecks
  install_docker
  deploy_stack
  wait_for_health
  print_summary
}

main "$@"
