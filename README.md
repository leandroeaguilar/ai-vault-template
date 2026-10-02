# AI Vault Template

[![versión](https://img.shields.io/badge/versión-v0.7.0-blue)](CHANGELOG.md)
[![licencia](https://img.shields.io/badge/código-MIT-green)](LICENSE)
[![contenido](https://img.shields.io/badge/contenido-CC%20BY--NC--SA%204.0-lightgrey)](LICENSE-CONTENT)

Un sistema operativo agéntico para tus notas en Markdown —un *vault* de Obsidian— con las guardas
deterministas ya puestas, estándar multi-agente universal y observabilidad visual offline:

- **ningún secreto entra al historial**: se bloquea el commit, y también el PR;
- **ningún comando peligroso se ejecuta**: se inspecciona antes, no después;
- **lo que escribiste vos no lo reescribe un agente**: se marca y se verifica en cada commit;
- **las tareas y recibos no pisan tu trabajo**: tablero Headless Kanban con validación humana;
- **observabilidad visual offline sin tokens**: mapa interactivo en HTML generado en local;
- **estándar universal agnóstico**: skills compatibles con Claude Code, Codex, Antigravity y OpenCode;
- **las mejoras del template te llegan** sin pisar una línea de tu contenido (`update.sh`).

Todo eso corre con `bash`, `python3` y `git`. Claude Code agrega comodidades de sesión, pero **no hace
falta**: las guardas que importan viven en los hooks de git y en CI, donde no hay harness que valga.

**Qué no es:** no es una app cerrada ni un plugin de Obsidian, es un repositorio de git con hooks ·
no es un framework pesado, no envuelve ningún modelo ni ninguna API de pago · no opina sobre cómo
tomás notas: impone un contrato de *metadatos*, seguridad y flujos.

📄 El porqué de cada decisión está en **[DECISIONES.md](DECISIONES.md)**.
🔧 Rutas en duro, supuestos y whitelists, en **[REFERENCIA.md](REFERENCIA.md)**.

---

## 1. Qué obtenés

```text
tu-vault/
├── 00 Sistema/           el contrato: SOPs, plantillas, flujos.yml, centinelas
├── 01 Index/             navegación: visión, objetivos, mapa personal
├── 02 MOCs/              mapas temáticos (Map of Content)
├── 03 Proyectos/         iniciativas + Kanban/ (Pendientes, En_Progreso, Hecho)
├── 04 Knowledge/         conocimiento reutilizable
├── 05 Diario/            diario operativo + bitácora de agentes
├── 06 Raw/               fuentes originales sin procesar
├── 99 Archivo/           terminado o retirado
│
├── .agents/              estándar universal: 5 skills agnósticas (AGENTS.md)
├── .claude/              22 hooks, scripts deterministas y settings.json
├── .githooks/            pre-commit, pre-push (gates locales)
├── .github/workflows/    los mismos gates, del lado del servidor
├── baseline-seguridad/   kit portable: llevás solo la seguridad a otro repo
│
├── AGENTS.md             la ley común que lee cualquier agente antes de escribir
├── Dashboard.md          panel de bienvenida y navegación central en Obsidian
├── Mapa de mis agentes   observabilidad visual interactiva (HTML offline, 0 tokens)
├── vault.conf            gobernanza: personal o equipo
└── install.sh · update.sh · personalize.sh
```

Las ocho carpetas numeradas forman un pipeline de procesamiento, no un archivador estático:
`06 Raw` → `04 Knowledge` → `02 MOCs` → `01 Index`, de crudo a navegable ([el porqué](<00 Sistema/Cómo funciona este vault.md>)).
Lo que **no** viene es el método personal —cómo estudiar o qué metas ponerte—: entra lo que ejecuta,
y lo que especifica lo que ejecuta.

---

## 2. Requisitos

| Qué | ¿Obligatorio? | Si falta |
|---|---|---|
| `bash` | sí (en Windows: Git Bash) | nada corre |
| `git` ≥ 2.9 | sí | los hooks no se activan (`core.hooksPath` existe desde 2.9) |
| `python3` | en la práctica sí | los hooks que lo usan **dejan de bloquear**, en vez de romper la sesión |
| `gh` (GitHub CLI) | no | el aviso de PRs sale en silencio y nadie se entera |
| Obsidian | no | podés usar cualquier editor de Markdown; con Obsidian ganás navegación gráfica y [Dashboard.md](Dashboard.md) |
| Cualquier Agente (Codex, Antigravity, OpenCode...) | no | leen `AGENTS.md` y ejecutan `.agents/skills/` directamente |
| Claude Code | no | los hooks de evento de `.claude/` quedan inertes; **el gate de git, CI y las skills universales siguen en pie** |

Esa última fila es la decisión de diseño más importante del repositorio: la gobernanza no depende de
una suscripción ni de una herramienta privada ([DECISIONES.md §1](DECISIONES.md)).

---

## 3. Instalación

Dos comandos. `install.sh` es **reanudable**: si falta tu identidad, te deja el archivo listo y
para; lo completás, lo volvés a correr y termina.

```bash
# 1. Forkeá en GitHub, después:
git clone https://github.com/<vos>/<tu-vault>.git
cd <tu-vault>

# 2. Instalar
./install.sh          # cablea hooks, engancha upstream, prepara owner.env y para
#    → completá owner.env (OWNER, OWNER_EMAIL, OWNER_GITHUB)
./install.sh          # retoma: resuelve los placeholders y termina
```

**Forkeá, no clones y ya.** Si `origin` apunta al template, `install.sh` no personaliza nada y te
dice cómo arreglarlo. El motivo: `pre-push` bloquea todo push a un remoto de la familia
`ai-vault-template` / `sistema-maestro-*` cuando el clon ya tiene identidad, porque publicaría tu
nombre y tu correo en el repositorio del template.

```bash
git remote set-url origin https://github.com/<vos>/<tu-vault>.git
./install.sh
```

**Qué hizo el instalador.** Es idempotente: correrlo de nuevo no rompe nada.

| Paso | Qué hace | Por qué |
|---|---|---|
| Hooks | `git config core.hooksPath .githooks` | `.git/hooks/` no se versiona: un hook que vive ahí no le llega a nadie más |
| Windows | `core.longpaths true` | sin esto, un checkout con nombres largos falla |
| Estado | crea `.vault-meta/` | marcas de sesión, locks y kill-switches; gitignorado |
| Upstream | `git remote add upstream <url>` | el canal de actualizaciones, que `update.sh` exige |
| Identidad | crea `owner.env` y corre `personalize.sh` | catorce `.md` se publican con el placeholder de owner literal |

Al abrir el vault en Obsidian, encontrarás **[Dashboard.md](Dashboard.md)** en la raíz como panel
de bienvenida y navegación central.

---

## 4. Probalo en dos minutos

Los cinco comandos que demuestran que las guardas, el tablero y la observabilidad están encendidos:

```bash
# 1. La guarda de secretos bloquea de verdad
printf 'AWS_SECRET_ACCESS_KEY=%s%s\n' AKIA 0000000000000000 > fuga.txt
git add -f fuga.txt && git commit -m prueba     # → debe FALLAR
git reset && rm fuga.txt

# 2. El guard de comandos bloquea ANTES de ejecutar
echo '{"tool_name":"Bash","tool_input":{"command":"cat .env"}}' \
  | python3 .claude/hooks/security-guard.py ; echo "exit=$?"

# 3. El auditor de seguridad completo
bash .claude/hooks/security-audit.sh

# 4. Creá una tarjeta en el tablero Headless Kanban
python .claude/scripts/crear-tarea.py --titulo "Auditar enlaces rotos" --agent mantenedor --skill check-links

# 5. Generá el mapa visual de tus agentes (0 tokens, abre en tu navegador)
python .claude/scripts/mapa-agentes.py
```

---

## 5. Tablero Headless Kanban y Patrón de Recibos

El **Tablero Headless Kanban** (`03 Proyectos/Kanban/`) es el mecanismo de desacoplamiento entre vos
y los agentes autónomos.

En lugar de mantener un chat de 20.000 tokens esperando a que un agente termine, cualquier actor
deposita una tarjeta markdown en `Pendientes/`.

### El Principio: Los agentes proponen, los humanos deciden

Un agente autónomo **nunca debe sobreescribir ni publicar directamente notas permanentes**. En su
lugar, aplica el **Patrón de Recibos (Human-in-the-Loop)**:

1. **El agente trabaja:** Genera el borrador en su ruta correspondiente.
2. **Emite un recibo:** Crea una tarjeta con `--recibo` en `03 Proyectos/Kanban/Pendientes/` con el
   enlace al diff o borrador.
3. **Validación humana:** Revisás el entregable cuando tengas tiempo, aprobás el cambio y movés la
   tarjeta a `Hecho/`.

```bash
# Crear un recibo de validación humana
python .claude/scripts/crear-tarea.py --titulo "Revisar borrador propuesto" --agent general --recibo
```

---

## 6. Observabilidad Visual (`Mapa de mis agentes`)

Tener agentes y skills no sirve de nada si no sabes qué tenés instalado ni qué corre en segundo
plano.

El script `.claude/scripts/mapa-agentes.py` hace análisis estático determinista del repositorio y
genera **`Mapa de mis agentes.html`**:

- **Cero Tokens / 100% Offline:** No consume APIs de pago ni envía un solo byte fuera de tu máquina.
- **Grafo interactivo:** Visualiza quién llama a quién, qué skills existen en `.agents/skills/`,
  qué comandos tenés disponibles y qué flujos están declarados en `00 Sistema/flujos.yml`.
- **Cola Kanban en vivo:** Muestra en qué estado están tus tareas pendientes.
- **Uso:** Hacé doble clic sobre `Mapa de mis agentes.html` para abrirlo en cualquier navegador.

---

## 7. Qué corre y cuándo

**Harness:** `CC` = solo dentro de Claude Code. `todos` = cualquier agente (Codex, Antigravity,
Claude Code, OpenCode) y humanos.

| Pieza | Se dispara con | Harness | Kill-switch (`.vault-meta/…`) |
|---|---|---|---|
| `session-context.sh` | inicio de sesión | CC | `session-context.disabled` |
| `check-routines.sh` | inicio de sesión | CC | `routines-monitor.disabled` |
| `update-notice.sh` | inicio de sesión | CC | `update-notice.disabled` |
| `pr-notice.sh` | inicio de sesión | CC | `pr-notice.disabled` |
| `pre-compact.sh` | antes de compactar contexto | CC | `precompact.disabled` |
| `sentinels-guard.sh` + `.py` | antes de `Write`/`Edit` | CC | `sentinels.disabled` |
| `security-guard.sh` + `.py` | antes de `Bash`/`Read` | CC | `security-guard.disabled` |
| `auto-commit.sh` | después de `Write`/`Edit` | CC | `autocommit.disabled` |
| `agent-diary` (`.agents/skills/`) | cierre de sesión | todos | `diary.disabled` |
| `check-diary-size.sh` | lo llama `agent-diary` | CC | `diary-cap.disabled` |
| `check-links` (`.agents/skills/`) | bajo demanda / mantenimiento | todos | — |
| `verifier` (`.agents/skills/`) | antes de `git commit` (self-review) | todos | — |
| `security-audit` (`.agents/skills/`) | bajo demanda / auditoría | todos | — |
| `crear-tarea` (`.agents/scripts/`) | creación de tareas y recibos | todos | — |
| gate de rama | `git commit` | todos | `branch-gate.disabled` |
| `secret-scan.sh` | `git commit` + CI | todos | `secret-scan.disabled` |
| `sentinels-verify.py` | `git commit` + CI | todos | `sentinels.disabled` |
| `generate-index.py` | `git commit` | todos | `index-gen.disabled` |
| `verify-commit.sh` | `git commit` + CI | todos | `verifier.disabled` |
| `.githooks/pre-push` | `git push` | todos | `prepush.disabled` |
| `verify.yml` · `aviso-de-pr.yml` | Pull Request | todos | desactivar el workflow |

---

## 8. Configuración

| Archivo | Qué es | ¿Se versiona? |
|---|---|---|
| `owner.env` | Identidad: `OWNER`, `OWNER_EMAIL`, `OWNER_GITHUB` | **no** (gitignoreado) |
| `vault.conf` | Gobernanza: `VAULT_MODE`, `MAIN_BRANCH`, `TEAM_MEMBERS` | **sí** |
| `.vault-meta/*.disabled` | Kill-switches, uno por guarda | no |

**Si lo van a usar varias personas**, editá `vault.conf` y commiteálo:

```ini
VAULT_MODE=equipo        # personal (default) | equipo
MAIN_BRANCH=main
TEAM_MEMBERS="Ana,Beto"
```

⚠️ Con `VAULT_MODE=equipo`, **todo commit sobre `main` queda bloqueado**. La salida es
`git switch -c <prefijo>/<tema>`, o `--no-verify` para una excepción puntual.

---

## 9. Actualizarse

```bash
./update.sh --check      # ¿hay versión nueva? No toca nada
./update.sh --dry-run    # qué archivos cambiarían
./update.sh              # interactivo: lista y pide confirmación
```

El updater copia por whitelist en tres clases:

| Clase | Qué es | Qué hace el update |
|---|---|---|
| `infrastructure` | Hooks, skills `.agents/**`, scripts, workflows, `00 Sistema/`, `baseline-seguridad/`, docs | se sobrescribe siempre |
| `scaffold` | `owner.env`, `vault.conf`, `FIRST_RUN.md`, `Dashboard.md`, stubs de `01 Index/`, Kanban | se instala una vez y **nunca** se pisa |
| contenido | todo lo demás (tus notas, proyectos, diario, MOCs) | no se toca jamás |

---

## 10. Adaptarlo a tu repo

**(a) Querés un vault entero.** Seguí la sección 3. Es el camino recomendado.

**(b) Querés solo la seguridad, en un repo de código.** Usá
[`baseline-seguridad/`](<baseline-seguridad/README.md>): siete archivos copiables y autocontenidos
con las capas 1 a 3 para tu proyecto.

**(c) Querés los hooks sobre tu propia estructura.** Se puede; las rutas en duro están documentadas
en [REFERENCIA.md](REFERENCIA.md).

---

## 11. Límites y licencia

Doble licencia, **por ruta**:

| Rutas | Licencia |
|---|---|
| `.agents/**`, `.claude/**`, `.githooks/**`, `.github/**`, `baseline-seguridad/**`, `*.sh`, `*.py`, `*.yml`, `Mapa de mis agentes.html`, `vault-manifest.json`, `vault.conf`, `owner.env.example`, `VERSION`, `.gitignore`, `.gitattributes` | [MIT](LICENSE) |
| Los `.md` **fuera** de esas rutas: `00 Sistema/**`, `05 Diario/**`, `AGENTS.md`, `README.md`, `DECISIONES.md`, `REFERENCIA.md`, `CHANGELOG.md`, y la arquitectura de carpetas | [CC BY-NC-SA 4.0](LICENSE-CONTENT) |

Historial de versiones en [CHANGELOG.md](CHANGELOG.md).

---

## Glosario

| Término | Qué significa acá |
|---|---|
| **vault** | La carpeta de notas en Markdown, con su estructura y su contrato. No es una base de datos ni una app |
| **harness** | La herramienta desde la que corre el agente (Claude Code, Codex, Antigravity, OpenCode). Un control que solo vive en un harness protege solo mientras uses ese harness |
| **centinela** | Marca `<!-- @user -->` / `<!-- @generated -->` que declara qué bloque de un documento es tuyo y cuál puede regenerar el sistema |
| **gate** · **guarda** | Chequeo determinista que puede **bloquear** una acción (un commit, un push, un comando) si viola una política de seguridad |
| **Headless Kanban** | Tablero asíncrono de tarjetas Markdown en `03 Proyectos/Kanban/` para delegar tareas a agentes sin mantener sesiones de chat abiertas |
| **recibo** | Tarjeta de tarea emitida por un agente tras generar un borrador para que el humano apruebe antes de tocar el documento final |
| **Mapa de agentes** | Interfaz HTML interactiva offline generada con 0 tokens de LLM que refleja el grafo de dependencias y estado de tus agentes |
| **fail-open** | Si a la guarda le falta una dependencia, deja pasar en vez de romper la sesión de trabajo |
| **warn-only** | El chequeo avisa pero no bloquea (modo por defecto del verifier) |
| **infrastructure** · **scaffold** | Las dos clases de la whitelist del updater: lo primero se sobrescribe con updates, lo segundo se instala una vez y nunca se pisa |
| **upstream** | El remote de git que apunta al template original para recibir mejoras |

© 2026 Leandro Esteban Aguilar Montilla.
