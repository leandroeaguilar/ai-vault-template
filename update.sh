#!/usr/bin/env bash
# Actualiza SOLO los archivos de framework desde el template upstream.
# Tu contenido (notas, diario, proyectos, 01 Index, Knowledge propio) NUNCA se toca.
# Patrón: whitelist explícita (prior art: COG-second-brain cog-update.sh).
#
# Uso: ./update.sh [--check | --dry-run | --force]
set -euo pipefail
cd "$(dirname "$0")"
REMOTE="upstream"; BRANCH="main"

# Whitelist de framework (sincronizada con vault-manifest.json → infrastructure)
FRAMEWORK_PATHS=(
  ".claude" ".githooks" ".gitattributes" ".gitignore"
  ".github/workflows/verify.yml" ".github/workflows/aviso-de-pr.yml"
  "00 Sistema" "baseline-seguridad"
  "01 Index/.gitkeep" "02 MOCs/.gitkeep" "03 Proyectos/.gitkeep"
  "04 Knowledge/.gitkeep" "06 Raw/.gitkeep" "99 Archivo/.gitkeep"
  "05 Diario/Bitácora Agentes/_Acerca de esta bitácora.md"
  "AGENTS.md" "README.md" "CHANGELOG.md" "VERSION" "vault-manifest.json"
  "install.sh" "update.sh" "personalize.sh" "owner.env.example"
  "LICENSE" "LICENSE-CONTENT"
)
# Ojo: se listan los workflows uno por uno, NO ".github" entero. Los archivos de .github que
# sean framework se agregan acá uno por uno. (El filtro de más abajo ya cubre el
# caso general —un archivo propio dentro de una ruta de framework— así que esto
# dejó de ser la única defensa; se mantiene porque listar solo lo que es
# framework sigue siendo lo correcto.)
# Nota: los index.md de carpeta son artefactos GENERADOS (generate-index.py en pre-commit),
# no se sincronizan — cada instancia regenera el suyo desde su propio frontmatter.
#
# ⚠️ `vault.conf` NO va en la lista, y no es un olvido. Está versionado (tiene que
# llegar al clon de cada persona) pero su contenido es una decisión de GOBERNANZA
# de la instancia: VAULT_MODE, MAIN_BRANCH, TEAM_MEMBERS. Si entrara acá, cada
# `update.sh` pisaría el `equipo` de un vault de organización con el `personal`
# del template — apagando el gate de rama sin que nadie lo haya pedido.
# Mismo criterio que `.github/CODEOWNERS`: se sincroniza el ejemplo, no el real.

MODE="${1:-interactive}"
git remote get-url "$REMOTE" >/dev/null 2>&1 || { echo "Falta remote '$REMOTE'. Corré ./install.sh"; exit 1; }
git fetch "$REMOTE" "$BRANCH" --quiet

LOCAL_V=$(cat VERSION 2>/dev/null || echo "?")
REMOTE_V=$(git show "$REMOTE/$BRANCH:VERSION" 2>/dev/null || echo "?")
echo "Versión local: $LOCAL_V · upstream: $REMOTE_V"
if [ "$MODE" = "--check" ]; then
  [ "$LOCAL_V" = "$REMOTE_V" ] && echo "Al día." || echo "Hay actualización disponible. Corré ./update.sh"
  exit 0
fi

# Archivos de framework que difieren del upstream
CHANGED=$(git -c core.quotepath=false diff --name-only HEAD "$REMOTE/$BRANCH" -- "${FRAMEWORK_PATHS[@]}" || true)

# Un archivo TUYO dentro de una ruta de framework —un SOP propio en "00 Sistema/",
# una skill propia en "04 Knowledge/Skills/"— existe en HEAD y no en upstream. El
# diff lo lista igual (como borrado, en esa dirección) y el checkout de más abajo
# falla: `pathspec ... did not match any file(s) known to 'upstream/main'`.
# Dos consecuencias, la segunda peor que la primera:
#   · el archivo aparece SIEMPRE en la lista, así que "Nada que actualizar" deja
#     de ser alcanzable aunque el framework esté al día;
#   · si cae último, el `while` devuelve 1 y con `set -euo pipefail` el script
#     aborta ANTES de personalize.sh y team-mode.sh — update a medio aplicar.
# Se filtran los que no existen upstream: no son framework, son tu contenido.
# (Es la misma trampa que el comentario de FRAMEWORK_PATHS describe para
#  .github/CODEOWNERS, pero resuelta de raíz en vez de esquivada ruta por ruta.)
#
# ⚠️ La pertenencia se resuelve con `ls-tree` + `grep -Fxq`, NO con
# `git cat-file -e "$REMOTE/$BRANCH:$f"`. En Git Bash (MSYS2, o sea Windows) ese
# argumento tiene dos puntos y partes que parecen rutas POSIX, así que la capa de
# conversión de MSYS lo toma por una LISTA DE RUTAS y la traduce a formato
# Windows: `upstream/main:.claude/x.md` → `upstream\main;.claude\x.md`, y
# cat-file responde "Not a valid object name". El fallo es silencioso y
# ASIMÉTRICO — solo golpea a las rutas SIN espacios (con espacios MSYS no las
# trata como lista), así que `una nota con espacios en el nombre` funcionaba y
# `.claude/commands/cerebro-audit.md` se marcaba como "tuyo" y NUNCA se
# actualizaba. `ls-tree` recibe revisión y ruta como argumentos separados: sin
# dos puntos no hay nada que convertir. Además es UNA llamada a git en vez de N.
UPSTREAM_LS=$(git -c core.quotepath=false ls-tree -r --name-only "$REMOTE/$BRANCH")
if [ -n "$CHANGED" ]; then
  DE_FRAMEWORK=""; MIOS=""
  while IFS= read -r f; do
    [ -n "$f" ] || continue
    if printf '%s\n' "$UPSTREAM_LS" | grep -Fxq -e "$f"; then
      DE_FRAMEWORK="${DE_FRAMEWORK}${f}"$'\n'
    else
      MIOS="${MIOS}${f}"$'\n'
    fi
  done <<< "$CHANGED"
  CHANGED="${DE_FRAMEWORK%$'\n'}"
  if [ -n "$MIOS" ]; then
    echo "Archivos tuyos dentro de rutas de framework (no se tocan):"
    printf '%s' "$MIOS" | sed 's/^/  · /'
  fi
fi

if [ -z "$CHANGED" ]; then echo "Nada que actualizar."; exit 0; fi
echo "Archivos de framework con cambios upstream:"; echo "$CHANGED" | sed 's/^/  · /'

if [ "$MODE" = "--dry-run" ]; then exit 0; fi
if [ "$MODE" != "--force" ]; then
  read -r -p "¿Actualizar estos archivos? Tu contenido no se toca. [s/N] " R
  case "$R" in [sS]) ;; *) echo "Cancelado."; exit 0;; esac
fi

# Herestring y no pipe: con pipe el `while` corre en una subshell y FALLIDOS se
# pierde al terminar. Además, un checkout que falle en la última vuelta hace
# salir la subshell con 1 y, con `set -e`, aborta el script justo antes de
# personalize.sh — el modo de falla que este arreglo viene a cerrar.
# ¿El update.sh que está CORRIENDO ahora mismo ya es el de upstream?
#
# Se mide ANTES del checkout y contra el ÁRBOL DE TRABAJO, no contra HEAD, y esa
# es toda la corrección. `CHANGED` compara HEAD con upstream: mientras el update
# no se commitee, update.sh aparece ahí en TODAS las corridas siguientes — así
# que el aviso de abajo se repetía idéntico para siempre y mandaba a re-correr
# un script que ya estaba al día. Lo que de verdad importa no es si el archivo
# difiere del último commit, sino si el proceso en ejecución está usando la
# whitelist FRAMEWORK_PATHS vieja: si el archivo en disco ya coincide con
# upstream, la whitelist nueva ya se aplicó y no hay nada que re-correr.
SELF_STALE=0
git diff --quiet "$REMOTE/$BRANCH" -- update.sh 2>/dev/null || SELF_STALE=1

FALLIDOS=""
while IFS= read -r f; do
  [ -n "$f" ] || continue
  if git -c core.quotepath=false checkout "$REMOTE/$BRANCH" -- "$f"; then
    echo "  ✓ $f"
  else
    FALLIDOS="${FALLIDOS}${f}"$'\n'
  fi
done <<< "$CHANGED"
if [ -n "$FALLIDOS" ]; then
  echo "⚠ No se pudieron actualizar (revisalos a mano):"
  printf '%s' "$FALLIDOS" | sed 's/^/  · /'
fi
echo ""
if [ -f owner.env ]; then bash ./personalize.sh; fi
# Re-aplica la capa multi-persona (no-op en modo personal; nunca pisa lo existente).
if [ -f team-mode.sh ]; then bash ./team-mode.sh; fi
if [ "$SELF_STALE" = "1" ] && printf '%s\n' "$CHANGED" | grep -qx "update.sh"; then
  echo "⚠ update.sh se actualizó a sí mismo — corré ./update.sh una vez más para aplicar la whitelist nueva."
fi
echo "Actualizado a $REMOTE_V. Revisá 'git status' y commiteá: git commit -m \"chore: update framework a $REMOTE_V\""
