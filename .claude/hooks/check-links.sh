#!/usr/bin/env bash
# check-links.sh — chequeador de integridad de enlaces del vault (Gap 2a).
#
# Escanea todos los .md, extrae los [[wikilinks]] (incluidos embeds ![[...]])
# Y TAMBIÉN los links markdown [txt](<ruta>) a notas, y reporta los que apuntan
# a un archivo inexistente. Resolución al estilo Obsidian: por basename (sin
# importar carpeta) o por ruta relativa, sin distinguir mayúsculas, y **honrando
# los `aliases:` del frontmatter** (un [[Alias]] que resuelve vía alias NO está
# roto). Reconoce alias `[[Nota|alias]]`, secciones `[[Nota#Título]]`, bloques
# `[[Nota#^id]]`, pipes escapados de tabla `\|`, y omite código en bloque/inline.
# Links markdown: destino con `/` se resuelve como ruta relativa al archivo
# (normaliza ./ y ../); destino de nombre pelado, por nombre (como un wikilink).
# Solo se chequean destinos .md o sin extensión (los assets png/pdf/… se saltan).
# El tipo de cada roto se marca en la 4ª columna del --tsv: `wiki` | `md`.
#
# Diseño: UN SOLO pase de awk para el índice+escaneo (más un pase liviano de
# extracción de aliases), para no spawnear subprocesos por archivo/token — clave
# en Git Bash, donde eso es lentísimo. No usa extensiones de gawk. Sin jq, sin
# node. La carpeta de plantillas se excluye del escaneo (sus links son
# placeholders intencionales), pero sus archivos siguen siendo destinos válidos.
#
# Uso:
#   check-links.sh            -> enlaces rotos agrupados por archivo + resumen
#   check-links.sh --quiet    -> solo el resumen
#   check-links.sh --tsv      -> una línea 'archivo<TAB>línea<TAB>texto_del_link'
#                                por roto, machine-readable (la consume
#                                heal-links.py). Sin resumen ni encabezados.
# Salida: 0 siempre (auditoría; no bloquea).
set -uo pipefail

ROOT="${CLAUDE_PROJECT_DIR:-$PWD}"
cd "$ROOT" 2>/dev/null || exit 0
MODE=pretty
case "${1:-}" in
  --quiet) MODE=quiet ;;
  --tsv)   MODE=tsv ;;
esac

PRUNE='-path ./.git -o -path ./.obsidian -o -path ./.claude -o -path ./.vault-meta -o -path ./node_modules'
PLANTILLAS='./00 Sistema/001_plantillas'

ALL="$(mktemp)"; MDS="$(mktemp)"; ALIAS="$(mktemp)"; BRK="$(mktemp)"
eval "find . \\( $PRUNE \\) -prune -o -type f -print"            > "$ALL"
eval "find . \\( $PRUNE -o -path '$PLANTILLAS' \\) -prune -o -type f -name '*.md' -print" > "$MDS"
mapfile -t MDARR < "$MDS"

# --- Aliases del frontmatter (destinos válidos adicionales) ---
# Emite un alias en minúsculas por línea. Soporta las tres formas YAML:
#   aliases: [Uno, Dos]   ·   aliases: Uno   ·   aliases:\n  - Uno\n  - Dos
# El frontmatter solo cuenta si la 1ª línea del archivo es '---'.
if [ "${#MDARR[@]}" -gt 0 ]; then
  awk '
    function trim(s){ gsub(/^[ \t"]+|[ \t"]+$/,"",s); return s }
    FNR==1 { fm=0; done=0; inal=0; if ($0=="---") fm=1; else done=1; next }
    done { next }
    fm && $0=="---" { done=1; next }
    fm {
      if (match($0, /^[ \t]*aliases:[ \t]*\[/)) {
        s=$0; sub(/^[^[]*\[/,"",s); sub(/\].*/,"",s)
        n=split(s,a,","); for(i=1;i<=n;i++){ v=trim(a[i]); if(v!="") print tolower(v) }
        inal=0; next
      }
      if (match($0, /^[ \t]*aliases:[ \t]*$/)) { inal=1; next }
      if (match($0, /^[ \t]*aliases:[ \t]*[^ \t]/)) {
        s=$0; sub(/^[ \t]*aliases:[ \t]*/,"",s); v=trim(s)
        if (v!="" && v!="[]") print tolower(v); inal=0; next
      }
      if (inal && match($0, /^[ \t]*-[ \t]*/)) {
        s=$0; sub(/^[ \t]*-[ \t]*/,"",s); v=trim(s); if(v!="") print tolower(v); next
      }
      if (inal && match($0, /^[^ \t-]/)) { inal=0 }
    }
  ' "${MDARR[@]}" > "$ALIAS"
fi

# --- Índice de destinos + escaneo de enlaces (un solo pase de awk) ---
# Entradas: ALL (rutas) y ALIAS (aliases) construyen el índice; luego se escanea
# cada .md. Se distingue la fase por FILENAME (sin extensiones de gawk).
SUMMARY="$(awk -v out="$BRK" -v allf="$ALL" -v aliasf="$ALIAS" '
  function noext(s){ if (match(s, /\.[^.\/]+$/)) return substr(s,1,RSTART-1); return s }
  function add(s){ if (s!="") have[tolower(s)]=1 }
  # normaliza un target relativo (con ./ y ../) al path desde la raíz del vault
  function normpath(dir, t,   base, parts, n, i, comp, k, out2, s2) {
    if (substr(t,1,1)=="/") base=substr(t,2)          # root-relative
    else base=(dir=="" ? t : dir "/" t)
    n=split(base, parts, "/"); k=0
    for(i=1;i<=n;i++){ comp=parts[i]
      if(comp=="."||comp=="") continue
      if(comp==".."){ if(k>0) k--; continue }
      k++; out2[k]=comp }
    s2=""; for(i=1;i<=k;i++) s2=(i==1?out2[i]:s2 "/" out2[i])
    return s2
  }
  FILENAME==allf {
    p=$0; sub(/^\.\//,"",p)
    n=split(p,a,"/"); base=a[n]
    add(base); add(noext(base)); add(p); add(noext(p))
    next
  }
  FILENAME==aliasf { add($0); next }
  FNR==1 { infence=0                                  # dir del archivo actual (para rutas md)
    f=FILENAME; sub(/^\.\//,"",f); nf=split(f,fa,"/"); fdir=""
    for(i=1;i<nf;i++) fdir=(i==1?fa[i]:fdir "/" fa[i])
  }
  {
    line=$0
    if (line ~ /^[ \t]*(```|~~~)/) { infence=!infence; next }
    if (infence) next
    gsub(/`[^`]*`/, "", line)
    f=FILENAME; sub(/^\.\//,"",f)
    # --- wikilinks [[...]] ---
    s=line
    while (match(s, /\[\[[^]]*\]\]/)) {
      tok=substr(s, RSTART+2, RLENGTH-4)
      s=substr(s, RSTART+RLENGTH)
      total++
      gsub(/\\\|/, "|", tok)        # pipe escapado de tabla -> pipe real
      raw=tok                        # texto del link tal cual (con alias/sección)
      sub(/\|.*/, "", tok)          # alias
      sub(/#.*/, "", tok)           # sección/bloque
      gsub(/^[ \t]+|[ \t]+$/, "", tok)
      if (tok=="") continue
      if (tok ~ /^https?:\/\//) continue
      key=tolower(tok); gsub(/\\/, "/", key)
      if (!(key in have)) { broken++; print f "\t" FNR "\t" tok "\t" raw "\twiki" > out }
    }
    # --- links markdown [txt](target) — solo destinos .md o sin extensión (notas) ---
    s=line
    while (match(s, /\]\(<[^>]*>\)|\]\([^)]*\)/)) {   # angular primero (permite ( ) en el nombre)
      mfull=substr(s, RSTART, RLENGTH)
      s=substr(s, RSTART+RLENGTH)
      mdraw=substr(mfull, 3, length(mfull)-3)   # contenido entre ]( y )
      t=mdraw
      if (substr(t,1,1)=="<" && substr(t,length(t),1)==">") t=substr(t,2,length(t)-2)  # corchetes angulares
      gsub(/%20/, " ", t)                    # decodificar espacios
      sub(/#.*/, "", t)                      # anchor de sección
      gsub(/^[ \t]+|[ \t]+$/, "", t)
      if (t=="") continue
      if (t ~ /^[a-zA-Z][a-zA-Z0-9+.-]*:\/\//) continue   # esquema:// (http, etc.)
      if (t ~ /^mailto:/) continue
      ext=""; if (match(t, /\.[^.\/]+$/)) ext=tolower(substr(t, RSTART+1))
      if (ext!="" && ext!="md") continue     # saltar assets (png, pdf, xlsx…)
      total++
      if (t ~ /\//) key=tolower(normpath(fdir, t))   # ruta -> resolver relativa al archivo
      else key=tolower(t)                            # nombre pelado -> por nombre (Obsidian)
      if (!(key in have) && !(noext(key) in have)) {
        broken++; print f "\t" FNR "\t" t "\t" mdraw "\tmd" > out
      }
    }
  }
  END { printf "check-links: %d enlace(s) roto(s) de %d revisados.", broken+0, total+0 }
' "$ALL" "$ALIAS" "${MDARR[@]}")"

case "$MODE" in
  pretty)
    if [ -s "$BRK" ]; then
      echo "Enlaces rotos (destino inexistente):"
      sort "$BRK" | awk -F'\t' '{ if($1!=p){print "";print $1;p=$1}
        if($5=="md") printf "  L%-5s [..](%s)\n",$2,$4
        else printf "  L%-5s [[%s]]\n",$2,$3 }'
      echo
    fi
    echo "$SUMMARY"
    ;;
  quiet)
    echo "$SUMMARY"
    ;;
  tsv)
    # archivo <TAB> línea <TAB> texto_del_link (raw) <TAB> kind (wiki|md)
    [ -s "$BRK" ] && sort "$BRK" | cut -f1,2,4,5
    ;;
esac

rm -f "$ALL" "$MDS" "$ALIAS" "$BRK" 2>/dev/null || true
