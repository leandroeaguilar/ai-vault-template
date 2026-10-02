---
name: agent-diary
description: Registra la entrada de handoff en la Bitácora de Agentes al finalizar un bloque de trabajo en el vault.
tipo: meta
version: "1.0"
---

# Agent Diary (Bitácora de Agentes)

Ejecutá esta skill al concluir un bloque coherente de trabajo o sesión en el vault para registrar el handoff.

## Cuándo usar
- Activación al cierre de sesión o bloque de trabajo: antes de hacer commit o al concluir una tarea compleja.
- Disparada al recibir recordatorio del hook `Stop` o al invocar `/agent-diary`.

## Entradas
- Lee `git status` y `git log` reciente para recopilar los cambios realizados.
- Lee `05 Diario/Bitácora Agentes/YYYY-MM.md` del mes actual para verificar si ya existe una entrada de la sesión actual.

## Salidas
- Escribe o amplía la entrada de handoff en `05 Diario/Bitácora Agentes/YYYY-MM.md`.

## Reglas de la Bitácora

1. **UNA sola entrada por sesión.** Si continuás trabajando en la misma sesión, ampliá tu propia entrada (no crees `(cont.)`).
2. **Ubicación:** `05 Diario/Bitácora Agentes/YYYY-MM.md` (archivo del mes vigente).
3. **Formato obligatorio:**
   ```markdown
   ## YYYY-MM-DD — <Persona / Agente>

   - **Qué se hizo:** Resumen conciso de los cambios.
   - **Archivos creados/modificados:** Lista de rutas principales.
   - **Qué debe saber el próximo agente:** Contexto clave, pendientes o advertencias.
   ```
4. **Append al final:** Escribí siempre al final del archivo para preservar el orden cronológico.
5. **No congelar pendientes:** El siguiente paso debe orientar al próximo agente sin predecir estados rígidos.
