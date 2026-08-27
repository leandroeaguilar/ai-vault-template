# Sistema Maestro — Toolkit

Las guardas, hooks y CI que hacen que un repositorio de notas sea **seguro de operar con
agentes de IA**: guardas deterministas que bloquean antes de ejecutar, un gate de secretos
que corre en cada commit y en cada PR, y un actualizador por whitelist para distribuir un
template sin pisar el contenido de nadie.

Es la capa de ingeniería de un sistema personal más grande (un vault de Obsidian que sigue
siendo privado). Acá está **lo que corre**, no el método: ningún SOP, ninguna nota, ninguna
plantilla de contenido. 44 archivos, 280 KB, sin dependencias más allá de `bash`, `git` y
`python3`.

> **Por qué está publicado:** porque el código que guarda un sistema se puede leer y probar
> en dos minutos, y el método no. Si querés evaluar el criterio detrás de esto, empezá por
> [`.githooks/pre-push`](.githooks/pre-push) — 91 líneas que explican por qué detectar el
> *efecto* de un force-push es distinto de detectar la *bandera*.

---

## Instalación

```bash
git clone https://github.com/leandroeaguilar/sistema-maestro-toolkit.git
cd sistema-maestro-toolkit
./install.sh
```

`install.sh` hace tres cosas y ninguna es mágica: `git config core.hooksPath .githooks`
(porque `.git/hooks/` **no se versiona**, así que un hook que vive ahí no le llega a nadie
más), `core.longpaths` para Windows, y crea `.vault-meta/` para el estado local.

Para usarlo en **tu** repo: copiá `.claude/`, `.githooks/`, `.github/workflows/` y
`install.sh`, y corré el instalador ahí.

---

## Seguridad

Cuatro capas, deliberadamente redundantes. Si una falla, otra ataja.

| Capa | Dónde | Qué hace |
|---|---|---|
| 1 · Declarativa | `.claude/settings.json` | 11 reglas `deny`: lectura y escritura fuera del repo, `curl`/`wget`, `git push --force`, y los archivos de credenciales por nombre |
| 2 · Preventiva | `.claude/hooks/security-guard.sh` + `.py` | `PreToolUse` sobre `Bash` y `Read`: inspecciona el comando **antes** de que se ejecute |
| 3 · De commit | `.claude/hooks/secret-scan.sh` | Gate `pre-commit`: bloquea si hay un secreto staged |
| 4 · Detectiva | `.claude/hooks/security-audit.sh` | Auditor por CLI, no cableado a eventos: se corre a mano |

**La capa 2 existe porque la 1 no alcanza.** Una regla `deny` sobre `Read(**/.env)` cubre la
herramienta `Read`, pero no cubre `cat .env` desde `Bash` — que llega al mismo archivo por
otra puerta. El guard mira el comando, no la herramienta.

**La capa 3 existe porque el commit es el punto de no retorno.** Un secreto que entra al
historial no se saca borrando el archivo: hay que reescribir la historia, y si ya se pusheó,
hay que rotar la credencial igual. El gate barato es el que corre antes.

El guard es **determinista y falla en abierto**: sin `python3` no bloquea nada en vez de
romper la sesión. Y tiene kill-switch por archivo (`.vault-meta/security-guard.disabled`),
porque una guarda que no se puede apagar se termina arrancando de raíz.

> **Limitación honesta:** el guard hace *pattern matching sobre el texto del comando*. Eso
> produce falsos positivos — un script que simplemente *menciona* un nombre de archivo de
> credenciales queda bloqueado igual. Es el intercambio elegido a propósito: preferimos el
> falso positivo, que cuesta una reformulación, al falso negativo, que cuesta una credencial.

---

## Centinelas

Bloques marcados `@user` en un documento son **de la persona**: un agente no los reescribe.
Los marcados `@generated` son del sistema y se regeneran libremente.

- `sentinels-guard.sh` + `.py` — `PreToolUse` sobre `Write|Edit`. Cubre solo al agente que
  respeta hooks del harness.
- `sentinels-verify.py` — corre en `pre-commit` **y** en CI. Ese es el que importa: cubre a
  cualquier agente, de cualquier harness, y a los humanos también.

El reparto es intencional. Un control que solo existe dentro de una herramienta protege
mientras se use esa herramienta.

---

## Verifier

`verify-commit.sh` relee lo que se va a commitear y valida las reglas mecánicas antes de que
entren a la historia. No juzga contenido — verifica lo verificable: campos obligatorios de
frontmatter, formato de tags, convenciones de nombres.

Es la contraparte barata del criterio: lo que una máquina puede chequear no debería gastar
la atención de una persona ni el contexto de un agente.

---

## Git

`.githooks/pre-push` bloquea el push **non-fast-forward**, que es lo que `--force` realmente
hace cuando destruye trabajo:

- Un `--force` que resulta fast-forward es inofensivo y **no** se marca.
- Un push sin `--force` nunca es non-fast-forward: git ya lo rechaza solo.

Se detecta el **efecto**, no la bandera. Por eso no se esquiva escribiendo el flag distinto
(`-f`, `--force-with-lease`, un alias). Escape explícito: `ALLOW_FORCE_PUSH=1`.

`.githooks/pre-commit` encadena los gates en orden de costo: gate de rama (barato) →
secretos → centinelas → índices. No tiene sentido escanear un commit que va a ser rechazado.

---

## Índices

`generate-index.py` regenera el `index.md` de cada carpeta a partir del frontmatter de sus
notas, y el `pre-commit` lo suma al commit. `harden-links.py` y `heal-links.py` convierten y
reparan enlaces; `check-links.sh` reporta los rotos resolviendo alias, secciones (`#`) y
bloques (`#^`) antes de acusar.

---

## Continuidad entre sesiones

El problema: cada sesión de un agente empieza en cero, y la anterior se lleva el contexto.

- `agent-diary.sh` — hook `Stop`. Si hubo trabajo, **bloquea el cierre** hasta que el agente
  deje una entrada de handoff. Deduplica por `session_id`: bloquea una vez por sesión, no en
  cada turno.
- `session-context.sh` — hook `SessionStart`. Inyecta la última entrada. El handoff que
  nadie lee no sirve de nada.
- `check-diary-size.sh` — pone tope. Un registro que crece sin límite deja de ser contexto y
  pasa a ser lastre.
- `pre-compact.sh` — respalda el transcript **antes** de que el agente compacte su contexto.
- `search-sessions.py` — busca en sesiones viejas.

Multi-agente: `wiki-lock.sh` implementa un lock advisory por archivo sin `flock` (que no
existe en Git-Bash), y `auto-commit.sh` commitea **solo** el archivo tocado.

---

## CI

`.github/workflows/verify.yml` corre el mismo gate del lado del servidor, porque los hooks
locales solo corren en el clon de quien commitea y solo si corrió el instalador. En un repo
compartido eso no es una garantía: es una esperanza.

Qué bloquea y qué no es deliberado — **secretos y centinelas bloquean**; frontmatter,
enlaces e índices **informan**. Una advertencia que salta por cualquier cosa se aprende a
ignorar, y ahí perdés las dos.

---

## El actualizador por whitelist

`update.sh` + `vault-manifest.json` son la parte que más cuesta hacer bien: distribuir
actualizaciones de un template a instancias que ya tienen contenido propio.

**Un `git merge` no sirve.** Las instancias divergen desde el primer día; el merge produce
conflictos en archivos que la persona nunca quiso tocar. La whitelist declara tres clases:

| Clase | Qué es | Qué hace el update |
|---|---|---|
| `infrastructure` | Hooks, scripts, workflows, config | Se sobrescribe siempre |
| `scaffold` | Archivos de arranque | Se instala una vez, **nunca** se pisa |
| contenido | Todo lo demás | No se toca jamás |

`update.sh` copia por `diff`/`checkout`, no mergea — por eso no necesita historia compartida
con el upstream.

> Estos dos archivos van **tal cual se usan** en el sistema privado: su lista de archivos
> nombra piezas que no están en este repo (`setup.sh`, `team-mode.sh`, `00 Inicio Rapido.md`).
> Se publican como implementación de referencia, no recortados para que parezcan hechos a
> medida. Adaptá la lista a tu repo.

---

## Probalo en dos minutos

Que la guarda de secretos bloquea de verdad:

```bash
./install.sh
printf 'AWS_SECRET_ACCESS_KEY=%s%s\n' AKIA 0000000000000000 > fuga.txt
git add -f fuga.txt && git commit -m prueba     # → debe FALLAR
git reset && rm fuga.txt
```

Que el guard de comandos bloquea antes de ejecutar:

```bash
echo '{"tool_name":"Bash","tool_input":{"command":"cat .env"}}' \
  | python3 .claude/hooks/security-guard.py ; echo "exit=$?"
```

El auditor completo:

```bash
bash .claude/hooks/security-audit.sh
```

Fijate que la clave de prueba se arma en **runtime** (`%s%s`) en vez de ir literal: si
fuera literal, el propio `secret-scan` bloquearía el commit de este repositorio. La
guarda se aplica a sí misma, que es la prueba más barata de que está encendida.

Ese primer comando es el que importa. La lección que originó buena parte de este repo es que
**una guarda que no falla ruidosamente es indistinguible de una que no existe** — dos de
estos hooks estuvieron rotos en silencio: uno perdió el bit ejecutable y solo moría en clones
Linux, el otro devolvía `exit=0` porque buscaba un nombre que había cambiado.

---

## Supuestos

Algunos hooks asumen la estructura del vault del que salieron. Se publican así a propósito:
un hook honesto sobre sus supuestos es mejor evidencia que uno genérico a medias.

| Hook | Asume |
|---|---|
| `agent-diary.sh`, `check-diary-size.sh`, `session-context.sh` | Bitácora en `05 Diario/Bitácora Agentes/AAAA-MM.md` |
| `verify-commit.sh` | Frontmatter obligatorio en ciertas carpetas |
| `check-links.sh`, `generate-index.py` | Sintaxis de wikilinks de Obsidian |
| `pr-notice.sh`, `check-routines.sh`, `auto-commit.sh` | `vault.conf` con `VAULT_MODE` |

Todo se apaga por archivo: `.vault-meta/<nombre>.disabled`.

---

## Qué NO está acá

Los SOPs, las plantillas de contenido, la arquitectura de carpetas, las skills y la
documentación del método. Eso es un sistema privado y no se publica. Este repo es la
maquinaria, no el manual.

---

## Licencia

[MIT](LICENSE) © 2026 Leandro Esteban Aguilar Montilla.
