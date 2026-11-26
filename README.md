<div align="center">

# OriginLabs

### Tu entorno de trabajo *self-hosted* completo en un solo servidor y en un solo comando.

Organizaciones, repositorios Git, **Workspaces con IDE en el navegador**, terminal WebSocket, documentación interna, chat de equipo, monitoreo contra saturación y respaldos cifrados — todo gobernado desde una interfaz minimalista oscura lista para producción.

*Un entorno de trabajo. Un comando. Un núcleo útil.*

[![CI](https://github.com/sushell-app/originlabs/actions/workflows/ci.yml/badge.svg)](https://github.com/sushell-app/originlabs/actions/workflows/ci.yml)
[![Docker Images (GHCR)](https://github.com/sushell-app/originlabs/actions/workflows/docker.yml/badge.svg)](https://github.com/sushell-app/originlabs/actions/workflows/docker.yml)
[![Licencia AGPL-3.0](https://img.shields.io/badge/Licencia-AGPL--3.0-7C5CFF?style=flat-square)](LICENSE)
[![Python 3.12 · FastAPI](https://img.shields.io/badge/Backend-Python%203.12%20%C2%B7%20FastAPI-34D399?style=flat-square)](backend/pyproject.toml)
[![React 19 · TypeScript](https://img.shields.io/badge/Frontend-React%2019%20%C2%B7%20TypeScript-8B6BFF?style=flat-square)](frontend/package.json)
[![Multi-Arch](https://img.shields.io/badge/Docker-linux%2Famd64%20%7C%20arm64-26262B?style=flat-square)](Dockerfile)

[Instalación en 1 comando](#instalación-en-1-comando-vps-linux) · [Capacidades](#capacidades-principales) · [Arquitectura](#arquitectura) · [Seguridad](#seguridad-en-5-capas) · [Consumo (`ESTIMADO`)](#requisitos-del-servidor-y-consumo-estimado) · [Contenedor único](#imagen-única-para-vps-pequeños-y-paas) · [Desarrollo local](#inicio-rápido-en-desarrollo-local)

<br />

<img src="docs/assets/originlabs-dashboard.jpg" alt="OriginLabs — Panel principal en producción" width="100%" />

</div>

---

## Instalación en 1 comando (VPS Linux)

Compatible con **Ubuntu 22.04 / 24.04 / 26.04 LTS** y **Debian 12 / 13** (`x86_64` y `ARM64`). No requiere Python en el host: toda la plataforma corre aislada en contenedores.

<table>
<tr>
<th>Instalación interactiva en 1 comando (te pregunta el dominio o usa HTTP :80)</th>
</tr>
<tr>
<td>

```bash
curl -fsSL https://sushell.com/labs | sudo bash
```

</td>
</tr>
<tr>
<th>Con dominio propio + HTTPS automático (no interactivo)</th>
</tr>
<tr>
<td>

```bash
curl -fsSL https://sushell.com/labs | sudo bash -s -- --domain panel.tu-dominio.com
```

</td>
</tr>
<tr>
<th>Prueba rápida en IP / localhost (HTTP en puerto 80)</th>
</tr>
<tr>
<td>

```bash
curl -fsSL https://sushell.com/labs | sudo bash -s -- --http-only
```

</td>
</tr>
</table>

> [!TIP]
> El instalador verifica sistema operativo, arquitectura, recursos y puertos; instala Docker si falta; genera claves criptográficas seguras en `/opt/originlabs/.env` sin sobrescribir despliegues previos; aplica migraciones automáticamente; levanta la imagen unificada `ghcr.io/sushell-app/originlabs:latest` junto a PostgreSQL 16, Redis 7 y Caddy; y muestra el **`ORIGINLABS_BOOTSTRAP_TOKEN`** de un solo uso para crear el primer administrador.
> Para VPS muy pequeños debajo del mínimo recomendado, puedes añadir `--skip-resource-check`.

---

## ¿Por qué OriginLabs?

**OriginLabs** resuelve la fragmentación diaria de equipos de desarrollo pequeños y medianos ofreciendo un único plano de control privado bajo tu propio dominio:

1. **Corres un comando** en tu servidor Linux limpio.
2. **Abres tu dominio** con TLS automático y completas el setup inicial protegido.
3. **Organizas equipos y repositorios** desde GitHub, GitLab o conector Git interno con variables `.env` cifradas.
4. **Abres Workspaces bajo demanda:** cada desarrollador programa en su propio contenedor `code-server` sin `root`, con terminal WebSocket integrada y routing `ws-<id>.tu-dominio.com`.
5. **Ahorras cómputo automáticamente:** los workspaces apagados consumen **0 CPU y 0 RAM** y el worker ARQ suspende entornos inactivos.
6. **Operas sin sorpresas:** auditoría en PostgreSQL, telemetría del servidor con control de admisión, respaldos cifrados con `restic` y notificaciones de nuevas versiones firmadas con Ed25519.

---

## Capacidades principales

| Módulo | Qué incluye | Estado |
| --- | --- | --- |
| **Identidad, Orgs & RBAC** | Setup inicial único, Argon2id, sesiones Redis (`HttpOnly`), invitaciones 72h, roles (`owner`, `admin`, `developer`, `viewer`) y `forward_auth` para Caddy. | Operativo |
| **`Projects` & Conectores Git** | Integración con **GitHub**, **GitLab** y contrato **OriginLabs Git**, miembros por proyecto y secretos `.env` cifrados con **Fernet**. | Operativo |
| **`Workspaces` & Terminal Web** | Orquestador Docker (`code-server` no-root, `cap_drop: ["ALL"]`, cuotas `cgroups`, routing dinámico Caddy y terminal WebSocket + auto-apagado ARQ). | Operativo |
| **Colaboración Interna** | **Knowledge Base** (carpetas, etiquetas y Markdown), **Team Chat** (canales y notas privadas) y **Tasks** conectadas desde mensajes. | Operativo |
| **Monitoreo & Admisión** | Telemetría en vivo de CPU, RAM y disco con bloqueo preventivo antes de saturar el servidor al iniciar workspaces. | Operativo |
| **Respaldos (`restic`)** | Configuración cifrada para repositorio local o S3, retención diaria/semanal, ejecución bajo demanda sin `shell=True` e historial de snapshots. | Operativo |
| **Updates & Notificaciones** | Verificación automática (ARQ cada 6h) de manifiestos firmados con **Ed25519** o GitHub Releases, centro de alertas y webhook HMAC. | Operativo |
| **Instalador 1-Comando** | `install.sh` y `uninstall.sh` con soporte `--domain`, `--http-only`, `--dry-run`, verificación real en Caddy y preservación de secretos. | Operativo |

---

## Arquitectura

```mermaid
flowchart TB
    Users["Equipo Dev / Navegador (HTTPS 80/443)"] --> Caddy

    subgraph CoreNet["Red núcleo aislada (originlabs_net)"]
        Caddy["Caddy Proxy<br/>TLS automático · forward_auth"]
        App["Imagen única OriginLabs<br/>React 19 SPA + FastAPI API (:8000)"]
        Worker["ARQ Worker<br/>Auto-apagado idle · Updates · Backups"]
        PG[("PostgreSQL 16<br/>Datos + Auditoría")]
        Redis[("Redis 7<br/>Sesiones + Colas ARQ")]

        Caddy --> App
        App <--> PG
        App <--> Redis
        Worker <--> PG
        Worker <--> Redis
    end

    subgraph WsNet["Red aislada de Workspaces (originlabs_workspaces)"]
        WS1["Workspace ws-1<br/>code-server · UID 1000 · cgroups"]
        WS2["Workspace ws-2<br/>code-server · UID 1000 · cgroups"]
    end

    Caddy -. "forward_auth → /api/v1/internal/forward-auth" .-> App
    Caddy --> WS1
    Caddy --> WS2
    App -- "Docker SDK (host)" --> WS1
    Worker -- "Idle Reaper" --> WS2
    Worker -- "restic (local / S3)" --> Backups[("Snapshots cifrados")]
```

---

## Seguridad en 5 capas

| Capa | Riesgo mitigado | Controles aplicados |
| --- | --- | --- |
| **1. Aislamiento de Workspaces** | Escalada al host o acceso lateral entre entornos. | Usuario `1000:1000` sin `root`, `cap_drop: ["ALL"]`, `no-new-privileges:true`, límites `cgroups` (CPU, RAM, `pids_limit`), red Docker aislada y **prohibición explícita de montar `/var/run/docker.sock`**. |
| **2. Perímetro y SSO** | Acceso directo sin sesión a puertos o subdominios IDE. | **Caddy** con TLS automático y validación obligatoria vía **`forward_auth`** antes de enrutar hacia cualquier `ws-<id>.dominio`. |
| **3. Identidad y Sesiones** | Fuerza bruta, secuestro de sesión o escalada de privilegios. | Hashing **Argon2id**, tokens opacos en **Redis** con cookies `HttpOnly; SameSite=Lax`, *rate limiting* en setup/login y RBAC granular. |
| **4. Secretos y Sanitización** | Fugas en BD o inyección de comandos. | Cifrado en reposo con **Fernet**, validación estricta **Pydantic v2**, ORM SQLAlchemy 2.0 parametrizado, inyección de credenciales Git/`restic` solo en memoria y cero `shell=True`. |
| **5. Auditoría, Updates y Backups** | Cambios sin trazabilidad o pérdida de datos. | Registro de auditoría en PostgreSQL (`/api/v1/audit`), snapshots cifrados con **`restic`** y verificación **Ed25519** de manifiestos de versión. |

Más detalles técnicos en [docs/security-sanitization.md](docs/security-sanitization.md) y [SECURITY.md](SECURITY.md).

---

## Requisitos del servidor y consumo (`ESTIMADO`)

> [!NOTE]
> Las cifras de CPU, memoria y disco marcadas como **`ESTIMADO`** sirven como referencia de dimensionamiento y se calibran según el stack real de tus repositorios.

### Servidor anfitrión

| Concepto | Mínimo (`ESTIMADO`) | Recomendado (`ESTIMADO`) |
| --- | --- | --- |
| **Uso previsto** | Pruebas · 1–2 workspaces | Equipo de ~5–10 devs · ~5 activos |
| **CPU** | 2 vCPU | 8 vCPU |
| **RAM** | 4 GB | 16–32 GB |
| **Disco** | 40 GB SSD | 200 GB NVMe |
| **SO soportados** | Ubuntu 22.04 / 24.04 / 26.04 LTS · Debian 12 / 13 | Ubuntu 22.04 / 24.04 / 26.04 LTS · Debian 12 / 13 |
| **Arquitectura** | `x86_64` (`amd64`) y `ARM64` (`arm64`) | `x86_64` (`amd64`) y `ARM64` (`arm64`) |
| **Red / Puertos** | `80`, `443` + DNS comodín `*.dominio` | `80`, `443` + DNS comodín `*.dominio` |

### Cuotas por clase de workspace (`ESTIMADO`)

| Clase | CPU (`ESTIMADO`) | RAM (`ESTIMADO`) | Disco (`ESTIMADO`) | Límite PIDs | Uso ideal |
| --- | --- | --- | --- | --- | --- |
| **Ligero** | 1 vCPU | 2 GB | 10 GB | 256 | Scripts, frontend, docs, microservicios |
| **Estándar** | 2 vCPU | 4 GB | 30 GB | 512 | APIs, apps full-stack, desarrollo diario |
| **Pesado** | 4 vCPU | 8 GB | 30 GB | 1024 | Monorepos, compilaciones pesadas |

- **Cero desperdicio en reposo:** un workspace detenido libera el 100% de CPU y RAM manteniendo su volumen de código intacto; el worker ARQ detiene automáticamente entornos tras su tiempo límite de inactividad.
- **Control de admisión:** antes de arrancar un workspace nuevo, el servidor evalúa memoria y disco libres para evitar caídas del VPS por saturación.

---

## Imagen única para VPS pequeños y PaaS

Si despliegas en un PaaS o VPS que ejecuta **un único contenedor** conectado a PostgreSQL 16 y Redis 7 externos, usa directamente la imagen oficial multi-arquitectura **`ghcr.io/sushell-app/originlabs:latest`** (incluye SPA React + FastAPI + auto-migración + soporte automático para `$PORT` / `$SERVER_PORT`):

```bash
docker run -d --name originlabs -p 8000:8000 \
  -e ORIGINLABS_ENV=production \
  -e ORIGINLABS_DOMAIN=panel.tu-dominio.com \
  -e ORIGINLABS_AUTO_MIGRATE=true \
  -e ORIGINLABS_ENCRYPTION_KEY="$(openssl rand -hex 32)" \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/originlabs" \
  -e REDIS_URL="redis://host:6379/0" \
  ghcr.io/sushell-app/originlabs:latest
```

---

## Inicio rápido en desarrollo local

Requisitos: **Docker** y **Docker Compose**.

```bash
cp .env.example .env
docker compose -f compose.dev.yml up --build -d
make migrate
```

- **Panel web (vía Caddy):** `http://localhost`
- **API Docs (solo dev):** `http://localhost/api/docs`
- **Healthcheck:** `http://localhost/api/v1/health`

<details>
<summary>Ver todos los atajos del Makefile</summary>

| Comando | Descripción |
| --- | --- |
| `make dev` | Levanta todos los contenedores en desarrollo con rebuild. |
| `make down` | Detiene los contenedores locales. |
| `make logs` | Muestra logs en tiempo real. |
| `make migrate` | Ejecuta `alembic upgrade head` dentro del contenedor `api`. |
| `make check-compose` | Valida `compose.dev.yml` y `compose.prod.yml`. |
| `make check-py` | Compila y verifica sintaxis de `backend/`. |
| `make check-bash` | Valida sintaxis de los scripts en `installer/`. |

</details>

---

## Calidad y matriz de CI verificada

Cada push y pull request a `main` ejecuta automáticamente 7 suites de verificación en [`.github/workflows/ci.yml`](.github/workflows/ci.yml) y publica contenedores multi-arch en [`.github/workflows/docker.yml`](.github/workflows/docker.yml):

| Suite en CI | Entorno real probado | Qué valida |
| --- | --- | --- |
| **Backend (`ubuntu-latest` y `windows-latest`)** | Python 3.12 | `ruff`, `mypy --strict` y pruebas unitarias `pytest`. |
| **Frontend (`ubuntu-latest` y `windows-latest`)** | Node 22 + Vite 6 | `tsc --noEmit` estricto y compilación de producción. |
| **Live E2E** | PostgreSQL 16 + Redis 7 | Migraciones Alembic `upgrade/downgrade/upgrade` + ciclo completo de API real. |
| **Infra & Distros Linux** | `ubuntu:22.04`, `ubuntu:24.04`, `debian:12` | `docker compose config`, `shellcheck` y dry-run de `install.sh` en contenedores reales. |
| **Single Container & 1-Command Installer E2E** | Ubuntu + Caddy + Docker | Build de `Dockerfile`, ejecución real de `install.sh --http-only`, verificación HTTP y `uninstall.sh --purge`. |

---

## Estructura del repositorio

```text
.
├── .github/            # Workflows CI/CD (multi-OS, E2E, GHCR) y Dependabot
├── backend/            # API FastAPI, workers ARQ, módulos de dominio, Alembic y pytest
├── frontend/           # SPA en React 19 + TypeScript + Vite 6 + Tailwind CSS v4
├── infra/caddy/        # Plantillas Caddyfile para desarrollo y producción
├── installer/          # Instalador y desinstalador automatizados en Bash
├── docs/               # Documentación de arquitectura, diseño, seguridad y updates
├── Dockerfile          # Imagen unificada multi-stage (Frontend + Core API + auto-migrate)
├── compose.dev.yml     # Entorno completo de desarrollo local
├── compose.prod.yml    # Stack de producción con imagen oficial GHCR
├── Makefile            # Atajos de desarrollo y validación
└── LICENSE             # Licencia GNU AGPL-3.0
```

## Documentación técnica y comunidad

- [docs/architecture.md](docs/architecture.md) — Arquitectura por capas, topología de red, `forward_auth` y persistencia.
- [docs/design-system.md](docs/design-system.md) — Sistema visual oscuro grafito, tokens y componentes.
- [docs/security-sanitization.md](docs/security-sanitization.md) — Controles criptográficos, sanitización y aislamiento.
- [docs/updates-and-notifications.md](docs/updates-and-notifications.md) — Releases firmados con Ed25519, canales y notificaciones.
- [CONTRIBUTING.md](CONTRIBUTING.md) — Cómo contribuir manteniendo el estándar de código y CI.

---

## Ediciones y Licencia

**OriginLabs** sigue un modelo **Open Core** desarrollado por **Sushell**:

- **Community (Gratis):** núcleo completo *self-hosted* bajo licencia **[GNU AGPL-3.0](LICENSE)**.
- **Extensiones y servicios gestionados (Post-MVP):** capacidades adicionales oficiales de Sushell, edición Pro, Cloud y Enterprise.

<div align="center">
  <sub>Hecho por <strong>Sushell</strong> · <a href="https://sushell.com/originlabs">sushell.com/originlabs</a></sub>
</div>
