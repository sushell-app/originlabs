# Sistema Visual y Design System — OriginLabs

Este documento define la paleta, tipografía, superficies y patrones de interfaz oficiales del panel web de **OriginLabs** en React.

---

## 1. Filosofía Visual

- **Oscuro neutro (grafito / obsidiana):** superficies limpias sin tinte azulado excesivo, pensadas para jornadas largas de desarrollo.
- **Jerarquía por contraste y bordes `1px`:** separación nítida con hairlines sutiles en lugar de sombras pesadas.
- **Densidad técnica clara:** contadores alineados (`tabular-nums`), indicadores semánticos sobrios y navegación en tres niveles cuando el contexto lo requiere.

---

## 2. Paleta de Color

### Superficies (Dark Neutrals)
| Token | Hex | Uso |
| --- | --- | --- |
| `--bg-canvas` | `#0E0E10` | Fondo principal del área de trabajo |
| `--bg-pane` | `#141417` | Panel contextual secundario / tarjetas base |
| `--bg-sidebar` | `#18181B` | Barra lateral principal de navegación |
| `--bg-card` | `#17171A` | Tarjetas de contenido y listas |
| `--bg-elevated` | `#1E1E22` | Inputs, cajas de ícono y chips |
| `--bg-hover` | `#232329` | Hover y pestaña segmentada activa |

### Bordes (Hairlines `1px`)
| Token | Hex | Uso |
| --- | --- | --- |
| `--border-subtle` | `#26262B` | Divisores entre columnas, tarjetas y filas |
| `--border-strong` | `#323238` | Bordes de pills activos, inputs en foco y controles |

### Tipografía
| Token | Hex | Uso |
| --- | --- | --- |
| `--text-primary` | `#F4F4F6` | Títulos, valores KPI y texto principal |
| `--text-secondary` | `#A1A1AA` | Descripciones, navegación inactiva y etiquetas |
| `--text-muted` | `#71717A` | Micro-títulos de sección (`10px–11px` uppercase `tracking-wider`), breadcrumbs |

### Acento y Estados Semánticos
| Token | Hex / RGBA | Uso |
| --- | --- | --- |
| `--accent-violet` | `#7C5CFF` / `#8B6BFF` | Isotipo, indicador lateral activo (`3px`), enfoque primario |
| `--accent-wash` | `rgba(124, 92, 255, 0.14)` | Fondo de ítem activo en navegación |
| `--accent-lavender` | `#C4B5FD` | Badges numéricos de módulo / énfasis suave |
| `--status-emerald` | `#34D399` | Servicios saludables, checks de verificación, workspaces activos |
| `--status-amber` | `#FBBF24` | Advertencias de capacidad/saturación, setup pendiente |
| `--status-rose` | `#EF6461` / `#F87171` | Alertas críticas, errores de servicio, badge de notificaciones |

---

## 3. Patrones de Layout y Componentes

1. **Shell de 3 paneles:**
   - **Sidebar principal (`240px`):** isotipo OriginLabs, navegación agrupada en micro-secciones (`ENTORNO`, `EQUIPO`, `SISTEMA`), indicador vertical violeta de `3px` en el ítem activo y pie con edición + versión.
   - **Panel contextual colapsable (`256px`):** selector de contexto/instancia, toggle segmentado, buscador con atajo `⌘ K` y árbol jerárquico con líneas guía verticales (`1px`).
   - **Canvas principal:** breadcrumbs superiores, encabezado de página, pestañas segmentadas (`Overview / Recursos / Módulos`), tarjetas KPI con `tabular-nums` y tablas limpias.
2. **Reglas de consistencia:**
   - Usar `tabular-nums` en cualquier métrica, contador de badge o cuota de CPU/RAM/disco.
   - Mantener bordes `1px solid #26262B` en tarjetas y paneles en lugar de `shadow-xl`.
   - Reservar el color violeta (`#7C5CFF`) y los badges semánticos solo para estado activo, prioridad o métricas reales.
