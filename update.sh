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
  "AGENTS.md" "README.md" "DECISIONES.md" "REFERENCIA.md" "CHANGELOG.md"
  "VERSION" "vault-manifest.json"
  "install.sh" "update.sh" "personalize.sh" "owner.env.example"
  "LICENSE" "LICENSE-CONTENT"
)
# Los workflows se listan uno por uno, NO ".github" entero.
# Los index.md de carpeta son artefactos GENERADOS (generate-index.py en pre-commit):
# no se sincronizan, cada instancia regenera el suyo desde su propio frontmatter.
#
# ⚠️ `vault.conf` NO va en la lista, y no es un olvido. Está versionado (tiene que
# llegar al clon de cada persona) pero su contenido es GOBERNANZA de la instancia:
# VAULT_MODE, MAIN_BRANCH, TEAM_MEMBERS. Si entrara acá, cada `update.sh` pisaría
# el `equipo` de un vault de organización con el `personal` del template, apagando
# el gate de rama sin que nadie lo haya pedido.
# Mismo criterio para `FIRST_RUN.md` y los stubs de `01 Index/`: son scaffold.

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
# diff lo lista igual (como borrado, en esa dirección) y el checkout falla:
# `pathspec ... did not match any file(s) known to 'upstream/main'`. Con eso,
# "Nada que actualizar" nunca se alcanza; y si el archivo cae último, el `while`
# devuelve 1 y `set -euo pipefail` aborta ANTES de personalize.sh, dejando el
# update a medio aplicar. Por eso se filtran los que no existen upstream: no son
# framework, son tu contenido.
#
# ⚠️ La pertenencia se resuelve con `ls-tree` + `grep -Fxq`, NO con
# `git cat-file -e "$REMOTE/$BRANCH:$f"`. En Git Bash (MSYS2, o sea Windows) ese
# argumento tiene dos puntos y partes que parecen rutas POSIX, así que la capa de
# conversión de MSYS lo toma por una LISTA DE RUTAS y la traduce a formato
# Windows, y cat-file responde "Not a valid object name". El fallo es silencioso
# y ASIMÉTRICO: solo golpea a las rutas SIN espacios, que quedan marcadas como
# "tuyas" y no se actualizan nunca. `ls-tree` recibe revisión y ruta como
# argumentos separados, así que no hay dos puntos que convertir; y es UNA llamada
# a git en vez de N.
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

# ¿El update.sh que está CORRIENDO ahora mismo ya es el de upstream?
#
# Se mide ANTES del checkout y contra el ÁRBOL DE TRABAJO, no contra HEAD. La
# pregunta no es si el archivo difiere del último commit —mientras el update no
# se commitee, update.sh difiere SIEMPRE— sino si el proceso en ejecución está
# usando la whitelist FRAMEWORK_PATHS vieja. Si el archivo en disco ya coincide
# con upstream, la whitelist nueva ya se aplicó y no hay nada que re-correr.
SELF_STALE=0
git diff --quiet "$REMOTE/$BRANCH" -- update.sh 2>/dev/null || SELF_STALE=1

# Herestring y no pipe: con pipe el `while` corre en una subshell, FALLIDOS se
# pierde al terminar, y un checkout que falle en la última vuelta aborta el script
# con `set -e` justo antes de personalize.sh.
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
if [ "$SELF_STALE" = "1" ] && printf '%s\n' "$CHANGED" | grep -qx "update.sh"; then
  echo "⚠ update.sh se actualizó a sí mismo — corré ./update.sh una vez más para aplicar la whitelist nueva."
fi
echo "Actualizado a $REMOTE_V. Revisá 'git status' y commiteá: git commit -m \"chore: update framework a $REMOTE_V\""
