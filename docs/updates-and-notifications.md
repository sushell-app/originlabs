# Actualizaciones Fáciles y Notificaciones al Administrador — OriginLabs

Este documento define cómo cada servidor con OriginLabs detecta nuevas versiones sin intervención manual, **notifica al administrador** de la instancia y ejecuta actualizaciones en 1 clic (o programadas) con respaldo previo y rollback seguro.

---

## 1. Principio de Diseño: Pull Firmado (Sin Telemetría Invasiva)

Cada servidor instalado con OriginLabs es autónomo: **no necesita que Sushell tenga acceso SSH ni un agente externo conectado**.

En su lugar, el servidor consulta periódicamente un manifiesto público y firmado (`releases.json`) servido desde la URL oficial de distribución (respaldada por GitHub Releases):

```text
https://originlabs.<dominio-sushell>/releases.json   (por confirmar URL final)
```

---

## 2. Manifiesto `releases.json` Firmado (Ed25519)

El manifiesto expone la última versión recomendada para cada canal (`stable` y `beta`) con firma criptográfica verificada usando la clave pública de Sushell embebida en el backend:

```json
{
  "schema_version": 1,
  "channels": {
    "stable": {
      "version": "0.2.0",
      "released_at": "2026-12-15T18:00:00Z",
      "severity": "security",
      "min_upgrade_from": "0.1.0",
      "changelog_summary": [
        "Parche de seguridad en aislamiento de red de workspaces.",
        "Mejora de velocidad al restaurar snapshots restic."
      ],
      "breaking_changes": false,
      "release_notes_url": "https://github.com/sushell/originlabs/releases/tag/v0.2.0",
      "images": {
        "api": "ghcr.io/sushell/originlabs-api:0.2.0@sha256:...",
        "frontend": "ghcr.io/sushell/originlabs-frontend:0.2.0@sha256:..."
      }
    },
    "beta": {
      "version": "0.3.0-beta.1",
      "released_at": "2026-12-20T18:00:00Z",
      "severity": "normal",
      "min_upgrade_from": "0.1.0",
      "changelog_summary": ["Soporte inicial de auto-apagado configurable."],
      "breaking_changes": false
    }
  },
  "signature": "<firma_ed25519_del_payload>"
}
```

**Ventajas de este enfoque:**
- El servidor verifica la firma **localmente** antes de aceptar una actualización.
- Distingue actualizaciones normales (`normal`) de parches críticos (`security`).
- Respeta el canal elegido por el admin en el panel (`stable` por defecto, o `beta`).

---

## 3. Detección y Notificación al Administrador (`instance_admin`)

Un job periódico en el worker **ARQ** (cada 6–12 horas) consulta `releases.json`, compara la versión remota contra `app_version` instalada y guarda el resultado en PostgreSQL (`update_checks` / `notifications`), evitando duplicar alertas para la misma versión.

### Canales de notificación al administrador

1. **Panel Web React (Activo por defecto · Cero configuración):**
   - **Banner superior discreto** visible únicamente para administradores (`instance_admin`) cuando hay una versión nueva:
     - Azul/Índigo para `severity: "normal"` (*"Nueva versión 0.2.0 disponible"*).
     - Ámbar/Rojo para `severity: "security"` (*"Actualización de seguridad recomendada: 0.2.0"*).
   - **Centro de notificaciones (campana en barra superior):** historial de nuevas versiones detectadas, resúmenes de cambios (`changelog_summary`), resultado de actualizaciones automáticas o avisos de respaldo/rollback.
   - Acciones directas desde la alerta: **"Ver cambios"**, **"Actualizar ahora"** o **"Posponer / Programar en ventana"**.

2. **Correo electrónico SMTP (Opcional, configurable en Panel → Operaciones):**
   - Si el admin configura su servidor SMTP, OriginLabs envía correo a los administradores de la instancia en 3 eventos clave:
     - Nueva versión disponible (priorizando alertas `security`).
     - Actualización automática completada con éxito.
     - Fallo de actualización y resultado del rollback.

3. **Webhook saliente (Opcional, configurable en Panel → Operaciones):**
   - Envío de evento JSON firmado (`HMAC-SHA256`) compatible con Slack, Discord, Microsoft Teams o n8n para equipos que prefieren alertas en su chat operativo.

---

## 4. Actualización Fácil en 1 Clic o en Ventana de Mantenimiento

### ¿Por qué un *Updater Helper* desacoplado?
El contenedor `api` **no puede actualizarse y reiniciarse a sí mismo directamente** mediante `docker compose up -d api`, porque al detenerse cortaría el proceso de actualización a mitad de camino.

Para resolverlo de forma limpia y sin intervención SSH:
- Se utiliza un contenedor auxiliar efímero o servicio ligero en el host (**`originlabs-updater`**), disparado de forma controlada cuando el admin pulsa **"Actualizar ahora"** o cuando se cumple la ventana de mantenimiento semanal/diaria.

### Flujo seguro en 5 pasos

1. **Pre-chequeo:** verificar espacio libre en disco, que no haya otra actualización en curso y que el canal/firma de `releases.json` sean válidos.
2. **Respaldo previo obligatorio (`restic`):** crear un snapshot consistente (dump de PostgreSQL + configuración + volúmenes críticos) etiquetado `pre-update-<version-actual>`. Si el respaldo falla, la actualización se aborta antes de tocar ningún contenedor.
3. **Descarga previa (`pull`):** descargar y verificar digests de las nuevas imágenes Docker mientras la versión actual sigue atendiendo al equipo sin cortes.
4. **Recreación y migración:** el *updater* guarda la versión previa como `rollback_target`, recrea `api`, `worker`, `frontend-assets` y `caddy`, y ejecuta `alembic upgrade head`.
5. **Verificación de salud y Rollback automático:**
   - Espera a que `GET /api/v1/health` responda `200 OK` (DB + Redis saludables) dentro de un timeout (ej. 60 s).
   - **Si pasa:** marca la actualización como exitosa y notifica al admin.
   - **Si falla:** restaura automáticamente los tags de imagen previos + snapshot `pre-update` de PostgreSQL si hubo migración, levanta la versión anterior y dispara una notificación crítica al administrador.

---

## 5. Alcance por Fases

- **Beta Cerrada (Módulo 8):**
  - Consulta periódica a `releases.json` firmado (canales `stable` / `beta`).
  - Banner + campana de notificaciones en React para `instance_admin`.
  - Actualización en 1 clic desde el panel y ventana automática con respaldo previo `restic` + rollback.
  - Notificación opcional por correo SMTP y webhook saliente.
- **Post-Beta:**
  - Notificaciones por canal de alertas de saturación de servidor y expiración/renovación de licencias comerciales.
