# Changelog

Formato: [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/) · versionado
[SemVer](https://semver.org/lang/es/).

Cada versión tiene un tag anotado en el repositorio. `update.sh` compara el archivo `VERSION`
contra el del upstream para decidir si una instancia está atrasada — por eso `VERSION`, el campo
`version` de `vault-manifest.json` y el tag tienen que decir lo mismo.

---

## [0.5.0] — 2026-09-20

El procedimiento de instalación documentado dejaba la instancia a medias. La causa no eran tres
errores sueltos: esta plantilla se talló de un template privado y se llevó `personalize.sh` **sin
las dos piezas de las que depende** (`FIRST_RUN.md` y la skill de onboarding). Esta versión cierra
la extracción y fija el principio que faltaba: **el camino de shell es canónico, no un plan B** —
la plantilla tiene que poder instalarse sin ningún agente, igual que sus guardas corren sin ningún
harness.

### Agregado
- **`/onboarding`** — la entrevista guiada, ahora sí publicada: identidad, modo de gobernanza y
  los tres stubs de `01 Index/`. Es **comodidad, no requisito**: todo lo imprescindible lo hace
  `install.sh`. No arrastra `team-mode.sh` ni `entity-mode.sh`, que siguen siendo del template
  privado.
- **`FIRST_RUN.md`** — el cartel de instancia sin inicializar que `personalize.sh` ya esperaba
  encontrar desde la v0.1.0. Documenta los dos caminos, y lo borran tanto `install.sh` como
  `/onboarding`.
- **Tres stubs en `01 Index/`** (`Vision`, `Objetivos`, `Mapa Personal`) — lo único que un script
  no puede inventar. Son `scaffold`: una vez que los llenás o los borrás, `update.sh` no te los
  devuelve.
- **`upstream` en `vault-manifest.json`** — la URL canónica del template, declarada **una sola
  vez**. `install.sh` la lee de ahí en vez de hardcodearla: duplicarla repetiría el incidente de
  la v0.3.0, donde un rename dejó un nombre hardcodeado como código muerto un release entero. El
  regex de familia de `pre-push` se queda donde está, porque es otra cosa — tiene que seguir
  matcheando los nombres viejos.

### Cambiado
- **`install.sh` es reanudable y hace la instalación entera.** Suma el remote `upstream` y encadena
  la identidad: si falta `owner.env` lo crea desde el ejemplo y para; lo completás, lo volvés a
  correr y termina. **La instalación pasó de seis pasos manuales a dos comandos.**
- **`install.sh` distingue los dos contextos en los que corre**, con la misma señal que usa
  `pre-push`: si `origin` apunta a la familia del template, no agrega `upstream` **y no crea
  `owner.env`**. Lo segundo es lo importante: crearlo en el checkout del mantenedor le bloquearía
  sus propios push, porque es justamente su ausencia lo que `pre-push` usa para reconocerlo. A
  quien clonó en vez de forkear, el aviso le llega ahora al instalar y no al pushear.

### Arreglado
- **`personalize.sh` mandaba a `/onboarding`, un comando que este repositorio no traía.** Callejón
  sin salida para quien instalaba a mano. Ahora la skill existe, y el mensaje de "falta
  `owner.env`" apunta primero al camino de shell.
- **El guard de `FIRST_RUN.md` en `personalize.sh` estaba muerto**: chequeaba un archivo que la
  plantilla no publicaba, así que nunca disparaba. Se sacó del todo en vez de revivirlo — bloquear
  la personalización manual contradice el principio de arriba.
- **`update.sh` exigía un remote `upstream` que `install.sh` no creaba**, y al faltar mandaba a
  correr `install.sh`, que era justo lo que no lo agregaba.
- **`update.sh` invocaba `team-mode.sh`**, que no existe en esta plantilla. La llamada estaba
  guardada con `[ -f ]`, así que no rompía nada, pero documentaba un archivo fantasma. Sacada,
  junto con dos comentarios que referenciaban `.github/CODEOWNERS`.
- **`00 Sistema/Cómo funciona este vault.md` §5 duplicaba el procedimiento de instalación y ya
  había derivado** respecto del README: omitía el fork y el `upstream`, y afirmaba que el verifier
  *frena* un commit con frontmatter incompleto cuando es **warn-only** por defecto. Ahora apunta al
  README en vez de repetirlo — misma regla que el propio repo aplica a las dos whitelists.
- **README reescrito.** Era un buen ensayo de diseño y un mal manual: la proporción porqué/cómo era
  de 80/20 y ese 20 describía menos de la mitad del procedimiento real. Trece secciones, con el
  ensayo íntegro en el puesto 7. Además: los kill-switches documentados **eran falsos para 11 de
  16** (`agent-diary.sh` se apaga con `diary.disabled`, no con `agent-diary.disabled`); la licencia
  se clasificaba por extensión, así que los `.md` dentro de `.claude/` caían en MIT y CC BY-NC-SA a
  la vez; `baseline-seguridad/` —la respuesta real a "cómo lo uso en mi repo"— no se nombraba ni
  una vez; y los conteos de archivos, líneas y hooks estaban desactualizados. Todo dato verificable
  lleva fecha.

## [0.4.0] — 2026-08-27

### Agregado
- **`00 Sistema/Cómo funciona este vault.md`** — el porqué de la arquitectura: las ocho carpetas
  numeradas como pipeline (`06 Raw` → `04 Knowledge` → `02 MOCs` → `01 Index`), el patrón
  [LLM Wiki](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) y el estándar
  [OKF](https://github.com/GoogleCloudPlatform/knowledge-catalog).
- **Dos skills:** `/revisar-seguridad` (auditoría a demanda antes de instalar o abrir algo; es la
  capa 5, la única falible) y `/revisar-pr` (traduce un PR de Markdown a lenguaje de vault).
- **Subagente `verifier`** — tier-2 LLM sobre el diff *staged*, complemento del `verify-commit.sh`
  determinista.

## [0.3.0] — 2026-08-27

### Cambiado
- **Renombrado a `ai-vault-template`** (antes `sistema-maestro-toolkit`). El nombre viejo reclamaba
  el nombre del sistema entero para lo que empezó siendo un accesorio.

### Arreglado
- El guard de `pre-push` que impide pushear un vault personalizado al repositorio de la plantilla
  matcheaba nombres de repo hardcodeados, y **ninguno era ya el de este repo**: era código muerto
  desde la primera publicación. Ahora matchea toda la familia, nombres viejos incluidos, porque un
  clon viejo conserva el remoto sin actualizar.

## [0.2.1] — 2026-08-27

### Arreglado
- Faltaba `05 Diario/index.md` y el índice raíz lo enlazaba. `generate-index.py --staged` —que es
  como lo llama el `pre-commit`— solo regenera directorios con un `.md` staged, y `05 Diario` no
  tenía ninguno propio, solo su subcarpeta.
- `VERSION` y `vault-manifest.json` decían `0.2.0` con el tag en `v0.2.1`. Con el archivo una
  versión atrás, el parche existía como tag pero era invisible para `update.sh`.

## [0.2.0] — 2026-08-27

### Agregado
- **Las 8 capas del vault**, `05 Diario/Bitácora Agentes/`, tres SOPs de contrato
  (`SOP Documentación`, `Centinelas de Edición`, `SOP Hooks y Automatización`), tres plantillas y
  un `AGENTS.md` recortado.
- **`LICENSE-CONTENT`** — al entrar contenido, MIT pura dejó de alcanzar: MIT para código,
  CC BY-NC-SA 4.0 para los `.md`.

### Arreglado
- `vault-manifest.json` listaba 46 rutas inexistentes (29 de 41 en `infrastructure`, 17 de 17 en
  `scaffold`) y ocho hooks hardcodeaban carpetas que el repositorio no traía. Se publicaba el motor
  de verificación sin el contrato que verifica.

## [0.1.0] — 2026-08-26

### Agregado
- Publicación inicial: 22 hooks, `.githooks/` (`pre-commit`, `pre-push`), dos workflows de CI,
  la Baseline de Seguridad portable, el actualizador por whitelist (`update.sh` +
  `vault-manifest.json`) y `personalize.sh`.
