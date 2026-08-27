#!/usr/bin/env bash
# verify-commit.sh — verifier pre-commit (self-review determinista del vault).
#
# Relee lo que se va a commitear (archivos STAGED) y valida las reglas mecánicas
# del sistema ANTES de que entren a la historia. Es la "última compuerta barata".
# Ver concepto en el README, sección Verifier. Sin jq, sin node.
#
# Qué valida (solo docs en zonas donde el frontmatter es obligatorio):
#   ERROR   — falta alguno de los 4 campos obligatorios (tipo_doc, estado,
#             ultima_revision, id) o no hay frontmatter.  (convención del vault privado; ver README)
#   AVISO   — tags no en formato [a, b] minúsculas sin '#'.
#
# Modo:
#   Por defecto WARN-ONLY (exit 0 siempre): reporta pero NO frena. Así no obliga
#   a normalizar retroactivamente docs viejos (regla "no retroactivo").
#   ESTRICTO (bloquea, exit 1, si hay ERRORES): activar con .vault-meta/verifier.strict
#   o VERIFIER_STRICT=1. Usar cuando el vault ya esté normalizado / en corridas autónomas.
#
# Kill-switch: .vault-meta/verifier.disabled  → no verifica (exit 0).
# FAIL-OPEN: cualquier error inesperado del propio script → exit 0 (no frena trabajo).
#
# Dos modos de selección de archivos (las REGLAS son las mismas en ambos):
#   (por defecto)              → lo STAGED. Es el modo del hook pre-commit.
#   --range <BASE> <HEAD>      → lo que cambió entre dos refs. Es el modo de CI:
#                                en un PR no hay nada staged. Ver .github/workflows/verify.yml
set -uo pipefail

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo "${CLAUDE_PROJECT_DIR:-$PWD}")"
cd "$ROOT" 2>/dev/null || exit 0
[ -f .vault-meta/verifier.disabled ] && exit 0

RANGE_BASE=""; RANGE_HEAD=""
if [ "${1:-}" = "--range" ]; then
  RANGE_BASE="${2:-}"; RANGE_HEAD="${3:-HEAD}"
  [ -n "$RANGE_BASE" ] || { echo "verify-commit: --range necesita <BASE> [HEAD]" >&2; exit 0; }
fi

STRICT=0
{ [ -f .vault-meta/verifier.strict ] || [ "${VERIFIER_STRICT:-0}" = "1" ]; } && STRICT=1

# Zonas donde el frontmatter (4 campos de la convención del vault) es obligatorio, y
# exenciones dentro de ellas. Skills y Prompts se EXIMEN porque tienen su propio
# esquema de frontmatter (Plantilla Skill/Prompt: fecha_actualizacion + version)
# y se registran en Catálogo de Skills / SOP Prompts, no en la convención del vault privado.
in_scope() {
  case "$1" in
    # index.md de carpeta: OKF estricto, SIN frontmatter (la convención del vault privado; adopción 2026-07-17)
    */index.md|index.md) return 1 ;;
    "04 Knowledge/Cursos/"*|"04 Knowledge/Skills/"*|"04 Knowledge/Prompts/"*|"00 Sistema/001_plantillas/"*|"04 Knowledge/"*" Career OS/"*) return 1 ;;
    "00 Sistema/"*|"01 Index/"*|"02 MOCs/"*|"04 Knowledge/"*) return 0 ;;
    *) return 1 ;;
  esac
}

# Contenido de la versión que se va a verificar (NO el working tree):
# lo staged, o el archivo tal como quedó en HEAD del rango.
staged() {
  if [ -n "$RANGE_BASE" ]; then git show "$RANGE_HEAD:$1" 2>/dev/null
  else git show ":$1" 2>/dev/null; fi
}

# Lista de archivos a verificar, según el modo.
changed_files() {
  if [ -n "$RANGE_BASE" ]; then
    git diff --name-only --diff-filter=ACM "$RANGE_BASE...$RANGE_HEAD" 2>/dev/null
  else
    git diff --cached --name-only --diff-filter=ACM 2>/dev/null
  fi
}

errors=0; warns=0; report=""

# Archivos staged agregados/copiados/modificados (no borrados), solo .md.
while IFS= read -r f; do
  [ -z "$f" ] && continue
  case "$f" in *.md) : ;; *) continue ;; esac
  in_scope "$f" || continue

  content="$(staged "$f")"
  # Extraer bloque de frontmatter (entre los dos primeros '---').
  fm="$(printf '%s\n' "$content" | awk 'NR==1&&$0=="---"{f=1;next} f&&/^---[ \t]*$/{exit} f{print}')"

  if [ -z "$fm" ]; then
    report="${report}  ✗ ${f}: sin frontmatter (faltan tipo_doc, estado, ultima_revision, id)\n"
    errors=$((errors+1))
    continue
  fi

  miss=""
  # Dual-key OKF: acepta la clave propia O su equivalente OKF (tipo_doc|type,
  # ultima_revision|timestamp) durante la transición. OKF v0.2: `generated:`
  # (bloque {by, at}) reemplaza a `timestamp`; se acepta cualquiera de los tres.
  printf '%s\n' "$fm" | grep -qE '^(tipo_doc|type):' || miss="${miss} tipo_doc"
  printf '%s\n' "$fm" | grep -qE '^estado:' || miss="${miss} estado"
  printf '%s\n' "$fm" | grep -qE '^(ultima_revision|timestamp|generated):' || miss="${miss} generated"
  printf '%s\n' "$fm" | grep -qE '^id:' || miss="${miss} id"
  if [ -n "$miss" ]; then
    report="${report}  ✗ ${f}: falta(n) campo(s):${miss}\n"
    errors=$((errors+1))
  fi

  # Aviso: tags con '#'. Cubre inline (tags: [#x]) y multilínea (- "#x").
  if printf '%s\n' "$fm" | grep -qE '(^tags:.*#|^[[:space:]]*-[[:space:]]*["'"'"']?#)'; then
    report="${report}  ⚠ ${f}: tags con '#' (usar [a, b] sin '#')\n"
    warns=$((warns+1))
  fi

  # Aviso: sin description (OKF T1, adoptado 2026-07-17) — una oración que
  # alimenta los index.md generados. Warn-only: se agrega al tocar.
  if ! printf '%s\n' "$fm" | grep -qE '^description:'; then
    report="${report}  ⚠ ${f}: sin description (OKF — agregar una oración al tocar)\n"
    warns=$((warns+1))
  fi
done < <(changed_files)

# --- Reporte ---
SCOPE="los archivos staged"
[ -n "$RANGE_BASE" ] && SCOPE="lo que cambió en $RANGE_BASE...$RANGE_HEAD"

if [ "$errors" -gt 0 ] || [ "$warns" -gt 0 ]; then
  echo "verify-commit: $errors error(es), $warns aviso(s):"
  printf "%b" "$report"
else
  echo "verify-commit: OK (frontmatter y tags conformes en $SCOPE)."
fi

if [ "$STRICT" -eq 1 ] && [ "$errors" -gt 0 ]; then
  if [ -n "$RANGE_BASE" ]; then
    echo "verify-commit: MODO ESTRICTO → PR bloqueado. Corregí el frontmatter de los archivos listados."
  else
    echo "verify-commit: MODO ESTRICTO → commit bloqueado. Corregí los errores, o desactivá con .vault-meta/verifier.disabled"
  fi
  exit 1
fi
exit 0
