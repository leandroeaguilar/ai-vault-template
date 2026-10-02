---
type: Reference
title: "Tablero Headless Kanban y Despachador de Tareas"
description: "Documentación y guía operativa del tablero Kanban headless para desacoplamiento y validación humana."
tags: [kanban, multiagente, tareas, headless, proyectos]
estado: 🟢 Activo
prioridad: 🟡 Media
id: "REF-KANBAN-001"
generated:
  by: human:{{OWNER}}
  at: 2026-10-02T00:00:00Z
fecha_creacion: 2026-10-02
---

# Tablero Headless Kanban y Despachador de Tareas

El **Tablero Headless Kanban** es el mecanismo de desacoplamiento entre el usuario, los agentes de fondo y las tareas del vault. 

En lugar de requerir una sesión de chat abierta continua, cualquier actor (humano o agente) deposita una **tarjeta markdown** en `Pendientes/`. 

---

## 📂 Estructura de Directorios

- **`Pendientes/`**: Tarjetas creadas a la espera de ejecución o atención.
- **`En_Progreso/`**: Tarjetas que se están procesando actualmente.
- **`Hecho/`**: Tarjetas completadas con su informe o recibo de ejecución.
- **`Archivado/`**: Tarjetas históricas archivadas.

---

## 🏷️ Anatomía de una Tarjeta Kanban

Toda tarjeta sigue la plantilla canónica [Plantilla Tarjeta Kanban](<../../00 Sistema/001_plantillas/Plantilla Tarjeta Kanban.md>):

```yaml
---
type: Tarea
title: "Revisar enlaces tras mover notas"
agent: mantenedor     # o verifier, general
skill: check-links    # skill a invocar
prioridad: 🟡 Media   # 🔥 Alta, 🟡 Media, 🟢 Baja
estado: 📥 Pendiente  # 📥 Pendiente, ⚙️ En Progreso, ✅ Hecho, ⚠️ Error
recibo: false         # true si es un recibo para validación humana
fecha_creacion: YYYY-MM-DD
---
```

---

## 🛡️ El Patrón de Recibos y Validación Humana (Human-in-the-Loop)

Un principio fundamental de este vault es: **los agentes proponen, los humanos deciden.**

Cuando un agente realiza un borrador, no sobreescribe ni publica directamente el documento final. En su lugar:
1. Genera el entregable como borrador o archivo propuesto.
2. Emite un **recibo** en `03 Proyectos/Kanban/Pendientes/` con `--recibo`.
3. El usuario puede abrir la tarjeta, revisar el enlace del diff o borrador, y mover la tarjeta a `Hecho/` tras aprobarlo.

---

## 🛠️ Herramientas CLI

```bash
# Crear una tarea estándar en Pendientes/
python .claude/scripts/crear-tarea.py --titulo "Auditar enlaces rotos" --agent "mantenedor" --skill "check-links"

# Crear un recibo de validación humana
python .claude/scripts/crear-tarea.py --titulo "Revisar borrador propuesto" --agent "general" --recibo
```
