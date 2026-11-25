# Arquitectura Técnica — OriginLabs

Este documento describe la arquitectura del núcleo de OriginLabs, el aislamiento de red entre servicios, el flujo de autenticación hacia workspaces y la organización del código.

---

## 1. Arquitectura por Capas

1. **Capa de Infraestructura (Host Linux + Docker Compose):**
   - Soportado únicamente sobre **Ubuntu 22.04 LTS**, **Ubuntu 24.04 LTS** y **Debian 12** (`x86_64` y `ARM64`).
   - Orquesta `caddy`, `api`, `worker`, `postgres`, `redis` y el frontend estático (o Vite en desarrollo).
2. **Núcleo OriginLabs (`AGPL-3.0`):**
   - Identidad, organizaciones, permisos RBAC y OIDC/SSO.
   - Gestión de proyectos y repositorios.
   - Orquestación de recursos, entornos y `forward_auth`.
   - Auditoría inmutable, API `/api/v1` y bus de eventos en Redis.
   - Respaldos (`restic`), actualizaciones y registro de extensiones/licencias.
3. **Módulos Core incluidos desde el día uno:**
   - **`Projects`**: equipos, repositorios GitHub/GitLab y variables cifradas.
   - **`Workspaces`**: contenedores aislados con `code-server` / OpenVSCode Server y terminal `xterm.js`.
4. **Capa de Extensiones (Post-MVP):**
   - Servicios propios de Sushell ejecutándose como contenedores firmados e independientes conectados al núcleo vía API y eventos, sin catálogo de terceros.

---

## 2. Topología de Red y Aislamiento

```text
Internet / Equipo Dev (HTTPS 80/443)
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                           Caddy                             │
│  • dominio.com           ──► Frontend React (SPA)           │
│  • dominio.com/api/*     ──► FastAPI (api:8000)             │
│  • dominio.com/ws/*      ──► FastAPI WebSockets (xterm.js)  │
│  • ws-<id>.dominio.com   ──► forward_auth(api) ──► ws-<id>  │
└───────────────┬─────────────────────────────┬───────────────┘
                │ (red núcleo: originlabs_net)│ (redes aisladas workspaces)
                ▼                             ▼
┌───────────────────────────────┐   ┌─────────────────────────┐
│  Núcleo Backend (Python)      │   │  Workspace ws-<id>      │
│  • FastAPI (api:8000)         │   │  • code-server (no-root)│
│  • ARQ Worker (Redis jobs)    │   │  • Volumen persistente  │
│  • PostgreSQL 16              │   │  • Límites CPU/RAM/Disk │
│  • Redis 7                    │   │  • Sin acceso al núcleo │
└───────────────┬───────────────┘   └─────────────────────────┘
                │
                ▼
      Docker Engine / restic
```

**Principio clave de aislamiento:** los contenedores de workspace **nunca** comparten red con `postgres`, `redis` ni con la Admin API interna de Caddy (`:2019`), y tampoco reciben el socket Docker del host (`/var/run/docker.sock`).

---

## 3. Flujos Principales

### 3.1 Acceso autenticado a `code-server` (`forward_auth`)
1. El desarrollador abre `https://ws-<id>.<dominio>`.
2. **Caddy** intercepta la petición y consulta a `http://api:8000/api/v1/internal/forward-auth`.
3. **FastAPI** valida la cookie de sesión en **Redis** y verifica en **PostgreSQL** que el usuario pertenece a la organización/proyecto del workspace.
4. Si está autorizado (`200 OK`), Caddy reenvía el tráfico hacia `code-server` dentro del contenedor del workspace; si no (`401`/`403`), redirige al login del panel.

### 3.2 Terminal web en tiempo real (`xterm.js`)
1. Desde React, el desarrollador solicita abrir una sesión de terminal; **FastAPI** valida RBAC, registra el evento en **Auditoría** y emite un token efímero de sesión.
2. React abre un WebSocket hacia `/ws/workspaces/<id>/terminal?token=...` a través de Caddy.
3. **FastAPI** (usando soporte WebSocket nativo) conecta el stream bidireccional con Docker Exec PTY dentro del contenedor del workspace, soportando redimensionamiento (`cols`/`rows`) y cierre limpio.

### 3.3 Operaciones asíncronas (Docker, Git y `restic`)
- Ninguna operación pesada corre dentro de una petición HTTP síncrona.
- `api` encola el trabajo en **Redis** y retorna un identificador de tarea.
- `worker` (**ARQ**) ejecuta la creación/arranque/apagado de contenedores vía Docker Engine SDK, actualiza rutas en Caddy Admin API (`:2019`), corre respaldos `restic` y actualiza el estado en PostgreSQL.

---

## 4. Organización del Código

```text
.
├── backend/
│   ├── app/
│   │   ├── api/v1/          # Routers REST (/health, /meta, futuros endpoints) y WebSockets
│   │   ├── core/            # Config (pydantic-settings), SQLAlchemy async, cliente Redis
│   │   ├── modules/
│   │   │   ├── identity/    # Setup admin, auth, orgs, RBAC, OIDC, forward_auth
│   │   │   ├── audit/       # Bitácora inmutable de seguridad en PostgreSQL
│   │   │   ├── extensions/  # Contratos LicenseProvider y ExtensionRegistry (Open Core)
│   │   │   ├── projects/    # Proyectos, equipos y conectores GitHub / GitLab
│   │   │   ├── workspaces/  # Orquestador Docker, clases, Caddy routing y PTY
│   │   │   └── system/      # Métricas, control de saturación, backups restic y updates
│   │   ├── main.py          # Entrypoint FastAPI
│   │   └── worker.py        # Entrypoint ARQ Worker
│   ├── migrations/          # Entorno async de Alembic
│   └── tests/               # Tests pytest
├── frontend/
│   └── src/                 # SPA en React + TypeScript + Vite + Tailwind CSS
├── infra/caddy/             # Caddyfile.dev y Caddyfile.prod
├── installer/               # install.sh y uninstall.sh en Bash puro
├── compose.dev.yml          # Stack de desarrollo local
└── compose.prod.yml         # Stack de producción
```

---

## 5. Mapa de Persistencia

| Almacenamiento | Qué guarda |
| --- | --- |
| **PostgreSQL (`postgres_data`)** | Usuarios, organizaciones, roles, proyectos, credenciales Git/OIDC/S3 cifradas, metadatos de workspaces, bitácora de auditoría e historial de actualizaciones/notificaciones. |
| **Redis (`redis_data`)** | Sesiones activas, cola de trabajos ARQ, estado temporal de métricas en vivo y bus de eventos. |
| **Volúmenes de Workspace** | Carpeta de trabajo persistente por workspace (conservada cuando el workspace se apaga). |
| **Caddy (`caddy_data`)** | Certificados TLS emitidos por Let's Encrypt y configuración persistida. |
