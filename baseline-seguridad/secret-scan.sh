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

# ACMR, con la R: un archivo renombrado y modificado sale como R(ename), no como M;
# sin la R, `git mv a b` + pegar el secreto en b pasaba sin escanearse.
# quotepath=false: sin esto git escapa las rutas no-ASCII y su contenido no se escanea.
staged="$(git -c core.quotepath=false diff --cached --name-only --diff-filter=ACMR 2>/dev/null || true)"
[ -z "$staged" ] && exit 0

violations=0

# 1) Por NOMBRE de archivo staged.
name_hits="$(printf '%s\n' "$staged" | grep -iE "$NAME_RE" | grep -viE '\.(example|sample|template|dist)$' || true)"
if [ -n "$name_hits" ]; then
  echo "🔴 secret-scan: archivos con nombre sensible en el commit:" >&2
  printf '%s\n' "$name_hits" | sed 's/^/   /' >&2
  violations=$((violations+1))
fi

# 2) Por CONTENIDO staged (ignora binarios; en markdown solo claves privadas).
# Una clave privada pegada entera: el encabezado va SOLO en su línea. En prosa
# («una clave empieza con `-----BEGIN ...`») aparece a mitad de renglón y no matchea.
MD_RE='^[[:space:]]*-----BEGIN [A-Z ]*PRIVATE KEY-----[[:space:]]*$'
while IFS= read -r f; do
  [ -z "$f" ] && continue
  re="$CONTENT_RE"
  case "$f" in
    # Los propios scanners CONTIENEN los patrones a propósito. Rutas EXACTAS:
    # con un glob por nombre (*secret-scan.sh), llamar a un archivo
    # `tools/mi-secret-scan.sh` alcanzaba para que nadie mirara su contenido.
    .claude/hooks/secret-scan.sh|.claude/hooks/security-audit.sh|.claude/hooks/security-guard.py) continue ;;
    baseline-seguridad/secret-scan.sh|baseline-seguridad/security-guard.py) continue ;;
    # Los .md hablan de secretos (nombran prefijos de tokens): ahí solo se busca
    # una clave privada completa, que no es prosa.
    *.md) re="$MD_RE" ;;
  esac
  hit="$(git show ":$f" 2>/dev/null | grep -nE -e "$re" || true)"
  if [ -n "$hit" ]; then
    echo "🔴 secret-scan: posible secreto en «$f»:" >&2
    printf '%s
' "$hit" | sed 's/^/   /' >&2
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
