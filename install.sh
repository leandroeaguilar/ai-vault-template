#!/usr/bin/env bash
# Instalador de la plantilla. Correr UNA vez, desde la raiz del repo donde lo usas.
# Idempotente: correrlo dos veces no rompe nada.
set -euo pipefail
cd "$(dirname "$0")"

echo "== AI Vault Template — install =="

# Lo unico imprescindible: que git use .githooks/ en vez de .git/hooks/.
# .git/hooks/ NO se versiona, asi que un hook que vive ahi no llega a nadie mas.
git config core.hooksPath .githooks
echo "✓ core.hooksPath -> .githooks (pre-commit y pre-push activos)"

# Windows: rutas largas. Sin esto, un checkout con nombres largos falla.
git config core.longpaths true 2>/dev/null && echo "✓ core.longpaths" || true

# Estado local de los hooks (marcas de sesion, locks, kill-switches). Gitignorado.
mkdir -p .vault-meta
echo "✓ .vault-meta/ (estado local, no se versiona)"

echo ""
echo "Proba que la guarda de secretos bloquea de verdad:"
echo "  printf 'AWS_SECRET_ACCESS_KEY=%s%s\\n' AKIA 0000000000000000 > fuga.txt"
echo "  git add -f fuga.txt && git commit -m prueba    # debe FALLAR"
echo "  git reset && rm fuga.txt"
echo ""
echo "(La clave de prueba se arma en runtime a proposito: si fuera literal, el"
echo " propio secret-scan bloquearia el commit de este repositorio.)"
