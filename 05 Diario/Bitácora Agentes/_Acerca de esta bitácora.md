---
type: Reference
title: "Bitácora de Agentes"
aliases:
  - Bitácora de Agentes
tags: [multiagente, bitacora, agentes]
estado: 🟢 Activo
prioridad: ⏳ Media
responsable: "{{OWNER}}"
id: "REF-BITACORA-AGENTES-001"
generated:
  by: human:{{OWNER}}
  at: 2026-07-02T00:00:00Z
fecha_creacion: 2026-07-01
resource:
---

# Bitácora de Agentes

Registro de **handoff entre agentes** (Claude Code, Codex, Antigravity, Hermes…). Cada agente, al cerrar una sesión donde tocó el vault, deja una entrada. Así cualquier agente que entre después arranca con contexto y no se repite trabajo.

Es la **capa de estado** de la interoperabilidad entre agentes: el patrón *Agent Diary*, implementado por `.claude/hooks/agent-diary.sh`.

## Cómo se completa (automático)

No hay que acordarse: el **hook `Stop`** (`.claude/hooks/agent-diary.sh`) detecta si hubo trabajo sobre el vault y le recuerda al agente registrar la entrada antes de terminar.

## Formato de cada entrada

Un archivo por mes: `YYYY-MM.md`. Dentro, una entrada por sesión significativa:

```markdown
## YYYY-MM-DD — <agente, ej. Claude Code>
- Qué se avanzó/creó/editó:
- Qué quedó bloqueado:
- Qué se decidió o cambió:
- Qué debe saber el próximo agente:
```

## Dos reglas de orden (no negociables)

El hook `SessionStart` (`.claude/hooks/session-context.sh`) inyecta al arrancar la **última entrada del archivo** asumiendo que la última físicamente es la más reciente. Para que esa suposición nunca se rompa:

1. **Append al final, siempre.** Cada entrada nueva va **al final del archivo** — la más reciente queda abajo. Nunca insertar arriba ni entre medio. (En jul-2026 se mezclaron append y prepend; el hook terminó inyectando una entrada vieja cuyo "siguiente = Gap B" ya estaba hecho → confusión. Ver esa corrección en `2026-07.md`.)

2. **El "siguiente paso" apunta al Roadmap, no lo congela.** En *"Qué debe saber el próximo agente"*, para el siguiente paso remitir al roadmap del vault (fuente viva). No escribir *"siguiente = X"* como hecho fijo: esa predicción se pudre cuando X se completa después y el hook la reinyecta como si fuera actual.

> **Señal de frescura (red de seguridad):** aunque el orden se respete, el hook avisa `⚠ Hubo N commit(s) DESPUÉS de este handoff` cuando hubo trabajo commiteado posterior al último toque de la bitácora — indica que el handoff mostrado puede estar desfasado y hay que confirmar contra el Roadmap y el `git log`.

## Tope de consolidación

Esta bitácora está acotada **al leer** (el hook inyecta solo la última entrada) pero sería infinita **al escribir**: sin un techo, nadie la sintetiza nunca y termina siendo un archivo histórico disfrazado de handoff.

`check-diary-size.sh` le pone techo al mes vigente y el hook `Stop` lo consulta: pasado el umbral, el aviso de bitácora suma la instrucción de **proponer una consolidación**. Lo valioso no es el número — es *el mecanismo que obliga a sintetizar*. A un agente al que solo se le pide "resumí bien" no lo hace; a uno que choca contra un tope, sí.

**Qué significa consolidar acá — y qué no:**

- **NO es borrar.** La bitácora sirve al handoff, no al archivo histórico, y la historia completa ya vive en git (`git log -p`).
- **SÍ es:** sintetizar las entradas viejas del mes en un bloque de aprendizajes duraderos, dejar **verbatim las últimas** (que son el handoff vivo), y mover a su nota lo que resultó ser **conocimiento reutilizable** en vez de diario.
- **La propone un agente; la tijera final la decide el dueño del vault.** El tope no borra ni bloquea: solo obliga a poner el tema sobre la mesa.

Ver el estado con `bash .claude/hooks/check-diary-size.sh`. Los umbrales se ajustan por variable de entorno (`DIARY_SOFT_CHARS`, `DIARY_HARD_CHARS`, `DIARY_SOFT_ENTRIES`, `DIARY_HARD_ENTRIES`).

## Controles

- **Desactivar la bitácora:** crear el archivo `.vault-meta/diary.disabled`.
- **Desactivar el auto-commit de agentes:** crear `.vault-meta/autocommit.disabled`.
- **Desactivar solo el tope de consolidación** (la bitácora sigue andando): crear `.vault-meta/diary-cap.disabled`.

> *Sesión significativa* = se crearon/editaron archivos del vault, se tocaron sistemas externos, o se crearon/mejoraron SOPs.
