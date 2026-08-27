#!/usr/bin/env bash
# security-audit.sh — auditor de seguridad del repo (CLI, NO cableado a eventos).
#
# Capa 4 (detectivo) del modelo de seguridad (ver el README): corre periódicamente
# (lo invoca la skill de mantenimiento / la rutina semanal) para detectar DRIFT
# de seguridad en lo que vive en git. Determinista, solo LEE, no arregla nada.
#
# Qué audita (todo visible en un clon del repo):
#   1. Secretos committeados (nombres de archivo + patrones de contenido).
#   2. Integridad del .gitignore (que siga protegiendo lo sensible).
#   3. Inventario de hooks + banderas de riesgo (red/secretos/eval en los scripts).
#   4. Inventario de plugins de Obsidian (para revisión humana — §3.1 del SOP).
#   5. Sanidad del wiring de settings.json (guardianes cableados).
#
# Qué NO puede ver (estado local/cuenta, no viaja en el repo) -> revisión manual:
#   - Allowlist de settings.local.json (gitignored).
#   - Conectores MCP de las rutinas cloud (estado de cuenta).
#
# Uso: bash .claude/hooks/security-audit.sh [--quiet]
# Exit 0 siempre (es reporte, no gate). Los hallazgos van por stdout.
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$ROOT" 2>/dev/null || { echo "security-audit: no pude entrar a $ROOT"; exit 0; }
QUIET=0; [ "${1:-}" = "--quiet" ] && QUIET=1

hits_secrets=0; hits_gitignore=0; hits_hooks=0; n_plugins=0; hits_wiring=0

say()  { [ "$QUIET" = 0 ] && printf '%s\n' "$*"; }
head() { [ "$QUIET" = 0 ] && printf '\n== %s ==\n' "$*"; }

# ── 1. Secretos committeados ────────────────────────────────────────────────
head "1. Secretos committeados"
# 1a. Por NOMBRE de archivo (lo que nunca debería estar en git).
name_hits="$(git ls-files 2>/dev/null | grep -iE '(^|/)\.env(\.|$)|\.pem$|\.ppk$|\.p12$|\.pfx$|(^|/)id_rsa|(^|/)id_ed25519|(^|/)credentials\.json$|\.key$|(^|/)\.aws/credentials' | grep -viE '\.(example|sample|template|dist)$' || true)"
if [ -n "$name_hits" ]; then
  say "🔴 Archivos con nombre sensible TRACKEADOS en git:"
  say "$name_hits" | sed 's/^/   /'
  hits_secrets=$((hits_secrets + $(printf '%s\n' "$name_hits" | grep -c . )))
else
  say "🟢 Sin archivos de secretos por nombre."
fi
# 1b. Por CONTENIDO, solo en archivos NO-markdown trackeados (donde viven de verdad;
#     evita falsos positivos de las notas que HABLAN de secretos).
SECRET_CONTENT='-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{22,}|xox[baprs]-[A-Za-z0-9-]{10,}|AIza[0-9A-Za-z_\-]{35}'
content_hits="$(git ls-files '*.json' '*.sh' '*.py' '*.env' '*.yml' '*.yaml' '*.ini' '*.cfg' '*.txt' 2>/dev/null \
  | while IFS= read -r f; do
      case "$f" in *secret-scan.sh|*security-audit.sh|*security-guard.py) continue ;; esac
      grep -InE -e "$SECRET_CONTENT" "$f" 2>/dev/null | sed "s|^|$f:|"
    done || true)"
if [ -n "$content_hits" ]; then
  say "🔴 Posibles secretos por contenido (claves/tokens con formato conocido):"
  say "$content_hits" | sed 's/^/   /'
  hits_secrets=$((hits_secrets + $(printf '%s\n' "$content_hits" | grep -c . )))
else
  say "🟢 Sin patrones de clave/token en archivos de config/código."
fi

# ── 2. Integridad del .gitignore ────────────────────────────────────────────
head "2. Integridad del .gitignore"
for must in ".vault-meta/" "settings.local.json"; do
  if grep -qF "$must" .gitignore 2>/dev/null; then
    say "🟢 .gitignore protege: $must"
  else
    # settings.local.json puede estar ignorado por default global de Claude Code.
    if [ "$must" = "settings.local.json" ] && ! git ls-files --error-unmatch .claude/settings.local.json >/dev/null 2>&1; then
      say "🟢 settings.local.json NO está trackeado (ignorado por default)."
    else
      say "🔴 .gitignore NO protege: $must"
      hits_gitignore=$((hits_gitignore + 1))
    fi
  fi
done
# Verificación dura: que lo sensible NO esté trackeado.
for leak in ".claude/settings.local.json"; do
  if git ls-files --error-unmatch "$leak" >/dev/null 2>&1; then
    say "🔴 FUGA: $leak está TRACKEADO en git."
    hits_gitignore=$((hits_gitignore + 1))
  fi
done
if git ls-files 2>/dev/null | grep -q '^\.vault-meta/'; then
  say "🔴 FUGA: hay archivos de .vault-meta/ trackeados."
  hits_gitignore=$((hits_gitignore + 1))
fi

# ── 3. Inventario de hooks + banderas de riesgo ─────────────────────────────
head "3. Hooks — inventario y banderas de riesgo"
RISK='(\bcurl\b|\bwget\b|\bnc\b|\bncat\b|\btelnet\b|base64[[:space:]]+-{1,2}d|\|[[:space:]]*(sh|bash|zsh)\b)'
for f in .claude/hooks/*.sh .claude/hooks/*.py .githooks/*; do
  [ -f "$f" ] || continue
  # security-guard/audit contienen estos tokens A PROPÓSITO (los detectan/documentan) -> se excluyen.
  case "$f" in *security-guard*|*security-audit*) say "   ⚪ $f (auditor/guardián — exento del escaneo de riesgo)"; continue ;; esac
  risky="$(grep -nE "$RISK" "$f" 2>/dev/null || true)"
  if [ -n "$risky" ]; then
    say "🟡 $f — contiene llamadas a revisar (¿legítimo?):"
    say "$risky" | sed 's/^/      /'
    hits_hooks=$((hits_hooks + 1))
  else
    say "   🟢 $f"
  fi
done

# ── 4. Inventario de plugins de Obsidian ────────────────────────────────────
head "4. Plugins de Obsidian (community) — revisar los nuevos (§3.1 del SOP)"
CP=".obsidian/community-plugins.json"
if [ -f "$CP" ]; then
  plugins="$(grep -oE '"[^"]+"' "$CP" | tr -d '"' | grep -v '^\s*$' || true)"
  if [ -n "$plugins" ]; then
    n_plugins=$(printf '%s\n' "$plugins" | grep -c .)
    say "Plugins community habilitados ($n_plugins):"
    say "$plugins" | sed 's/^/   - /'
  else
    say "🟢 Sin plugins community habilitados."
  fi
else
  say "⚪ No hay $CP (sin plugins community o .obsidian no versionado)."
fi

# ── 5. Sanidad del wiring ───────────────────────────────────────────────────
head "5. Wiring de guardianes (settings.json)"
for g in security-guard sentinels-guard; do
  if grep -q "$g" .claude/settings.json 2>/dev/null; then
    say "🟢 $g cableado en settings.json"
  else
    say "🔴 $g NO está cableado en settings.json"
    hits_wiring=$((hits_wiring + 1))
  fi
done

# ── Resumen ─────────────────────────────────────────────────────────────────
printf '\nsecurity-audit: 🔴 secretos=%d · gitignore=%d · 🟡 hooks-a-revisar=%d · plugins=%d · wiring=%d\n' \
  "$hits_secrets" "$hits_gitignore" "$hits_hooks" "$n_plugins" "$hits_wiring"
say ""
say "Recordá lo que ESTE checker NO ve (revisión manual local):"
say "  · Allowlist de settings.local.json (gitignored) — abrila y revisá drift."
say "  · Conectores MCP de las rutinas cloud — verificá mínimo privilegio en claude.ai/code/routines."
exit 0
