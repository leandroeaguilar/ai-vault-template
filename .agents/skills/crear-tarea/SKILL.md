---
name: crear-tarea
description: Crea una tarjeta de tarea en el tablero Headless Kanban (03 Proyectos/Kanban/Pendientes/) con frontmatter canónico y contratos E/S.
tipo: acción
version: "1.0.0"
---

# crear-tarea

## ⚡ Cuándo usar
- **Manual:** Cuando el usuario diga «crea una tarea: …», «apunta en Kanban …» o delegue un trabajo pendiente.
- **Por agentes:** Cuando un agente termina un paso y necesita dejar una tarea subsiguiente o un recibo de validación humana en el tablero sin abrir Obsidian.

## 📥 Entradas (Inputs)
- **Parámetros de tarea:** Título descriptivo, agente asignado (`mantenedor`, `verifier`, `general`), skill a invocar.
- **Ruta de origen:** Archivo de insumo en `06 Raw/` o `04 Knowledge/`.
- **Plantilla base:** [Plantilla Tarjeta Kanban](<../../../00 Sistema/001_plantillas/Plantilla Tarjeta Kanban.md>).

## 📤 Salidas (Outputs)
- **Tarjeta Kanban:** Escribe `03 Proyectos/Kanban/Pendientes/AAAA-MM-DD - <slug>.md` con frontmatter canónico (`type: Tarea`, `estado: 📥 Pendiente`, `prioridad`).
- **Enlace Markdown:** Emite el enlace directo `[Título](<03 Proyectos/Kanban/Pendientes/...>)`.

## 📋 Pasos de ejecución
1. Ejecutar el script determinista:
   ```bash
   python .claude/scripts/crear-tarea.py --titulo "<título>" --agent "<agente>" --skill "<skill>" --prioridad "🟡 Media"
   ```
2. Si es un recibo de validación para el usuario, añadir el flag `--recibo`:
   ```bash
   python .claude/scripts/crear-tarea.py --titulo "Revisar: <título>" --agent "general" --recibo
   ```
3. Confirmar al usuario el enlace de la tarjeta creada.
