<div align="center">

# OriginLabs

**Entorno de trabajo open source y modular que convierte cualquier servidor Linux en un espacio de desarrollo completo para equipos.**

*Un entorno de trabajo. Un comando. Un núcleo útil.*

[![Licencia AGPL-3.0](https://img.shields.io/badge/Licencia-AGPL--3.0-7C5CFF?style=flat-square)](LICENSE)
[![Python 3.12 · FastAPI](https://img.shields.io/badge/Backend-Python%203.12%20%C2%B7%20FastAPI-34D399?style=flat-square)](backend/pyproject.toml)
[![React · TypeScript](https://img.shields.io/badge/Frontend-React%20%C2%B7%20TypeScript%20%C2%B7%20Vite-8B6BFF?style=flat-square)](frontend/package.json)
[![Docker Compose](https://img.shields.io/badge/Infra-Docker%20%2B%20Caddy%20%2B%20PostgreSQL-26262B?style=flat-square)](compose.prod.yml)
[![Estado Pre-Beta](https://img.shields.io/badge/Estado-En%20desarrollo%20(Pre--Beta)-FBBF24?style=flat-square)](#estado-actual-camino-a-beta-v01)

[Sitio oficial](https://sushell.com/originlabs) · [Capacidades](#capacidades-principales) · [Consumo y optimización](#requisitos-del-servidor-y-consumo-de-recursos-estimado) · [Seguridad](#nivel-de-seguridad-y-cómo-se-maneja) · [Inicio rápido](#inicio-rápido-en-desarrollo-local) · [Documentación](#documentación-técnica)

</div>

---

## ¿Qué es OriginLabs?

**OriginLabs** es una plataforma *self-hosted* desarrollada por **Sushell** para que equipos de desarrollo pequeños y medianos dispongan de su propio entorno de trabajo privado: organizaciones, proyectos conectados a GitHub/GitLab y workspaces con IDE y terminal directamente en el navegador, en un solo servidor y listos desde el primer día.

### Capacidades principales

| Capacidad | Qué resuelve para tu equipo |
| --- | --- |
| **Instalación en un comando** | Despliegue automatizado sobre Docker + Compose con proxy inverso y certificados SSL automáticos (Let's Encrypt). |
| **Organizaciones y RBAC** | Multi-organización, invitaciones por enlace temporal y roles granulares por instancia, organización y proyecto. |
| **`Projects` (incluido)** | Conexión con **GitHub**, **GitLab** (y contrato preparado para Git interno), gestión de equipos y variables `.env` cifradas. |
| **`Workspaces` (incluido)** | Entornos aislados con IDE en el navegador (`code-server` / OpenVSCode Server) y terminal interactiva (`xterm.js`). |
| **Operación integrada** | Auditoría en PostgreSQL, monitoreo contra saturación, respaldos cifrados con `restic` y actualizaciones verificadas. |
| **Arquitectura modular** | Núcleo útil desde el inicio con base extensible para servicios propios adicionales (post-MVP). |

---

## Cómo funciona

Seis pasos desde un servidor vacío hasta tu equipo programando en un solo panel:

1. **Corres un comando** en tu servidor Linux compatible.
2. **Abres el panel** en tu dominio propio con **SSL automático** (Let's Encrypt vía Caddy).
3. **Creas la organización** e invitas a tus colaboradores.
4. **Conectas tus repositorios** (GitHub / GitLab) y organizas tus proyectos.
5. **Cada desarrollador abre su workspace:** IDE (`code-server`) + terminal web (`xterm.js`) en el navegador.
6. **Activas servicios adicionales** del ecosistema cuando el equipo los necesite (post-MVP).

---

## Estado actual (camino a Beta `v0.1`)

OriginLabs se encuentra en construcción activa hacia su primera **Beta Cerrada**:

- [x] **Infraestructura base y Design System:** Docker Compose (`dev` y `prod`), Caddy, PostgreSQL 16, Redis 7, FastAPI + ARQ Worker y panel React en tema oscuro neutro.
- [x] **Identidad, Organizaciones y RBAC:** setup único del primer administrador, sesiones en Redis (`HttpOnly`), invitaciones por enlace de 72h, roles (`owner`, `admin`, `developer`, `viewer`) y `forward_auth` para Caddy.
- [x] **Auditoría inmutable:** registro de eventos críticos en PostgreSQL (`/api/v1/audit`).
- [x] **`Projects` y conectores Git:** conexiones verificadas a GitHub y GitLab (con contrato listo para OriginLabs Git interno), equipos por proyecto y variables de entorno cifradas en reposo con Fernet.
- [x] **Notificaciones de nuevas versiones:** verificación automática (ARQ cron cada 6h) contra manifiestos firmados con **Ed25519** o GitHub Releases, banner en el panel para administradores, centro de notificaciones y webhook HMAC opcional.
- [ ] **Orquestador de `Workspaces` + Terminal:** contenedores `code-server` sin `root`, límites por clase, routing dinámico `ws-<id>.dominio` en Caddy y terminal `xterm.js` vía WebSocket.
- [ ] **Monitoreo y control de saturación:** métricas en vivo del host/contenedores y control de admisión por recursos.
- [ ] **Respaldos (`restic`) y actualización automática:** backups cifrados (local / S3), restauración desde el panel y *updater* con respaldo previo y rollback.
- [x] **Instalador en 1 comando (`install.sh`) y validación E2E:** instalación automatizada en Ubuntu 22.04/24.04 LTS y Debian 12, migraciones automáticas y smoke tests en vivo en CI.

---

## Arquitectura en un vistazo

```text
Internet / Equipo Dev (HTTPS 80/443)
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                           Caddy                             │
│  • panel.dominio         ──► Frontend React (SPA)           │
│  • panel.dominio/api/*   ──► FastAPI (api:8000)             │
│  • panel.dominio/ws/*    ──► FastAPI WebSockets (xterm.js)  │
│  • ws-<id>.dominio       ──► forward_auth(api) ──► ws-<id>  │
└───────────────┬─────────────────────────────┬───────────────┘
                │ (red núcleo: originlabs_net)│ (red aislada de workspaces)
                ▼                             ▼
┌───────────────────────────────┐   ┌─────────────────────────┐
│  Núcleo Backend (Python)      │   │  Workspace ws-<id>      │
│  • FastAPI + SQLAlchemy async │   │  • code-server (no-root)│
│  • ARQ Worker (Redis jobs)    │   │  • Volumen persistente  │
│  • PostgreSQL 16 + Redis 7    │   │  • Límites CPU/RAM/Disk │
└───────────────┬───────────────┘   └─────────────────────────┘
                │
                ▼
      Docker Engine / restic
```

---

## Requisitos del servidor y consumo de recursos (`ESTIMADO`)

> [!NOTE]
> Las cifras de CPU, memoria y disco de esta sección están marcadas como **`ESTIMADO`** (sin fuente de medición propia aún; se calibrarán empíricamente durante las pruebas previas a la Beta).

### Servidor base

| Concepto | Mínimo (`ESTIMADO`) | Recomendado (`ESTIMADO`) |
| --- | --- | --- |
| **Uso previsto** | Prueba · 1–2 workspaces | Equipo de ~5–10 devs · ~5 activos |
| **CPU** | 2 vCPU | 8 vCPU |
| **RAM** | 4 GB | 16–32 GB |
| **Disco** | 40 GB SSD | 200 GB NVMe |
| **SO soportados** | Ubuntu 22.04 LTS · Ubuntu 24.04 LTS · Debian 12 | Ubuntu 22.04 LTS · Ubuntu 24.04 LTS · Debian 12 |
| **Arquitectura** | `x86_64` y `ARM64` | `x86_64` y `ARM64` |
| **Dominio** | Dominio propio con DNS comodín (`*.dominio`) | Dominio propio con DNS comodín (`*.dominio`) |
| **Puertos** | `80` y `443` (web y SSL) · `22` (SSH de administración) | `80` y `443` (web y SSL) · `22` (SSH de administración) |

### Consumo por clase de workspace (`ESTIMADO`)

| Clase | CPU (`ESTIMADO`) | RAM (`ESTIMADO`) | Disco (`ESTIMADO`) | Uso previsto |
| --- | --- | --- | --- | --- |
| **Ligero** | 1 vCPU | 2 GB | 10 GB | Web, scripts |
| **Estándar** | 2 vCPU | 4 GB | 30 GB | Apps con base de datos |
| **Pesado** | 4 vCPU | 8 GB | 30 GB | Builds grandes, Docker dentro |

### Optimización de consumo de recursos al no estar en uso

OriginLabs está pensado para maximizar la densidad de desarrolladores en un único servidor sin pagar infraestructura ociosa:

- **0 CPU y 0 RAM cuando un workspace está apagado:** al detener un entorno, su contenedor se detiene por completo y libera el 100% de cómputo y memoria para el resto del equipo. El código, dependencias locales y configuración permanecen intactos en su volumen persistente para retomar el trabajo en segundos.
- **Auto-apagado por inactividad *(en hoja de ruta · Módulo 5)*:** suspensión automática configurable tras un periodo sin actividad en el IDE o la terminal, evitando que entornos olvidados consuman memoria durante la noche o fines de semana.
- **Núcleo liviano en reposo:** el plano de control (FastAPI + Worker ARQ + PostgreSQL + Redis + Caddy) se mantiene dentro de un margen estimado de **~1 vCPU y ~2 GB de RAM** sin workspaces activos.
- **Cuotas estrictas y control de admisión *(en hoja de ruta · Módulo 7)*:** cada workspace respeta límites duros según su clase (`Ligero`, `Estándar`, `Pesado`) y el sistema alerta o bloquea nuevos arranques antes de saturar el servidor.

**Cálculo rápido de dimensionamiento (`ESTIMADO`):**
- **CPU necesaria** ≈ `1 vCPU (núcleo)` + suma de vCPU de workspaces **activos simultáneamente**.
- **RAM necesaria** ≈ `2 GB (núcleo)` + suma de RAM de workspaces **activos simultáneamente**.
- **Disco necesario** ≈ `~15 GB (sistema e imágenes base)` + suma de disco de **todos** los workspaces (activos y apagados) + espacio para snapshots locales si no respaldas hacia S3.

---

## Nivel de seguridad y cómo se maneja

OriginLabs aplica **defensa en profundidad en 5 capas** para proteger tanto al servidor anfitrión como los repositorios y secretos del equipo:

| Capa | Qué protege | Cómo se implementa |
| --- | --- | --- |
| **1. Aislamiento de workspaces** | Evita que código arbitrario dentro de un workspace afecte al servidor o a otros proyectos. | Contenedores sin `root`, `no-new-privileges`, `cap_drop: ["ALL"]`, límites `cgroups` (CPU, RAM, disco y `pids_limit`), red Docker aislada sin acceso a PostgreSQL/Redis/`caddy:2019` y **prohibición de montar `/var/run/docker.sock`** del host *(diseño Módulo 5)*. |
| **2. Perímetro y acceso** | Protege el tráfico externo y los subdominios de IDE/terminal. | **Caddy** con TLS automático (Let's Encrypt), cabeceras HTTP de seguridad y endpoint interno **`forward_auth`** que valida la sesión del usuario antes de permitir la entrada a cualquier `ws-<id>.dominio`. |
| **3. Identidad y RBAC** | Controla quién accede a la instancia, organizaciones y proyectos. | Contraseñas con **Argon2id**, sesiones opacas en **Redis** con cookies `HttpOnly; SameSite=Lax`, *rate limiting* en login/setup y roles granulares por instancia, organización (`owner`, `admin`, `developer`, `viewer`) y proyecto (`maintainer`, `developer`, `viewer`). |
| **4. Secretos y sanitización** | Protege tokens Git, variables `.env` y entradas de API. | Cifrado en reposo con **Fernet** y clave dedicada (`ORIGINLABS_ENCRYPTION_KEY`) en PostgreSQL; validación estricta con **Pydantic v2** (bloqueo de inyección de flags en `git` y URLs inseguras), ORM parametrizado SQLAlchemy 2.0 y cero ejecución vía `shell=True`. |
| **5. Auditoría, backups y updates** | Garantiza trazabilidad y recuperación segura ante fallos. | Bitácora de auditoría en PostgreSQL (`/api/v1/audit`), respaldos cifrados con **`restic`** hacia disco local o S3, y actualizaciones verificadas por firma **Ed25519** con respaldo previo obligatorio y *rollback* automático *(Módulo 8)*. |

Para el detalle técnico de controles, sanitización y auditoría de dependencias, consulta [docs/security-sanitization.md](docs/security-sanitization.md).

---

## Instalación en 1 comando (VPS Linux)

En un servidor limpio con **Ubuntu 22.04 LTS**, **Ubuntu 24.04 LTS** o **Debian 12** (`x86_64` o `ARM64`):

**Con dominio propio y SSL automático (Let's Encrypt vía Caddy):**
```bash
curl -fsSL https://raw.githubusercontent.com/sushell-app/originlabs/main/installer/install.sh | sudo bash -s -- --domain panel.tu-dominio.com
```

**Prueba rápida sin dominio (solo HTTP por puerto 80 / IP):**
```bash
curl -fsSL https://raw.githubusercontent.com/sushell-app/originlabs/main/installer/install.sh | sudo bash -s -- --http-only
```

El instalador verifica el sistema operativo y recursos, instala Docker si falta, descarga la imagen única `ghcr.io/sushell-app/originlabs:latest`, genera secretos seguros en `/opt/originlabs/.env`, aplica las migraciones de PostgreSQL y levanta toda la plataforma mostrando el `bootstrap_token` inicial.

---

## Inicio rápido en desarrollo local

Requisitos previos en tu máquina: **Docker** y **Docker Compose**.

1. Copia el archivo de variables de entorno y levanta el stack:
   ```bash
   cp .env.example .env
   docker compose -f compose.dev.yml up --build -d
   ```
2. Aplica las migraciones de PostgreSQL:
   ```bash
   make migrate
   ```
3. Abre el panel en **`http://localhost`** para crear el primer administrador y tu primera organización.

Endpoints útiles en local:
- **Panel React (vía Caddy):** `http://localhost`
- **API Docs (solo desarrollo):** `http://localhost/api/docs`
- **Healthcheck (API + PostgreSQL + Redis):** `http://localhost/api/v1/health`
- **Metadata de instancia:** `http://localhost/api/v1/meta`

Comandos disponibles en [Makefile](Makefile):

| Comando | Descripción |
| --- | --- |
| `make dev` | Levanta todos los contenedores en desarrollo con rebuild. |
| `make down` | Detiene los contenedores locales. |
| `make logs` | Muestra logs en tiempo real. |
| `make migrate` | Ejecuta `alembic upgrade head` dentro del contenedor `api`. |
| `make check-compose` | Valida `compose.dev.yml` y `compose.prod.yml`. |
| `make check-py` | Compila/verifica sintaxis de `backend/`. |
| `make check-bash` | Valida sintaxis de los scripts en `installer/`. |

### Imagen única para VPS pequeños (`ghcr.io/sushell-app/originlabs`)

Si usas un PaaS o un VPS pequeño que despliega **un solo contenedor** (apuntando a tu PostgreSQL 16 y Redis 7 gestionados), OriginLabs publica una imagen unificada (`linux/amd64` y `linux/arm64`) que incluye tanto el panel React como la API FastAPI:

```bash
docker run -d --name originlabs -p 8000:8000 \
  -e ORIGINLABS_ENV=production \
  -e ORIGINLABS_DOMAIN=panel.tu-dominio.com \
  -e ORIGINLABS_ENCRYPTION_KEY="$(openssl rand -hex 32)" \
  -e DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/originlabs" \
  -e REDIS_URL="redis://host:6379/0" \
  ghcr.io/sushell-app/originlabs:latest
```

---

## Stack tecnológico y estructura

| Capa | Tecnología |
| --- | --- |
| **Contenedores y Proxy** | Docker + Docker Compose · Caddy (TLS automático + routing `*.dominio`) |
| **Backend y Workers** | Python 3.12+ · FastAPI · SQLAlchemy 2.0 async · Alembic · ARQ · Docker SDK |
| **Base de datos y Colas** | PostgreSQL 16 · Redis 7 |
| **Frontend** | React · TypeScript · Vite · Tailwind CSS |
| **Workspaces y Respaldos** | `code-server` / OpenVSCode Server · `xterm.js` · `restic` |

```text
.
├── backend/            # API FastAPI, workers ARQ, módulos de dominio, migraciones y tests
├── frontend/           # SPA en React + TypeScript + Vite + Tailwind CSS
├── infra/caddy/        # Plantillas Caddyfile para desarrollo y producción
├── installer/          # Scripts Bash de instalación y desinstalación (v0.1 en desarrollo)
├── docs/               # Documentación técnica (arquitectura, diseño, seguridad, updates)
├── Dockerfile          # Imagen unificada (Frontend + Core API) publicada en GHCR
├── compose.dev.yml     # Stack completo para desarrollo local
├── compose.prod.yml    # Stack de producción (usa ghcr.io/sushell-app/originlabs)
├── Makefile            # Atajos de desarrollo y validación
└── LICENSE             # Licencia GNU AGPL-3.0
```

---

## Documentación técnica

- [docs/architecture.md](docs/architecture.md) — Arquitectura por capas, topología de red, `forward_auth` y mapa de persistencia.
- [docs/design-system.md](docs/design-system.md) — Paleta oscura neutra, tokens CSS y patrones visuales del panel.
- [docs/security-sanitization.md](docs/security-sanitization.md) — Guía de sanitización del repositorio, API, contenedores Docker y frontend.
- [docs/updates-and-notifications.md](docs/updates-and-notifications.md) — Diseño de actualizaciones firmadas (`stable` / `beta`), notificaciones al admin, respaldo previo `restic` y rollback.

---

## Ediciones y Licencia

OriginLabs sigue un modelo **Open Core**:
- **Community (Gratis):** núcleo open source *self-hosted* bajo licencia **[GNU AGPL-3.0](LICENSE)**, útil desde el día uno con `Projects` y `Workspaces`.
- **Servicios y ediciones futuras (Post-MVP):** extensiones propias de Sushell, edición Pro, Cloud administrado y Enterprise.

Más información en **[sushell.com/originlabs](https://sushell.com/originlabs)**.
