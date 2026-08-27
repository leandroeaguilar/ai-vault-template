#!/usr/bin/env python3
"""heal-links.py — propone (y opcionalmente aplica) el saneo de enlaces rotos.

Filosofía (adaptada de obsidian-second-brain `heal_links.py`/`triage_links.py`
a las reglas del vault: "proponer, nunca decidir solo" · "nunca borrar"):

  - Detección: NO reimplementa nada. Corre `check-links.sh --tsv`, así su
    conteo es idéntico al del chequeador (una sola fuente de verdad). Maneja
    ambos tipos que reporta el checker (columna `kind`): wikilinks `[[..]]` y
    links markdown `[txt](<..>)`; el repunte md va a nombre pelado `](<Nuevo.md>)`.
  - Clasifica cada roto, sin IA, por parecido de nombre (difflib):
      · repunte seguro : existe EXACTAMENTE una nota muy parecida  -> se sugiere
      · ambiguo        : dos o más notas parecidas                 -> decidí vos
      · sin destino    : ninguna nota parecida (concepto planificado o typo)
                         -> crear la nota o quitar el enlace (decisión de contenido)
  - Por defecto SOLO PROPONE (no toca ningún archivo). El repunte lo aplica un
    humano/agente tras revisar. `--apply` existe para corridas acotadas: aplica
    solo repuntes seguros, hasta --max, recontando cada pase (bucle cerrado) y
    frenando si el conteo no baja. Nunca toca placeholders ({}*<>) ni plantillas.

Uso:
  python heal-links.py                  # propone (dry-run) — no cambia nada
  python heal-links.py --apply --max 15 # aplica hasta 15 repuntes seguros, solo
"""
import argparse
import os
import subprocess
import sys
from collections import defaultdict
from difflib import get_close_matches
from pathlib import Path

# Windows: la consola suele ser cp1252 y el vault es todo UTF-8 (acentos, ñ, box-drawing).
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

ROOT = Path(os.environ.get("CLAUDE_PROJECT_DIR", os.getcwd()))
PRUNE = {".git", ".obsidian", ".claude", ".vault-meta", "node_modules"}
PLACEHOLDER = set("*{}<>")
CUTOFF = 0.90          # umbral de parecido. El prior art usa 0.84, pero en este
                       # vault eso colisiona por semántica ("prompts del sistema"
                       # vs "roadmap del sistema"): 0.90 solo agarra typos/renames.


def is_target_candidate(rel_parts) -> bool:
    """¿Este .md puede ser destino de un repunte? (no pruned, no plantilla)."""
    if any(part in PRUNE for part in rel_parts):
        return False
    if "001_plantillas" in rel_parts:
        return False
    return True


def build_index():
    """{stem_en_minúscula: stem_para_mostrar} de las notas reales del vault."""
    idx = {}
    for p in ROOT.rglob("*.md"):
        rel = p.relative_to(ROOT).parts
        if not is_target_candidate(rel):
            continue
        idx.setdefault(p.stem.lower(), p.stem)
    return idx


def get_broken():
    """Corre check-links.sh --tsv -> lista de (archivo, línea, texto_del_link)."""
    script = ROOT / ".claude" / "hooks" / "check-links.sh"
    try:
        res = subprocess.run(
            ["bash", str(script), "--tsv"],
            cwd=str(ROOT), capture_output=True, text=True,
            encoding="utf-8", timeout=120,   # la salida del vault es UTF-8, no cp1252
        )
    except (OSError, subprocess.SubprocessError) as e:
        sys.exit(f"heal-links: no pude correr check-links.sh ({e})")
    rows = []
    for ln in res.stdout.splitlines():
        parts = ln.split("\t")
        if len(parts) >= 3 and parts[1].isdigit():
            kind = parts[3] if len(parts) >= 4 else "wiki"
            rows.append((parts[0], int(parts[1]), parts[2], kind))
    return rows


def split_link(raw):
    """'Destino#sección|alias' -> (destino_base, sección|None, alias|None)."""
    body, alias = (raw.split("|", 1) + [None])[:2] if "|" in raw else (raw, None)
    target, anchor = (body.split("#", 1) + [None])[:2] if "#" in body else (body, None)
    target = target.strip()
    if "/" in target:
        target = target.rsplit("/", 1)[-1]
    if target.lower().endswith(".md"):
        target = target[:-3]
    return target, anchor, alias


def rebuild(raw, new_stem):
    """Reconstruye el wikilink cambiando solo el destino, preservando sección y alias."""
    _, anchor, alias = split_link(raw)
    out = new_stem
    if anchor is not None:
        out += "#" + anchor
    if alias is not None:
        out += "|" + alias
    return out


def md_inner(raw):
    """Quita los corchetes angulares de un raw markdown: '<a/b.md>' -> 'a/b.md'."""
    return raw[1:-1] if raw.startswith("<") and raw.endswith(">") else raw


def target_stem(raw, kind):
    """Nombre base (sin carpeta/.md/#ancla) para buscar match por parecido, según tipo."""
    if kind == "md":
        t = md_inner(raw).split("#", 1)[0].strip()
        if "/" in t:
            t = t.rsplit("/", 1)[-1]
        if t.lower().endswith(".md"):
            t = t[:-3]
        return t
    return split_link(raw)[0]


def old_literal(raw, kind):
    """Substring exacto a buscar/reemplazar en el archivo."""
    return "](" + raw + ")" if kind == "md" else "[[" + raw + "]]"


def new_literal(raw, kind, new_stem):
    """Substring de reemplazo, preservando sección/alias (wiki) o ancla (md).

    md repunta a nombre pelado `](<Nuevo.md>)` — patrón "nace por nombre, se
    endurece a ruta" del vault: harden-links lo lleva a ruta relativa después.
    """
    if kind == "md":
        inner = md_inner(raw)
        anchor = inner.split("#", 1)[1] if "#" in inner else None
        return "](<" + new_stem + ".md" + ("#" + anchor if anchor else "") + ">)"
    return "[[" + rebuild(raw, new_stem) + "]]"


def show_link(raw, kind):
    """Representación legible para el reporte."""
    return "[..](" + raw + ")" if kind == "md" else "[[" + raw + "]]"


def classify(raw, kind, index):
    """-> ('fix', nuevo_stem) | ('ambiguous', [stems]) | ('no_target', None) | ('skip', None)."""
    content = md_inner(raw) if kind == "md" else raw   # no confundir <> de md con placeholders
    if any(c in content for c in PLACEHOLDER):
        return "skip", None
    target = target_stem(raw, kind)
    if not target:
        return "skip", None
    lb = target.lower()
    if lb in index:                       # ya resolvería (guarda defensiva)
        return "skip", None
    near = get_close_matches(lb, list(index.keys()), n=2, cutoff=CUTOFF)
    if len(near) == 1:
        return "fix", index[near[0]]
    if len(near) > 1:
        return "ambiguous", [index[n] for n in near]
    return "no_target", None


def propose():
    rows = get_broken()
    index = build_index()
    fixes = defaultdict(list)       # (raw, kind, new_stem) -> [(archivo, línea)]
    ambiguous = defaultdict(list)   # (raw, kind) -> [(archivo, línea, [candidatos])]
    no_target = defaultdict(list)   # (raw, kind) -> [(archivo, línea)]
    for f, line, raw, kind in rows:
        k, tgt = classify(raw, kind, index)
        if k == "fix":
            fixes[(raw, kind, tgt)].append((f, line))
        elif k == "ambiguous":
            ambiguous[(raw, kind)].append((f, line, tgt))
        elif k == "no_target":
            no_target[(raw, kind)].append((f, line))

    print(f"\nheal-links (propuesta) — {len(rows)} enlace(s) roto(s)\n")

    print(f"── Repuntes seguros (match único, sin IA): {len(fixes)} ──")
    if fixes:
        print("   Aplicá tras revisar (o `heal-links.py --apply`).")
        for (raw, kind, tgt), locs in sorted(fixes.items()):
            print(f"   {show_link(raw, kind)}  ->  {new_literal(raw, kind, tgt)}   ({len(locs)} uso/s)")
            for f, line in locs:
                print(f"        {f}:{line}")
    else:
        print("   (ninguno)")

    print(f"\n── Ambiguos (2+ notas parecidas — decidí vos): {len(ambiguous)} ──")
    for (raw, kind), occ in sorted(ambiguous.items()):
        cands = occ[0][2]
        print(f"   {show_link(raw, kind)}  ~  {', '.join('[[%s]]' % c for c in cands)}   ({len(occ)} uso/s)")

    print(f"\n── Sin destino (crear la nota o quitar el enlace): {len(no_target)} ──")
    print("   Triage de contenido — decisión del dueño del vault. Agrupados por link distinto:")
    for (raw, kind), locs in sorted(no_target.items(), key=lambda kv: (-len(kv[1]), kv[0][0])):
        print(f"   {show_link(raw, kind)}   ({len(locs)} uso/s)  ej. {locs[0][0]}:{locs[0][1]}")

    print("\nDRY RUN: no se cambió nada.\n")


def apply_loop(max_fixes):
    print(f"\nBucle acotado a {max_fixes} repuntes seguros. Recuenta cada pase.\n")
    applied = 0
    while applied < max_fixes:
        rows = get_broken()
        before = len(rows)
        index = build_index()
        nxt = None
        for f, line, raw, kind in rows:
            k, tgt = classify(raw, kind, index)
            if k == "fix":
                if old_literal(raw, kind) in (ROOT / f).read_text(encoding="utf-8", errors="replace"):
                    nxt = (f, raw, kind, tgt)
                    break
        if nxt is None:
            print("  no quedan repuntes seguros aplicables. fin.")
            break
        f, raw, kind, tgt = nxt
        path = ROOT / f
        text = path.read_text(encoding="utf-8", errors="replace")
        old, new = old_literal(raw, kind), new_literal(raw, kind, tgt)
        path.write_text(text.replace(old, new), encoding="utf-8")
        after = len(get_broken())
        applied += 1
        print(f"  {applied:>2}: {show_link(raw, kind)} -> {new}  en {f}   rotos {before}->{after}")
        if after >= before:
            print("  el conteo no bajó — guard de no-progreso, freno.")
            break
    print(f"\nFin. {applied} enlace(s) repuntado(s).\n")


def main():
    ap = argparse.ArgumentParser(description="Propone/aplica saneo de enlaces rotos.")
    ap.add_argument("--apply", action="store_true", help="aplica repuntes seguros (acotado)")
    ap.add_argument("--max", type=int, default=15, help="tope de repuntes en --apply")
    args = ap.parse_args()
    if args.apply:
        apply_loop(args.max)
    else:
        propose()


if __name__ == "__main__":
    main()
