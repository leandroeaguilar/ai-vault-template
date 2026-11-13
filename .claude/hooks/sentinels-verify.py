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
de la versión ANTERIOR y exige que su contenido siga presente, textual Y DENTRO
DE UN BLOQUE @user, en la versión nueva. Si un bloque se alteró, desapareció
(incluso por borrar el archivo entero) o quedó sin marcadores → violación. Un
archivo renombrado se compara contra su ruta anterior.

Los marcadores que viven dentro de código —bloques ``` / ~~~ **y** spans inline
entre backticks— se IGNORAN: las guías del vault documentan los centinelas con
ejemplos, y sin esto darían falso positivo. No es teórico: un marcador de
apertura suelto en un ejemplo inline (`<!--@user-->`, ilustrando que los espacios
son flexibles) empareja con el primer cierre real que encuentre 24 líneas más
abajo y crea una **región fantasma** que protege media nota. La lógica vive en
sentinels_common.py, compartida con el guard PreToolUse para que decidan igual.

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
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from sentinels_common import lost_regions, user_regions  # noqa: E402


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


def changed_md(base, head):
    """
    [(ruta_vieja, ruta_nueva)] de los .md que cambiaron. ruta_nueva es None si
    el archivo se borró; en un rename las dos rutas difieren.

    Los renames se piden EXPLÍCITOS (-M, estado R): con un filtro ACMD, un
    archivo renombrado y alterado en el mismo commit no aparecía ni por la ruta
    vieja ni por la nueva, y el bloque @user se perdía sin que nadie lo viera.
    """
    args = ['diff', '--name-status', '-z', '-M', '--diff-filter=ACMDR']
    args += ['%s...%s' % (base, head)] if base else ['--cached']
    raw = git(*args)
    if not raw:
        return []
    fields = raw.split(chr(0))
    pairs, i = [], 0
    while i < len(fields) and fields[i]:
        status = fields[i][0]
        if status in 'RC' and i + 2 < len(fields):
            old, new = fields[i + 1], fields[i + 2]
            i += 3
            if status == 'C':
                continue             # copia: el original sigue donde estaba
        elif i + 1 < len(fields):
            old = fields[i + 1]
            new = None if status == 'D' else old
            i += 2
        else:
            break
        if old.endswith('.md'):
            pairs.append((old, new))
    return pairs


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

    old_ref = base if base else 'HEAD'

    def show_new(path):
        return git('show', '%s:%s' % (head, path)) if base else git('show', ':%s' % path)

    violations = []
    for old_path, new_path in changed_md(base, head):
        old = git('show', '%s:%s' % (old_ref, old_path))
        if not old:
            continue                 # archivo nuevo: no había nada protegido
        total = len([r for r in user_regions(old) if r.strip()])
        if not total:
            continue

        new = show_new(new_path) if new_path else None
        if new is None:
            # No existe del lado nuevo: el archivo se borró con contenido protegido dentro.
            violations.append((old_path, 'el archivo se borra y contenía %d bloque(s) @user' % total))
            continue

        missing = len(lost_regions(old, new))
        if missing:
            where = old_path if new_path == old_path else '%s -> %s' % (old_path, new_path)
            violations.append((where, '%d de %d bloque(s) @user alterados, eliminados o desprotegidos'
                               % (missing, total)))

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
