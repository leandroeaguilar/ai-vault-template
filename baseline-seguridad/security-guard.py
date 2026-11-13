#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
security-guard.py — guardián de seguridad del vault (capa 2, PreToolUse Bash|Read|Write|Edit).

Lo invoca el wrapper security-guard.sh. Escanea el comando/ruta ENTERO y bloquea
un set ACOTADO de patrones inequívocamente peligrosos, atajando evasiones que el
`deny` por-prefijo de settings.local.json no ve (curl embebido, `cat .env`,
force-push a media línea, redirect a config). Ver el README del repositorio.

Además de leer secretos y salir a la red, ataja que el agente APAGUE los
controles: crear un kill-switch `.vault-meta/*.disabled`, cambiar
`core.hooksPath`, o commitear/pushear con `--no-verify`. Eso lo decide el humano.

Contrato con Claude Code:
  - exit 0  -> permite la herramienta.
  - exit 2  -> bloquea; el texto de stderr se le muestra al modelo.

Diseño FAIL-OPEN: ante cualquier error/ambigüedad -> permite (exit 0). Un bug del
hook nunca debe frenar trabajo legítimo; la capa 1 (permisos) sigue vigente igual.
Fail-open no es fail-silent: el motivo queda en .vault-meta/guard-errors.log.
Reglas de alta confianza: preferimos NO bloquear antes que dar un falso positivo.

A propósito NO cubre (decisión documentada, no olvido):
  - `rm -rf`  -> demasiado falso-positivo-propenso; queda en permisos/humano.
  - Salida de red por PowerShell (Invoke-RestMethod/WebRequest) -> vía admin real
    del owner (creación de repos por API). Solo se ataja la salida por Bash.
  - Comandos armados en runtime (`c''url`, `$(printf cu)rl`), globs (`.en*`) e
    intérpretes (`python -c "open('.env')"`): una regex no los ve sin llenarse
    de falsos positivos. Están listados en tests/test_security_guard.py
    (LIMITES_CONOCIDOS); la defensa ahí es la capa 1 y el aislamiento de red.

Cada regla tiene casos "bloquea", "permite" y de evasión en
tests/test_security_guard.py. Al tocar una regex, corré los tests.
"""
import sys, os, re

def allow():
    sys.exit(0)

def block(msg):
    try:
        sys.stderr.buffer.write(msg.encode('utf-8'))
    except Exception:
        sys.stderr.write(msg)
    sys.exit(2)

def log_fail_open(exc):
    """Fail-open NO es fail-silent: deja el motivo en .vault-meta/guard-errors.log."""
    try:
        root = sys.argv[1] if len(sys.argv) > 1 else (os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd())
        d = os.path.join(root, '.vault-meta')
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, 'guard-errors.log')
        if os.path.isfile(path) and os.path.getsize(path) > 1000000:
            return
        import datetime
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write('%s security-guard fail-open: %s: %s\n' % (
                datetime.datetime.now().isoformat(timespec='seconds'),
                type(exc).__name__, str(exc)[:200]))
    except Exception:
        pass

# --- Rutas sensibles (secretos/credenciales) ---
SECRET_PATH = re.compile(
    r'(\.env\b|\.env\.[A-Za-z]|\bid_rsa\b|\bid_ed25519\b|\.pem\b|\.ppk\b|'
    r'credentials\.json\b|\.aws[/\\]credentials|\.ssh[/\\]|'
    r'\bsecrets?\.(json|ya?ml|txt)\b)',
    re.IGNORECASE)
# Sufijos de archivos-ejemplo (NO son secretos): .env.example, owner.env.sample, etc.
SAFE_SUFFIX = re.compile(r'\.(example|sample|template|dist)(\b|$)', re.IGNORECASE)

# --- Reglas sobre comandos Bash (patrón en CUALQUIER parte del comando) ---
NETWORK_OUT = re.compile(r'\b(curl|wget|ncat|telnet)\b', re.IGNORECASE)
# `nc` aparte, con bordes estrictos, para no chocar con palabras que contienen "nc".
NETCAT = re.compile(r'(^|[\s;&|(])nc([\s]|$)', re.IGNORECASE)

READER = re.compile(
    r'\b(cat|bat|less|more|head|tail|grep|egrep|fgrep|rg|ag|strings|xxd|od|'
    r'hexdump|base64|cp|mv|scp|rsync|dd|awk|sed|tar|zip|source)\b',
    re.IGNORECASE)
# `. archivo` (el `source` de POSIX): cargar un .env también es leerlo.
DOT_SOURCE = re.compile(r'(^|[;&|(]\s*|\s)\.\s+\S')

# El flag tiene que estar en el MISMO comando simple que el push (se corta en
# ; & |): `git push origin main && git log -f` no es un force-push.
# `+ref` es force-push por refspec, sin ningún flag.
FORCE_PUSH = re.compile(
    r'\bgit\b[^\n;&|]*\bpush\b[^\n;&|]*'
    r'(--force\b|--force-with-lease|\s-f\b|\s\+[\w./@{}~^-]+)',
    re.IGNORECASE)

CONTROL = r'(\.claude[/\\]|\.githooks[/\\]|\.mcp\.json)'
CONTROL_WRITE = re.compile(
    r'(>>?|\btee\b(\s+-a)?)\s*["\']?[^\s"\'|;&]*' + CONTROL,
    re.IGNORECASE)
# Mismo daño sin redirect: pisar, mover, borrar o editar in-place un archivo de
# control. `git mv` / `git rm` se permiten: quedan en el diff, a la vista.
# Para `cp` solo cuenta el DESTINO (último argumento): copiar DESDE .claude/ es leer.
CONTROL_CLOBBER = re.compile(
    r'(?<!git )\b(mv|rm|truncate|sed\s+(-\w+\s+)*-i\w*|perl\s+(-\w+\s+)*-\w*i\w*)\b'
    r'[^\n;&|]*' + CONTROL
    + r'|\bcp\b[^\n;&|]*\s["\']?[^\s"\'|;&]*' + CONTROL + r'[^\s"\'|;&]*["\']?\s*($|[;&|)])',
    re.IGNORECASE)

# --- Apagar los controles (lo decide el humano, no el agente) ---
KILL_SWITCH = re.compile(
    r'(>>?|\b(touch|tee|cp|mv|ln|install)\b)[^\n;&|]*\.vault-meta[/\\][\w.-]*\.disabled\b',
    re.IGNORECASE)
KILL_PATH = re.compile(r'\.vault-meta[/\\][\w.-]*\.disabled$', re.IGNORECASE)
# Asignar core.hooksPath a algo que no sea .githooks, o quitarlo. Leerlo se permite.
HOOKS_PATH = re.compile(
    r'core\.hookspath(=|\s+)(?![;&|)]|["\']?\.githooks\b)\S'
    r'|--unset(-all)?\s+core\.hookspath',
    re.IGNORECASE)
# Se evalúa sobre el comando SIN el contenido de las comillas: un mensaje de
# commit que menciona el flag no es usarlo.
NO_VERIFY = re.compile(
    r'\bgit\b[^\n;&|]*\b(commit|push|merge|am|rebase)\b[^\n;&|]*--no-verify\b'
    r'|\bgit\b[^\n;&|]*\bcommit\b[^\n;&|]*\s-[a-zA-Z]*n[a-zA-Z]*\b')
QUOTED = re.compile(r'"(?:\\.|[^"\\])*"|\'[^\']*\'')

DISABLE_TROJAN = "  (Si es un falso positivo puntual, pedile al dueño del repo que cree .vault-meta/security-guard.disabled)"
KILL_MSG = ("[SECURITY-GUARD] Crear un kill-switch (.vault-meta/*.disabled) bloqueado: apagar "
            "una guarda es una decisión del dueño del repo, no del agente. Explicale qué "
            "falso positivo encontraste y que lo cree él.")

def has_secret_path(text):
    """
    ¿`text` nombra un archivo de secretos? El sufijo de ejemplo (.example, etc.)
    exime SOLO al token que lo lleva: `cat .env .env.example` sigue leyendo .env.
    """
    for m in SECRET_PATH.finditer(text):
        a, b = m.start(), m.end()
        while a > 0 and not text[a - 1].isspace() and text[a - 1] not in '"\'<>|;&()=':
            a -= 1
        while b < len(text) and not text[b].isspace() and text[b] not in '"\'<>|;&()':
            b += 1
        if not SAFE_SUFFIX.search(text[a:b]):
            return True
    return False

def check_bash(cmd):
    if NETWORK_OUT.search(cmd) or NETCAT.search(cmd):
        block("[SECURITY-GUARD] Salida de red por shell (curl/wget/nc/telnet) bloqueada. "
              "El canal sancionado del vault es WebFetch/WebSearch (o PowerShell Invoke-RestMethod "
              "para APIs). Exfiltrar por shell rompe la tríada letal — ver el README del repositorio." + DISABLE_TROJAN)
    if (READER.search(cmd) or DOT_SOURCE.search(cmd)) and has_secret_path(cmd):
        block("[SECURITY-GUARD] Acceso a un archivo de secretos/credenciales por shell bloqueado "
              "(.env / id_rsa / .pem / credentials.json / .ssh / .aws). Los secretos no se leen "
              "ni copian por shell. Ver el README del repositorio." + DISABLE_TROJAN)
    if FORCE_PUSH.search(cmd):
        block("[SECURITY-GUARD] `git push --force/-f/+ref` bloqueado: reescribir historia remota es "
              "destructivo. Usá un push normal, o pedíselo al dueño del repo explícitamente." + DISABLE_TROJAN)
    if CONTROL_WRITE.search(cmd) or CONTROL_CLOBBER.search(cmd):
        block("[SECURITY-GUARD] Escritura por shell a un archivo de control (.claude/ .githooks/ "
              ".mcp.json) bloqueada: la config se edita con la herramienta Edit, no por redirect, "
              "cp, mv, rm ni sed -i. Ver el README del repositorio." + DISABLE_TROJAN)
    if KILL_SWITCH.search(cmd):
        block(KILL_MSG)
    if HOOKS_PATH.search(cmd) or NO_VERIFY.search(QUOTED.sub('""', cmd)):
        block("[SECURITY-GUARD] Saltear el gate de git (--no-verify, commit -n, cambiar "
              "core.hooksPath) bloqueado: el pre-commit es el control universal del vault. "
              "Corregí lo que el gate marca, o pedile al dueño del repo que haga él la excepción.")
    allow()

def main():
    raw = sys.stdin.buffer.read().decode('utf-8', 'replace')
    import json
    data = json.loads(raw)
    tool = data.get('tool_name') or ''
    ti = data.get('tool_input') or {}

    if tool == 'Read':
        fp = ti.get('file_path') or ''
        if has_secret_path(fp):
            block("[SECURITY-GUARD] Lectura de un archivo de secretos/credenciales bloqueada «%s». "
                  "Refuerza el `deny` de Read. Ver el README del repositorio." % fp + DISABLE_TROJAN)
        allow()

    if tool in ('Write', 'Edit'):
        if KILL_PATH.search(ti.get('file_path') or ''):
            block(KILL_MSG)
        allow()

    if tool == 'Bash':
        cmd = ti.get('command') or ''
        check_bash(cmd)

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
