#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sentinels-guard.py — guardián de centinelas @user (Gap 3).

Lo invoca el wrapper sentinels-guard.sh en PreToolUse (Write|Edit). Impide que
un agente sobrescriba contenido marcado como propiedad humana con centinelas:

    <!-- @user -->
    ...contenido protegido, no lo toca la IA...
    <!-- /@user -->

(Los bloques <!-- @generated --> son propiedad del agente: NO se protegen,
la IA puede regenerarlos libremente. Ver el README, sección Centinelas.)

Contrato con Claude Code:
  - exit 0  -> permite la herramienta.
  - exit 2  -> bloquea; el texto de stderr se le muestra al modelo.

Diseño FAIL-OPEN: solo bloquea cuando está SEGURO de que la edición cae dentro
de un bloque @user. Ante cualquier error/ambigüedad -> permite (exit 0). Un bug
nunca debe frenar trabajo legítimo. Sin jq/node; usa python (ya requerido por el
SOP para validar JSON).
"""
import sys, os, json, re

def allow():
    sys.exit(0)

def block(msg):
    # Escribir bytes UTF-8 directo: evita mojibake si la consola es cp1252.
    try:
        sys.stderr.buffer.write(msg.encode('utf-8'))
    except Exception:
        sys.stderr.write(msg)
    sys.exit(2)

OPEN_RE = re.compile(r'<!--\s*@user\s*-->')
CLOSE_RE = re.compile(r'<!--\s*/@user\s*-->')
FENCE_RE = re.compile(r'^\s*(```|~~~)')
INLINE_CODE_RE = re.compile(r'(`+)(?:(?!\1).)*\1')


def code_spans(text):
    """Rangos [inicio, fin) que son código: fences y spans inline entre backticks."""
    spans = []
    pos = 0
    in_fence = False
    start = 0
    for line in text.splitlines(keepends=True):
        if FENCE_RE.match(line):
            if in_fence:
                spans.append((start, pos + len(line)))
                in_fence = False
            else:
                in_fence = True
                start = pos
        elif not in_fence:
            for m in INLINE_CODE_RE.finditer(line):
                spans.append((pos + m.start(), pos + m.end()))
        pos += len(line)
    if in_fence:
        spans.append((start, pos))
    return spans


def user_regions(text):
    """
    Contenido de cada bloque @user cerrado, ignorando los marcadores que son
    CÓDIGO (ejemplos en las guías del vault).

    Sin este filtro, un marcador de apertura suelto dentro de un ejemplo inline
    empareja con el primer cierre real que aparezca más abajo y crea una REGIÓN
    FANTASMA que protege media nota — bloqueando ediciones legítimas. Pasaba de
    verdad en «Centinelas de Edición.md». Mismo criterio que sentinels-verify.py.
    """
    spans = code_spans(text)

    def is_code(i):
        return any(a <= i < b for a, b in spans)

    opens = [m.end() for m in OPEN_RE.finditer(text) if not is_code(m.start())]
    closes = [m.start() for m in CLOSE_RE.finditer(text) if not is_code(m.start())]

    regions = []
    ci = 0
    for o in opens:
        while ci < len(closes) and closes[ci] < o:
            ci += 1
        if ci >= len(closes):
            break                    # apertura sin cierre: no es un bloque
        regions.append(text[o:closes[ci]])
        ci += 1
    return regions

def main():
    root = sys.argv[1] if len(sys.argv) > 1 else (os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd())
    raw = sys.stdin.buffer.read().decode('utf-8', 'replace')
    data = json.loads(raw)
    ti = data.get('tool_input') or {}
    fp = ti.get('file_path')
    if not fp:
        allow()

    path = fp if os.path.isabs(fp) else os.path.join(root, fp)
    if not os.path.isfile(path):
        allow()  # archivo nuevo: aún no hay contenido protegido

    text = open(path, encoding='utf-8', errors='replace').read()
    regions = user_regions(text)
    if not regions:
        allow()  # el archivo no tiene centinelas @user

    old = ti.get('old_string')      # Edit
    content = ti.get('content')     # Write

    if old is not None:
        # Edit: ¿el texto que se reemplaza vive dentro de un bloque @user?
        for r in regions:
            if old and old in r:
                block(
                    "[CENTINELA @user] La edición toca contenido protegido "
                    "(<!-- @user -->) en «%s». Ese bloque es propiedad humana: no lo "
                    "edites ni lo reescribas. Editá fuera del bloque, o pedile al dueño del vault "
                    "que lo cambie. (Desactivar guard: crear .vault-meta/sentinels.disabled)" % fp
                )
        allow()

    if content is not None:
        # Write (sobrescritura total): ¿se perdería/alteraría algún bloque @user?
        for r in regions:
            if r.strip() and r not in content:
                block(
                    "[CENTINELA @user] Este Write sobrescribiría «%s» y perdería o "
                    "alteraría un bloque protegido (<!-- @user -->). Preservá ese bloque "
                    "textual, o usá Edit fuera de él. (Desactivar: .vault-meta/sentinels.disabled)" % fp
                )
        allow()

    allow()

if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        # Fail-open: cualquier error inesperado no debe bloquear.
        sys.exit(0)
