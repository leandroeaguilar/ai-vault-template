#!/usr/bin/env bash
# check-diary-size.sh — tope de consolidación del Agent Diary.
#
# EL PROBLEMA: la bitácora está acotada AL LEER (`session-context.sh` inyecta solo
# la última entrada) pero es infinita AL ESCRIBIR. Nadie la sintetiza nunca.
# Medición 2026-08-08: `2026-07.md` = 1022 líneas · 377 KB · 76 entradas. Eso ya
# no es un handoff, es un archivo histórico disfrazado de handoff.
#
# LA IDEA (tomada de Hermes, que le pone tope duro a su MEMORY.md y devuelve error
# al excederse): lo valioso no es el número, es **el mecanismo que obliga a
# sintetizar**. Un agente al que solo se le pide "resumí bien" no lo hace; uno que
# choca contra un tope, sí.
#
# CÓMO SE APLICA ACÁ, Y POR QUÉ NO ES UN BLOQUEO: el vault manda "nunca borrar" y
# "siempre proponer, nunca decidir solo". Entonces el tope **no borra ni bloquea**:
# hace que el hook `Stop` le pida al agente que PROPONGA la consolidación cuando el
# mes se pasó de largo. La decisión de tijera sigue siendo del propietario.
#
# Mide CARACTERES, no líneas: las entradas son párrafos largos (~370 chars/línea),
# así que contar líneas subestimaría el costo real de contexto casi 4x.
#
# USO:
#   bash .claude/hooks/check-diary-size.sh              → reporta todos los meses
#   bash .claude/hooks/check-diary-size.sh --level      → imprime OK|SOFT|HARD del mes vigente
#                                                         (lo consume agent-diary.sh)
#
# Kill-switch: .vault-meta/diary-cap.disabled
# FAIL-OPEN: cualquier problema → exit 0 / nivel OK.
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$ROOT" 2>/dev/null || { [ "${1:-}" = "--level" ] && echo "OK"; exit 0; }

DIR="05 Diario/Bitácora Agentes"

# Umbrales. Calibrados contra datos reales: 2026-08 (73 KB / 10 entradas) tiene que
# quedar en silencio; 2026-07 (377 KB / 76) tiene que gritar. El objetivo del techo
# es que el mes vigente siga siendo LEÍBLE de una sentada por un humano o un agente.
SOFT_CHARS="${DIARY_SOFT_CHARS:-120000}"
HARD_CHARS="${DIARY_HARD_CHARS:-200000}"
SOFT_ENTRIES="${DIARY_SOFT_ENTRIES:-25}"
HARD_ENTRIES="${DIARY_HARD_ENTRIES:-40}"

if [ -f .vault-meta/diary-cap.disabled ]; then
  [ "${1:-}" = "--level" ] && echo "OK"
  exit 0
fi

entries_of() { grep -cE '^#{2,3} 20[0-9][0-9]-[0-9]' "$1" 2>/dev/null || echo 0; }
chars_of()   { wc -c < "$1" 2>/dev/null | tr -d ' ' || echo 0; }

level_of() {
  local f="$1" c e
  c="$(chars_of "$f")"; e="$(entries_of "$f")"
  c="${c:-0}"; e="${e:-0}"
  if [ "$c" -gt "$HARD_CHARS" ] || [ "$e" -gt "$HARD_ENTRIES" ]; then echo "HARD"
  elif [ "$c" -gt "$SOFT_CHARS" ] || [ "$e" -gt "$SOFT_ENTRIES" ]; then echo "SOFT"
  else echo "OK"; fi
}

# --- Modo --level: solo el mes vigente, una palabra. Es la interfaz del hook Stop.
if [ "${1:-}" = "--level" ]; then
  F="$DIR/$(date +%Y-%m).md"
  [ -f "$F" ] && level_of "$F" || echo "OK"
  exit 0
fi

# --- Modo reporte: todos los meses.
[ -d "$DIR" ] || { echo "No existe «$DIR»."; exit 0; }

echo "Tope del Agent Diary (soft: ${SOFT_CHARS} chars / ${SOFT_ENTRIES} entradas · hard: ${HARD_CHARS} / ${HARD_ENTRIES})"
echo
over=0
for f in "$DIR"/20*.md; do
  [ -f "$f" ] || continue
  c="$(chars_of "$f")"; e="$(entries_of "$f")"; l="$(level_of "$f")"
  case "$l" in
    HARD) icon="🔴"; over=$((over+1)) ;;
    SOFT) icon="🟡"; over=$((over+1)) ;;
    *)    icon="✅" ;;
  esac
  printf '  %s %-42s %8s chars · %3s entradas · %s\n' "$icon" "$(basename "$f")" "$c" "$e" "$l"
done

if [ "$over" -gt 0 ]; then
  echo
  echo "Qué significa consolidar acá (y qué NO):"
  echo "  · NO es borrar. La bitácora sirve al HANDOFF, no al archivo histórico —"
  echo "    y la historia completa ya vive en git, recuperable con \`git log -p\`."
  echo "  · SÍ es: sintetizar las entradas viejas del mes en un bloque de aprendizajes"
  echo "    duraderos, conservando VERBATIM las últimas (que son el handoff vivo), y"
  echo "    mandando a su nota lo que sea conocimiento reutilizable en vez de diario."
  echo "  · La propone un agente; la tijera final la decide el propietario."
fi
exit 0
