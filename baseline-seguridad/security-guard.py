#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
security-guard.py — guardián de seguridad del vault (capa 2, PreToolUse Bash|Read).

Lo invoca el wrapper security-guard.sh. Escanea el comando/ruta ENTERO y bloquea
un set ACOTADO de patrones inequívocamente peligrosos, atajando evasiones que el
`deny` por-prefijo de settings.local.json no ve (curl embebido, `cat .env`,
force-push a media línea, redirect a config). Ver el README del repositorio.

Contrato con Claude Code:
  - exit 0  -> permite la herramienta.
  - exit 2  -> bloquea; el texto de stderr se le muestra al modelo.

Diseño FAIL-OPEN: ante cualquier error/ambigüedad -> permite (exit 0). Un bug del
hook nunca debe frenar trabajo legítimo; la capa 1 (permisos) sigue vigente igual.
Reglas de alta confianza: preferimos NO bloquear antes que dar un falso positivo.

A propósito NO cubre (decisión documentada, no olvido):
  - `rm -rf`  -> demasiado falso-positivo-propenso; queda en permisos/humano.
  - Salida de red por PowerShell (Invoke-RestMethod/WebRequest) -> vía admin real
    del owner (creación de repos por API). Solo se ataja la salida por Bash.
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
    r'hexdump|base64|cp|mv|scp|rsync|dd|awk|sed|tar|zip)\b',
    re.IGNORECASE)

FORCE_PUSH = re.compile(
    r'\bgit\b[^\n]*\bpush\b[^\n]*(--force\b|--force-with-lease|(^|\s)-f\b)',
    re.IGNORECASE)

CONTROL_WRITE = re.compile(
    r'(>>?|\btee\b(\s+-a)?)\s*["\']?[^\s"\'|;&]*'
    r'(\.claude[/\\]|\.githooks[/\\]|\.mcp\.json)',
    re.IGNORECASE)

DISABLE_TROJAN = "  (Si es un falso positivo puntual, desactivá el guard: crear .vault-meta/security-guard.disabled)"

def check_bash(cmd):
    if NETWORK_OUT.search(cmd) or NETCAT.search(cmd):
        block("[SECURITY-GUARD] Salida de red por shell (curl/wget/nc/telnet) bloqueada. "
              "El canal sancionado del vault es WebFetch/WebSearch (o PowerShell Invoke-RestMethod "
              "para APIs). Exfiltrar por shell rompe la tríada letal — ver el README del repositorio." + DISABLE_TROJAN)
    if READER.search(cmd) and SECRET_PATH.search(cmd) and not SAFE_SUFFIX.search(cmd):
        block("[SECURITY-GUARD] Acceso a un archivo de secretos/credenciales por shell bloqueado "
              "(.env / id_rsa / .pem / credentials.json / .ssh / .aws). Los secretos no se leen "
              "ni copian por shell. Ver el README del repositorio." + DISABLE_TROJAN)
    if FORCE_PUSH.search(cmd):
        block("[SECURITY-GUARD] `git push --force/-f` bloqueado: reescribir historia remota es "
              "destructivo. Usá un push normal, o pedíselo al dueño del repo explícitamente." + DISABLE_TROJAN)
    if CONTROL_WRITE.search(cmd):
        block("[SECURITY-GUARD] Escritura por shell a un archivo de control (.claude/ .githooks/ "
              ".mcp.json) bloqueada: la config se edita con la herramienta Edit, no por redirect. "
              "Ver el README del repositorio." + DISABLE_TROJAN)
    allow()

def main():
    raw = sys.stdin.buffer.read().decode('utf-8', 'replace')
    import json
    data = json.loads(raw)
    tool = data.get('tool_name') or ''
    ti = data.get('tool_input') or {}

    if tool == 'Read':
        fp = ti.get('file_path') or ''
        if SECRET_PATH.search(fp) and not SAFE_SUFFIX.search(fp):
            block("[SECURITY-GUARD] Lectura de un archivo de secretos/credenciales bloqueada «%s». "
                  "Refuerza el `deny` de Read. Ver el README del repositorio." % fp + DISABLE_TROJAN)
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
    except Exception:
        # Fail-open: cualquier error inesperado no debe bloquear.
        sys.exit(0)
