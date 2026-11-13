#!/usr/bin/env bash
# PostToolUse (Write|Edit) — marca la sesión y auto-commitea SOLO el archivo tocado.
#
# Diseño (adaptado de claude-obsidian, sin node y sin jq — no disponibles aquí):
#   - Parsea file_path del JSON de stdin con sed (no hay jq).
#   - Normaliza rutas Windows con cygpath.
#   - Commitea EXCLUSIVAMENTE ese archivo (nunca `git add -A`) para no barrer
#     cambios pendientes no relacionados (p.ej. .obsidian/graph.json, borrados sueltos).
#   - Identidad de agente vía `git -c` (no contamina la config del repo).
#   - Deja una marca .vault-meta/session-touched para que el hook Stop (Agent Diary)
#     sepa que hubo trabajo, aunque el auto-commit esté desactivado.
#   - Kill-switch: .vault-meta/autocommit.disabled
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$ROOT" 2>/dev/null || exit 0
[ -d .git ] || exit 0

INPUT="$(cat)"

# --- extraer file_path del JSON (sin jq) ---
# Con python: un parser de JSON de verdad. Entiende los escapes \uXXXX (una ruta
# con tilde puede llegar como "Decisión.md"), las comillas escapadas y un
# "file_path" que aparezca además dentro del `content` de un Write.
# Sin python: sed, que cubre el caso común (rutas en UTF-8 crudo).
PY="$(command -v python3 2>/dev/null || command -v python 2>/dev/null || true)"
FILE=""
if [ -n "$PY" ]; then
  FILE="$(printf '%s' "$INPUT" | "$PY" -c '
import json, sys
try:
    d = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace"))
    fp = (d.get("tool_input") or {}).get("file_path") or ""
    sys.stdout.buffer.write(str(fp).encode("utf-8"))
except Exception:
    pass
' 2>/dev/null || true)"
else
  FILE="$(printf '%s' "$INPUT" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
  FILE="${FILE//\\\\/\\}"      # desescapar backslashes de JSON (\\ -> \)
fi
[ -z "$FILE" ] && exit 0

# Normalizar a ruta unix.
UNIXFILE="$(cygpath -u "$FILE" 2>/dev/null || printf '%s' "$FILE")"
ROOTU="$(cygpath -u "$ROOT" 2>/dev/null || printf '%s' "$ROOT")"
REL="${UNIXFILE#"$ROOTU"/}"

# Solo contenido del vault (.md/.canvas); excluir config/estado/dispositivo o rutas no resueltas.
case "$REL" in
  /*|[A-Za-z]:*)
    # El archivo no cae bajo la raíz del vault (o cygpath tradujo raíz y archivo
    # de forma distinta). No se commitea, pero queda dicho: antes salía en silencio.
    case "$REL" in *.md|*.canvas)
      mkdir -p .vault-meta 2>/dev/null && printf '%s auto-commit: ruta fuera de la raíz, no se commitea: %s (raíz: %s)
'         "$(date '+%Y-%m-%dT%H:%M:%S' 2>/dev/null)" "$REL" "$ROOTU" >> .vault-meta/guard-errors.log 2>/dev/null ;;
    esac
    exit 0 ;;
  .claude/*|.vault-meta/*|.obsidian/*) exit 0 ;;
  *.md|*.canvas) : ;;
  *) exit 0 ;;
esac

# Marca de sesión para el Agent Diary (siempre, aunque el auto-commit esté off).
mkdir -p .vault-meta 2>/dev/null || true
: > .vault-meta/session-touched 2>/dev/null || true

# Kill-switch del auto-commit.
[ -f .vault-meta/autocommit.disabled ] && exit 0

# Modo equipo: `main` es el vault que TODOS abren; se toca SOLO por PR (el README, sección Git).
# Cuando VAULT_MODE=equipo, no auto-commitear en main/master — el trabajo va en una
# rama de persona y se integra por PR. En una rama de trabajo el auto-commit sigue igual.
# (La marca session-touched de arriba ya avisó al Agent Diary que hubo cambios.)
# El modo vive en vault.conf, que está VERSIONADO y por lo tanto llega a todos
# los clones. owner.env queda como fallback de compatibilidad: está gitignoreado,
# así que ahí el modo nunca llegaba al clon de las demás personas.
# La lectura vive en vault-conf.sh (la misma que usa el pre-commit).
# shellcheck source=.claude/hooks/vault-conf.sh
if . "$PWD/.claude/hooks/vault-conf.sh" 2>/dev/null && [ "$(vault_mode)" = "equipo" ]; then
  BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || printf '')"
  case "$BRANCH" in "$(vault_conf MAIN_BRANCH main)"|main|master) exit 0 ;; esac
fi

# Consciente de locks: si OTRO agente tiene un lock vigente sobre este archivo,
# no lo commitees (es trabajo en curso ajeno) — dejá el cambio para su dueño.
# Camino común (sin locks) intacto: si el dir de locks está vacío, ni consultamos.
LOCKDIR=".vault-meta/locks"
if [ -n "$(ls -A "$LOCKDIR" 2>/dev/null)" ]; then
  SELF="${WIKI_LOCK_AGENT:-${USER:-agent}}"
  OWNER="$(bash "$ROOT/.claude/hooks/wiki-lock.sh" owner "$REL" 2>/dev/null || true)"
  [ -n "$OWNER" ] && [ "$OWNER" != "$SELF" ] && exit 0
fi

# Commit SOLO ese archivo, con identidad de agente.
git add -- "$REL" 2>/dev/null || exit 0
git diff --cached --quiet -- "$REL" 2>/dev/null && exit 0
git -c user.name="Claude Code" -c user.email="claude@agent.local"     commit -q -m "chore(agent): auto-commit $(basename "$REL")" -- "$REL" >/dev/null 2>&1 || exit 0

# Resincronizar el index.md de la carpeta. `git commit -- <ruta>` es un commit
# PARCIAL: git arma un índice temporal, y lo que el pre-commit le agrega ahí (el
# index.md regenerado) entra al commit pero NO vuelve al índice real. Resultado:
# el índice real se queda con la versión VIEJA del index.md ya staged, y el
# siguiente `git commit` manual la revierte (o borra el archivo, si era nuevo).
# Como el index.md del disco es idéntico al de HEAD, re-stagearlo deja todo limpio.
IDX="$(dirname "$REL")/index.md"; IDX="${IDX#./}"
# Se compara por hash contra HEAD (y no con `git diff`, que mira el índice real,
# justamente el que quedó desfasado): solo se re-stagea si disco == HEAD, o sea
# si no hay nada del usuario que pisar.
if [ -f "$IDX" ]; then
  IN_HEAD="$(git rev-parse -q --verify "HEAD:$IDX" 2>/dev/null || true)"
  if [ -n "$IN_HEAD" ] && [ "$(git hash-object -- "$IDX" 2>/dev/null)" = "$IN_HEAD" ]; then
    git add -- "$IDX" 2>/dev/null || true
  fi
fi
exit 0
