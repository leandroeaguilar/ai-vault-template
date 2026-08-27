#!/usr/bin/env bash
# PreToolUse (Bash|Read) — guardián de seguridad (capa 2, determinista).
#
# Wrapper delgado: chequea el kill-switch, ubica python y delega la lógica en
# security-guard.py (parseo robusto del JSON de stdin). El .py decide exit 0
# (permitir) o exit 2 (bloquear, con motivo en stderr).
#
# Complementa el `deny` de settings.local.json (capa 1): la allowlist matchea
# por PREFIJO del comando; este hook escanea el comando ENTERO y ataja evasiones
# (curl embebido, `cat .env`, force-push a media línea, redirects a config).
# Ver el README del toolkit.
#
# FAIL-OPEN: si no hay python, no bloquea (permite) — la capa 1 (permisos) sigue
# vigente igual. Kill-switch: .vault-meta/security-guard.disabled
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$ROOT/.vault-meta/security-guard.disabled" ] && exit 0

PY="$(command -v python 2>/dev/null || command -v python3 2>/dev/null || true)"
[ -z "$PY" ] && exit 0   # sin python -> fail-open

exec "$PY" "$ROOT/.claude/hooks/security-guard.py" "$ROOT"
