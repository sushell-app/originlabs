# Política de Seguridad — OriginLabs

La seguridad del servidor anfitrión, los contenedores de workspace y los secretos de tu equipo es prioridad en **OriginLabs**.

## Versiones soportadas

OriginLabs se encuentra actualmente en fase **Pre-Beta (`0.1.x`)** en desarrollo activo. Las correcciones de seguridad se aplican directamente sobre la rama principal y los próximos releases etiquetados.

## Cómo reportar una vulnerabilidad

**Por favor, no reportes vulnerabilidades de seguridad abriendo un Issue público.**

Si encuentras un problema relacionado con:
- Escape o aislamiento de contenedores de workspace (`Docker` / `cgroups` / red).
- Autenticación, sesiones, RBAC o validación `forward_auth` en Caddy.
- Cifrado en reposo de tokens Git, variables de entorno o manejo de secretos.
- Scripts de instalación o actualización (`installer/install.sh`, `installer/uninstall.sh`).

Repórtalo de forma privada mediante:
1. **GitHub Security Advisories** (pestaña *Security → Advisories → Report a vulnerability* del repositorio), o
2. Contacto directo con el equipo de seguridad en **https://sushell.com/originlabs**.

Incluye pasos de reproducción, impacto estimado y, de ser posible, una prueba de concepto mínima. Responderemos confirmando la recepción y coordinando la mitigación antes de divulgar detalles públicos.
