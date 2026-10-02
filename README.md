# AI Vault Template

[![versión](https://img.shields.io/badge/versión-v0.7.0-blue)](CHANGELOG.md)
[![licencia](https://img.shields.io/badge/código-MIT-green)](LICENSE)
[![contenido](https://img.shields.io/badge/contenido-CC%20BY--NC--SA%204.0-lightgrey)](LICENSE-CONTENT)

Una carpeta de notas en Markdown —un *vault*— con las guardas ya puestas para que la opere un
agente de IA sin que eso sea un riesgo:

- **ningún secreto entra al historial**: se bloquea el commit, y también el PR;
- **ningún comando peligroso se ejecuta**: se inspecciona antes, no después;
- **lo que escribiste vos no lo reescribe un agente**: se marca y se verifica en cada commit;
- **las tareas y recibos no pisan tu trabajo**: tablero Headless Kanban con validación humana;
- **las mejoras del template te llegan** sin pisar una línea de tu contenido.

Todo eso corre con `bash` y `git`. Claude Code agrega comodidades, pero **no hace falta**: las
guardas que importan viven en los hooks de git y en CI, donde no hay herramienta que valga.

**Qué no es:** no es una app ni un plugin de Obsidian, es un repositorio de git con hooks · no es
un framework de agentes, no envuelve ningún modelo ni ninguna API · no opina sobre cómo tomás
notas: impone un contrato de *metadatos*, no de método.

📄 El porqué de cada decisión está en **[DECISIONES.md](DECISIONES.md)**.
🔧 Rutas en duro, supuestos y whitelists, en **[REFERENCIA.md](REFERENCIA.md)**.

---

## 1. Qué obtenés

```
tu-vault/
├── 00 Sistema/           el contrato: SOPs, plantillas, flujos.yml, centinelas
├── 01 Index/             navegación: visión, objetivos, mapa personal
├── 02 MOCs/              mapas temáticos
├── 03 Proyectos/         iniciativas + Kanban/ (Pendientes, En_Progreso, Hecho)
├── 04 Knowledge/         conocimiento reutilizable
├── 05 Diario/            diario operativo + bitácora de agentes
├── 06 Raw/               fuentes sin procesar
├── 99 Archivo/           terminado o retirado
│
├── .agents/              estándar universal: 5 skills agnósticas (AGENTS.md)
├── .claude/              22 hooks, 3 commands, scripts deterministas
├── .githooks/            pre-commit, pre-push
├── .github/workflows/    los mismos gates, del lado del servidor
├── baseline-seguridad/   kit portable: llevás solo la seguridad a otro repo
│
├── AGENTS.md             la ley común que lee cualquier agente antes de escribir
├── Dashboard.md          panel de bienvenida y navegación en Obsidian
├── Mapa de mis agentes   observabilidad visual interactiva (HTML offline, 0 tokens)
├── vault.conf            gobernanza: personal o equipo
└── install.sh · update.sh · personalize.sh
```

Las ocho carpetas numeradas son un pipeline, no un archivador: `06 Raw` → `04 Knowledge` →
`02 MOCs` → `01 Index`, de crudo a navegable ([el porqué](<00 Sistema/Cómo funciona este vault.md>)).
Lo que **no** viene es el método —cómo estudiar, cómo decidir, cómo revisar—: entra lo que ejecuta,
y lo que especifica lo que ejecuta.

## 2. Requisitos

| Qué | ¿Obligatorio? | Si falta |
|---|---|---|
| `bash` | sí (en Windows: Git Bash) | nada corre |
| `git` ≥ 2.9 | sí | los hooks no se activan (`core.hooksPath` existe desde 2.9) |
| `python3` | en la práctica sí | los hooks que lo usan **dejan de bloquear**, en vez de romper la sesión |
| `gh` (GitHub CLI) | no | el aviso de PRs sale en silencio y nadie se entera |
| Obsidian + Templater | no | las 3 plantillas quedan con el tag de fecha literal |
| Claude Code | no | los 9 hooks de `.claude/` quedan inertes; **el gate de git y el de CI siguen en pie** |

Esa última fila es la decisión de diseño más importante del repositorio, y está argumentada en
[DECISIONES.md](DECISIONES.md).

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
| Identidad | crea `owner.env` y, en la segunda corrida, corre `personalize.sh` | catorce `.md` se publican con el placeholder de owner literal |

`owner.env` está **gitignoreado**: es identidad, y no viaja al clon de nadie. La gobernanza va en
`vault.conf`, que sí se versiona (sección 6).

**Lo que ningún script puede hacer por vos.** Al terminar quedan tres stubs en `01 Index/`
—`Vision`, `Objetivos`, `Mapa Personal`— en `estado: 🟡 Borrador`. Son la capa de orientación del
vault. Llenalos a mano, o pedile `/onboarding` a un agente en esta carpeta: la skill te entrevista
y los escribe con tus respuestas. Es **comodidad, no requisito**.

## 4. Probalo en dos minutos

Los tres comandos que demuestran que las guardas están encendidas. Corrélos ahora, no el día que
las necesites.

```bash
# 1. La guarda de secretos bloquea de verdad
printf 'AWS_SECRET_ACCESS_KEY=%s%s\n' AKIA 0000000000000000 > fuga.txt
git add -f fuga.txt && git commit -m prueba     # → debe FALLAR
git reset && rm fuga.txt

# 2. El guard de comandos bloquea ANTES de ejecutar
echo '{"tool_name":"Bash","tool_input":{"command":"cat .env"}}' \
  | python3 .claude/hooks/security-guard.py ; echo "exit=$?"

# 3. El auditor completo
bash .claude/hooks/security-audit.sh
```

La clave de prueba se arma en runtime (`%s%s`) en vez de ir literal: si fuera literal, el propio
`secret-scan` bloquearía el commit de este repositorio.

## 5. Qué corre y cuándo

**Harness:** `CC` = solo dentro de Claude Code. `todos` = cualquier agente, de cualquier harness, y
los humanos también.

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
| `agent-diary.sh` | cierre de sesión | CC | `diary.disabled` |
| `check-diary-size.sh` | lo llama `agent-diary.sh` | CC | `diary-cap.disabled` |
| gate de rama | `git commit` | todos | `branch-gate.disabled` |
| `secret-scan.sh` | `git commit` + CI | todos | `secret-scan.disabled` |
| `sentinels-verify.py` | `git commit` + CI | todos | `sentinels.disabled` |
| `generate-index.py` | `git commit` | todos | `index-gen.disabled` |
| `verify-commit.sh` | `git commit` + CI | todos | `verifier.disabled` |
| `.githooks/pre-push` | `git push` | todos | `prepush.disabled` |
| `verify.yml` · `aviso-de-pr.yml` | Pull Request | todos | desactivar el workflow |

> **Los kill-switches no siguen el nombre del archivo.** `agent-diary.sh` se apaga con
> `diary.disabled`; los tres centinelas comparten `sentinels.disabled`. Usá la columna de esta
> tabla: está verificada contra el código, no deducida del nombre.

Al abrir una sesión con Claude Code vas a ver cuatro avisos seguidos: son esos cuatro primeros
hooks. Y al cerrarla, si tocaste algo, el cierre **queda bloqueado** hasta que el agente deje su
entrada de handoff en `05 Diario/Bitácora Agentes/`. Ninguna de las dos cosas es un cuelgue.

**Lo que se invoca desde el agente** (solo Claude Code): `/onboarding` para inicializar el vault,
`/revisar-seguridad` para auditar algo antes de instalarlo o abrirlo, `/revisar-pr` para traducir
un PR a lenguaje de vault, y el subagente `verifier` como segunda opinión sobre el diff staged.
Los cuatro proponen: ninguno aprueba, mergea ni ejecuta lo que está auditando.

Los comandos que se corren a mano están en [REFERENCIA.md](REFERENCIA.md).

## 6. Configuración

| Archivo | Qué es | ¿Se versiona? |
|---|---|---|
| `owner.env` | Identidad: `OWNER`, `OWNER_EMAIL`, `OWNER_GITHUB` | **no** (gitignoreado) |
| `vault.conf` | Gobernanza: `VAULT_MODE`, `MAIN_BRANCH`, `TEAM_MEMBERS`, `ROUTINES_EXPECTED` | **sí** |
| `.vault-meta/*.disabled` | Kill-switches, uno por guarda | no |

**Si lo van a usar varias personas**, editá `vault.conf` y commiteálo:

```ini
VAULT_MODE=equipo        # personal (default) | equipo
MAIN_BRANCH=main
TEAM_MEMBERS="Ana,Beto"
```

⚠️ Con `VAULT_MODE=equipo`, **todo commit sobre `main` queda bloqueado**. La salida es
`git switch -c <prefijo>/<tema>`, o `--no-verify` para una excepción puntual. El modo también
enciende el aviso de PRs y hace que el auto-commit se abstenga en la rama principal.

El modo vive en `vault.conf` y no en `owner.env` porque `owner.env` no viaja: ahí, el gate de rama
de la segunda persona nacería inerte. Y `vault.conf` se **parsea, nunca se sourcea** —un `source`
convertiría un PR a este archivo en ejecución de código en la máquina de cada persona—, así que
**un comentario va en su propia línea**, nunca al final de un valor.

**Apagar una guarda, o endurecer el verifier:**

```bash
touch .vault-meta/diary.disabled        # apaga agent-diary.sh
touch .vault-meta/verifier.strict       # el verifier BLOQUEA en vez de avisar
```

Por defecto el verifier es **warn-only**: te avisa qué campo de frontmatter falta y deja pasar el
commit. En CI el equivalente de `strict` es `VERIFIER_STRICT: "1"` en el workflow.

**No toques `.gitattributes` sin leerlo.** `*.sh text eol=lf` es infraestructura crítica en
Windows: con CRLF, el shebang rompe la ejecución en Git Bash y los hooks no arrancan.

## 7. Actualizarse

```bash
./update.sh --check      # ¿hay versión nueva? No toca nada
./update.sh --dry-run    # qué archivos cambiarían
./update.sh              # interactivo: lista y pide confirmación
```

Requiere el remote `upstream`, que `install.sh` cablea solo. Un `git merge` no serviría —las
instancias divergen desde el primer día y el merge daría conflictos en archivos que nadie quiso
tocar—, así que el updater copia por whitelist, con tres clases:

| Clase | Qué es | Qué hace el update |
|---|---|---|
| `infrastructure` | Hooks, scripts, workflows, `00 Sistema/`, `baseline-seguridad/`, docs del template | se sobrescribe siempre |
| `scaffold` | `owner.env`, `vault.conf`, `FIRST_RUN.md`, los 3 stubs de `01 Index/` | se instala una vez y **nunca** se pisa |
| contenido | todo lo demás | no se toca jamás |

Un archivo **tuyo** dentro de una ruta de framework (un SOP propio en `00 Sistema/`) se detecta
porque no existe upstream: se lista aparte y no se toca.

## 8. Adaptarlo a tu repo

**(a) Querés un vault entero.** Seguí la sección 3. Es el camino soportado.

**(b) Querés solo la seguridad, en un repo de código.** Usá
[`baseline-seguridad/`](<baseline-seguridad/README.md>): siete archivos copiables y autocontenidos
con las capas 1 a 3, su propio README con los cinco pasos, y el bloque que pegás en el `CLAUDE.md`
del proyecto destino. No necesita las ocho carpetas ni el verifier.

> **Lo que no hay que hacer** es copiar `.claude/` + `.githooks/` sueltos a otro repo: te llevás
> los hooks sin el contrato que aplican, sin `AGENTS.md`, sin `vault.conf` y sin canal de
> actualizaciones.

**(c) Querés los hooks sobre tu propia estructura de carpetas.** Se puede, pero es trabajo manual:
hay nueve archivos con rutas en duro. La lista y el orden sugerido para reescribirlas están en
[REFERENCIA.md](REFERENCIA.md).

## 9. Límites y licencia

El guard de comandos hace pattern matching sobre el texto, así que produce falsos positivos: un
script que solo *menciona* un archivo de credenciales queda bloqueado igual. Es el intercambio
elegido a propósito. Lo que asume cada hook está en [REFERENCIA.md](REFERENCIA.md).

Doble licencia, **por ruta** (no por extensión, para que un `.md` dentro de `.claude/` no caiga en
las dos a la vez):

| Rutas | Licencia |
|---|---|
| `.claude/**`, `.githooks/**`, `.github/**`, `baseline-seguridad/**`, `*.sh`, `*.py`, `*.yml`, `vault-manifest.json`, `vault.conf`, `owner.env.example`, `VERSION`, `.gitignore`, `.gitattributes` | [MIT](LICENSE) |
| Los `.md` **fuera** de esas rutas: `00 Sistema/**`, `05 Diario/**`, `AGENTS.md`, `README.md`, `DECISIONES.md`, `REFERENCIA.md`, `CHANGELOG.md`, y la arquitectura de carpetas | [CC BY-NC-SA 4.0](LICENSE-CONTENT) |

Las skills, el subagente y los README dentro de rutas MIT son **MIT**: son piezas ejecutables,
aunque estén escritas en Markdown. En caso de duda sobre un archivo no listado, rige
CC BY-NC-SA 4.0. Historial de versiones en [CHANGELOG.md](CHANGELOG.md).

## Glosario

| Término | Qué significa acá |
|---|---|
| **vault** | La carpeta de notas en Markdown, con su estructura y su contrato. No es una base de datos ni una app |
| **harness** | La herramienta desde la que corre el agente (Claude Code, Codex, otra). Un control que solo vive en un harness protege solo mientras uses ese harness |
| **centinela** | Marca `<!-- @user -->` / `<!-- @generated -->` que declara qué bloque de un documento es tuyo y cuál puede regenerar el sistema |
| **gate** · **guarda** | Chequeo que puede **bloquear** una acción —un commit, un push, un comando—, a diferencia de un aviso |
| **fail-open** | Si a la guarda le falta una dependencia, deja pasar en vez de romper. Frenar tu trabajo por una causa ajena sale más caro |
| **warn-only** | El chequeo avisa pero no bloquea. Es el modo por defecto del verifier |
| **infrastructure** · **scaffold** | Las dos clases de la whitelist del updater: lo primero se sobrescribe siempre, lo segundo se instala una vez y nunca se pisa |
| **upstream** | El remote de git que apunta al template. Es el canal por el que llegan las actualizaciones |

© 2026 Leandro Esteban Aguilar Montilla.
