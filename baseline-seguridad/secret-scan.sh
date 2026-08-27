#!/usr/bin/env bash
# secret-scan.sh — gate pre-commit: BLOQUEA secretos antes de que entren al historial.
#
# Best practice de cadena de suministro (git-secrets/gitleaks): frenar el secreto
# en el commit es mejor que detectarlo después (una vez en el historial ya "se filtró").
# Complementa a security-audit.sh (que audita lo YA committeado, periódico).
#
# Lo invoca .githooks/pre-commit. Escanea SOLO lo staged. Exit != 0 => aborta el commit.
# FAIL-OPEN ante error propio (no rompe commits); FAIL-CLOSED ante detección (bloquea).
# Kill-switch: .vault-meta/secret-scan.disabled   ·   También CLI: bash .claude/hooks/secret-scan.sh
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "$PWD")"
cd "$ROOT" 2>/dev/null || exit 0
[ -f .vault-meta/secret-scan.disabled ] && exit 0

# Nombres de archivo que nunca deberían committearse.
NAME_RE='(^|/)\.env(\.|$)|\.pem$|\.ppk$|\.p12$|\.pfx$|(^|/)id_rsa|(^|/)id_ed25519|(^|/)credentials\.json$|\.key$|(^|/)\.aws/credentials'
# Contenido con formato de clave/token conocido (bajo falso positivo).
CONTENT_RE='-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_\-]{35}|-----BEGIN OPENSSH PRIVATE KEY-----'

staged="$(git diff --cached --name-only --diff-filter=ACM 2>/dev/null || true)"
[ -z "$staged" ] && exit 0

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
  hit="$(git show ":$f" 2>/dev/null | grep -nE -e "$CONTENT_RE" || true)"
  if [ -n "$hit" ]; then
    echo "🔴 secret-scan: posible secreto en «$f»:" >&2
    printf '%s\n' "$hit" | sed 's/^/   /' >&2
    violations=$((violations+1))
  fi
done <<< "$staged"

if [ "$violations" -gt 0 ]; then
  echo "" >&2
  echo "Commit ABORTADO por secretos. Sacá el secreto del stage, movelo a una variable de entorno" >&2
  echo "o a un gestor de secretos, y confirmá que .gitignore lo cubra. Ver el README del repositorio." >&2
  echo "(Falso positivo puntual: git commit --no-verify, o kill-switch .vault-meta/secret-scan.disabled)" >&2
  exit 1
fi
exit 0
