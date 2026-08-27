#!/usr/bin/env bash
# wiki-lock.sh — lock advisory por-archivo para escritura multi-agente (sin flock).
#
# Adaptado de claude-obsidian. El original usa `flock` para un meta-lock que
# serializa el robo de locks vencidos; en Git Bash (Windows) `flock` NO existe.
# Port: se elimina el meta-lock porque es innecesario para un lock por-archivo.
#   - Primitiva atómica de posesión = `mkdir` del directorio-lock (atómico en
#     cualquier FS, incluido NTFS): solo un proceso puede crearlo.
#   - Robo de lock vencido = `mv` (rename) atómico: rename() elimina el origen,
#     así que de N procesos que intentan robar el mismo lock vencido, solo UNO
#     logra el rename; el resto recibe ENOENT y reintenta el mkdir. Esto evita
#     el bug de "ambos rm -rf y ambos mkdir → doble dueño" sin meta-lock.
# Sin flock, sin jq, sin node.
#
# Uso:
#   wiki-lock.sh acquire <ruta-rel> [agente]   -> 0 si lo tomó, 1 si está ocupado
#   wiki-lock.sh release <ruta-rel> [agente]   -> libera solo si sos el dueño
#   wiki-lock.sh peek    <ruta-rel>            -> imprime dueño/edad o "unlocked"
#   wiki-lock.sh owner   <ruta-rel>            -> imprime el dueño si el lock está
#                                                 VIGENTE (nada si libre/vencido);
#                                                 machine-friendly (lo usa auto-commit)
#   wiki-lock.sh list                          -> inventario de todos los locks
#   wiki-lock.sh clear-stale                   -> borra todos los locks vencidos
#
# Vars de entorno (opcionales): WIKI_LOCK_TTL (s, def 120), WIKI_LOCK_RETRIES
# (def 10), WIKI_LOCK_SLEEP (s, def 1), WIKI_LOCK_AGENT (identidad de agente por
# defecto para acquire/release; si no, cae a $USER).
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
LOCKDIR="$ROOT/.vault-meta/locks"
TTL="${WIKI_LOCK_TTL:-120}"
RETRIES="${WIKI_LOCK_RETRIES:-10}"
SLEEP="${WIKI_LOCK_SLEEP:-1}"

mkdir -p "$LOCKDIR" 2>/dev/null || true

# Nombre de lock estable a partir de la ruta (neutraliza chars raros de NTFS).
_slug()  { printf '%s' "$1" | tr '/\\ ' '___' | tr -cd 'A-Za-z0-9._-'; }
_now()   { date +%s; }
_mtime() { stat -c %Y "$1" 2>/dev/null || stat -f %m "$1" 2>/dev/null || echo 0; }
_field() { sed -n "s/^$1=//p" "$2" 2>/dev/null | head -1; }

_acquire() {
  local rel="${1:-}" agent="${2:-${WIKI_LOCK_AGENT:-${USER:-agent}}}" lock meta owner age i=0
  [ -z "$rel" ] && { echo "acquire: falta la ruta relativa" >&2; return 2; }
  lock="$LOCKDIR/$(_slug "$rel").lock"; meta="$lock/meta"
  while :; do
    if mkdir "$lock" 2>/dev/null; then
      printf 'agent=%s\npid=%s\nts=%s\npath=%s\n' "$agent" "$$" "$(_now)" "$rel" > "$meta"
      return 0
    fi
    owner="$(_field agent "$meta")"
    # Re-entrante: ya lo tenés vos (misma identidad de agente). Refrescá el ts
    # para que una operación larga no quede vencida y se la roben.
    if [ "$owner" = "$agent" ]; then
      printf 'agent=%s\npid=%s\nts=%s\npath=%s\n' "$agent" "$$" "$(_now)" "$rel" > "$meta" 2>/dev/null || true
      return 0
    fi
    # ¿Vencido? Robo atómico vía rename (solo un proceso lo consigue).
    age=$(( $(_now) - $(_mtime "$meta") ))
    if [ "$age" -ge "$TTL" ]; then
      mv "$lock" "$lock.stale.$$" 2>/dev/null && rm -rf "$lock.stale.$$" 2>/dev/null
      continue
    fi
    i=$((i+1))
    [ "$i" -ge "$RETRIES" ] && { echo "busy: $rel (dueño=$owner, ${age}s)" >&2; return 1; }
    sleep "$SLEEP"
  done
}

_release() {
  local rel="${1:-}" agent="${2:-${WIKI_LOCK_AGENT:-${USER:-agent}}}" lock meta owner
  [ -z "$rel" ] && { echo "release: falta la ruta relativa" >&2; return 2; }
  lock="$LOCKDIR/$(_slug "$rel").lock"; meta="$lock/meta"
  [ -d "$lock" ] || return 0
  owner="$(_field agent "$meta")"
  if [ -n "$owner" ] && [ "$owner" != "$agent" ]; then
    echo "release: $rel pertenece a '$owner', no a '$agent' (no liberado)" >&2
    return 1
  fi
  rm -rf "$lock" 2>/dev/null || true
  return 0
}

_peek() {
  local rel="${1:-}" lock meta age
  [ -z "$rel" ] && { echo "peek: falta la ruta relativa" >&2; return 2; }
  lock="$LOCKDIR/$(_slug "$rel").lock"; meta="$lock/meta"
  if [ -d "$lock" ]; then
    age=$(( $(_now) - $(_mtime "$meta") ))
    echo "locked: $rel"
    sed 's/^/  /' "$meta" 2>/dev/null
    echo "  age=${age}s ttl=${TTL}s$([ "$age" -ge "$TTL" ] && echo ' (STALE)')"
  else
    echo "unlocked: $rel"
  fi
}

_owner() {
  # Imprime el dueño SOLO si el lock existe y NO está vencido. Silencio si libre
  # o vencido (un lock vencido = como si no hubiera dueño). Salida machine-friendly.
  local rel="${1:-}" lock meta age owner
  [ -z "$rel" ] && { echo "owner: falta la ruta relativa" >&2; return 2; }
  lock="$LOCKDIR/$(_slug "$rel").lock"; meta="$lock/meta"
  [ -d "$lock" ] || return 0
  age=$(( $(_now) - $(_mtime "$meta") ))
  [ "$age" -ge "$TTL" ] && return 0
  owner="$(_field agent "$meta")"
  [ -n "$owner" ] && printf '%s\n' "$owner"
  return 0
}

_list() {
  local d meta age owner path n=0
  for d in "$LOCKDIR"/*.lock; do
    [ -d "$d" ] || continue
    meta="$d/meta"
    owner="$(_field agent "$meta")"; path="$(_field path "$meta")"
    age=$(( $(_now) - $(_mtime "$meta") ))
    printf 'agent=%s age=%ss%s path=%s\n' \
      "$owner" "$age" "$([ "$age" -ge "$TTL" ] && echo ' (STALE)')" "$path"
    n=$((n+1))
  done
  [ "$n" -eq 0 ] && echo "(sin locks)"
  return 0
}

_clear_stale() {
  local d meta age n=0
  for d in "$LOCKDIR"/*.lock; do
    [ -d "$d" ] || continue
    meta="$d/meta"; age=$(( $(_now) - $(_mtime "$meta") ))
    if [ "$age" -ge "$TTL" ]; then
      mv "$d" "$d.stale.$$" 2>/dev/null && rm -rf "$d.stale.$$" 2>/dev/null && n=$((n+1))
    fi
  done
  echo "clear-stale: $n lock(s) vencido(s) removido(s)"
}

cmd="${1:-}"; shift 2>/dev/null || true
case "$cmd" in
  acquire)     _acquire "$@" ;;
  release)     _release "$@" ;;
  peek)        _peek "$@" ;;
  owner)       _owner "$@" ;;
  list)        _list ;;
  clear-stale) _clear_stale ;;
  *) echo "uso: wiki-lock.sh {acquire|release|peek|owner|list|clear-stale} <ruta-rel> [agente]" >&2; exit 2 ;;
esac
