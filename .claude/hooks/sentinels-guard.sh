#!/usr/bin/env bash
# PreToolUse (Write|Edit) — guardián de centinelas @user (Gap 3).
#
# Wrapper delgado: chequea el kill-switch, ubica python y delega la lógica en
# sentinels-guard.py (parseo robusto del JSON de stdin). El .py decide exit 0
# (permitir) o exit 2 (bloquear, con motivo en stderr).
#
# FAIL-OPEN: si no hay python, no bloquea (permite). Kill-switch:
# .vault-meta/sentinels.disabled
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
[ -f "$ROOT/.vault-meta/sentinels.disabled" ] && exit 0

PY="$(command -v python 2>/dev/null || command -v python3 2>/dev/null || true)"
[ -z "$PY" ] && exit 0   # sin python -> fail-open

exec "$PY" "$ROOT/.claude/hooks/sentinels-guard.py" "$ROOT"
