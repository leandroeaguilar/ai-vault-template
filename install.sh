#!/usr/bin/env bash
# Instalador de la plantilla. Correr desde la raiz del repo donde la usas.
#
# Idempotente: correrlo dos veces no rompe nada. Y es REANUDABLE: si todavia no
# completaste owner.env, deja el archivo listo y sale; volves a correrlo y sigue
# desde ahi. Por eso la instalacion son dos comandos y no seis pasos manuales.
#
# Este script corre en DOS contextos distintos y tiene que distinguirlos:
#   - el checkout del MANTENEDOR del template (origin ES el template);
#   - el clon de quien INSTALA (origin es su propio fork).
# Ver el bloque del remote upstream, mas abajo.
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

# ── Remote upstream: el canal por el que llegan las actualizaciones ──────────
# update.sh y update-notice.sh lo EXIGEN. Que no lo cableara este script era el
# agujero del procedimiento: update.sh abortaba diciendo "corre ./install.sh",
# que es justo lo que no lo agregaba.
#
# La URL se declara UNA sola vez, en vault-manifest.json, y se lee de ahi.
# Hardcodearla aca —ademas del regex de familia de .githooks/pre-push— repetiria
# el incidente de la v0.3.0: el repo se renombro, nadie actualizo el nombre
# hardcodeado y el guard quedo como codigo muerto un release entero. El regex de
# pre-push se queda donde esta porque es otra cosa: tiene que seguir matcheando
# los nombres VIEJOS de la familia, no la URL canonica de hoy.
TEMPLATE_URL="$(sed -n 's/.*"upstream"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p' vault-manifest.json 2>/dev/null | head -1)"
FAMILIA='ai-vault-template|sistema-maestro-(pro|template|toolkit)'
ORIGIN_URL="$(git remote get-url origin 2>/dev/null || echo '')"

# ¿En cual de los dos contextos estamos? Una sola señal decide, y es la misma
# que usa .githooks/pre-push: si origin apunta a la familia del template, este
# checkout NO es la instancia de nadie. O sos el mantenedor, o clonaste en vez
# de forkear. Abajo se usa dos veces: para el remote y para la identidad.
ES_TEMPLATE=0
if printf '%s' "$ORIGIN_URL" | grep -qE "$FAMILIA"; then ES_TEMPLATE=1; fi

if git remote get-url upstream >/dev/null 2>&1; then
  echo "✓ remote upstream ya configurado"
elif [ "$ES_TEMPLATE" = "1" ]; then
  # Agregar un upstream que apunta al mismo lugar que origin no sirve de nada.
  echo "⚠ origin apunta al TEMPLATE ($ORIGIN_URL) — no se agrega upstream."
elif [ -z "$TEMPLATE_URL" ]; then
  echo "⚠ no se pudo leer \"upstream\" de vault-manifest.json. Agregalo a mano:"
  echo "    git remote add upstream <url-del-template>"
else
  git remote add upstream "$TEMPLATE_URL"
  echo "✓ remote upstream -> $TEMPLATE_URL (./update.sh ya puede correr)"
fi

# ── Identidad: owner.env + resolucion de placeholders ───────────────────────
# Once archivos .md se publican con el placeholder de owner literal. Sin este
# paso quedan sin resolver el frontmatter de las plantillas y el prompt de las
# skills. Por eso el instalador lo encadena en vez de confiar en que lo leas.
#
# Con origin apuntando al template, este paso NO corre, y es deliberado:
#   - En el checkout del MANTENEDOR, crear owner.env seria destructivo: es
#     justamente su ausencia lo que .githooks/pre-push usa para reconocerlo.
#     Con owner.env presente, el mantenedor se bloquearia sus propios push.
#   - Y a quien CLONO en vez de forkear le conviene arreglar origin ANTES de
#     personalizar: si personaliza primero, se lleva la sorpresa en el push.
if [ "$ES_TEMPLATE" = "1" ]; then
  cat <<'MSG'

→ No se personaliza nada: origin apunta al template.

   Si este vault es TUYO, re-apuntá origin y volvé a correr este script:
     git remote set-url origin https://github.com/<vos>/<tu-vault>.git
     ./install.sh

   (Si sos el mantenedor del template, está bien así: terminó acá.)
MSG
  exit 0
fi

if [ ! -f owner.env ]; then
  cp owner.env.example owner.env
  cat <<'MSG'

→ Falta un paso, y es tuyo: completá owner.env (OWNER, OWNER_EMAIL, OWNER_GITHUB).

   Ya te dejé el archivo creado a partir del ejemplo. Cuando lo llenes:

     ./install.sh          # retoma desde acá y resuelve los placeholders

   ¿Preferís que te lo pregunte un agente y de paso llene tu 01 Index?
   Abrí esta carpeta con Claude Code y pedí:  /onboarding
MSG
  exit 0
fi

bash ./personalize.sh

# La instancia ya esta inicializada: el cartel de primera vez sobra.
# if/then y no `[ -f x ] && rm x`: con `set -e`, esa lista devuelve 1 cuando la
# condicion es falsa y aborta el script justo en el caso normal.
if [ -f FIRST_RUN.md ]; then
  rm -f FIRST_RUN.md
  echo "✓ FIRST_RUN.md borrado (instancia inicializada)"
  echo ""
  echo "→ Queda una cosa, y no la puede hacer un script: los tres stubs de"
  echo "  '01 Index/' (Vision, Objetivos, Mapa Personal) siguen en 🟡 Borrador."
  echo "  Llenalos a mano, o pedí /onboarding a un agente en esta carpeta."
fi

echo ""
echo "Probá que la guarda de secretos bloquea de verdad:"
echo "  printf 'AWS_SECRET_ACCESS_KEY=%s%s\\n' AKIA 0000000000000000 > fuga.txt"
echo "  git add -f fuga.txt && git commit -m prueba    # debe FALLAR"
echo "  git reset && rm fuga.txt"
echo ""
echo "(La clave de prueba se arma en runtime a proposito: si fuera literal, el"
echo " propio secret-scan bloquearia el commit de este repositorio.)"
