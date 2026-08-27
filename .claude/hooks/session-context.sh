#!/usr/bin/env bash
# SessionStart (startup|resume|compact) — memoria de LECTURA (Gap A).
#
# Cierra el círculo del Agent Diary: el Stop escribe el handoff; ESTE hook lo
# LEE y lo inyecta al contexto al arrancar (o reanudar, o tras compactar). Así
# el próximo agente arranca "caliente" sin que nadie le recuerde leer la bitácora.
# Patrón "hot cache" adaptado de claude-obsidian / obsidian-second-brain, pero
# reusando la Bitácora de Agentes en vez de un archivo aparte. Sin jq, sin node.
#
# Lo que inyecta (breve y factual):
#   - Estado git: rama, último commit, nº de cambios sin commitear.
#   - La ÚLTIMA entrada de la Bitácora de Agentes del mes vigente (el handoff).
#
# La salida por stdout la agrega Claude Code al contexto de la sesión.
# Kill-switch: .vault-meta/session-context.disabled
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$ROOT" 2>/dev/null || exit 0
[ -f .vault-meta/session-context.disabled ] && exit 0

DIR="05 Diario/Bitácora Agentes"

# Bitácora más reciente por nombre (YYYY-MM.md); ignora el _Acerca.
FILE="$(ls "$DIR"/20*.md 2>/dev/null | sort | tail -1)"

echo "[MEMORIA DE SESIÓN — contexto restaurado automáticamente]"

# Estado del repo (dónde quedamos).
if [ -d .git ]; then
  branch="$(git branch --show-current 2>/dev/null)"
  last="$(git log --oneline -1 2>/dev/null)"
  dirty="$(git status --short 2>/dev/null | grep -c .)"
  echo "Git: rama '${branch}' · último commit: ${last} · ${dirty} cambio(s) sin commitear."
fi

# Última entrada de la bitácora (el handoff del agente anterior).
if [ -n "$FILE" ] && [ -f "$FILE" ]; then
  ln="$(grep -nE '^#{2,3} 20[0-9][0-9]-[0-9]' "$FILE" 2>/dev/null | tail -1 | cut -d: -f1)"
  echo
  echo "Último handoff en «$FILE»:"
  if [ -n "$ln" ]; then
    sed -n "${ln},\$p" "$FILE" | head -40
  else
    tail -20 "$FILE"
  fi
  # Señal de frescura: si hubo commits DESPUÉS del último toque a la bitácora,
  # el handoff de arriba puede estar desfasado (trabajo sin registrar o entrada
  # vieja). No aplica si la bitácora está sucia en el working tree (se está
  # actualizando ahora mismo).
  if [ -d .git ]; then
    diary_dirty="$(git status --short -- "$FILE" 2>/dev/null | grep -c .)"
    if [ "${diary_dirty:-0}" -eq 0 ]; then
      last_diary_commit="$(git log -1 --format=%H -- "$FILE" 2>/dev/null)"
      if [ -n "$last_diary_commit" ]; then
        commits_since="$(git rev-list --count "${last_diary_commit}..HEAD" 2>/dev/null)"
        if [ "${commits_since:-0}" -gt 0 ]; then
          echo
          echo "⚠ Hubo ${commits_since} commit(s) DESPUÉS de este handoff — puede estar desfasado. Confirmá el estado real contra «01 Index/Roadmap del Sistema.md» y el git log antes de decidir el siguiente paso."
        fi
      fi
    fi
  fi
  echo
  echo "(Bitácora completa: «$FILE». Para desactivar esta inyección: .vault-meta/session-context.disabled)"
else
  echo "(Sin bitácora de agentes aún: $DIR)"
fi
exit 0
