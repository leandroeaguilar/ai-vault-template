# -*- coding: utf-8 -*-
"""
sentinels_common.py — lógica compartida de los centinelas @user.

La usan sentinels-guard.py (PreToolUse, solo Claude Code) y sentinels-verify.py
(commit/PR, universal). Antes cada uno tenía su copia de estas funciones y la
copia del guard arrastró un bug que el verify ya había arreglado (la región
fantasma). Una sola definición: los dos deciden igual, siempre.

Funciones PURAS (texto -> datos), sin E/S: se prueban con Hypothesis en
tests/test_sentinels.py.

    <!-- @user -->
    ...contenido protegido, propiedad humana...
    <!-- /@user -->

Los marcadores que viven dentro de código —bloques ``` / ~~~ y spans inline
entre backticks— se IGNORAN: las guías del vault documentan los centinelas con
ejemplos. Sin ese filtro, un marcador de apertura suelto en un ejemplo inline
empareja con el primer cierre real que aparezca más abajo y crea una REGIÓN
FANTASMA que protege media nota.
"""
import re

OPEN_RE = re.compile(r'<!--\s*@user\s*-->')
CLOSE_RE = re.compile(r'<!--\s*/@user\s*-->')
FENCE_RE = re.compile(r'^\s*(```|~~~)')
INLINE_CODE_RE = re.compile(r'(`+)(?:(?!\1).)*\1')


def code_spans(text):
    """Rangos [inicio, fin) de offsets que son código: fences y spans inline."""
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
    if in_fence:              # fence sin cerrar: hasta el final
        spans.append((start, pos))
    return spans


def user_regions(text):
    """Contenido de cada bloque @user cerrado, ignorando los marcadores que son código."""
    spans = code_spans(text)

    def is_code(i):
        return any(a <= i < b for a, b in spans)

    opens = [m.end() for m in OPEN_RE.finditer(text) if not is_code(m.start())]
    closes = [m.start() for m in CLOSE_RE.finditer(text) if not is_code(m.start())]

    regions = []
    ci = 0
    for o in opens:
        # Primer cierre que esté después de esta apertura.
        while ci < len(closes) and closes[ci] < o:
            ci += 1
        if ci >= len(closes):
            break                    # apertura sin cierre: no es un bloque, se ignora
        regions.append(text[o:closes[ci]])
        ci += 1
    return regions


def lost_regions(old_text, new_text):
    """
    Bloques @user de `old_text` que NO sobreviven en `new_text`.

    Sobrevivir = el contenido sigue textual Y sigue dentro de un bloque @user.
    Que el texto "esté en algún lado" no alcanza: sacar los marcadores dejando
    el texto lo desprotege, y el siguiente cambio lo edita sin que nadie lo vea.
    Los bloques vacíos (solo espacios) no protegen nada y se ignoran.
    """
    old = [r for r in user_regions(old_text) if r.strip()]
    if not old:
        return []
    new = user_regions(new_text)
    return [r for r in old if not any(r in n for n in new)]


def apply_edit(text, old_string, new_string, replace_all=False):
    """El texto tal como quedaría después de un Edit (misma semántica que la tool)."""
    if not old_string or old_string not in text:
        return text
    if replace_all:
        return text.replace(old_string, new_string)
    return text.replace(old_string, new_string, 1)
