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

Cómo decide: SIMULA la edición y pregunta si cada bloque @user sigue textual y
protegido en el resultado (sentinels_common.lost_regions — el mismo criterio que
sentinels-verify.py aplica en el commit). Antes preguntaba "¿old_string está
dentro de un bloque?", y un Edit cuyo old_string CONTENÍA el bloque entero, o
cruzaba su borde, pasaba sin bloquear.

Contrato con Claude Code:
  - exit 0  -> permite la herramienta.
  - exit 2  -> bloquea; el texto de stderr se le muestra al modelo.

Diseño FAIL-OPEN: ante cualquier error/ambigüedad -> permite (exit 0) y deja el
motivo en .vault-meta/guard-errors.log. Un bug nunca debe frenar trabajo
legítimo. Sin jq/node; usa python (ya requerido por el SOP para validar JSON).
"""
import sys, os, json

def allow():
    sys.exit(0)

def block(msg):
    # Escribir bytes UTF-8 directo: evita mojibake si la consola es cp1252.
    try:
        sys.stderr.buffer.write(msg.encode('utf-8'))
    except Exception:
        sys.stderr.write(msg)
    sys.exit(2)

def project_root():
    return sys.argv[1] if len(sys.argv) > 1 else (os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd())

def log_fail_open(exc):
    """Fail-open NO es fail-silent: deja el motivo en .vault-meta/guard-errors.log."""
    try:
        d = os.path.join(project_root(), '.vault-meta')
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, 'guard-errors.log')
        if os.path.isfile(path) and os.path.getsize(path) > 1000000:
            return
        import datetime
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('%s sentinels-guard fail-open: %s: %s\n' % (
                datetime.datetime.now().isoformat(timespec='seconds'),
                type(exc).__name__, str(exc)[:200]))
    except Exception:
        pass

def main():
    from sentinels_common import apply_edit, lost_regions

    root = project_root()
    raw = sys.stdin.buffer.read().decode('utf-8', 'replace')
    data = json.loads(raw)
    ti = data.get('tool_input') or {}
    fp = ti.get('file_path')
    if not fp:
        allow()

    path = fp if os.path.isabs(fp) else os.path.join(root, fp)
    if not os.path.isfile(path):
        allow()  # archivo nuevo: aún no hay contenido protegido

    # newline='' : sin traducir finales de línea, para comparar contra el
    # old_string/content tal como los manda la tool.
    with open(path, encoding='utf-8', errors='replace', newline='') as fh:
        text = fh.read()

    old = ti.get('old_string')      # Edit
    content = ti.get('content')     # Write

    if old is not None:
        result = apply_edit(text, old, ti.get('new_string') or '', bool(ti.get('replace_all')))
        if lost_regions(text, result):
            block(
                "[CENTINELA @user] La edición toca contenido protegido "
                "(<!-- @user -->) en «%s». Ese bloque es propiedad humana: no lo "
                "edites, no lo reescribas ni le saques los marcadores. Editá fuera del bloque, "
                "o pedile al dueño del vault que lo cambie." % fp
            )
        allow()

    if content is not None:
        # Write (sobrescritura total): ¿se perdería/alteraría algún bloque @user?
        if lost_regions(text, content):
            block(
                "[CENTINELA @user] Este Write sobrescribiría «%s» y perdería, "
                "alteraría o desprotegería un bloque <!-- @user -->. Preservá ese bloque "
                "textual y con sus marcadores, o usá Edit fuera de él." % fp
            )
        allow()

    allow()

if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        raise
    except Exception as exc:
        # Fail-open: cualquier error inesperado no debe bloquear. Pero queda dicho.
        log_fail_open(exc)
        sys.exit(0)
