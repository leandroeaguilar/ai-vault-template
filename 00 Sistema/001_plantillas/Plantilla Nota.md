---
type: Plantilla
title: "[Título del Concepto]"
estado: 🟢 Activo
fecha_creacion: 2026-06-17
generated:
  by: human:{{OWNER}}
  at: 2026-07-03T00:00:00Z
resource:
---

>[!warning] Plugin requerido
>Esta plantilla usa **Templater**. Si la fecha aparece como `<% tp.date.now(...) %>`, instalá el plugin Templater desde Configuración → Plugins de comunidad.

---
type: Explanation          # tipo Diátaxis que corresponda (§4.3 SOP Documentación)
tags: [tema]                   # minúsculas, SIN #, formato [a, b]
estado: 🌱 Semilla / 🏗️ Desarrollo / ✅ Consolidado
prioridad: ⏳ Media
responsable: "{{OWNER}}"
id: "EXP-000"                  # prefijo por tipo + número libre (§7.1 SOP Documentación)
fecha_creacion: <% tp.date.now("YYYY-MM-DD") %>
generated:                     # OKF v0.2: quién generó/editó y cuándo (§4 SOP Documentación)
  by: human:{{OWNER}}          # actor real; un agente pone su process:<id>
  at: <% tp.date.now("YYYY-MM-DD") %>T00:00:00Z   # última edición de fondo (ISO 8601)
moc_principal: "[[MOC - ]]"
life_areas: []
domains: []
---

# [Título del Concepto]

## Definición esencial
Una definición concisa que sirva de ancla conceptual. Una sola idea principal.

## Qué problema resuelve
Explica por qué esta nota merece existir y cuándo usarla.

## Desarrollo
Contexto, detalles técnicos, comandos, ejemplos, código reutilizable.

```
// código o snippet si aplica
```

## Conexiones
- [[nota-relacionada-1]]
- [[nota-relacionada-2]]
- MOC: [[MOC - ]]
- Proyecto: [[]]
- Fuente: [[]]

## Evolución
Cómo cambia este conocimiento con el tiempo. Actualizá cada vez que aparezca nueva información relevante (y subí `timestamp`).
- **Qué aprendí desde la última vez:**
- **Qué cambió / qué corregí:**

> [!info] Esta plantilla absorbe a la "Nota Evergreen"
> No hay tipo aparte para notas vivas. Una **nota evergreen** = esta misma nota con `estado: 🌱 Semilla` que revisás y hacés crecer periódicamente. La fecha de creación queda en `fecha_creacion`; cada revisión de fondo actualiza `timestamp`.

> [!tip] Regla de oro
> Si este concepto apareció 3 o más veces en distintas fuentes → merece vivir aquí como nota permanente.
