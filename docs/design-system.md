# Sistema Visual y Design System — OriginLabs

Este documento define la paleta, tipografía, superficies y patrones de interfaz oficiales del panel web de **OriginLabs** en React, basado en una estética minimalista de grafito oscuro.

---

## 1. Filosofía Visual

- **Grafito neutro limpio:** superficies en escala carbón/grafito (`#161618` / `#202023`) con contraste suave y sin saturación agresiva.
- **Navegación de 2 paneles como estructura principal:** barra lateral izquierda única (`256px`) con perfil arriba, acordeones con contadores cuadrados y área principal amplia.
- **Tabs minimalistas con subrayado inferior:** pestañas limpias en texto con borde inferior blanco (`2px solid #F4F4F5`) y buscador alineado a la derecha.
- **Tarjetas compactas y empty states centrados:** bordes sutiles `1px`, esquinas redondeadas suaves (`rounded-xl` / `rounded-2xl`) y botones discretos.

---

## 2. Paleta de Color

### Superficies (Dark Graphite)
| Token | Hex | Uso |
| --- | --- | --- |
| `--bg-canvas` | `#161618` | Fondo principal del área de trabajo |
| `--bg-sidebar` | `#202023` | Barra lateral izquierda principal |
| `--bg-container` | `#1C1C1F` | Contenedores grandes, tablas y empty states |
| `--bg-card` | `#1E1E21` | Tarjetas horizontales (proyectos recientes, carpetas, KPIs) |
| `--bg-elevated` | `#242429` | Inputs, cajas de ícono y chips elevados |
| `--bg-active` | `#2A2A2F` | Ítem activo de sidebar, botones secundarios y contadores cuadrados |

### Bordes (Hairlines `1px`)
| Token | Hex | Uso |
| --- | --- | --- |
| `--border-subtle` | `#2C2C31` | Divisores entre sidebar y canvas, filas y tarjetas base |
| `--border-strong` | `#3A3A42` | Bordes de inputs en foco, botones y chips activos |

### Tipografía
| Token | Hex | Uso |
| --- | --- | --- |
| `--text-primary` | `#F4F4F5` | Títulos, valores numéricos y pestaña activa |
| `--text-secondary` | `#A1A1AA` | Etiquetas, navegación inactiva y subtítulos |
| `--text-muted` | `#71717A` | Metadatos secundarios, placeholders y timestamps |

### Acentos y Estados Semánticos
| Token | Hex / RGBA | Uso |
| --- | --- | --- |
| `--accent-violet` | `#7C5CFF` / `#8B6BFF` | Isotipo OriginLabs y énfasis puntual |
| `--status-emerald` | `#34D399` | Servicios saludables, tareas completadas, estados activos |
| `--status-amber` | `#FBBF24` | Advertencias de capacidad, notas privadas, prioridad media/pendiente |
| `--status-rose` | `#EF6461` | Alertas críticas de seguridad, tareas rechazadas |

---

## 3. Patrones de Layout

1. **Sidebar izquierdo único (`w-64 bg-[#202023]`):**
   - Cabecera superior con avatar de usuario, nombre completo, correo y selector de organización.
   - Ítems con ícono `16px`, texto `13px`, acordeón colapsable en **Projects** (`—` / `+`) y chips de conteo cuadrados (`rounded-md bg-[#2A2A2F] tabular-nums`).
2. **Canvas principal (`bg-[#161618]`):**
   - Encabezados limpios, fila horizontal de tarjetas recientes (`Recent projects`) y sección inferior con tabs subrayadas (`border-b-2 border-[#F4F4F5]`).
   - Empty states centrados dentro de contenedores `rounded-2xl border-[#2B2B30] bg-[#1C1C1F]` con ícono en tono metálico neutro y acciones claras.
3. **Vistas colaborativas integradas:**
   - **Knowledge Base:** explorador con árbol de carpetas/etiquetas, tarjetas de carpeta y editor/visor de documentos Markdown bajo la misma paleta grafito.
   - **Team Chat & Tasks:** canales de conversación con soporte de *nota privada* y conversión directa de mensajes a tareas con acciones rápidas (`Aceptar`, `Completar`, `Rechazar`).
