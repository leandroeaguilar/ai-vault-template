#!/usr/bin/env bash
# secret-scan.sh — gate pre-commit: BLOQUEA secretos antes de que entren al historial.
#
# Best practice de cadena de suministro (git-secrets/gitleaks): frenar el secreto
# en el commit es mejor que detectarlo después (una vez en el historial ya "se filtró").
# Complementa a security-audit.sh (que audita lo YA committeado, periódico).
#
# Lo invoca .githooks/pre-commit. Exit != 0 => aborta el commit.
# FAIL-OPEN ante error propio (no rompe commits); FAIL-CLOSED ante detección (bloquea).
# Kill-switch: .vault-meta/secret-scan.disabled   ·   También CLI: bash .claude/hooks/secret-scan.sh
#
# Dos modos (mismos patrones en ambos):
#   (por defecto)          → lo STAGED. Modo del hook pre-commit.
#   --range <BASE> <HEAD>  → lo que cambió entre dos refs. Modo de CI: en un PR
#                            no hay nada staged. Ver .github/workflows/verify.yml
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
cd "$ROOT" 2>/dev/null || exit 0
[ -f .vault-meta/secret-scan.disabled ] && exit 0

RANGE_BASE=""; RANGE_HEAD=""
if [ "${1:-}" = "--range" ]; then
  RANGE_BASE="${2:-}"; RANGE_HEAD="${3:-HEAD}"
  [ -n "$RANGE_BASE" ] || { echo "secret-scan: --range necesita <BASE> [HEAD]" >&2; exit 0; }
fi

# Nombres de archivo que nunca deberían committearse.
NAME_RE='(^|/)\.env(\.|$)|\.pem$|\.ppk$|\.p12$|\.pfx$|(^|/)id_rsa|(^|/)id_ed25519|(^|/)credentials\.json$|\.key$|(^|/)\.aws/credentials'
# Contenido con formato de clave/token conocido (bajo falso positivo).
CONTENT_RE='-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_\-]{35}|-----BEGIN OPENSSH PRIVATE KEY-----'

# quotepath=false: sin esto git entrecomilla y escapa las rutas no-ASCII
# ("contrase\361a.env"); el nombre escapado evade el chequeo por NAME_RE y
# `git show ":$path"` no resuelve -> el CONTENIDO de un archivo con nombre/ruta
# acentuada nunca se escanea. Agujero de seguridad, no cosmético.
if [ -n "$RANGE_BASE" ]; then
  staged="$(git -c core.quotepath=false diff --name-only --diff-filter=ACM "$RANGE_BASE...$RANGE_HEAD" 2>/dev/null || true)"
else
  staged="$(git -c core.quotepath=false diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)"
fi
[ -z "$staged" ] && exit 0

# Contenido de la versión a escanear (staged, o la del HEAD del rango).
blob() {
  if [ -n "$RANGE_BASE" ]; then git show "$RANGE_HEAD:$1" 2>/dev/null
  else git show ":$1" 2>/dev/null; fi
}

violations=0

# 1) Por NOMBRE de archivo staged.
name_hits="$(printf '%s\n' "$staged" | grep -iE "$NAME_RE" | grep -viE '\.(example|sample|template|dist)$' || true)"
if [ -n "$name_hits" ]; then
  echo "🔴 secret-scan: archivos con nombre sensible en el commit:" >&2
  printf '%s\n' "$name_hits" | sed 's/^/   /' >&2
  violations=$((violations+1))
fi

# 2) Por CONTENIDO staged (solo el diff agregado; ignora binarios y markdown-prosa).
while IFS= read -r f; do
  [ -z "$f" ] && continue
  # .md hablan de secretos; los propios scanners CONTIENEN los patrones a propósito.
  case "$f" in *.md|*secret-scan.sh|*security-audit.sh|*security-guard.py) continue ;; esac
  hit="$(blob "$f" | grep -nE -e "$CONTENT_RE" || true)"
  if [ -n "$hit" ]; then
    echo "🔴 secret-scan: posible secreto en «$f»:" >&2
    printf '%s\n' "$hit" | sed 's/^/   /' >&2
    violations=$((violations+1))
  fi
done <<< "$staged"

if [ "$violations" -gt 0 ]; then
  echo "" >&2
  if [ -n "$RANGE_BASE" ]; then
    echo "PR BLOQUEADO por secretos. Un secreto que llegó a una rama publicada YA se filtró:" >&2
    echo "rotalo en el sistema de origen ANTES de limpiar el historial. Ver SOP de Seguridad §5." >&2
  else
    echo "Commit ABORTADO por secretos. Sacá el secreto del stage, movelo a una variable de entorno" >&2
    echo "o a un gestor de secretos, y confirmá que .gitignore lo cubra. Ver el README, sección Seguridad." >&2
    echo "(Falso positivo puntual: git commit --no-verify, o kill-switch .vault-meta/secret-scan.disabled)" >&2
  fi
  exit 1
fi
exit 0
