#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""generate-index.py — regenera los index.md del vault (OKF estricto).

Port de bundle/index.py del repo OKF (GoogleCloudPlatform/knowledge-catalog),
adaptado a las convenciones de este vault:

  - index.md = listado puro SIN frontmatter (excepción: la raíz lleva okf_version).
  - Secciones agrupadas por `tipo_doc` (fallback "Otros"), orden alfabético.
  - Entradas: `* [Título](<Archivo.md>) - descripción` — links markdown relativos.
  - Título = primer H1 de la nota; si no hay, el nombre del archivo.
  - Descripción = campo `description` del frontmatter de la nota (T1/P1).
    Si la nota no tiene, se PRESERVA la descripción que ya tuviera el index
    (idem para subdirectorios, cuya descripción es curada a mano).
  - El índice es un ARTEFACTO REGENERABLE: no editarlo a mano salvo las
    descripciones de subdirectorios (que este script preserva).

Uso:
  python generate-index.py               # regenera todos los index del vault
  python generate-index.py "04 Knowledge/Temas" ...   # solo esas carpetas
  python generate-index.py --staged      # solo carpetas con .md staged (pre-commit)

Kill-switch: .vault-meta/index-gen.disabled
Ver el README, sección Índices.
"""
import io
import os
import re
import subprocess
import sys
from collections import defaultdict

VAULT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Carpetas que NO se indexan ni se listan como subdirectorio de conocimiento.
EXCLUDED_DIRS = {
    ".git", ".obsidian", ".claude", ".githooks", ".vault-meta", ".trash",
    "node_modules", "__pycache__", "graphify-out",
    "Baseline de Seguridad",   # tooling (README propio, convención GitHub)
    "001_plantillas",          # plantillas Templater (frontmatter placeholder)
    "ANEXOS",                  # material de apoyo, no conceptos
    "plantillas-deprecadas",   # archivado profundo
}

ROOT_DIRS_LABEL = "Capas del sistema"
SUBDIR_LABEL = "Subdirectorios"
FILES_LABEL = "Archivos"
FALLBACK_GROUP = "Otros"

ENTRY_RE = re.compile(r"^\*\s+\[(?P<title>.+?)\]\(<(?P<target>.+?)>\)(?:\s+-\s+(?P<desc>.*))?\s*$")


def parse_frontmatter(text):
    """Devuelve (dict_frontmatter, cuerpo). Parser minimalista línea a línea."""
    fm = {}
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return fm, text
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            return fm, "\n".join(lines[i + 1:])
        m = re.match(r"^([A-Za-z_][\w-]*):\s*(.*)$", lines[i])
        if m:
            val = m.group(2).strip().strip('"').strip("'")
            fm[m.group(1)] = val
    return {}, text  # frontmatter sin cerrar: tratar como cuerpo


def first_h1(body):
    for line in body.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return None


def existing_descriptions(index_path):
    """target -> descripción, del index actual (preserva curado manual)."""
    out = {}
    if not os.path.isfile(index_path):
        return out
    try:
        for line in io.open(index_path, encoding="utf-8"):
            m = ENTRY_RE.match(line.rstrip("\n"))
            if m and m.group("desc"):
                out[m.group("target")] = m.group("desc").strip()
    except Exception:
        pass
    return out


def build_index(dirpath, is_root=False):
    """Genera el texto del index.md de un directorio. Devuelve str o None."""
    prev = existing_descriptions(os.path.join(dirpath, "index.md"))

    subdirs, mdfiles, otherfiles = [], [], []
    for name in sorted(os.listdir(dirpath), key=str.casefold):
        full = os.path.join(dirpath, name)
        if os.path.isdir(full):
            if name not in EXCLUDED_DIRS and not name.startswith(".") and has_knowledge(full):
                subdirs.append(name)
        elif name.lower().endswith(".md"):
            if name.lower() not in ("index.md", "log.md"):
                mdfiles.append(name)
        elif not name.startswith(".") and name.lower() not in ("desktop.ini", "thumbs.db"):
            otherfiles.append(name)

    groups = defaultdict(list)  # tipo_doc -> [(title, target, desc)]
    for name in mdfiles:
        try:
            text = io.open(os.path.join(dirpath, name), encoding="utf-8").read()
        except Exception:
            text = ""
        fm, body = parse_frontmatter(text)
        title = fm.get("title") or first_h1(body) or os.path.splitext(name)[0]
        desc = fm.get("description") or prev.get(name, "")
        # Dual-key OKF (RUN-001 F2): acepta tipo_doc o type
        group = fm.get("tipo_doc") or fm.get("type") or FALLBACK_GROUP
        groups[group].append((title, name, desc))

    sections = []

    # Subdirectorios primero (progressive disclosure hacia abajo).
    if subdirs:
        label = ROOT_DIRS_LABEL if is_root else SUBDIR_LABEL
        lines = ["# " + label, ""]
        for d in subdirs:
            target = d + "/index.md"
            desc = prev.get(target, "")
            suffix = " - " + desc if desc else ""
            lines.append("* [%s](<%s>)%s" % (d, target, suffix))
        sections.append("\n".join(lines))

    for group in sorted(groups, key=str.casefold):
        lines = ["# " + group, ""]
        for title, target, desc in sorted(groups[group], key=lambda e: e[0].casefold()):
            suffix = " - " + desc if desc else ""
            lines.append("* [%s](<%s>)%s" % (title, target, suffix))
        sections.append("\n".join(lines))

    if otherfiles:
        lines = ["# " + FILES_LABEL, ""]
        for name in otherfiles:
            desc = prev.get(name, "")
            suffix = " - " + desc if desc else ""
            lines.append("* [%s](<%s>)%s" % (os.path.splitext(name)[0], name, suffix))
        sections.append("\n".join(lines))

    if not sections:
        sections = ["# Contenido\n\n*(carpeta vacía por el momento)*"]

    header = '---\nokf_version: "0.2"\n---\n\n' if is_root else ""
    return header + "\n\n".join(sections) + "\n"


def has_knowledge(dirpath, _cache={}):
    """True si el dir (o su descendencia no excluida) contiene algún .md real.
    Carpetas de puros assets (datasets, imágenes) NO llevan index."""
    if dirpath in _cache:
        return _cache[dirpath]
    result = False
    try:
        for name in os.listdir(dirpath):
            full = os.path.join(dirpath, name)
            if os.path.isdir(full):
                if name not in EXCLUDED_DIRS and not name.startswith(".") and has_knowledge(full):
                    result = True
                    break
            elif name.lower().endswith(".md") and name.lower() not in ("index.md", "log.md"):
                result = True
                break
    except OSError:
        pass
    _cache[dirpath] = result
    return result


def all_dirs():
    """Directorios a indexar: raíz + recursivo, saltando excluidos y
    carpetas sin conocimiento (.md) propio ni descendiente."""
    result = [VAULT]
    for base, dirs, _files in os.walk(VAULT):
        dirs[:] = [d for d in dirs if d not in EXCLUDED_DIRS and not d.startswith(".")]
        for d in dirs:
            full = os.path.join(base, d)
            if has_knowledge(full):
                result.append(full)
    return result


def staged_dirs():
    # -z + quotepath=false: rutas crudas UTF-8 separadas por NUL. Sin -z, git
    # entrecomilla y escapa (\303\255) los paths no-ASCII y el `.md"` final
    # rompe el endswith(".md") -> las carpetas acentuadas nunca se regeneraban.
    try:
        out = subprocess.check_output(
            ["git", "-c", "core.quotepath=false", "diff", "--cached",
             "--name-only", "-z", "--diff-filter=ACMR"],
            cwd=VAULT).decode("utf-8", "replace")
    except Exception:
        return []
    dirs = set()
    for line in out.split("\0"):
        if not line:
            continue
        if line.lower().endswith(".md") and os.path.basename(line).lower() != "index.md":
            d = os.path.join(VAULT, os.path.dirname(line)) if os.path.dirname(line) else VAULT
            parts = os.path.relpath(d, VAULT).split(os.sep)
            if any(p in EXCLUDED_DIRS or p.startswith(".") for p in parts if p != "."):
                continue
            if os.path.isdir(d):
                dirs.add(d)
    return sorted(dirs)


def main():
    # El pre-commit lee las rutas impresas y hace `git add` de cada una. En
    # Windows, print() a un pipe emite \r\n: el `read` del hook dejaba un \r
    # final y `git add "…/index.md\r"` fallaba en silencio. Forzar LF (y UTF-8,
    # por las rutas acentuadas que en stdout cp1252 podrían reventar).
    try:
        sys.stdout.reconfigure(encoding="utf-8", newline="\n")
    except Exception:
        pass
    if os.path.isfile(os.path.join(VAULT, ".vault-meta", "index-gen.disabled")):
        return 0
    args = sys.argv[1:]
    if args and args[0] == "--staged":
        targets = staged_dirs()
    elif args:
        targets = [os.path.join(VAULT, a) for a in args]
    else:
        targets = all_dirs()

    changed = []
    for d in targets:
        if not os.path.isdir(d):
            continue
        is_root = os.path.normpath(d) == os.path.normpath(VAULT)
        new = build_index(d, is_root=is_root)
        path = os.path.join(d, "index.md")
        old = io.open(path, encoding="utf-8").read() if os.path.isfile(path) else None
        if new != old:
            io.open(path, "w", encoding="utf-8", newline="\n").write(new)
            changed.append(os.path.relpath(path, VAULT))
    for c in changed:
        print(c)
    return 0


if __name__ == "__main__":
    sys.exit(main())
