#!/usr/bin/env bash
# Stop hook — Agent Diary. Si hubo trabajo sobre el vault esta sesión, hace que el
# agente registre una entrada de bitácora ANTES de terminar (contexto para el próximo).
#
# Mecánica (patrón de obsidian-mind / claude-obsidian, sin node y sin jq):
#   - Guard anti-loop: si el modelo ya reentró por el Stop (stop_hook_active=true),
#     limpia la marca y permite terminar.
#   - Dispara solo si existe la marca .vault-meta/session-touched (la deja auto-commit.sh
#     cuando se escribe contenido del vault).
#   - DEDUPE POR SESIÓN (v2, 2026-07-05): bloquea UNA sola vez por session_id (stamp
#     .vault-meta/diary-done-<sid>). Antes bloqueaba en cada cierre de turno con ediciones
#     → un turno extra del modelo por turno de trabajo (caro en conversaciones largas).
#     Si el agente sigue trabajando tras registrar, la convención es AMPLIAR su entrada
#     (voluntario, sin bloqueo). Stamps viejos (>7 días) se limpian solos.
#   - Salida JSON estática {"decision":"block","reason":...} → el modelo continúa,
#     escribe la entrada y luego termina (segunda pasada = stop_hook_active).
#   - Kill-switch: .vault-meta/diary.disabled
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"

# Nombre del dueño para los mensajes. No sirve el placeholder {{OWNER}}: personalize.sh
# solo reescribe *.md y *.txt, asi que en un .sh quedaria literal para siempre. Se lee
# del archivo de identidad (gitignorado) en tiempo de ejecucion, con fallback neutro.
OWNER_NAME="quien opera el vault"
if [ -f "$ROOT/owner.env" ]; then
  _n="$(sed -n 's/^OWNER=//p' "$ROOT/owner.env" | head -1 | tr -d '\"' )"
  [ -n "${_n:-}" ] && OWNER_NAME="$_n"
fi
cd "$ROOT" 2>/dev/null || exit 0

INPUT="$(cat)"

# Guard anti-loop: segunda pasada → limpiar marca y salir.
case "$INPUT" in
  *'"stop_hook_active":true'*|*'"stop_hook_active": true'*)
    rm -f .vault-meta/session-touched 2>/dev/null || true
    exit 0 ;;
esac

# Kill-switch.
[ -f .vault-meta/diary.disabled ] && exit 0

# ¿Hubo trabajo en el vault esta sesión?
[ -f .vault-meta/session-touched ] || exit 0

# Dedupe por sesión: si esta sesión ya registró bitácora, no volver a bloquear.
SID="$(printf '%s' "$INPUT" | sed -n 's/.*"session_id"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' | head -1)"
[ -n "$SID" ] || SID="dia-$(date +%Y-%m-%d)"
STAMP=".vault-meta/diary-done-${SID}"
[ -f "$STAMP" ] && exit 0
mkdir -p .vault-meta 2>/dev/null || true
: > "$STAMP" 2>/dev/null || true
find .vault-meta -maxdepth 1 -name 'diary-done-*' -mtime +7 -delete 2>/dev/null || true

MONTH="$(date +%Y-%m)"
DAY="$(date +%Y-%m-%d)"

# Tope de consolidación: si el mes vigente se pasó de largo, el aviso suma la
# instrucción de PROPONER una consolidación. Se pide acá y no en otro lado porque
# este es el único momento en que el agente ya está con la bitácora en la mano.
# El fragmento va sin comillas dobles ni backslashes: se inyecta en un string JSON.
CAP_MSG=""
case "$(bash "$ROOT/.claude/hooks/check-diary-size.sh" --level 2>/dev/null || echo OK)" in
  SOFT) CAP_MSG='\n\nNOTA DE TAMAÑO: la bitácora de este mes va larga. Al escribir, sé breve y no repitas lo que ya está en entradas previas.' ;;
  HARD) CAP_MSG='\n\n⚠ TOPE DE CONSOLIDACIÓN ALCANZADO: la bitácora de este mes superó el techo (corré «bash .claude/hooks/check-diary-size.sh» para ver los números). Además de tu entrada, PROPONÉ a '"$OWNER_NAME"' una consolidación del mes: sintetizar las entradas viejas en aprendizajes duraderos, dejar VERBATIM las últimas (el handoff vivo) y mover a su nota lo que sea conocimiento reutilizable. NO consolides por tu cuenta: proponé y esperá su decisión.' ;;
esac

printf '{"decision":"block","reason":"[AGENT DIARY] Se trabajó sobre el vault esta sesión. Antes de terminar, registrá UNA entrada en la bitácora \\"05 Diario/Bitácora Agentes/%s.md\\" (creá el archivo y la carpeta si no existen) con este formato exacto:\\n\\n## %s — <tu agente, ej. Claude Code>\\n- Qué se avanzó/creó/editó:\\n- Qué quedó bloqueado:\\n- Qué se decidió o cambió:\\n- Qué debe saber el próximo agente:\\n\\nTRES REGLAS (el hook de sesión inyecta la ÚLTIMA entrada del archivo):\\n1. Agregá tu entrada AL FINAL del archivo (la más reciente SIEMPRE abajo).\\n2. En \\"Qué debe saber\\", el siguiente paso apuntá a tu lista viva de pendientes (roadmap, backlog), NO congeles un paso concreto.\\n3. UNA entrada por sesión: este aviso no se repite; si seguís trabajando después de registrarla, AMPLIÁ tu propia entrada (no crees otra).\\n\\nDespués terminá normalmente. (Para desactivar esta bitácora: crear el archivo .vault-meta/diary.disabled)%s"}' "$MONTH" "$DAY" "$CAP_MSG"
exit 0
