# Sanitización, Seguridad e Higiene del Proyecto — OriginLabs

Este documento define las reglas prácticas para mantener limpio y seguro el repositorio, el backend en Python/FastAPI, los contenedores de workspace, el frontend en React y el proxy Caddy.

---

## 1. Sanitización del Repositorio Git (Antes de cada `git push`)

1. **Exclusión de documentos internos y secretos:**
   - [`.gitignore`](../.gitignore) excluye explícitamente documentación interna de planificación, archivos `.env`, llaves privadas (`*.pem`, `*.key`), cachés de Python y `node_modules/`.
   - **Nunca** uses `git add -f` sobre archivos ignorados ni incluyas credenciales reales en `.env.example` o fixtures de tests.
   - Si alguna vez un archivo interno o secreto llega a quedar trackeado por error, retíralo del índice (`git rm --cached`) y rota inmediatamente cualquier clave expuesta.
2. **Separación estricta Open Core:**
   - Este repositorio contiene únicamente código **AGPL-3.0** del núcleo y módulos incluidos.
   - Nunca subas código propietario de futuros servicios comerciales ni claves privadas de firma (solo la clave pública de verificación para `releases.json` o licencias).
3. **Escaneo automático de secretos:**
   - Ejecutar `gitleaks` (local o en CI) antes de publicar releases para garantizar que no existan tokens de GitHub/GitLab, claves S3 ni contraseñas en el historial.

---

## 2. Sanitización de Entradas y API (Backend Python / FastAPI)

1. **Validación estricta con Pydantic v2:**
   - Todo parámetro de ruta, query y body debe pasar por esquemas Pydantic con límites de longitud y expresiones regulares estrictas.
   - Los identificadores usados en subdominios o nombres Docker (slugs de organización, proyecto o workspace) deben restringirse a `^[a-z0-9][a-z0-9-]{1,30}[a-z0-9]$`.
   - Validar URLs de repositorios Git (`https://` o formato SSH permitido) y nombres de rama/ref antes de pasarlos a `git`, bloqueando argumentos que empiecen por `-` (prevención de *argument injection*).
2. **Cero ejecución de shell con entradas de usuario:**
   - Prohibido usar `os.system()`, `subprocess(..., shell=True)` o interpolar variables en cadenas de comandos.
   - La gestión de contenedores debe hacerse exclusivamente mediante el **SDK oficial de Docker para Python** (o llamadas directas al socket Docker API).
   - Para utilidades CLI inevitables como `restic` o `git`, usar siempre listas de argumentos (`subprocess.run(["restic", ...], shell=False)`) y variables de entorno dedicadas para credenciales.
3. **Consultas SQL parametrizadas:**
   - Usar siempre el ORM y queries parametrizadas de SQLAlchemy 2.0. Prohibido construir SQL por concatenación o f-strings.
4. **Secretos en reposo y en logs:**
   - Tokens OAuth de GitHub/GitLab, secretos OIDC, credenciales S3 y variables de entorno de proyecto deben almacenarse **cifrados** en PostgreSQL (p. ej. AES-GCM / Fernet derivado con clave dedicada).
   - Nunca registrar tokens, contraseñas, cookies ni headers `Authorization` en logs de FastAPI o ARQ.
5. **Protección contra abuso (Rate Limiting):**
   - Limitar intentos de login, Setup inicial, emisión de tickets WebSocket y creación masiva de workspaces usando contadores en Redis.

---

## 3. Sanitización y Aislamiento de Workspaces (Docker)

Los workspaces ejecutan código arbitrario de desarrolladores; deben tratarse como entornos no confiables respecto al host:

- **Sin `root`:** usuario no privilegiado dentro de la imagen de workspace.
- **Privilegios mínimos:** `security_opt: ["no-new-privileges:true"]` y `cap_drop: ["ALL"]`.
- **Límites duros por clase (`cgroups`):** memoria (`mem_limit`), CPU (`nano_cpus`), límite de procesos (`pids_limit`) para evitar *fork bombs*, y cuota de almacenamiento por volumen.
- **Aislamiento de red:** los workspaces no pueden alcanzar `postgres`, `redis` ni `caddy:2019` (Admin API).
- **Sin socket Docker del host:** prohibido montar `/var/run/docker.sock` dentro de un workspace. Para el caso futuro de clase `Pesado` (*"Docker dentro"*), usar aislamiento específico (rootless DinD / Sysbox) y validar el modelo de amenazas antes de habilitarlo.

---

## 4. Sanitización del Frontend (React) y Proxy (Caddy)

1. **Frontend React:**
   - Confiar en el escape automático de JSX; evitar `dangerouslySetInnerHTML` o validarlo con sanitización estricta si alguna vez se renderiza Markdown.
   - No guardar tokens de sesión de larga duración en `localStorage`; usar cookies **`HttpOnly; Secure; SameSite=Lax`** emitidas por FastAPI.
   - Aplicar validación CSRF (token o doble validación de origen) en peticiones mutantes cuando se use cookie de sesión.
2. **Cabeceras de seguridad en Caddy:**
   - En producción (`Caddyfile.prod`), aplicar `Strict-Transport-Security`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, `X-Frame-Options: SAMEORIGIN` y política `Content-Security-Policy` acorde al panel y WebSockets.

---

## 5. Checklist de Higiene antes de cada Merge / Release

- **Python (`backend/`):** `ruff check .`, `mypy app`, `pytest`, y revisión periódica de CVEs con `pip-audit`.
- **React (`frontend/`):** `npm run typecheck`, `npm run lint`, `npm run build` y `npm audit --omit=dev`.
- **Instalador (`installer/`):** `bash -n` y `shellcheck` sobre `install.sh` y `uninstall.sh`.
- **Docker:** imágenes base fijadas por tag/digest y ejecutándose con usuario no-root cuando aplique (`api` y workspaces).
