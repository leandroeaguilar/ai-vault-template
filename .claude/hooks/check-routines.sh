#!/usr/bin/env bash
# check-routines.sh — monitor de rutinas programadas (cloud).
#
# EL PROBLEMA QUE RESUELVE (incidente 2026-07-16): las rutinas cloud escriben su
# informe y lo commitean, pero **nadie avisa cuando NO corren**. Entre el 05/07 y
# el 16/07 ninguna corrida se ejecutó y el panel las mostraba "activa": once días
# de silencio que nadie notó, porque el sistema es *pull* (hay que ir a mirar) y
# el propietario es *push* (se entera de lo que le llega).
#
# LA IDEA: no se puede empujar una notificación desde acá (no hay infraestructura
# de aviso), pero SÍ se puede hacer que la ausencia sea **imposible de no ver en
# el momento de contacto** — al abrir una sesión. Eso convierte "nadie se enteró
# en 11 días" en "te enterás la próxima vez que abrís el vault".
#
# QUÉ MIDE, Y POR QUÉ ESO: mide el **resultado** (¿hay informe reciente?), no el
# mecanismo (¿el cron disparó?). Es deliberado y es lo que lo hace robusto:
#   - No depende de la API de rutinas ni de credenciales.
#   - Un informe escrito a mano cuenta como mantenimiento hecho — que es la verdad
#     operativa: lo que importa es que el mantenimiento ocurra, no quién lo corrió.
#   - Sobrevive a un clon fresco: la fecha sale del NOMBRE del archivo, no del
#     mtime (que en un clon es la hora del checkout y mentiría).
#
# SILENCIO CUANDO TODO ANDA. Solo habla si algo está vencido. Un aviso que aparece
# siempre se vuelve parte del paisaje y deja de verse — que es exactamente cómo se
# perdieron los once días.
#
# OPT-IN POR `vault.conf` (`ROUTINES_EXPECTED`), y esto NO es opcional:
# un vault recién creado no tiene ningún informe, así que sin este interruptor el
# monitor gritaría «NUNCA corrió» desde el día uno en toda instancia nueva — el
# falso positivo permanente que este mismo diseño dice que hay que evitar. Vigilar
# una rutina exige **declararla**: explícito le gana a adivinar. Vacío = mudo.
#
# USO:
#   bash .claude/hooks/check-routines.sh            → modo hook: calla si está OK
#   bash .claude/hooks/check-routines.sh --status   → siempre reporta (CLI)
#
# Kill-switch: .vault-meta/routines-monitor.disabled
# FAIL-OPEN: cualquier problema → exit 0 (nunca frena una sesión).
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$ROOT" 2>/dev/null || exit 0
[ -f .vault-meta/routines-monitor.disabled ] && exit 0

SHOW_ALL=0
[ "${1:-}" = "--status" ] && SHOW_ALL=1

# Qué rutinas vigilar. Se PARSEA, nunca se sourcea: `vault.conf` está versionado y
# un `source` convertiría un PR a ese archivo en ejecución de código en la máquina
# de cada persona (misma regla que `pr-notice.sh` / `auto-commit.sh`).
EXPECTED="$(sed -n 's/^[[:space:]]*ROUTINES_EXPECTED=//p' vault.conf 2>/dev/null | tr -d "\"' " | head -1)"

if [ -z "$EXPECTED" ]; then
  [ "$SHOW_ALL" -eq 1 ] && {
    echo "Monitor de rutinas: no hay ninguna rutina declarada."
    echo "  Este vault no vigila rutinas programadas. Para activarlo, poné en «vault.conf»:"
    echo "      ROUTINES_EXPECTED=semanal,mensual"
    echo "  (claves disponibles: semanal · mensual)"
  }
  exit 0
fi

DIR="05 Diario/Auditorías"
[ -d "$DIR" ] || exit 0

# Rutinas conocidas: clave | etiqueta | prefijo del informe | gracia | cadencia
#
# Los días de gracia son "una corrida entera perdida + margen", no "un día tarde":
# la rutina semanal corre cada 7 → a los 10 días seguro se saltó una. La mensual
# corre cada ~30 → a los 40 seguro se saltó una. Umbral flojo a propósito: un
# falso positivo acá cuesta credibilidad, y un monitor al que no le creés no sirve.
ROUTINES="
semanal|Mantenimiento semanal|Informe Mantenimiento|10|semanal (domingos 18:00 ART)
mensual|Revisión mensual|Revisión Mensual|40|mensual (día 26, 09:00 ART)
"

today_s="$(date +%s 2>/dev/null)" || exit 0
problems=""
oks=""

while IFS='|' read -r key label prefix grace cadence; do
  [ -z "${key:-}" ] && continue
  # Solo las declaradas en vault.conf. Coma-delimitado, con bordes para que
  # «mensual» no matchee dentro de otra clave más larga.
  case ",${EXPECTED}," in *",${key},"*) : ;; *) continue ;; esac

  # Informe más reciente POR FECHA DEL NOMBRE (no por mtime: ver cabecera).
  last_date="$(ls -1 "$DIR/$prefix - "*.md 2>/dev/null \
    | sed -n 's/.*\([0-9]\{4\}-[0-9]\{2\}-[0-9]\{2\}\)\.md$/\1/p' \
    | sort | tail -1)"

  if [ -z "$last_date" ]; then
    problems="${problems}  🔴 ${label}: NUNCA corrió (no hay ningún «${prefix} - <fecha>.md» en «${DIR}»).\n"
    continue
  fi

  last_s="$(date -d "$last_date" +%s 2>/dev/null)" || continue
  [ -z "$last_s" ] && continue
  days=$(( (today_s - last_s) / 86400 ))

  if [ "$days" -gt "$grace" ]; then
    problems="${problems}  🔴 ${label}: último informe hace ${days} días (${last_date}); esperado ${cadence}.\n"
  else
    oks="${oks}  ✅ ${label}: al día (${last_date}, hace ${days} días).\n"
  fi
done <<< "$ROUTINES"

if [ -n "$problems" ]; then
  echo "⚠ MONITOR DE RUTINAS — hay rutinas cloud vencidas:"
  printf "%b" "$problems"
  echo "  → Diagnóstico rápido (incidente 2026-07-16): revisá https://github.com/settings/installations"
  echo "    y confirmá que la GitHub App «Claude» siga instalada con acceso al repo. El panel de"
  echo "    rutinas puede decir «activa» y estar rota igual. Detalle en «04 Knowledge/Automatización/Rutinas Programadas.md»."
  [ "$SHOW_ALL" -eq 1 ] && [ -n "$oks" ] && printf "%b" "$oks"
  echo "  (Silenciar: .vault-meta/routines-monitor.disabled)"
elif [ "$SHOW_ALL" -eq 1 ]; then
  echo "Monitor de rutinas: todas al día."
  printf "%b" "$oks"
fi

exit 0
