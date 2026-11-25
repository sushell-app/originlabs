#!/usr/bin/env bash
set -euo pipefail

# OriginLabs Uninstaller (v0.1 — Base del Módulo 0/1)
INSTALL_DIR="${ORIGINLABS_INSTALL_DIR:-/opt/originlabs}"
MODE="ask"

usage() {
  cat <<'EOF'
Uso: uninstall.sh [--keep-data | --purge]
  --keep-data   Detiene contenedores pero conserva volúmenes de BD, workspaces y respaldos.
  --purge       Elimina contenedores, volúmenes y archivos de OriginLabs del servidor.
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --keep-data) MODE="keep" ;;
      --purge) MODE="purge" ;;
      -h|--help) usage; exit 0 ;;
      *) echo "Opción desconocida: $1" >&2; usage; exit 1 ;;
    esac
    shift
  done
}

main() {
  parse_args "$@"

  if [[ "${EUID}" -ne 0 ]]; then
    echo "[originlabs][ERROR] Ejecuta uninstall.sh como root." >&2
    exit 1
  fi

  if [[ "${MODE}" == "ask" ]]; then
    read -r -p "¿Deseas borrar también todos los datos y volúmenes? (escribe PURGE para borrar, cualquier otra tecla conserva datos): " answer
    if [[ "${answer}" == "PURGE" ]]; then
      MODE="purge"
    else
      MODE="keep"
    fi
  fi

  if [[ -f "${INSTALL_DIR}/compose.prod.yml" ]] && command -v docker >/dev/null 2>&1; then
    if [[ "${MODE}" == "purge" ]]; then
      docker compose -f "${INSTALL_DIR}/compose.prod.yml" down -v --remove-orphans
      rm -rf "${INSTALL_DIR}"
      echo "[originlabs] OriginLabs y todos sus datos fueron eliminados del servidor."
    else
      docker compose -f "${INSTALL_DIR}/compose.prod.yml" down --remove-orphans
      echo "[originlabs] Contenedores detenidos. Los datos y volúmenes se conservaron."
    fi
  else
    echo "[originlabs] No se encontró una instalación activa en ${INSTALL_DIR}."
  fi
}

main "$@"
