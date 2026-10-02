# Decisiones de diseño

Por qué cada pieza de esta plantilla está hecha así. El [README](README.md) dice qué hace cada
cosa y cómo se usa; esto es el porqué, y se lee solo.

Si viniste a evaluar el criterio y no a instalar nada, este es el archivo. El otro atajo es
[`.githooks/pre-push`](.githooks/pre-push): 92 líneas que explican por qué detectar el *efecto* de
un force-push es distinto de detectar la *bandera*.

---

## 1. Seguridad: cuatro capas deterministas, y una quinta falible

Las cuatro son deliberadamente redundantes. Si una falla, otra ataja.

| Capa | Dónde | Qué hace |
|---|---|---|
| 1. Declarativa | `.claude/settings.json` | 11 reglas `deny`: lectura y escritura fuera del repo, `curl`/`wget`, `git push --force`, y los archivos de credenciales por nombre |
| 2. Preventiva | `.claude/hooks/security-guard.sh` + `.py` | `PreToolUse` sobre `Bash` y `Read`: inspecciona el comando **antes** de que se ejecute |
| 3. De commit | `.claude/hooks/secret-scan.sh` | Gate `pre-commit` (y de CI): bloquea si hay un secreto staged |
| 4. Detectiva | `.claude/hooks/security-audit.sh` | Auditor por CLI, no cableado a eventos: se corre a mano |

Hay una **quinta capa, y es la única falible**, porque es criterio y no código: la skill
`/revisar-seguridad`. Se cuenta aparte de las cuatro a propósito. Un juicio de un modelo no es una
guarda determinista, y mezclarlos en la misma lista sería contarse un cuento.

**La capa 2 existe porque la 1 no alcanza.** Una regla `deny` sobre `Read(**/.env)` cubre la
herramienta `Read`, pero no cubre `cat .env` desde `Bash`, que llega al mismo archivo por otra
puerta. El guard mira el comando, no la herramienta.

**La capa 3 existe porque el commit es el punto de no retorno.** Un secreto que entra al historial
no se saca borrando el archivo: hay que reescribir la historia, y si ya se pusheó, hay que rotar la
credencial igual. El gate barato es el que corre antes.

El guard es **determinista y falla en abierto**: sin `python3` no bloquea nada, en vez de romper la
sesión. Y tiene kill-switch por archivo, porque una guarda que no se puede apagar se termina
arrancando de raíz.

> **Limitación honesta:** el guard hace *pattern matching sobre el texto del comando*. Eso produce
> falsos positivos: un script que simplemente *menciona* un nombre de archivo de credenciales queda
> bloqueado igual. Es el intercambio elegido a propósito, porque el falso positivo cuesta una
> reformulación y el falso negativo cuesta una credencial.

## 2. Centinelas: el reparto entre harness y git

Bloques marcados `@user` en un documento son **de la persona**: un agente no los reescribe. Los
marcados `@generated` son del sistema y se regeneran libremente. Se escriben como comentarios HTML,
así que no se ven en el modo lectura de Obsidian y son Markdown puro:

```markdown
<!-- @user -->
Esta reflexión es mía. La IA no la toca. Puede ocupar varias líneas.
<!-- /@user -->
```

Los marcadores que aparecen dentro de bloques de código o entre backticks **no cuentan**. Sin esa
excepción, un marcador de apertura suelto en un ejemplo empareja con el primer cierre real de más
abajo y "protege" media nota. La spec completa está en
[`Centinelas de Edición`](<00 Sistema/Centinelas de Edición.md>).

Lo hacen cumplir dos piezas, en dos momentos:

- `sentinels-guard.sh` + `.py`, en `PreToolUse` sobre `Write`/`Edit`. Cubre solo al agente que
  respeta hooks del harness.
- `sentinels-verify.py`, en `pre-commit` **y** en CI. Ese es el que importa: cubre a cualquier
  agente, de cualquier harness, y a los humanos también. Escape deliberado:
  `SENTINELS_OK=1 git commit …`.

**El reparto es intencional, y es el criterio que ordena todo el repositorio.** Un control que solo
existe dentro de una herramienta protege mientras se use esa herramienta. Por eso cada control que
de verdad importa tiene su equivalente en `git`, donde no hay harness que valga. Es también el
motivo por el que la instalación por shell es el camino canónico y `/onboarding` es comodidad: una
plantilla que solo se puede instalar con un agente es una plantilla que depende de ese agente.

## 3. Verifier

`verify-commit.sh` relee lo que se va a commitear y valida las reglas mecánicas antes de que entren
a la historia. No juzga contenido: verifica lo verificable. Los cuatro campos obligatorios de
frontmatter (`tipo_doc`, `estado`, `ultima_revision`, `id`), el formato de los tags, la presencia
de `description`.

Ese es **el** contrato del repositorio: lo especifica
[`SOP Documentación`](<00 Sistema/SOP Documentación.md>) y lo aplica este script. Acepta la clave
propia o su equivalente OKF (`type` por `tipo_doc`, `timestamp` o `generated` por
`ultima_revision`) mientras dure la transición.

Es la contraparte barata del criterio: lo que una máquina puede chequear no debería gastar la
atención de una persona ni el contexto de un agente.

**Es warn-only por defecto**, y eso también es una decisión. Obliga a normalizar el frontmatter *al
tocar* un documento, no a hacer una migración retroactiva de todo el vault el día uno.

## 4. Git

`.githooks/pre-push` tiene dos guardas, en este orden:

1. **No pushear un vault personalizado al repositorio del template.** Bloquea todo push a un remoto
   de la familia `ai-vault-template` / `sistema-maestro-*` cuando el clon ya tiene `owner.env`:
   publicaría tu nombre y tu correo en el repositorio del template. Escape para el mantenedor:
   `ALLOW_TEMPLATE_PUSH=1`.
2. **Bloquear el push non-fast-forward**, que es lo que `--force` realmente hace cuando destruye
   trabajo. Un `--force` que resulta fast-forward es inofensivo y **no** se marca; un push sin
   `--force` nunca es non-fast-forward, porque git ya lo rechaza solo.

Se detecta el **efecto**, no la bandera. Por eso no se esquiva escribiendo el flag distinto (`-f`,
`--force-with-lease`, un alias). Escape explícito: `ALLOW_FORCE_PUSH=1`. Si no se puede determinar
la relación entre los commits, permite: fail-open.

`.githooks/pre-commit` encadena los gates en orden de costo: gate de rama (barato) → secretos →
centinelas → índices → aviso de archivos de control → verifier. No tiene sentido escanear un commit
que va a ser rechazado.

## 5. Índices y enlaces

`generate-index.py` regenera el `index.md` de cada carpeta a partir del frontmatter de sus notas, y
el `pre-commit` lo suma al commit. `harden-links.py` y `heal-links.py` convierten y reparan
enlaces; `check-links.sh` reporta los rotos resolviendo alias, secciones (`#`) y bloques (`#^`)
antes de acusar.

Los `index.md` son **artefactos generados**, no contenido. Por eso `update.sh` no los sincroniza
—cada instancia regenera el suyo desde su propio frontmatter— y por eso el CI avisa si un diff de
regeneración no da cero: significa que alguien commiteó sin el hook.

## 6. Continuidad entre sesiones

El problema: cada sesión de un agente empieza en cero, y la anterior se lleva el contexto.

- `agent-diary.sh`, hook `Stop`. Si hubo trabajo, **bloquea el cierre** hasta que el agente deje una
  entrada de handoff. Deduplica por `session_id`, así que bloquea una vez por sesión y no en cada
  turno: antes costaba un turno extra del modelo por cada turno de trabajo.
- `session-context.sh`, hook `SessionStart`. Inyecta la última entrada. El handoff que nadie lee no
  sirve de nada.
- `check-diary-size.sh` pone tope. Un registro que crece sin límite deja de ser contexto y pasa a
  ser lastre; pasado el umbral, el hook `Stop` le pide al agente que **proponga** una consolidación.
  No borra ni bloquea: la tijera sigue siendo del propietario.
- `pre-compact.sh` respalda el transcript **antes** de que el agente compacte su contexto.
- `search-sessions.py` busca en sesiones viejas.

Multi-agente: `wiki-lock.sh` implementa un lock advisory por archivo sin `flock` (que no existe en
Git Bash), usando `mkdir` como primitiva atómica de posesión. Y `auto-commit.sh` commitea **solo**
el archivo tocado, nunca `git add -A`.

## 7. CI

`.github/workflows/verify.yml` corre el mismo gate del lado del servidor, porque los hooks locales
solo corren en el clon de quien commitea y solo si esa persona corrió el instalador. En un
repositorio compartido eso no es una garantía: es una esperanza.

Qué bloquea y qué no es deliberado:

| Chequeo | En CI |
|---|---|
| `secret-scan` | **bloquea** — un secreto en una rama publicada ya se filtró |
| `sentinels-verify` | **bloquea** — que un PR altere un bloque `@user` no se negocia |
| `verify-commit` | avisa (bloquea con `VERIFIER_STRICT: "1"` en el workflow) |
| `check-links` | informa — los rotos incluyen promesas `[[wikilink]]` intencionales |
| índices | informa — si el diff no da cero, alguien commiteó sin el hook |

Una advertencia que salta por cualquier cosa se aprende a ignorar, y ahí perdés las dos.

`.github/workflows/aviso-de-pr.yml` comenta en cada PR mencionando a quien tiene que revisar, y
marca si el PR toca archivos que cambian el comportamiento del agente de la otra persona. Existe
porque `CODEOWNERS` no auto-asigna revisor en repositorios privados con plan Free (verificado
2026-08-07), así que la vista "te pidieron review" queda muerta y una mención notifica siempre.
Nunca falla el check: un aviso roto no debe bloquear un PR.

## 8. Por qué las guardas fallan ruidosamente

Dos de estos hooks estuvieron rotos en silencio: uno perdió el bit ejecutable y solo moría en
clones Linux, el otro devolvía `exit=0` porque buscaba un nombre que había cambiado. De ahí sale la
prueba de dos minutos del README, y de ahí sale que la clave de ejemplo se arme en runtime: si
fuera literal, el propio `secret-scan` bloquearía el commit de este repositorio. **La guarda se
aplica a sí misma, que es la prueba más barata de que está encendida.**

**Una guarda que no falla ruidosamente es indistinguible de una que no existe.**

## 9. Por qué el vault mínimo viaja con los hooks

Las ocho carpetas no son decoración: nueve archivos del toolkit las nombran en duro (la tabla está
en [REFERENCIA.md](REFERENCIA.md)). Y con ellas viajan los SOPs que definen el contrato, porque
**publicar un validador sin su esquema no sirve de nada** — así estuvo este repositorio en su
primera versión, con los hooks aplicando un contrato que vivía en un archivo privado.

Los hooks se publican sin generalizar, a propósito: un hook honesto sobre sus supuestos es mejor
evidencia que uno genérico a medias.

## 10. El patrón que comparten todas las piezas

**El modelo nunca es la única capa.** `verify-commit.sh` decide lo que se puede decidir con un
`grep`; el subagente `verifier` opina sobre lo que no. La guarda determinista bloquea; la skill
recomienda. Cuando los dos coinciden no aporta nada; cuando difieren, ahí está el hallazgo.

Y las tres piezas que invoca el agente tienen la misma restricción escrita en el prompt:
**proponen, no deciden.** No aprueban PRs, no mergean, no ejecutan lo que están auditando. Un
agente que se autoaprueba no es un control.
