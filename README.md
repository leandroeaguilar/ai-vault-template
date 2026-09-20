# AI Vault Template

[![versión](https://img.shields.io/badge/versión-v0.5.0-blue)](CHANGELOG.md)
[![licencia](https://img.shields.io/badge/código-MIT-green)](LICENSE)
[![contenido](https://img.shields.io/badge/contenido-CC%20BY--NC--SA%204.0-lightgrey)](LICENSE-CONTENT)

## 1. Qué es

Plantilla para arrancar un **vault de conocimiento que se opera con agentes de IA sin que eso
sea un riesgo**: guardas deterministas que bloquean antes de ejecutar, un gate de secretos en
cada commit y en cada PR, centinelas que protegen lo que escribiste vos de ser reescrito por un
agente, y un actualizador por whitelist para distribuir cambios sin pisar el contenido de nadie.

Es la capa de ingeniería de un sistema personal más grande (un vault de Obsidian que sigue
siendo privado): acá está **lo que corre y lo que especifica lo que corre**. El método —los SOPs
de cómo se estudia, se decide y se revisa— no está, y [§12.3](#123--qué-no-está-acá) dice por qué.

**Qué NO es:**

- No es una app ni un plugin de Obsidian. Es un repositorio de git con hooks.
- No es un framework de agentes. No envuelve ningún modelo ni ninguna API.
- No opina sobre cómo tomás notas. Impone un contrato de *metadatos*, no de método.

**Estado:** v0.5.0 · 76 archivos · ~291 KB · datos de este README verificados el **2026-09-20**.

> **Por qué está publicado:** porque el código que guarda un sistema se puede leer y probar en
> dos minutos, y el método no. Si venís a **evaluar el criterio** y no a instalar nada, saltá a
> [§7 Las decisiones de diseño](#7-las-decisiones-de-diseño) o abrí directamente
> [`.githooks/pre-push`](.githooks/pre-push) — 92 líneas que explican por qué detectar el
> *efecto* de un force-push es distinto de detectar la *bandera*.

---

## 2. Requisitos

| Qué | ¿Obligatorio? | Para qué | Si falta |
|---|---|---|---|
| `bash` | sí | Todos los hooks. En Windows: Git Bash | nada corre |
| `git` ≥ 2.9 | sí | `core.hooksPath` (existe desde 2.9) | los hooks no se activan |
| `python3` | en la práctica sí | Guard de comandos, centinelas, índices | **fail-open**: esos hooks dejan de bloquear en vez de romper la sesión |
| `gh` (GitHub CLI) | no | `pr-notice.sh` y la skill `/revisar-pr` | `pr-notice.sh` sale en silencio (`exit 0`): el aviso de PRs no existe y nadie se entera |
| Obsidian + Templater | no | Las 3 plantillas traen `<% tp.date.now() %>` | las plantillas quedan con el tag literal; los hooks corren igual |
| Claude Code | no | Los 9 hooks de `.claude/` (sesión, centinelas en vivo, auto-commit, bitácora) y las tres piezas a demanda, `/onboarding` incluida | quedan inertes; **el gate de git y el de CI siguen en pie**, y la instalación por shell funciona igual |

La frontera de la última fila es la decisión de diseño más importante del repo, y está
argumentada en [§7.2](#72--centinelas--el-reparto-entre-harness-y-git).

---

## 3. Instalación

**Dos comandos.** `install.sh` es reanudable: si falta tu identidad, te deja el archivo listo y
para; lo completás, lo volvés a correr y termina.

```bash
# 1. Forkeá en GitHub, después:
git clone https://github.com/<vos>/<tu-vault>.git
cd <tu-vault>

# 2. Instalar
./install.sh          # cablea hooks, engancha upstream, deja owner.env listo y para
#    → completá owner.env (OWNER, OWNER_EMAIL, OWNER_GITHUB)
./install.sh          # retoma: resuelve los placeholders y termina
```

Y listo. Lo que sigue explica qué hizo cada cosa y por qué el fork es el paso 1.

### 3.1 · Por qué forkear, y no clonar y ya

Si `origin` apunta al template, `install.sh` **no personaliza nada** y te dice cómo arreglarlo:

```bash
git remote set-url origin https://github.com/<vos>/<tu-vault>.git
./install.sh
```

> **No es celo de formulario.** El hook `pre-push` bloquea todo push a un remoto de la familia
> `ai-vault-template` / `sistema-maestro-*` cuando el clon ya tiene `owner.env`: publicaría tu
> nombre y tu correo en el repo del template. Si personalizás primero y arreglás `origin` después,
> la sorpresa te llega en el push. El instalador usa **la misma señal que el hook** para avisarte
> antes. (Escape para el mantenedor: `ALLOW_TEMPLATE_PUSH=1`.)

### 3.2 · Qué hace `install.sh`

| Paso | Qué hace | Por qué |
|---|---|---|
| Hooks | `git config core.hooksPath .githooks` | `.git/hooks/` **no se versiona**: un hook que vive ahí no le llega a nadie más |
| Windows | `core.longpaths true` | Sin esto, un checkout con nombres largos falla |
| Estado | Crea `.vault-meta/` | Marcas de sesión, locks y kill-switches. Gitignorado |
| Upstream | `git remote add upstream <url>` | El canal de actualizaciones. `update.sh` lo **exige**; la URL sale de `vault-manifest.json`, declarada una sola vez |
| Identidad | Crea `owner.env` del ejemplo, y en la segunda corrida ejecuta `personalize.sh` | Once `.md` se publican con `{{ OWNER }}` literal |

Es idempotente: correrlo de nuevo no rompe nada.

**Sobre la identidad.** `owner.env` está **gitignoreado**: es lo único que distingue tu copia de
cualquier otra y no viaja al clon de nadie. Por eso ahí va solo identidad, nunca gobernanza — ver
[§10.2](#102--vaultconf--gobernanza).

Los once archivos con placeholder son las tres plantillas, `Centinelas de Edición`,
`Cómo funciona este vault`, `SOP Documentación`, `SOP Hooks y Automatización`,
`_Acerca de esta bitácora`, las dos skills y el subagente `verifier`. Sin resolverlos te quedan el
frontmatter de todas las plantillas **y el prompt de las skills** con el token adentro.
`personalize.sh` reescribe solo `.md` y `.txt`, que es donde están; `agent-diary.sh` también
necesita tu nombre, pero lo lee de `owner.env` en runtime.

### 3.3 · Lo que ningún script puede hacer por vos

Al terminar quedan tres stubs en `01 Index/` —`Vision`, `Objetivos`, `Mapa Personal`— en
`estado: 🟡 Borrador`. Son la capa de orientación del vault y nadie los puede inventar. Llenalos a
mano, o pedí la entrevista guiada:

```
/onboarding
```

La skill hace lo mismo que los dos comandos de arriba pero preguntando, y además llena esos tres
documentos con tus respuestas. **Es comodidad, no requisito**: esta plantilla tiene que poder
instalarse sin ningún agente, igual que sus guardas corren sin ningún harness ([§7.2](#72--centinelas--el-reparto-entre-harness-y-git)).

### 3.4 · Si lo van a usar varias personas

Editá [`vault.conf`](vault.conf) y commiteálo:

```ini
VAULT_MODE=equipo        # personal (default) | equipo
MAIN_BRANCH=main
TEAM_MEMBERS="Ana,Beto"
```

Qué cambia exactamente, en [§10.2](#102--vaultconf--gobernanza). El aviso más importante: con
`equipo`, **todo commit sobre `main` queda bloqueado**.

---

## 4. Probalo en dos minutos

Los tres comandos que demuestran que las guardas están encendidas. Corrélos ahora, no el día
que las necesites.

**Que la guarda de secretos bloquea de verdad:**

```bash
printf 'AWS_SECRET_ACCESS_KEY=%s%s\n' AKIA 0000000000000000 > fuga.txt
git add -f fuga.txt && git commit -m prueba     # → debe FALLAR
git reset && rm fuga.txt
```

**Que el guard de comandos bloquea antes de ejecutar:**

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"cat .env"}}' \
  | python3 .claude/hooks/security-guard.py ; echo "exit=$?"
```

**El auditor completo:**

```bash
bash .claude/hooks/security-audit.sh
```

Fijate que la clave de prueba se arma en **runtime** (`%s%s`) en vez de ir literal: si fuera
literal, el propio `secret-scan` bloquearía el commit de este repositorio. La guarda se aplica a
sí misma, que es la prueba más barata de que está encendida.

Ese primer comando es el que importa. La lección que originó buena parte de este repo es que
**una guarda que no falla ruidosamente es indistinguible de una que no existe** — dos de estos
hooks estuvieron rotos en silencio: uno perdió el bit ejecutable y solo moría en clones Linux,
el otro devolvía `exit=0` porque buscaba un nombre que había cambiado.

---

## 5. Tu primera sesión

Si abrís el vault con Claude Code, lo primero que pasa es que **saltan cuatro avisos seguidos**.
No es un cuelgue: son los cuatro hooks `SessionStart`.

| Lo que ves | Quién lo escribe | Qué significa |
|---|---|---|
| Estado de git + última entrada de bitácora | `session-context.sh` | El handoff de la sesión anterior. En un vault nuevo viene vacío |
| Rutinas vencidas | `check-routines.sh` | Callado por defecto: `ROUTINES_EXPECTED` viene vacío a propósito |
| Hay versión nueva del template | `update-notice.sh` | Máximo una vez por día, y solo si configuraste `upstream` (3.6) |
| PRs abiertos esperándote | `pr-notice.sh` | Inerte en modo `personal`; callado sin `gh` |

Y al **cerrar** la sesión, si tocaste algún archivo del vault, el hook `Stop` **bloquea el
cierre** hasta que el agente deje una entrada en `05 Diario/Bitácora Agentes/AAAA-MM.md`.
Bloquea una vez por sesión, no en cada turno. Tampoco es un cuelgue: es el handoff, y el porqué
está en [§7.6](#76--continuidad-entre-sesiones).

**El primer commit** es la otra sorpresa útil. Escribí una nota desde
`00 Sistema/001_plantillas/Plantilla Nota.md`, borrale un campo del frontmatter y commiteala:
el verifier te va a **avisar**, no frenar. Es warn-only a propósito; para que bloquee, ver
[§10.3](#103--kill-switches-y-modo-estricto).

---

## 6. Mapa: qué corre y cuándo

La referencia central del repo. Una fila por pieza.

**Columna *harness*:** `CC` = solo dentro de Claude Code (lo cablea
[`.claude/settings.json`](.claude/settings.json)). `todos` = corre para cualquier agente, de
cualquier harness, y para los humanos también.

### 6.1 · Se disparan solas

| Pieza | Disparador | Harness | Necesita | Kill-switch (`.vault-meta/…`) |
|---|---|---|---|---|
| `session-context.sh` | SessionStart | CC | — | `session-context.disabled` |
| `check-routines.sh` | SessionStart | CC | `ROUTINES_EXPECTED` en `vault.conf` | `routines-monitor.disabled` |
| `update-notice.sh` | SessionStart | CC | remote `upstream` + red | `update-notice.disabled` |
| `pr-notice.sh` | SessionStart | CC | `gh` + `VAULT_MODE=equipo` | `pr-notice.disabled` |
| `pre-compact.sh` | PreCompact | CC | — | `precompact.disabled` |
| `sentinels-guard.sh` + `.py` | PreToolUse `Write`/`Edit` | CC | `python3` | `sentinels.disabled` |
| `security-guard.sh` + `.py` | PreToolUse `Bash`/`Read` | CC | `python3` | `security-guard.disabled` |
| `auto-commit.sh` | PostToolUse `Write`/`Edit` | CC | — | `autocommit.disabled` |
| `agent-diary.sh` | Stop | CC | — | `diary.disabled` |
| `check-diary-size.sh` | lo consulta `agent-diary.sh` | CC | — | `diary-cap.disabled` |
| gate de rama | `git commit` | todos | `VAULT_MODE=equipo` | `branch-gate.disabled` |
| `secret-scan.sh` | `git commit` + CI | todos | — | `secret-scan.disabled` |
| `sentinels-verify.py` | `git commit` + CI | todos | `python3` | `sentinels.disabled` |
| `generate-index.py` | `git commit` | todos | `python3` | `index-gen.disabled` |
| `verify-commit.sh` | `git commit` + CI | todos | — | `verifier.disabled` |
| `.githooks/pre-push` | `git push` | todos | — | `prepush.disabled` |
| `verify.yml` | Pull Request | todos | GitHub Actions | desactivar el workflow |
| `aviso-de-pr.yml` | Pull Request | todos | GitHub Actions | desactivar el workflow |

> **Los kill-switches no siguen el nombre del archivo.** `agent-diary.sh` se apaga con
> `diary.disabled`, no con `agent-diary.disabled`; los tres centinelas comparten uno solo,
> `sentinels.disabled`. Usá la columna de esta tabla: está verificada contra el código, no
> deducida del nombre.

`.vault-meta/` está gitignoreado a propósito: versionarlo haría que el kill-switch de una
persona apagara la guarda de todas las demás.

### 6.2 · Se corren a mano

| Comando | Para qué |
|---|---|
| `bash .claude/hooks/security-audit.sh` | Auditoría completa: secretos committeados, integridad del `.gitignore`, inventario de hooks y de plugins, sanidad del wiring de `settings.json` |
| `bash .claude/hooks/check-links.sh` | Enlaces rotos, resolviendo alias, secciones (`#`) y bloques (`#^`) antes de acusar |
| `python3 .claude/hooks/harden-links.py [--dry]` | Convierte nombres pelados a rutas relativas y re-apunta enlaces cuyo destino se mudó |
| `python3 .claude/hooks/heal-links.py` | Reparación de enlaces rotos |
| `python3 .claude/hooks/search-sessions.py` | Busca en transcripts de sesiones viejas |
| `bash .claude/hooks/wiki-lock.sh acquire\|release\|peek <ruta>` | Lock advisory por archivo para escritura multi-agente |
| `bash .claude/hooks/check-diary-size.sh` | Estado del tope de la bitácora del mes |

### 6.3 · Se invocan desde el agente

| Pieza | Qué hace | Necesita |
|---|---|---|
| `/onboarding` | Entrevista de inicialización: identidad, modo de gobernanza y los tres stubs de `01 Index/`. **Comodidad, no requisito**: `install.sh` hace todo lo imprescindible sin agente | Claude Code |
| `/revisar-seguridad` | Auditoría a demanda antes de instalar o abrir algo: plugin, hook, paquete, repo externo, contenido no confiable. **Nunca ejecuta el target** | Claude Code |
| `/revisar-pr` | Traduce un PR de Markdown a lenguaje de vault: qué cambió de verdad, qué contradice algo ya decidido, qué no se llegó a mirar. **No aprueba ni mergea** | Claude Code + `gh` |
| `verifier` (subagente) | Tier-2 del verifier: juez LLM sobre el diff *staged*, en contexto fresco, antes de commitear. **Advisory, no toca archivos** | Claude Code |

Las tres tienen la misma restricción escrita en el prompt: **proponen, no deciden.** No aprueban
PRs, no mergean, no ejecutan lo que están auditando. Un agente que se autoaprueba no es un
control.

---

## 7. Las decisiones de diseño

Hasta acá, qué hace cada pieza. De acá en adelante, por qué está hecha así.

### 7.1 · Seguridad

**Cuatro capas deterministas**, deliberadamente redundantes. Si una falla, otra ataja.

| Capa | Dónde | Qué hace |
|---|---|---|
| 1 · Declarativa | `.claude/settings.json` | 11 reglas `deny`: lectura y escritura fuera del repo, `curl`/`wget`, `git push --force`, y los archivos de credenciales por nombre |
| 2 · Preventiva | `.claude/hooks/security-guard.sh` + `.py` | `PreToolUse` sobre `Bash` y `Read`: inspecciona el comando **antes** de que se ejecute |
| 3 · De commit | `.claude/hooks/secret-scan.sh` | Gate `pre-commit` (y de CI): bloquea si hay un secreto staged |
| 4 · Detectiva | `.claude/hooks/security-audit.sh` | Auditor por CLI, no cableado a eventos: se corre a mano |

Hay una **quinta capa, y es la única falible**, porque es criterio y no código:
`/revisar-seguridad` ([§6.3](#63--se-invocan-desde-el-agente)). Se cuenta aparte de las cuatro de
arriba a propósito — un juicio de un modelo no es una guarda determinista, y mezclarlos en la
misma lista sería contarse un cuento.

**La capa 2 existe porque la 1 no alcanza.** Una regla `deny` sobre `Read(**/.env)` cubre la
herramienta `Read`, pero no cubre `cat .env` desde `Bash` — que llega al mismo archivo por otra
puerta. El guard mira el comando, no la herramienta.

**La capa 3 existe porque el commit es el punto de no retorno.** Un secreto que entra al
historial no se saca borrando el archivo: hay que reescribir la historia, y si ya se pusheó, hay
que rotar la credencial igual. El gate barato es el que corre antes.

El guard es **determinista y falla en abierto**: sin `python3` no bloquea nada en vez de romper
la sesión. Y tiene kill-switch por archivo, porque una guarda que no se puede apagar se termina
arrancando de raíz.

> **Limitación honesta:** el guard hace *pattern matching sobre el texto del comando*. Eso
> produce falsos positivos — un script que simplemente *menciona* un nombre de archivo de
> credenciales queda bloqueado igual. Es el intercambio elegido a propósito: preferimos el falso
> positivo, que cuesta una reformulación, al falso negativo, que cuesta una credencial.

### 7.2 · Centinelas — el reparto entre harness y git

Bloques marcados `@user` en un documento son **de la persona**: un agente no los reescribe. Los
marcados `@generated` son del sistema y se regeneran libremente. Se escriben como comentarios
HTML, así que no se ven en el modo lectura de Obsidian y son Markdown puro:

```markdown
<!-- @user -->
Esta reflexión es mía. La IA no la toca. Puede ocupar varias líneas.
<!-- /@user -->
```

Abre con `<!-- @user -->` (o `@generated`) y cierra con `<!-- /@user -->`. Los espacios internos
son flexibles, podés tener varios bloques por nota, y fuera de los bloques el texto es libre.
Los marcadores que aparecen dentro de bloques de código o entre backticks **no cuentan**: sin esa
excepción, un marcador de apertura suelto en un ejemplo empareja con el primer cierre real de más
abajo y "protege" media nota. La spec completa está en
[`Centinelas de Edición`](<00 Sistema/Centinelas de Edición.md>).

Lo hacen cumplir dos piezas, en dos momentos:

- `sentinels-guard.sh` + `.py` — `PreToolUse` sobre `Write`/`Edit`. Cubre solo al agente que
  respeta hooks del harness.
- `sentinels-verify.py` — corre en `pre-commit` **y** en CI. Ese es el que importa: cubre a
  cualquier agente, de cualquier harness, y a los humanos también. Escape deliberado:
  `SENTINELS_OK=1 git commit …`.

**El reparto es intencional, y es el criterio que ordena todo el repo.** Un control que solo
existe dentro de una herramienta protege mientras se use esa herramienta. Por eso cada control
que de verdad importa tiene su equivalente en `git`, donde no hay harness que valga.

### 7.3 · Verifier

`verify-commit.sh` relee lo que se va a commitear y valida las reglas mecánicas antes de que
entren a la historia. No juzga contenido — verifica lo verificable: los cuatro campos
obligatorios de frontmatter (`tipo_doc`, `estado`, `ultima_revision`, `id`), el formato de los
tags, la presencia de `description`.

Ese es **el** contrato del repo: lo especifica
[`SOP Documentación`](<00 Sistema/SOP Documentación.md>) y lo aplica este script. Acepta la
clave propia o su equivalente OKF (`type` por `tipo_doc`, `timestamp` o `generated` por
`ultima_revision`) mientras dure la transición.

Es la contraparte barata del criterio: lo que una máquina puede chequear no debería gastar la
atención de una persona ni el contexto de un agente.

**Es warn-only por defecto**, y eso también es una decisión: obliga a normalizar el frontmatter
*al tocar* un documento, no a hacer una migración retroactiva de todo el vault el día uno. Para
que bloquee, ver [§10.3](#103--kill-switches-y-modo-estricto).

### 7.4 · Git

`.githooks/pre-push` tiene dos guardas, en este orden:

1. **No pushear un vault personalizado al repo del template.** Ver [§3.1](#31--por-qué-forkear-y-no-clonar-y-ya).
2. **Bloquear el push non-fast-forward**, que es lo que `--force` realmente hace cuando destruye
   trabajo:
   - Un `--force` que resulta fast-forward es inofensivo y **no** se marca.
   - Un push sin `--force` nunca es non-fast-forward: git ya lo rechaza solo.

Se detecta el **efecto**, no la bandera. Por eso no se esquiva escribiendo el flag distinto
(`-f`, `--force-with-lease`, un alias). Escape explícito: `ALLOW_FORCE_PUSH=1`. Si no se puede
determinar la relación entre los commits, permite: fail-open.

`.githooks/pre-commit` encadena los gates en orden de costo: gate de rama (barato) → secretos →
centinelas → índices → aviso de archivos de control → verifier. No tiene sentido escanear un
commit que va a ser rechazado.

### 7.5 · Índices y enlaces

`generate-index.py` regenera el `index.md` de cada carpeta a partir del frontmatter de sus notas,
y el `pre-commit` lo suma al commit. `harden-links.py` y `heal-links.py` convierten y reparan
enlaces; `check-links.sh` reporta los rotos resolviendo alias, secciones (`#`) y bloques (`#^`)
antes de acusar.

Los `index.md` son **artefactos generados**, no contenido: por eso `update.sh` no los sincroniza
—cada instancia regenera el suyo desde su propio frontmatter— y por eso el CI avisa si un diff de
regeneración no da cero (significa que alguien commiteó sin el hook).

### 7.6 · Continuidad entre sesiones

El problema: cada sesión de un agente empieza en cero, y la anterior se lleva el contexto.

- `agent-diary.sh` — hook `Stop`. Si hubo trabajo, **bloquea el cierre** hasta que el agente deje
  una entrada de handoff. Deduplica por `session_id`: bloquea una vez por sesión, no en cada
  turno — antes costaba un turno extra del modelo por cada turno de trabajo.
- `session-context.sh` — hook `SessionStart`. Inyecta la última entrada. El handoff que nadie lee
  no sirve de nada.
- `check-diary-size.sh` — pone tope. Un registro que crece sin límite deja de ser contexto y pasa
  a ser lastre; pasado el umbral, el hook `Stop` le pide al agente que **proponga** una
  consolidación. No borra ni bloquea: la tijera sigue siendo del propietario.
- `pre-compact.sh` — respalda el transcript **antes** de que el agente compacte su contexto.
- `search-sessions.py` — busca en sesiones viejas.

Multi-agente: `wiki-lock.sh` implementa un lock advisory por archivo sin `flock` (que no existe
en Git Bash) usando `mkdir` como primitiva atómica de posesión, y `auto-commit.sh` commitea
**solo** el archivo tocado, nunca `git add -A`.

### 7.7 · CI

`.github/workflows/verify.yml` corre el mismo gate del lado del servidor, porque los hooks
locales solo corren en el clon de quien commitea y solo si corrió el instalador. En un repo
compartido eso no es una garantía: es una esperanza.

Qué bloquea y qué no es deliberado:

| Chequeo | En CI |
|---|---|
| `secret-scan` | **bloquea** — un secreto en una rama publicada ya se filtró |
| `sentinels-verify` | **bloquea** — que un PR altere un bloque `@user` no se negocia |
| `verify-commit` | avisa (bloquea con `VERIFIER_STRICT: "1"` en el workflow) |
| `check-links` | informa — los rotos incluyen promesas `[[wikilink]]` intencionales |
| índices | informa — si el diff no da cero, alguien commiteó sin el hook |

Una advertencia que salta por cualquier cosa se aprende a ignorar, y ahí perdés las dos.

`.github/workflows/aviso-de-pr.yml` comenta en cada PR mencionando a quien tiene que revisar y
**marcando si el PR toca archivos que cambian el comportamiento del agente de la otra persona**.
Existe porque `CODEOWNERS` no auto-asigna revisor en repos privados con plan Free (verificado
2026-08-07), así que la vista "te pidieron review" queda muerta; una mención notifica siempre.
Nunca falla el check: un aviso roto no debe bloquear un PR.

### 7.8 · El patrón que comparten todas las piezas

**El modelo nunca es la única capa.** `verify-commit.sh` decide lo que se puede decidir con un
`grep`; el subagente opina sobre lo que no. La guarda determinista bloquea; la skill recomienda.
Cuando los dos coinciden no aporta nada; cuando difieren, ahí está el hallazgo.

---

## 8. El vault mínimo

Las ocho carpetas (`00 Sistema` … `99 Archivo`) no son decoración: **nueve archivos del toolkit
las nombran en duro** — ocho hooks en `.claude/hooks/` más `.githooks/pre-commit`. Sin ellas el
repo se clona y los hooks no tienen sobre qué correr.

| Carpeta | Quién la nombra en duro |
|---|---|
| `00 Sistema` | `check-links.sh`, `sentinels-verify.py`, `verify-commit.sh`, `pre-commit` |
| `01 Index` | `session-context.sh`, `verify-commit.sh` |
| `02 MOCs` | `verify-commit.sh` |
| `04 Knowledge` | `verify-commit.sh`, `sentinels-verify.py`, `generate-index.py`, `check-routines.sh` |
| `05 Diario` | `agent-diary.sh`, `check-diary-size.sh`, `session-context.sh`, `check-routines.sh` |
| `03 Proyectos`, `06 Raw`, `99 Archivo` | **ningún hook** — viajan por la estructura PARA, no porque el código las necesite |

Junto con las carpetas viaja lo mínimo para que el verifier tenga sentido:

| Qué | Por qué está |
|---|---|
| [`SOP Documentación`](<00 Sistema/SOP Documentación.md>) | El contrato que aplican `verify-commit.sh`, `harden-links.py` y `generate-index.py`: frontmatter canónico, naming, esquema de `id`, regla de enlaces |
| [`Centinelas de Edición`](<00 Sistema/Centinelas de Edición.md>) | La spec de `sentinels-guard.*` y `sentinels-verify.py` |
| [`SOP Hooks y Automatización`](<00 Sistema/SOP Hooks y Automatización.md>) | Cómo se escribe, se cablea y se apaga un hook; los locks advisory |
| [`Cómo funciona este vault`](<00 Sistema/Cómo funciona este vault.md>) | El porqué de las ocho carpetas: el pipeline `06 Raw` → `04 Knowledge` → `02 MOCs` → `01 Index`, LLM Wiki y OKF |
| 3 plantillas | El frontmatter que el verifier exige, en un archivo que se puede copiar |
| [`AGENTS.md`](AGENTS.md) | El contrato que lee cualquier agente antes de escribir |
| 3 stubs en `01 Index/` | La capa de orientación: `Vision`, `Objetivos`, `Mapa Personal`. Son `scaffold`, no infraestructura — los llenás una vez y `update.sh` no vuelve a tocarlos |

**Publicar un validador sin su esquema no sirve de nada**, y así estuvo este repo en su primera
versión: los hooks aplicaban un contrato que vivía en un archivo privado.

---

## 9. Adaptarlo a tu repo

Tres escenarios. Elegí el tuyo antes de copiar nada.

### (a) Querés un vault entero

Seguí [§3](#3-instalación). Es el camino soportado: te llevás la estructura, el contrato y el
canal de actualizaciones.

### (b) Querés solo la seguridad, en un repo de código

Usá [`baseline-seguridad/`](<baseline-seguridad/README.md>) — un kit portable y **autocontenido** de las
capas 1 a 3, pensado exactamente para esto. Son siete archivos copiables: `settings.json` (fusionás el
bloque `deny` con el tuyo), `security-guard.sh` + `.py`, `secret-scan.sh`, un `pre-commit`, un
`gitignore-secretos.txt`, y su propio README con los cinco pasos y el bloque que pegás en el
`CLAUDE.md` / `AGENTS.md` del proyecto destino.

No necesita las ocho carpetas, ni el verifier, ni `python3` para vivir (el guard es fail-open).

> **Lo que NO hay que hacer** es copiar `.claude/` + `.githooks/` sueltos a otro repo. Te llevás
> los hooks sin `00 Sistema/` —el contrato que aplican—, sin `AGENTS.md`, sin `vault.conf` y sin
> canal de actualizaciones: exactamente el bug que §8 declara arreglado. Si querés seguridad en
> un repo de código, la respuesta es `baseline-seguridad/`.

### (c) Querés los hooks sobre tu propia estructura de carpetas

Se puede, pero es trabajo manual y hay que reescribir rutas en duro. La lista completa está en la
tabla de [§8](#8-el-vault-mínimo): son nueve archivos. Empezá por
`verify-commit.sh` (define las zonas donde el frontmatter es obligatorio, y sus exenciones),
seguí por `agent-diary.sh` y `session-context.sh` (la ruta de la bitácora) y terminá por
`generate-index.py` y `sentinels-verify.py`.

Se publican sin generalizar, a propósito: un hook honesto sobre sus supuestos es mejor evidencia
que uno genérico a medias.

---

## 10. Configuración

### 10.1 · `owner.env` — identidad

Gitignoreado. `OWNER`, `OWNER_EMAIL`, `OWNER_GITHUB`. Lo consume `personalize.sh` (sustitución
en los `.md`) y `agent-diary.sh` (en runtime, para dirigirse a vos por tu nombre).

### 10.2 · `vault.conf` — gobernanza

**Versionado**, y eso es el punto. `owner.env` es identidad y no llega al clon de nadie; la
gobernanza sí tiene que llegar. Mientras el modo vivía en `owner.env`, la segunda persona clonaba
el vault y su gate de rama nacía inerte sin que nadie se enterara — justo para quien había que
frenar.

| Clave | Valores | Qué cambia |
|---|---|---|
| `VAULT_MODE` | `personal` (default) · `equipo` | `equipo` enciende el gate de rama en `pre-commit`, el aviso de PRs al abrir sesión, y hace que el auto-commit se abstenga en la rama principal. En `personal` toda esa capa es inerte |
| `MAIN_BRANCH` | `main` | La rama que el gate protege |
| `TEAM_MEMBERS` | lista separada por comas | Solo con `VAULT_MODE=equipo` |
| `ROUTINES_EXPECTED` | `semanal`, `mensual` | Vacío por defecto: un vault nuevo no tiene informes, y un monitor encendido gritaría "NUNCA corrió" desde el día uno. **Vigilar exige declarar** |

> `vault.conf` se **parsea, nunca se sourcea**. Es un archivo versionado: un `source` convertiría
> un PR a este archivo en ejecución de código en la máquina de cada persona, en cada commit.
> Consecuencia práctica: **un comentario va en su propia línea**, nunca al final de un valor.

**Con `VAULT_MODE=equipo`, todo commit sobre `main` queda bloqueado.** Es el efecto más visible y
el más fácil de olvidar; la salida es `git switch -c <prefijo>/<tema>`, o `--no-verify` para una
excepción puntual.

`vault.conf` está declarado como `scaffold` en `vault-manifest.json`: se instala una vez y
`update.sh` **nunca** lo pisa. Si entrara en la whitelist de infraestructura, cada actualización
apagaría el modo `equipo` de un vault de organización sin que nadie lo hubiera pedido.

### 10.3 · Kill-switches y modo estricto

Cada guarda se apaga creando un archivo vacío en `.vault-meta/`. **Los nombres no se deducen del
nombre del hook** — la lista verificada es la columna de [§6.1](#61--se-disparan-solas):

```bash
touch .vault-meta/diary.disabled        # agent-diary.sh
touch .vault-meta/sentinels.disabled    # los TRES centinelas
touch .vault-meta/verifier.disabled     # verify-commit.sh
```

Para que el verifier **bloquee** en vez de avisar:

```bash
touch .vault-meta/verifier.strict       # o: VERIFIER_STRICT=1 git commit …
```

En CI, el equivalente es `VERIFIER_STRICT: "1"` en `.github/workflows/verify.yml`.

### 10.4 · `.gitattributes`

No lo toques sin leerlo. `*.sh text eol=lf` es **infraestructura crítica en Windows**: con CRLF,
el shebang y los `\r` finales rompen la ejecución en Git Bash y los hooks no arrancan. Y
`merge=union` en la bitácora y el changelog evita que dos personas que registran su handoff en
paralelo choquen siempre en la última línea.

---

## 11. Actualizarse

`update.sh` + `vault-manifest.json` son la parte que más cuesta hacer bien: distribuir
actualizaciones de un template a instancias que ya tienen contenido propio.

**Requiere el remote `upstream`**, que `install.sh` cablea solo ([§3.2](#32--qué-hace-installsh)). Sin él, aborta.

```bash
./update.sh --check      # ¿hay versión nueva? No toca nada
./update.sh --dry-run    # qué archivos cambiarían
./update.sh              # interactivo: lista y pide confirmación
./update.sh --force      # sin preguntar
```

**Un `git merge` no sirve.** Las instancias divergen desde el primer día; el merge produce
conflictos en archivos que la persona nunca quiso tocar. La whitelist declara tres clases:

| Clase | Qué es | Qué hace el update |
|---|---|---|
| `infrastructure` | Hooks, scripts, workflows, `00 Sistema/`, `baseline-seguridad/`, docs del template | Se sobrescribe siempre |
| `scaffold` | `owner.env`, `vault.conf`, `FIRST_RUN.md`, los 3 stubs de `01 Index/` | Se instala una vez, **nunca** se pisa. Si los llenaste o los borraste, un update no te los devuelve |
| contenido | Todo lo demás | No se toca jamás |

`update.sh` copia por `diff`/`checkout`, no mergea — por eso no necesita historia compartida con
el upstream. Un archivo **tuyo** dentro de una ruta de framework (un SOP propio en `00 Sistema/`)
se detecta porque no existe upstream, se lista aparte y no se toca.

Después del update corre `personalize.sh` solo, para que los placeholders de los archivos nuevos
queden resueltos.

> La whitelist de `update.sh` y la de `vault-manifest.json` **tienen que decir lo mismo, y toda
> ruta que nombran tiene que existir**. Es fácil que se desincronicen —agregás un archivo al
> manifest y te olvidás del script— y el modo de falla es silencioso: el updater simplemente no
> copia ese archivo, sin decir nada.

---

## 12. Supuestos y límites

### 12.1 · Qué asume cada hook

| Hook | Asume |
|---|---|
| `agent-diary.sh`, `check-diary-size.sh`, `session-context.sh` | Bitácora en `05 Diario/Bitácora Agentes/AAAA-MM.md` |
| `verify-commit.sh` | Frontmatter obligatorio en `00 Sistema`, `01 Index`, `02 MOCs` y `04 Knowledge`, con exenciones declaradas en el propio script |
| `check-links.sh`, `generate-index.py` | Sintaxis de wikilinks de Obsidian |
| `pr-notice.sh`, `check-routines.sh`, `auto-commit.sh` | `vault.conf` con `VAULT_MODE` |
| `pr-notice.sh`, `/revisar-pr` | `gh` instalado y autenticado |
| Los 9 hooks de `.claude/` | Claude Code. En otro harness quedan inertes |

### 12.2 · Cabos sueltos

Referencias que el repo arrastra y que **no existen** en esta versión. Se declaran en vez de
esconderse:

| Referencia | Quién la nombra | Efecto real |
|---|---|---|
| `.github/CODEOWNERS` | `aviso-de-pr.yml` | Ninguno: es una de tres fuentes de menciones, y la ausencia queda declarada en el log del workflow. No se publica un archivo de ejemplo porque los handles son de cada instancia |

Hasta la v0.4.0 había dos más, y eran bugs de verdad: `personalize.sh` mandaba a `/onboarding`, un
comando que el repositorio no traía, y `update.sh` invocaba `team-mode.sh`, que tampoco existía.
Los dos venían de la misma causa —esta plantilla se talló de un template privado y se llevó los
scripts sin las piezas de las que dependen— y los dos se cerraron en la v0.5.0: el onboarding
ahora existe, `team-mode.sh` se sacó. Ver el [CHANGELOG](CHANGELOG.md).

### 12.3 · Qué NO está acá

Los SOPs de método —cómo se estudia, se decide, se revisa, se construye carrera—, las plantillas
de conocimiento, las skills de auditoría y revisión, los MOCs y el `CLAUDE.md` con la taxonomía
completa. Eso es un sistema privado y no se publica.

La línea de corte: **entra lo que ejecuta, y lo que especifica lo que ejecuta.**
`SOP Documentación` entra porque el verifier lo aplica en cada commit; un SOP sobre cómo escribir
notas atómicas no, porque ningún hook lo aplica. Este repo es la maquinaria y su contrato, no el
manual del sistema.

---

## 13. Licencia · Changelog

Doble licencia, **por ruta** (no por extensión, para que un `.md` dentro de `.claude/` no caiga
en las dos a la vez):

| Rutas | Licencia |
|---|---|
| `.claude/**`, `.githooks/**`, `.github/**`, `baseline-seguridad/**`, `*.sh`, `*.py`, `*.yml`, `vault-manifest.json`, `vault.conf`, `owner.env.example`, `VERSION`, `.gitignore`, `.gitattributes` | [MIT](LICENSE) |
| Los `.md` **fuera** de esas rutas: `00 Sistema/**`, `05 Diario/**`, `AGENTS.md`, `README.md`, `CHANGELOG.md`, y la arquitectura de carpetas | [CC BY-NC-SA 4.0](LICENSE-CONTENT) |

Las skills, el subagente y los README dentro de rutas MIT son **MIT**: son piezas ejecutables,
aunque estén escritas en Markdown. En caso de duda sobre un archivo no listado, rige
CC BY-NC-SA 4.0.

Historial de versiones en [CHANGELOG.md](CHANGELOG.md). El archivo `VERSION`, el campo `version`
de `vault-manifest.json` y el tag de git tienen que decir lo mismo: `update.sh` compara `VERSION`
contra el del upstream para decidir si una instancia está atrasada.

© 2026 Leandro Esteban Aguilar Montilla.
