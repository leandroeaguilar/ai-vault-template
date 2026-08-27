#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""harden-links.py — endurece y repara links markdown del vault (F1 de RUN-001).

Tres operaciones (probadas en PoC 2026-07-17, spec OKF §5):
  1. ENDURECER : [Texto](<Nombre.md>) nombre pelado -> ruta relativa, si el
                 destino existe y es único por nombre.
  2. REPARAR   : [Texto](<ruta/muerta.md>) -> re-punteo por basename único
                 (el destino se mudó). Ambiguo o inexistente: no se toca
                 (OKF tolera rotos = conocimiento planificado).
  3. CONVERTIR : [[Wikilink]] resuelto -> [Título](<ruta relativa.md>).
                 SOLO con --wiki (se usa en F3 de la migración total, no antes).
                 Promesas (sin destino) y frontmatter YAML: intactos siempre.

Uso:  python harden-links.py [--dry] [--wiki] [rutas...]
      (sin rutas = vault completo). --dry solo reporta, no escribe.
Kill-switch: .vault-meta/harden.disabled
"""
import io, os, re, sys

VAULT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
EXCLUDED = {".git", ".obsidian", ".claude", ".githooks", ".vault-meta", ".trash",
            "node_modules", "__pycache__", "graphify-out", "Baseline de Seguridad",
            "001_plantillas"}

MD_BARE = re.compile(r"\[([^\]]+)\]\(<([^/\\<>]+\.md)>\)")
MD_PATH = re.compile(r"\[([^\]]+)\]\(<([^<>]*/[^<>]+\.md)>\)")
WIKI = re.compile(r"\[\[([^\]|#/]+)(\|([^\]]+))?\]\]")
FM_END = re.compile(r"^---\s*$")


def md_files(root):
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in EXCLUDED and not d.startswith(".")]
        for f in files:
            if f.lower().endswith(".md"):
                yield os.path.join(base, f)


def split_frontmatter(text):
    """Devuelve (frontmatter_crudo, cuerpo) — el frontmatter NUNCA se toca."""
    lines = text.split("\n")
    if lines and lines[0].strip() == "---":
        for i in range(1, len(lines)):
            if FM_END.match(lines[i]):
                return "\n".join(lines[:i + 1]) + "\n", "\n".join(lines[i + 1:])
    return "", text


def main():
    if os.path.isfile(os.path.join(VAULT, ".vault-meta", "harden.disabled")):
        return 0
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    dry = "--dry" in sys.argv
    wiki = "--wiki" in sys.argv
    roots = [os.path.join(VAULT, a) for a in args] or [VAULT]

    names = {}
    for p in md_files(VAULT):
        names.setdefault(os.path.basename(p), []).append(p)

    def rel(target, fromfile):
        return os.path.relpath(target, os.path.dirname(fromfile)).replace(os.sep, "/")

    changed = 0
    for root in roots:
        it = md_files(root) if os.path.isdir(root) else [root]
        for p in it:
            if os.path.basename(p).lower() == "index.md":
                continue  # los índices los regenera generate-index.py
            raw = io.open(p, encoding="utf-8").read()
            fm, body = split_frontmatter(raw)
            orig = body

            def fix_bare(m):
                hits = names.get(m.group(2), [])
                if len(hits) == 1 and hits[0] != p:
                    return "[%s](<%s>)" % (m.group(1), rel(hits[0], p))
                return m.group(0)
            body = MD_BARE.sub(fix_bare, body)

            def heal_path(m):
                tgt = os.path.normpath(os.path.join(os.path.dirname(p), m.group(2)))
                if os.path.isfile(tgt):
                    return m.group(0)
                hits = names.get(os.path.basename(m.group(2)), [])
                if len(hits) == 1:
                    return "[%s](<%s>)" % (m.group(1), rel(hits[0], p))
                return m.group(0)
            body = MD_PATH.sub(heal_path, body)

            if wiki:
                def fix_wiki(m):
                    name, alias = m.group(1).strip(), m.group(3)
                    hits = names.get(name + ".md", [])
                    if len(hits) == 1 and hits[0] != p:
                        return "[%s](<%s>)" % (alias or name, rel(hits[0], p))
                    return m.group(0)
                body = WIKI.sub(fix_wiki, body)

            if body != orig:
                changed += 1
                print(("DRY: " if dry else "endurecido: ") + os.path.relpath(p, VAULT))
                if not dry:
                    io.open(p, "w", encoding="utf-8", newline="").write(fm + body)
    if changed == 0:
        print("harden-links: nada que endurecer/reparar.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
