#!/usr/bin/env bash
# Reemplaza los placeholders de owner ({{ OWNER }}, {{ OWNER_EMAIL }},
# {{ OWNER_GITHUB }}) usando owner.env. Idempotente.
#
# NO hace falta correrlo a mano: lo encadena install.sh. Queda invocable por
# separado porque update.sh lo re-corre tras cada actualizacion, para resolver
# los placeholders de los archivos nuevos.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -f owner.env ]; then
  cat >&2 <<'MSG'
No hay owner.env, asi que no hay con que reemplazar los placeholders.

  cp owner.env.example owner.env     # y completalo
  ./install.sh                       # retoma desde ahi

(O, con un agente: abri esta carpeta con Claude Code y pedi /onboarding.)
MSG
  exit 0
fi

# shellcheck disable=SC1091
source ./owner.env
: "${OWNER:?owner.env sin OWNER=}"

# No hay guard contra FIRST_RUN.md: personalizar a mano tiene que poder hacerse
# sin ningun agente. De lo que falta al terminar avisa install.sh.

# sed -i NO es portable: GNU no lleva sufijo, BSD/macOS lo exige. Se evita del todo
# reescribiendo cada archivo via temp-file (funciona igual en Linux, macOS y Git-Bash).
#
# Alcance: .md y .txt. NO toca .py ni .sh — un placeholder hardcodeado en un hook
# no se resuelve nunca por esta via (agent-diary.sh lee owner.env en runtime).
find . -path ./.git -prune -o -type f \( -name "*.md" -o -name "*.txt" \) -print0 | \
  while IFS= read -r -d '' f; do
    sed -e "s/{{OWNER_EMAIL}}/${OWNER_EMAIL:-}/g" \
        -e "s/{{OWNER_GITHUB}}/${OWNER_GITHUB:-}/g" \
        -e "s/{{OWNER}}/${OWNER}/g" "$f" > "$f.tmp" && mv "$f.tmp" "$f"
  done
echo "✓ Personalizado para: $OWNER"
