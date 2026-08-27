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
FILE="$(printf '%s' "$INPUT" | sed -n 's/.*"file_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
[ -z "$FILE" ] && exit 0

# Desescapar backslashes de JSON (\\ -> \) y normalizar a ruta unix.
FILE="${FILE//\\\\/\\}"
UNIXFILE="$(cygpath -u "$FILE" 2>/dev/null || printf '%s' "$FILE")"
ROOTU="$(cygpath -u "$ROOT" 2>/dev/null || printf '%s' "$ROOT")"
REL="${UNIXFILE#"$ROOTU"/}"

# Solo contenido del vault (.md/.canvas); excluir config/estado/dispositivo o rutas no resueltas.
case "$REL" in
  .claude/*|.vault-meta/*|.obsidian/*|/*) exit 0 ;;
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
TEAM_MODE="$(sed -n 's/^[[:space:]]*VAULT_MODE=//p' vault.conf 2>/dev/null | tr -d "\"' " | head -1)"
[ -n "$TEAM_MODE" ] || TEAM_MODE="$(sed -n 's/^[[:space:]]*VAULT_MODE=//p' owner.env 2>/dev/null | tr -d "\"' " | head -1)"
if [ "${TEAM_MODE:-personal}" = "equipo" ]; then
  BRANCH="$(git symbolic-ref --short HEAD 2>/dev/null || printf '')"
  case "$BRANCH" in main|master) exit 0 ;; esac
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
git -c user.name="Claude Code" -c user.email="claude@agent.local" \
    commit -q -m "chore(agent): auto-commit $(basename "$REL")" -- "$REL" >/dev/null 2>&1 || true
exit 0
