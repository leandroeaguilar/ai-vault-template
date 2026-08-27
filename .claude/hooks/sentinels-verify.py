#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
sentinels-verify.py — integridad de los bloques @user, verificada en el COMMIT.

Es el equivalente AGNÓSTICO de sentinels-guard.py: aquel corre en PreToolUse y
por lo tanto solo protege a Claude Code; este corre en `git commit` (vía
.githooks/pre-commit) y en el PR (vía .github/workflows/verify.yml), así que
cubre a CUALQUIER agente y a cualquier humano. Ver el README, sección Centinelas.

Reparto deliberado de responsabilidades:
  guard  (PreToolUse) → temprano y preciso, pero solo Claude Code.
  verify (commit/PR)  → tarde pero universal. No evita que el agente escriba;
                        evita que lo escrito ENTRE a la historia.

Qué valida: para cada .md que cambió, toma los bloques
    <!-- @user --> ... <!-- /@user -->
de la versión ANTERIOR y exige que su contenido siga presente, textual, en la
versión nueva. Si un bloque se alteró o desapareció (incluso por borrar el
archivo entero) → violación.

Los marcadores que viven dentro de código —bloques ``` / ~~~ **y** spans inline
entre backticks— se IGNORAN: las guías del vault documentan los centinelas con
ejemplos, y sin esto darían falso positivo. No es teórico: un marcador de
apertura suelto en un ejemplo inline (`<!--@user-->`, ilustrando que los espacios
son flexibles) empareja con el primer cierre real que encuentre 24 líneas más
abajo y crea una **región fantasma** que protege media nota. Es el bug que tenía
—y tiene— el guard PreToolUse. (Mismo tipo de fix que ya llevaba check-contradictions.sh.)

Modos (las reglas son idénticas en ambos):
  (por defecto)          → lo STAGED, contra HEAD. Modo del hook pre-commit.
  --range <BASE> <HEAD>  → lo que cambió entre dos refs. Modo de CI (en un PR no
                           hay nada staged).

Salida: exit 0 si todo bien; exit 1 si hay violaciones (BLOQUEA).
Escapes: .vault-meta/sentinels.disabled  ·  SENTINELS_OK=1
FAIL-OPEN ante error inesperado (exit 0): un bug del verificador nunca debe
frenar trabajo legítimo.
"""
import os
import re
import subprocess
import sys

OPEN_RE = re.compile(r'<!--\s*@user\s*-->')
CLOSE_RE = re.compile(r'<!--\s*/@user\s*-->')
FENCE_RE = re.compile(r'^\s*(```|~~~)')
INLINE_CODE_RE = re.compile(r'(`+)(?:(?!\1).)*\1')


def git(*args):
    """
    Corre git y devuelve stdout (str). Devuelve None si el comando falla.

    `core.quotepath=false` NO es opcional: por defecto git escapa los caracteres
    no-ASCII en los nombres que imprime, y devolvería
    «"00 Sistema/Centinelas de Edici\\303\\263n.md"» — un nombre que después no
    resuelve en `git show`. El archivo se saltearía EN SILENCIO, que es el peor
    modo de falla posible para un verificador. Este vault tiene rutas con tilde
    (`04 Knowledge/Automatización/`), así que el caso es real, no teórico.
    Mismo motivo por el que update.sh usa el flag.
    """
    try:
        out = subprocess.run(
            ['git', '-c', 'core.quotepath=false'] + list(args),
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, check=False)
    except Exception:
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode('utf-8', 'replace')


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
            # Código inline: `<!--@user-->` en una guía es un EJEMPLO, no un marcador.
            for m in INLINE_CODE_RE.finditer(line):
                spans.append((pos + m.start(), pos + m.end()))
        pos += len(line)
    if in_fence:              # fence sin cerrar: hasta el final
        spans.append((start, pos))
    return spans


def user_regions(text):
    """Contenido de cada bloque @user cerrado, ignorando los marcadores que son código."""
    spans = code_spans(text)

    def in_fence(i):
        return any(a <= i < b for a, b in spans)

    opens = [m.end() for m in OPEN_RE.finditer(text) if not in_fence(m.start())]
    closes = [m.start() for m in CLOSE_RE.finditer(text) if not in_fence(m.start())]

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
    return [r for r in regions if r.strip()]


def main():
    root = git('rev-parse', '--show-toplevel')
    if not root:
        sys.exit(0)                  # fuera de un repo: nada que verificar
    os.chdir(root.strip())

    if os.path.isfile('.vault-meta/sentinels.disabled'):
        sys.exit(0)
    if os.environ.get('SENTINELS_OK') == '1':
        sys.exit(0)

    base = head = None
    if len(sys.argv) > 1 and sys.argv[1] == '--range':
        base = sys.argv[2] if len(sys.argv) > 2 else ''
        head = sys.argv[3] if len(sys.argv) > 3 else 'HEAD'
        if not base:
            print('sentinels-verify: --range necesita <BASE> [HEAD]', file=sys.stderr)
            sys.exit(0)

    if base:
        names = git('diff', '--name-only', '--diff-filter=ACMD', '%s...%s' % (base, head))
        old_ref, new_ref = base, head
    else:
        names = git('diff', '--cached', '--name-only', '--diff-filter=ACMD')
        old_ref, new_ref = 'HEAD', None   # new_ref None => índice

    if not names:
        sys.exit(0)

    violations = []
    for path in names.splitlines():
        if not path.endswith('.md'):
            continue

        old = git('show', '%s:%s' % (old_ref, path))
        if not old:
            continue                 # archivo nuevo: no había nada protegido
        regions = user_regions(old)
        if not regions:
            continue

        new = git('show', '%s:%s' % (new_ref, path)) if new_ref else git('show', ':%s' % path)
        if new is None:
            # No existe del lado nuevo: el archivo se borró con contenido protegido dentro.
            violations.append((path, 'el archivo se borra y contenía %d bloque(s) @user' % len(regions)))
            continue

        missing = sum(1 for r in regions if r not in new)
        if missing:
            violations.append((path, '%d de %d bloque(s) @user alterados o eliminados'
                               % (missing, len(regions))))

    if not violations:
        print('sentinels-verify: OK (bloques @user intactos).')
        sys.exit(0)

    msg = ['sentinels-verify: %d archivo(s) con contenido protegido alterado:' % len(violations)]
    for path, why in violations:
        msg.append('  ✗ %s: %s' % (path, why))
    msg.append('')
    msg.append('Los bloques <!-- @user --> son propiedad humana: no se editan ni se reescriben.')
    msg.append('Restaurá ese contenido textual, o —si el cambio es tuyo y es deliberado—')
    msg.append('repetí el commit con SENTINELS_OK=1 (o creá .vault-meta/sentinels.disabled).')
    out = '\n'.join(msg) + '\n'
    try:
        sys.stderr.buffer.write(out.encode('utf-8'))
    except Exception:
        sys.stderr.write(out)
    sys.exit(1)


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception:
        sys.exit(0)                  # fail-open
