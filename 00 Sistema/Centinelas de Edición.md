---
type: How-to
title: "Centinelas de Edición (@user / @generated)"
tags: [multiagente, centinelas, edicion, proteccion, hooks]
estado: 🟢 Activo
prioridad: 🔥 Alta
responsable: "{{OWNER}}"
id: "HOW-002"
generated:
  by: human:{{OWNER}}
  at: 2026-07-01T00:00:00Z
fecha_creacion: 2026-07-01
resource:
---

# Centinelas de Edición (@user / @generated)

## 1. Para qué sirven

Un centinela es un **marcador invisible** que declara *de quién es* un fragmento de una nota, para que un agente de IA sepa qué puede reescribir y qué no. Resuelve el problema de separar **contenido humano** (intocable) de **contenido generado** (regenerable) dentro de un mismo archivo.

| Centinela | Dueño | La IA puede… |
|---|---|---|
| `@user` | Humano ({{OWNER}}) | **NO** editar ni sobrescribir. Solo leer. |
| `@generated` | Agente | Regenerar libremente (es suyo). |

Se escriben como **comentarios HTML**, así que **no se ven** en el modo lectura de Obsidian y son Markdown puro y portable.

---

## 2. La sintaxis

```markdown
<!-- @user -->
Esta reflexión es mía. La IA no la toca.
Puede ocupar varias líneas.
<!-- /@user -->

<!-- @generated -->
Este resumen lo mantiene un agente; se puede regenerar.
<!-- /@generated -->
```

Reglas:
- Todo bloque abre con `<!-- @user -->` (o `@generated`) y cierra con `<!-- /@user -->` (o `/@generated`).
- Los espacios internos son flexibles (`<!--@user-->` también vale).
- Podés tener varios bloques por nota.
- Fuera de los bloques, el texto es "libre": la IA puede editarlo.

---

## 3. El guardián (enforcement automático)

La convención no depende de que el agente "se acuerde": la **obligan** dos hooks, en dos momentos distintos.

| Capa | Cuándo | A quién cubre |
|---|---|---|
| `sentinels-guard.sh` + `.py` | `PreToolUse`, antes del `Write`/`Edit` | **solo Claude Code** — los hooks de `settings.json` no corren en otros harness |
| `sentinels-verify.py` | `git commit` y PR (`verify.yml`) | **cualquier agente y cualquier humano** |

El reparto es deliberado: el guardián evita que el agente **escriba** dentro de tu bloque; el verificador evita que lo escrito **entre a la historia**. El segundo llega tarde, pero es el único que existe si trabajás con Codex o con cualquier otro agente. Ver `AGENTS.md` §Trabajo en paralelo con otros agentes.

### 3.1 El guardián (`PreToolUse`)

- **`.claude/hooks/sentinels-guard.sh`** (+ `sentinels-guard.py`) corre en `PreToolUse` (antes de cada `Write`/`Edit`).
- Lógica:
  - **Edit** cuyo `old_string` cae **dentro** de un bloque `@user` → **bloqueado** (exit 2). El motivo se le muestra al agente.
  - **Write** (sobrescritura total) que **perdería o alteraría** un bloque `@user` existente → **bloqueado**.
  - Archivo sin centinelas, o edición fuera del bloque → permitido.
- **FAIL-OPEN:** ante cualquier duda o error, **permite** (nunca frena trabajo legítimo por un bug). Los bloques `@generated` **no** se protegen (son del agente).
- **Kill-switch:** crear `.vault-meta/sentinels.disabled` desactiva el guard.

### 3.2 El verificador (`git commit` y PR)

- **`.claude/hooks/sentinels-verify.py`**, invocado por `.githooks/pre-commit` y por el workflow `verify.yml`.
- Lógica: toma los bloques `@user` de la versión **anterior** de cada `.md` que cambió y exige que su contenido siga textual en la versión nueva. Cubre también el caso de **borrar el archivo entero** con contenido protegido adentro.
- **Bloquea** (exit 1). Escapes: `SENTINELS_OK=1 git commit …` para un cambio deliberado tuyo, o el mismo kill-switch `.vault-meta/sentinels.disabled`.
- Compara **blob contra blob** (lo commiteado vs. lo staged), nunca contra el working tree: así el final de línea CRLF/LF no puede producir un falso positivo.

> **Los marcadores que son ejemplos no cuentan.** Ambos hooks ignoran los que viven dentro de código —bloques ``` y spans entre backticks—. Sin eso, un marcador de apertura suelto en un ejemplo (como el `<!--@user-->` de §2, que ilustra que los espacios son flexibles) empareja con el primer cierre real que aparezca más abajo y crea una **región fantasma** que "protege" media nota y bloquea ediciones legítimas. Pasaba de verdad en esta misma guía; corregido 2026-07-23.

> Como hoy ninguna nota tiene centinelas reales, ambas capas están activas pero **inertes**: recién actúan cuando empezás a marcar bloques `@user`.

---

## 4. Cómo usarlo (workflow)

1. **Protegé** lo que no querés que la IA toque: envolvelo en `<!-- @user --> … <!-- /@user -->`. Ej.: tus reflexiones en una nota que además tiene secciones que un agente mantiene.
2. **Marcá como regenerable** lo que un agente produce y vas a dejar que actualice: `<!-- @generated --> … <!-- /@generated -->`.
3. A partir de ahí, si un agente intenta editar dentro de tu bloque, el guardián lo frena y le explica por qué.
4. Si necesitás que la IA sí modifique algo protegido, o quitás la protección (sacás los marcadores) o desactivás el guard temporalmente con el kill-switch.

### Limitación conocida (v1)
Una edición que **cruza el borde** de un bloque (parte dentro, parte fuera) puede no detectarse en el guardián `PreToolUse` (fail-open). El caso común —editar de lleno dentro de un `@user`— sí se bloquea. **El verificador de commit no tiene esta limitación**: no mira la operación de edición sino el resultado, así que un bloque alterado por el borde igual se detecta al commitear. Es otra razón por la que las dos capas se complementan.

## 5. Referencias
- Prior art: `obsidian-second-brain` (edición con centinelas)
- El guardián que los aplica → `.claude/hooks/sentinels-guard.sh` y `sentinels-verify.py`
- Cómo se crean/prueban hooks → [SOP Hooks y Automatización](<SOP Hooks y Automatización.md>)

## Cómo leer este documento
Para proteger contenido, §2 (sintaxis) + §4 (workflow). Para entender qué bloquea y qué no, §3. El *porqué* está en §13.3 de la Orquestación.
