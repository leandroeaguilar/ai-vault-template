#!/usr/bin/env python3
"""search-sessions.py — buscador sobre los transcripts de sesiones pasadas.

EL PROBLEMA QUE RESUELVE: `pre-compact.sh` viene guardando conversaciones enteras
en `.vault-meta/session-logs/*.jsonl` y **nunca las consultó nadie**. El dato
estaba y el buscador no. El Agent Diary tampoco lo cubre: `session-context.sh`
inyecta SOLO la última entrada, y la bitácora es un resumen escrito a mano — sirve
para el handoff, no para "¿qué decidimos exactamente sobre X hace tres semanas?".

QUÉ ES Y QUÉ NO ES:
  - ES: grep con estructura. Sabe qué es un turno, de quién, cuándo, y sabe que
    dos archivos pueden ser dos fotos de la MISMA sesión (dedupe por sessionId).
  - NO ES: búsqueda semántica. Busca por palabra, igual que el `bibliotecario`.
    Si algún día entra el RAG del Roadmap, este es el corpus obvio a indexar.

Se eligió escaneo directo en vez de un índice (SQLite FTS5, que es lo que usa
Hermes) porque el corpus son unos pocos MB y el escaneo tarda menos que mantener
el índice sincronizado. La regla del vault es "simplicidad antes que complejidad";
si el corpus crece a cientos de sesiones, acá es donde entra FTS5.

DOS FUENTES, Y EL PORQUÉ DE CADA UNA:

  1. LOCAL — `.vault-meta/session-logs/` (o `.repo-meta/` en repos de código), que
     llena `pre-compact.sh`. Es **nuestra**: nosotros controlamos la ruta, el
     formato y la retención, y no depende de qué harness se use. Pero solo captura
     **al compactar**, así que una sesión que nunca compactó no deja rastro.
  2. HARNESS — `~/.claude/projects/<proyecto>/`, donde Claude Code guarda **todas**
     las sesiones por su cuenta, una por archivo, sin que nadie configure nada.
     Mismo formato JSONL. Es la fuente completa.

La diferencia no es teórica: medido el 2026-08-08 en el vault, la local tenía **2**
sesiones y la del harness **52**.

Se leen LAS DOS y se deduplica por `sessionId`. Por qué no solo la del harness, que
es la completa: es una ruta **interna y no documentada** del harness, específica de
Claude Code — puede cambiar de versión y no existe en Codex/Hermes. La local es el
ancla portable. Si la del harness desaparece, esto sigue funcionando con menos
corpus en vez de romperse.

⚠️ Lo que NINGUNA de las dos da: sesiones de otras personas o de otra máquina. Y la
retención del harness no la controlamos (poda cuando quiere). `--list` te dice
exactamente qué hay: usalo antes de concluir que algo "no existe".

Uso:
  python search-sessions.py --list              # inventario: qué sesiones hay
  python search-sessions.py "graphify"          # buscar en todo
  python search-sessions.py "OKF" --role user   # solo lo que pidió el humano
  python search-sessions.py "verif.*commit" --regex --full
  CLAUDE_PROJECTS_DIR=/otra/ruta python search-sessions.py --list   # override
"""
import argparse
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

# Windows: la consola suele ser cp1252 y los transcripts son UTF-8.
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))


def local_dirs():
    """Los backups que deja `pre-compact.sh`. Se aceptan los dos nombres para que
    este script sea UNO SOLO y sirva igual en el vault (`.vault-meta/`) y en un
    repo de código (`.repo-meta/`) — dos copias divergirían con el tiempo."""
    return [d for d in (ROOT / ".vault-meta" / "session-logs",
                        ROOT / ".repo-meta" / "session-logs") if d.is_dir()]


def harness_dir():
    """Dónde Claude Code guarda las sesiones de ESTE proyecto.

    El nombre de la carpeta es la ruta absoluta con ':' y separadores vueltos '-'
    (C:\\Users\\x\\vault → C--Users-x-vault). Como es una convención interna del
    harness y no un contrato, no se confía solo en armar el nombre: si no está, se
    buscan todas las carpetas de proyecto y se elige la que declare este mismo
    `cwd` adentro. Si tampoco, se devuelve None y el buscador sigue con la local."""
    override = os.environ.get("CLAUDE_PROJECTS_DIR")
    base = Path(override) if override else Path.home() / ".claude" / "projects"
    if not base.is_dir():
        return None

    root_abs = str(ROOT.resolve())
    guess = base / re.sub(r"[:\\/]", "-", root_abs)
    if guess.is_dir():
        return guess

    # Fallback: preguntarle a los datos en vez de adivinar el nombre.
    target = root_abs.replace("/", "\\").lower()
    for cand in base.iterdir():
        if not cand.is_dir():
            continue
        for f in sorted(cand.glob("*.jsonl"))[:1]:
            try:
                with f.open(encoding="utf-8", errors="replace") as fh:
                    for line in fh:
                        cwd = (json.loads(line).get("cwd") or "") if line.strip() else ""
                        if cwd and cwd.replace("/", "\\").lower() == target:
                            return cand
                        if cwd:
                            break
            except (OSError, json.JSONDecodeError, ValueError):
                continue
    return None

# Ruido del harness: turnos que no son conversación real y ensucian los resultados.
NOISE = re.compile(
    r"^\s*<(local-command-caveat|command-name|command-message|command-args"
    r"|system-reminder|local-command-stdout)>",
    re.I,
)


def fold(s: str) -> str:
    """Minúsculas y sin acentos: 'Revisión' matchea 'revision' y viceversa."""
    return "".join(
        c for c in unicodedata.normalize("NFD", s.lower())
        if not unicodedata.combining(c)
    )


def blocks_to_text(content) -> str:
    """El campo `content` es str en los turnos simples y lista de bloques en los
    ricos. Se aplanan solo los bloques con texto humano/del agente; los
    `tool_result` se omiten (son volcados de archivos: ruido puro para buscar)."""
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    out = []
    for b in content:
        if not isinstance(b, dict):
            continue
        t = b.get("type")
        if t in ("text", "thinking"):
            out.append(b.get(t) or b.get("text") or "")
        elif t == "tool_use":
            # El nombre de la herramienta sí sirve ("¿en qué sesión corrí graphify?").
            out.append(f"[tool:{b.get('name', '?')}]")
    return "\n".join(x for x in out if x)


def load_sessions():
    """Devuelve {session_id: {...}} quedándose con la foto MÁS COMPLETA de cada
    sesión. Dos snapshots de una sesión larga son el mismo hilo capturado dos
    veces —y ahora, además, la misma sesión puede venir por las DOS fuentes—:
    contarlas por separado inflaría el inventario y duplicaría cada resultado."""
    sessions = {}

    # (etiqueta, archivos). La local va primero para que, ante empate exacto de
    # tamaño, gane la fuente que controlamos nosotros.
    fuentes = []
    for d in local_dirs():
        fuentes.append(("local", sorted(d.glob("session_*.jsonl"))))
    hd = harness_dir()
    if hd:
        fuentes.append(("harness", sorted(hd.glob("*.jsonl"))))

    for src, files in fuentes:
        for f in files:
            turns, sid, first_ts, last_ts = [], None, None, None
            try:
                fh = f.open(encoding="utf-8", errors="replace")
            except OSError:
                continue
            with fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        o = json.loads(line)
                    except (json.JSONDecodeError, ValueError):
                        continue
                    sid = o.get("sessionId") or sid
                    typ = o.get("type")
                    if typ not in ("user", "assistant"):
                        continue
                    if o.get("isMeta"):
                        continue
                    text = blocks_to_text((o.get("message") or {}).get("content"))
                    if not text.strip() or NOISE.match(text):
                        continue
                    ts = o.get("timestamp") or ""
                    if ts:
                        first_ts = first_ts or ts
                        last_ts = ts
                    turns.append({"role": typ, "ts": ts, "text": text})

            if not turns:
                continue
            key = sid or f.name
            prev = sessions.get(key)
            # Se queda la foto con más turnos. Cubre los dos casos de duplicado:
            # dos snapshots de una misma sesión larga, y la misma sesión llegando
            # por la fuente local y por la del harness.
            if prev is None or len(turns) > len(prev["turns"]):
                sessions[key] = {
                    "id": key, "file": f.name, "turns": turns, "src": src,
                    "first": first_ts or "", "last": last_ts or "",
                }
    return sessions


def snippet(text: str, span, width: int) -> str:
    a, b = span
    start, end = max(0, a - width // 2), min(len(text), b + width // 2)
    s = text[start:end].replace("\n", " ⏎ ")
    s = re.sub(r"\s+", " ", s).strip()
    return ("…" if start > 0 else "") + s + ("…" if end < len(text) else "")


def main():
    p = argparse.ArgumentParser(
        description="Busca en los transcripts de sesiones pasadas del vault.")
    p.add_argument("query", nargs="?", help="texto a buscar (sin acentos, da igual)")
    p.add_argument("--list", action="store_true", help="inventario de sesiones guardadas")
    p.add_argument("--regex", action="store_true", help="tratar la consulta como regex")
    p.add_argument("--role", choices=["user", "assistant", "all"], default="all")
    p.add_argument("--context", type=int, default=200, help="ancho del extracto (def 200)")
    p.add_argument("--limit", type=int, default=40, help="máximo de coincidencias (def 40)")
    p.add_argument("--full", action="store_true", help="imprimir el turno entero")
    args = p.parse_args()

    sessions = load_sessions()
    if not sessions:
        print("No se encontró ningún transcript de este proyecto.")
        print(f"  · local   : {[str(d) for d in local_dirs()] or 'no existe'}")
        print(f"  · harness : {harness_dir() or 'no encontrado'}")
        print("La local la llena `pre-compact.sh` y SOLO al compactar; la del harness")
        print("la escribe Claude Code sola. Si las dos están vacías, no hay historia que buscar.")
        return 1

    ordered = sorted(sessions.values(), key=lambda s: s["first"])

    if args.list or not args.query:
        total = sum(len(s["turns"]) for s in ordered)
        n_loc = sum(1 for s in ordered if s["src"] == "local")
        n_har = len(ordered) - n_loc
        print(f"{len(ordered)} sesión(es) · {total} turnos "
              f"({n_loc} de la copia local, {n_har} del harness)\n")
        for s in ordered:
            day = (s["first"] or "?")[:10]
            hi = (s["first"] or "")[11:16]
            hf = (s["last"] or "")[11:16]
            nu = sum(1 for t in s["turns"] if t["role"] == "user")
            tag = "local  " if s["src"] == "local" else "harness"
            print(f"  {day} {hi}–{hf} · {len(s['turns']):4d} turnos ({nu} del humano) · [{tag}]")
            first_user = next((t["text"] for t in s["turns"] if t["role"] == "user"), "")
            if first_user:
                print(f"      ↳ arranque: {snippet(first_user, (0, 0), 150)}")
        if not args.query:
            print("\n(Pasá un texto para buscar: python search-sessions.py \"graphify\")")
        return 0

    try:
        pat = re.compile(args.query if args.regex else re.escape(fold(args.query)))
    except re.error as e:
        print(f"Regex inválida: {e}", file=sys.stderr)
        return 2

    hits = shown = 0
    for s in ordered:
        header_done = False
        for t in s["turns"]:
            if args.role != "all" and t["role"] != args.role:
                continue
            hay = t["text"] if args.regex else fold(t["text"])
            for m in pat.finditer(hay):
                hits += 1
                if shown >= args.limit:
                    continue
                shown += 1
                if not header_done:
                    print(f"\n━━ {(s['first'] or '?')[:10]} · [{s['src']}] {s['file']}")
                    header_done = True
                who = "👤 humano" if t["role"] == "user" else "🤖 agente"
                print(f"  [{(t['ts'] or '')[11:16]}] {who}:")
                if args.full:
                    print("    " + t["text"].replace("\n", "\n    "))
                else:
                    print("    " + snippet(t["text"], m.span(), args.context))
                break  # una coincidencia por turno: alcanza para ubicarlo

    if not hits:
        print(f"Sin coincidencias para «{args.query}» en {len(ordered)} sesión(es).")
        print("Ojo: solo se ven sesiones de ESTA máquina y este usuario, y el harness")
        print("poda las suyas cuando quiere. Mirá `--list` para saber qué hay de verdad.")
        return 1
    print(f"\n{hits} coincidencia(s)" + (f", mostrando {shown}." if hits > shown else "."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
