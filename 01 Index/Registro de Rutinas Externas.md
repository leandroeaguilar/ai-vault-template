---
type: Reference
title: "Registro de Rutinas Externas"
description: "Rutinas programadas en plataformas sin API para listarlas (Gemini, ChatGPT). Las lee el Mapa de mis agentes, pestaña Rutinas & Calendario."
tags: [rutinas, automatización, mapa]
estado: 🟢 Activo
responsable: "{{OWNER}}"
id: "REG-RUTINAS-EXTERNAS-001"
generated:
  by: agent:claude-code
  at: 2026-10-04T00:00:00Z
fecha_creacion: 2026-10-04
resource:
---

# Registro de Rutinas Externas

Las rutinas que corren solas viven en tres lugares. Solo esta tabla se carga a mano:

| Dónde corre | Cómo llega al mapa |
|---|---|
| Esta máquina (Programador de Tareas `SistemaMaestro-*`) | Automático: `mapa-agentes.py` lo lee en cada regeneración |
| Nube de Claude (`/schedule`, claude.ai/code) | Snapshot `.vault-meta/rutinas-cloud.json`, que refresca la skill `/mapa` |
| **Gemini** (acciones programadas) y **ChatGPT** (tareas programadas) | **Esta tabla.** Ninguna de las dos expone una API para listarlas |

## Rutinas

Una fila por rutina. Al crear, cambiar o pausar una en Gemini o ChatGPT, actualizá la fila acá.

- **Cadencia:** `diaria` · `lun-vie` · `semanal` · `mensual`
- **Día:** nombre del día si es `semanal` (`lunes`), número si es `mensual` (`15`); vacío en los demás casos
- **Hora:** hora local `HH:MM`
- **Activa:** `sí` / `no`

| Plataforma | Rutina | Cadencia | Día | Hora | Qué hace | Activa |
|---|---|---|---|---|---|---|

## Relacionado

- [SOP Hooks y Automatización](<../00 Sistema/SOP Hooks y Automatización.md>)
- Skill `/mapa`: `.agents/skills/mapa/SKILL.md`
