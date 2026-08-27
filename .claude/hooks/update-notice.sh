#!/usr/bin/env bash
# SessionStart: avisa (máx 1 vez/día) si hay versión nueva del template upstream.
# Fail-open siempre: sin red, sin remote o sin timeout → silencio y exit 0.
# Kill-switch: .vault-meta/update-notice.disabled
ROOT="${CLAUDE_PROJECT_DIR:-.}"
cd "$ROOT" 2>/dev/null || exit 0
[ -f .vault-meta/update-notice.disabled ] && exit 0
STAMP=".vault-meta/last-update-check"
today="$(date +%Y-%m-%d)"
if [ -f "$STAMP" ] && [ "$(cat "$STAMP" 2>/dev/null)" = "$today" ]; then exit 0; fi
mkdir -p .vault-meta 2>/dev/null || exit 0
echo "$today" > "$STAMP"
git remote get-url upstream >/dev/null 2>&1 || exit 0
if command -v timeout >/dev/null 2>&1; then
  timeout 8 git fetch upstream main --quiet 2>/dev/null || exit 0
else
  git fetch upstream main --quiet 2>/dev/null || exit 0
fi
L="$(cat VERSION 2>/dev/null || echo '?')"
R="$(git show upstream/main:VERSION 2>/dev/null | tr -d '[:space:]')"
if [ -n "$R" ] && [ "$L" != "$R" ]; then
  echo "[TEMPLATE] Hay una actualización de la plantilla: $L → $R. Corré ./update.sh (tu contenido no se toca; ./update.sh --check para ver el detalle)."
fi
exit 0
