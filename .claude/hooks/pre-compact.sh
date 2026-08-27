#!/usr/bin/env bash
# PreCompact — respaldo del transcript ANTES de que el agente compacte su contexto.
#
# Cuando una sesión se hace larga, el harness "compacta": resume lo viejo para
# liberar espacio, y en ese resumen se pierde el detalle exacto. Este hook saca
# una copia completa de la conversación a disco justo antes, para poder
# rehidratar historia si hace falta. Es invisible: solo corre al compactar.
#
# Guarda en .vault-meta/session-logs/ (gitignored) como session_<trigger>_<ts>.jsonl
# y conserva solo los N más recientes (PRECOMPACT_RETAIN, def 20; borra los viejos).
#
# Adaptado de obsidian-mind (pre-compact.ts) a shell puro: sin node, sin jq.
# Kill-switch: .vault-meta/precompact.disabled
# FAIL-OPEN: cualquier problema → exit 0 (nunca frena la compactación).
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$ROOT" 2>/dev/null || exit 0
[ -f .vault-meta/precompact.disabled ] && exit 0
RETAIN="${PRECOMPACT_RETAIN:-20}"

INPUT="$(cat)"

# Extraer transcript_path y trigger del JSON de stdin (sin jq).
TP="$(printf '%s' "$INPUT" | sed -n 's/.*"transcript_path"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
TRIG="$(printf '%s' "$INPUT" | sed -n 's/.*"trigger"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
[ -z "$TP" ] && exit 0

# Desescapar backslashes de JSON y normalizar a ruta unix (Windows/Git Bash).
TP="${TP//\\\\/\\}"
TPU="$(cygpath -u "$TP" 2>/dev/null || printf '%s' "$TP")"
[ -f "$TPU" ] || exit 0

DIR=".vault-meta/session-logs"
mkdir -p "$DIR" 2>/dev/null || exit 0
cp "$TPU" "$DIR/session_${TRIG:-unknown}_$(date +%Y%m%d_%H%M%S).jsonl" 2>/dev/null || exit 0

# Retención: conservar solo los RETAIN más recientes; borrar el resto.
ls -1t "$DIR"/session_*.jsonl 2>/dev/null | tail -n +"$((RETAIN+1))" | while IFS= read -r f; do
  rm -f "$f" 2>/dev/null || true
done
exit 0
