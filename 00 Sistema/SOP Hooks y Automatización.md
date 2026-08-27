---
type: How-to
title: "SOP Hooks y Automatización"
tags: [sop, hooks, automatizacion, multiagente, git]
estado: 🟢 Activo
prioridad: 🔥 Alta
responsable: "{{OWNER}}"
id: "SOP-HOOKS-001"
generated:
  by: human:{{OWNER}}
  at: 2026-07-02T00:00:00Z
fecha_creacion: 2026-07-01
resource:
---

# SOP Hooks y Automatización

## 1. Objetivo

Estandarizar cómo se **crean, prueban, documentan y desactivan** los *hooks* de automatización del vault: código determinista que el harness ejecuta en eventos del ciclo de sesión, para que las convenciones del sistema (registrar bitácora, validar frontmatter, commitear) dejen de depender de que el agente "se acuerde".

> **Principio rector:** *el código posee el entorno; el agente posee el contenido.* Lo repetitivo y verificable lo hace un hook; el criterio lo pone el agente. (Patrón adoptado de `obsidian-mind`.)

---

## 2. Qué es un hook acá (y qué NO es)

| | |
|---|---|
| **SÍ es** | Un hook del **harness Claude Code** (evento del ciclo: `Stop`, `PostToolUse`, `SessionStart`…), configurado en `.claude/settings.json`. |
| **NO es** | Un git hook clásico de `.git/hooks/` (`pre-commit`, etc.). Aunque las **buenas prácticas de documentación son las mismas** (ver §8). |

Eventos más útiles para el vault: `SessionStart` (cargar contexto), `PostToolUse` con matcher `Write|Edit` (validar/commitear tras escribir), `Stop` (wrap-up / bitácora), `PreCompact` (respaldar contexto).

---

## 3. Dónde vive cada cosa

| Capa | Ubicación | Qué es |
|---|---|---|
| **Ejecutable** | `.claude/hooks/*.sh` | Los scripts (shell puro). `.claude/hooks/README.md` los lista. |
| **Wiring** | `.claude/settings.json` (`hooks`) | Conecta evento → script. Cross-CLI: `.codex/hooks.json` puede apuntar a los mismos scripts. |
| **Estado runtime** | `.vault-meta/` (gitignored) | Marcas de sesión, locks y **kill-switches** locales. No es contenido del vault. |
| **How-to** | este SOP | Cómo trabajar con hooks. |
| **Reference** | [README del repositorio](<../README.md>) | Qué hace cada hook/lock. |
| **Concepto** | Hooks y ciclo de vida del agente | Por qué existen (nota de estudio). |

> Es el mismo patrón de capas que Skills y Prompts: **ejecutable** en `.claude/`, **documentación** en el vault (`00 Sistema` + `04 Knowledge/Automatización`).

### 3.1 Alcance: proyecto vs global (¡importante!)

Dónde vive el `settings.json` decide **en qué carpetas** se disparan los hooks:

| Ubicación del `settings.json` | Alcance | Cuándo usarla |
|---|---|---|
| `<vault>/.claude/settings.json` (**proyecto**) | Solo cuando Claude Code corre **dentro de este vault** | **Nuestro caso.** Los hooks de este vault están acá → no aparecen en otras carpetas. |
| `~/.claude/settings.json` (**global**) | **Toda** carpeta donde arranques Claude Code | Solo si querés que el hook aplique a varios proyectos. Entonces el script debe ser "a-prueba-de-no-vault" (salir limpio si no encuentra el vault). |

> **Regla:** un hook específico de un sistema va en el `settings.json` **de ese proyecto**, nunca en el global. Poner un hook de vault en el global lo dispararía en cada sesión de Claude Code (aunque no tenga que ver con el vault). Por eso `session-context.sh` y compañía viven en el settings del proyecto: quedan **aislados** a este vault. (Contraste: `claude-obsidian` instala en global y por eso diseñó sus hooks para salir sin error en sesiones no-vault.)

---

## 4. Requisitos (Windows)

- **Git Bash** disponible (los scripts son bash). En `settings.json` se fuerza `"shell": "bash"` — sin esto, Windows usaría PowerShell.
- **Sin `node` ni `jq`** (no están): parsear stdin con `sed`, no con `jq`.
- **`python` SÍ está** (3.12+): usar solo cuando el parseo con `sed` no alcanza — p.ej. JSON multilínea con escapes (`sentinels-guard`). Los hooks que lo usen deben hacer **fail-open** si falta python.
- **`flock` NO existe** en Git Bash → no usarlo (afecta al lock, ver §7).

---

## 5. Cómo crear un hook (paso a paso)

1. **Escribir el script** en `.claude/hooks/<nombre>.sh`. Reglas:
   - Cabecera con propósito y diseño (comentarios: buena práctica no negociable).
   - Leer el JSON de stdin (`INPUT="$(cat)"`); extraer campos con `sed` (no hay `jq`).
   - Usar `${CLAUDE_PROJECT_DIR:-$PWD}` como raíz.
   - **Kill-switch:** salir temprano si existe `.vault-meta/<nombre>.disabled`.
   - Fallar en silencio hacia afuera (`|| true`, `exit 0`) salvo que se quiera bloquear.
2. **Pipe-test** (obligatorio — un hook que falla en silencio es peor que ninguno). Sintetizar el payload y probar:
   ```bash
   echo '{"tool_input":{"file_path":"04 Knowledge/Temas/_x.md"}}' | bash .claude/hooks/<nombre>.sh
   ```
   Verificar exit code **y** efecto real. Recién cuando funciona, envolver con `|| true`.
3. **Wire** en `.claude/settings.json` (fusionar, no reemplazar):
   ```json
   { "hooks": { "PostToolUse": [ { "matcher": "Write|Edit",
     "hooks": [ { "type": "command", "shell": "bash",
       "command": "bash \"${CLAUDE_PROJECT_DIR:-.}/.claude/hooks/<nombre>.sh\"", "timeout": 30 } ] } ] } }
   ```
4. **Validar JSON:** `python -c "import json;json.load(open('.claude/settings.json',encoding='utf-8'))"`.
5. **Activar:** abrir `/hooks` en Claude Code o reiniciar (el watcher no siempre recarga en caliente).
6. **Documentar:** documentar el hook donde vivan las fichas de herramientas (acá, el [README](<../README.md>)).

---

## 6. Bloquear en `Stop` (el patrón del Agent Diary)

Para que el modelo **continúe** y complete una tarea antes de terminar, el hook `Stop` emite:
```json
{"decision":"block","reason":"<qué debe hacer el agente>"}
```
Para no entrar en loop, **guard `stop_hook_active`**: si el JSON de stdin lo trae en `true`, salir `0` (permitir terminar). Ver `agent-diary.sh` como ejemplo.

---

## 7. Locks advisory (multi-writer)

Cuando dos agentes escriben en paralelo el **mismo** archivo, worktrees no alcanzan (pueden estar en la misma rama). Un **lock advisory** por-archivo lo resuelve a nivel harness.

- **Implementado:** `.claude/hooks/wiki-lock.sh` (adaptado de `claude-obsidian`). ✅
- **Port sin `flock`:** el original usa `flock` para un meta-lock que serializa el robo de locks vencidos; en Git Bash `flock` **no existe**. Se eliminó porque es innecesario para un lock por-archivo:
  - **Posesión** = `mkdir` del directorio-lock (atómico en cualquier FS, incluido NTFS): solo un proceso puede crearlo.
  - **Robo de lock vencido** = `mv` (rename) atómico: de N procesos que intentan robar el mismo lock vencido, solo UNO logra el rename (los demás reciben ENOENT y reintentan el `mkdir`). Evita el bug de "ambos `rm -rf` → doble dueño" sin meta-lock.
- **Propiedad = identidad de agente** (no pid): `release` y la re-entrancia se validan por nombre de agente, porque cada `acquire`/`release` corre en un proceso distinto. Reacquirir refresca el timestamp (una operación larga no se vence).
- **Uso (herramienta CLI, no se cablea a eventos):** el agente la invoca **alrededor** de una edición riesgosa en zona compartida:
  ```bash
  L=.claude/hooks/wiki-lock.sh; F="04 Knowledge/Temas/Nota.md"
  bash $L acquire "$F" claude || exit 1   # 0 = tomado, 1 = ocupado
  # ...editar $F...
  bash $L release "$F" claude
  ```
  Otros comandos: `peek <archivo>` (ver dueño/edad), `owner <archivo>` (imprime el dueño si el lock está vigente — salida machine-friendly), `list` (inventario de todos los locks), `clear-stale` (limpiar vencidos). TTL por defecto 120s (`WIKI_LOCK_TTL`), reintentos `WIKI_LOCK_RETRIES`, espera `WIKI_LOCK_SLEEP`, identidad `WIKI_LOCK_AGENT`.
- **Auto-commit consciente de locks:** el hook `auto-commit.sh` consulta `wiki-lock owner` antes de commitear: si otro agente tiene el archivo bloqueado, no lo commitea (trabajo en curso ajeno). Para que el auto-commit reconozca tus propios locks como propios, exportá `WIKI_LOCK_AGENT` con la misma identidad que usás al `acquire`.
- No se cablea en `settings.json`: un lock debe envolver **toda** la edición (acquire antes, release después), no dispararse por-evento. Los locks viven en `.vault-meta/locks/` (gitignored).
- 🔴 **Alcance: una máquina.** Como `.vault-meta/` está gitignoreado, un lock **no viaja al remoto y las demás personas no lo ven**. Es lo correcto —un lock es estado efímero, no historial: versionarlo dejaría locks huérfanos en el árbol de todos— pero hay que decir el límite en voz alta: `wiki-lock.sh` resuelve **agente ↔ agente en un mismo clon**, y **no protege nada entre personas**. En vault compartido el sustituto es la regla del **escritor único sobre los hotspots**, que es convención hablada y no tiene herramienta.
- Ver detalle en el [README](<../README.md>), sección *Git*.

---

## 8. Convenciones y bypass (buenas prácticas)

- **Comentar los scripts** (propósito + diseño en la cabecera).
- **Mensajes de error claros** para que un fallo sea diagnosticable.
- **Kill-switch por hook** en `.vault-meta/<nombre>.disabled` (local, gitignored). Documentar *cuándo* es aceptable desactivar:
  - `autocommit.disabled` → **sesiones interactivas curadas** (para no ensuciar el historial con commits `chore(agent):`). Reactivar para corridas autónomas.
  - `diary.disabled` → normalmente **siempre ON**; desactivar solo en pruebas.
- **Identidad de commit** en hooks que commitean: `git -c user.name=… user.email=…@agent.local` (no contamina la config del repo).
- Cambios a hooks: proponer, revisar y recién integrar (como cualquier código del sistema).

---

## 9. Troubleshooting

| Síntoma | Causa | Solución |
|---|---|---|
| El hook no dispara | El watcher no recargó `.claude/settings.json` | Abrir `/hooks` o reiniciar Claude Code |
| Error de shell en Windows | Corrió en PowerShell, no bash | Asegurar `"shell": "bash"` en el hook |
| `jq: command not found` | jq no está | Parsear con `sed`, no `jq` |
| `busy: <archivo>` al acquirir | Otro agente tiene el lock vigente | Reintentar, o `peek` para ver dueño/edad; si quedó colgado, `clear-stale` |
| Lock colgado tras crash del agente | El proceso murió sin `release` | Se roba solo al vencer el TTL (120s); o forzar con `clear-stale` |
| Auto-commit barrió cambios de más | Se usó `git add -A` | Commitear **solo** el archivo tocado (pathspec) |
| Loop de `Stop` | Falta guard | Chequear `stop_hook_active` y salir 0 |

---

## 10. Referencias

- [README del repositorio](<../README.md>) — qué hace cada hook y por qué
- Prior art: `obsidian-mind` (hooks TS), `claude-obsidian` (hooks shell + `wiki-lock.sh`)
- Buenas prácticas git hooks — https://git-scm.com/book/en/v2/Customizing-Git-Git-Hooks

## Cómo leer este SOP
Si vas a **crear** un hook, seguí §5 (+ §6 si bloquea). Si vas a **entender** qué hay, andá al [README](<../README.md>). Si algo falla, §9.
