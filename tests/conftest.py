"""Infraestructura común de los tests de las guardas.

Cada test corre contra un VAULT DESCARTABLE: un repo git recién creado en un
directorio temporal, con una copia de los hooks reales. Nunca se toca el repo
de trabajo.

Dos formas de ejercitar el código:
  - caja negra  -> `vault.hook(...)` / `vault.git("commit", ...)`: se ejecuta el
                   script real, como lo haría el harness o git. Es lo que prueba
                   el contrato (códigos de salida), que es lo único que importa
                   en guardas fail-open: un script roto "pasa" en silencio.
  - caja blanca -> `load_hook("generate-index")`: importa el módulo para probar
                   funciones puras con Hypothesis sin pagar un proceso por caso.

Los secretos de prueba se ARMAN EN RUNTIME (ver `fake_secrets`): ningún archivo
de tests contiene un token con formato válido, así el propio secret-scan no
bloquea el commit de los tests.
"""
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import pytest

# Perfiles de Hypothesis. `dev` (por defecto) es rápido para iterar; `ci` busca
# más. Elegir con HYPOTHESIS_PROFILE=ci. Sin base de datos de ejemplos: no deja
# un directorio .hypothesis/ en la raíz del vault (aparecería en los índices).
from hypothesis import settings as _hsettings

_hsettings.register_profile("dev", database=None)
_hsettings.register_profile("ci", database=None, max_examples=200, deadline=None)
_hsettings.load_profile(os.environ.get("HYPOTHESIS_PROFILE", "dev"))

REPO = Path(__file__).resolve().parent.parent
HOOKS = REPO / ".claude" / "hooks"


def _find_bash():
    """Git Bash en Windows (no el bash de WSL de System32); `bash` en el resto."""
    if os.name == "nt":
        git = shutil.which("git")
        if git:
            for up in (Path(git).parent.parent, Path(git).parent.parent.parent):
                cand = up / "bin" / "bash.exe"
                if cand.is_file():
                    return str(cand)
    return shutil.which("bash") or "bash"


BASH = _find_bash()


def clean_env(**extra):
    """Entorno sin variables que cambien el comportamiento de git o de los hooks."""
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and k not in (
               "CLAUDE_PROJECT_DIR", "VERIFIER_STRICT", "SENTINELS_OK",
               "ALLOW_FORCE_PUSH", "ALLOW_TEMPLATE_PUSH", "WIKI_LOCK_AGENT")}
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "PYTHONUTF8": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
    })
    env.update(extra)
    return env


class Vault:
    """Un vault descartable con los hooks reales instalados."""

    def __init__(self, root: Path):
        self.root = root

    # ── ejecución ────────────────────────────────────────────────────────────
    def run(self, argv, stdin=None, env=None, cwd=None):
        if isinstance(stdin, str):
            stdin = stdin.encode("utf-8")
        return subprocess.run(
            argv, input=stdin, cwd=str(cwd or self.root),
            env=clean_env(**(env or {})),
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)

    def git(self, *args, env=None, check=False):
        argv = ["git", "-c", "core.quotepath=false", *args]
        p = self.run(argv, env=env)
        # Windows: el antivirus/indexador a veces retiene un archivo recién creado
        # en %TEMP% y git falla con "Permission denied". Es del entorno, no de lo
        # que se prueba: se reintenta SOLO ese error y SOLO en comandos de armado.
        for _ in range(3):
            if not (check and p.returncode != 0 and b"Permission denied" in p.stderr):
                break
            time.sleep(0.5)
            p = self.run(argv, env=env)
        if check and p.returncode != 0:
            raise AssertionError("git %s falló:\n%s" % (" ".join(args), out(p)))
        return p

    def hook(self, name, stdin=None, args=(), env=None):
        """Corre un hook de .claude/hooks/ (.sh con bash, .py con python)."""
        path = self.root / ".claude" / "hooks" / name
        env = dict(env or {})
        env.setdefault("CLAUDE_PROJECT_DIR", str(self.root))
        argv = [sys.executable, str(path)] if name.endswith(".py") else [BASH, str(path)]
        return self.run(argv + list(args), stdin=stdin, env=env)

    def tool(self, hook_name, tool_name, **tool_input):
        """Simula el evento PreToolUse/PostToolUse que el harness manda por stdin."""
        payload = json.dumps({"tool_name": tool_name, "tool_input": tool_input})
        return self.hook(hook_name, stdin=payload)

    # ── archivos ─────────────────────────────────────────────────────────────
    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(text.encode("utf-8"))
        return p

    def read(self, rel):
        return (self.root / rel).read_bytes().decode("utf-8")

    def commit(self, msg="test", *args, env=None):
        return self.git("commit", "-q", "-m", msg, *args, env=env)

    def commit_all(self, msg="base"):
        """Stagea todo y commitea SIN hooks (para armar el estado inicial)."""
        self.git("add", "-A", check=True)
        self.git("commit", "-q", "--no-verify", "-m", msg, check=True)

    def status(self):
        return self.git("status", "--porcelain").stdout.decode("utf-8")

    def head(self):
        return self.git("rev-parse", "HEAD").stdout.decode().strip()


def out(p):
    """stdout+stderr de un proceso, para mensajes de aserción legibles."""
    return (p.stdout + b"\n" + p.stderr).decode("utf-8", "replace")


def build_vault(root: Path) -> Vault:
    root.mkdir(parents=True, exist_ok=True)
    v = Vault(root)
    v.git("init", "-q", "-b", "main", check=True)
    for k, val in (("user.name", "Test"), ("user.email", "test@example.invalid"),
                   ("core.hooksPath", ".githooks"), ("core.autocrlf", "false"),
                   ("commit.gpgsign", "false")):
        v.git("config", k, val, check=True)
    shutil.copytree(HOOKS, root / ".claude" / "hooks",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(REPO / ".githooks", root / ".githooks")
    for f in (".gitattributes", ".gitignore", "vault.conf"):
        shutil.copy2(REPO / f, root / f)
    v.write("01 Index/Nota base.md", NOTE.format(title="Nota base", id="IX-001"))
    v.commit_all("base")
    return v


NOTE = """---
type: nota
title: {title}
description: Nota de prueba.
estado: 🟢 Activo
generated:
  by: test
  at: 2026-01-01T00:00:00
id: {id}
---
# {title}

Cuerpo.
"""


@pytest.fixture
def vault(tmp_path):
    return build_vault(tmp_path / "vault")


@pytest.fixture
def note():
    """Fábrica de notas con frontmatter válido."""
    def _note(title="Nota", id="KN-001", body=""):
        return NOTE.format(title=title, id=id) + body
    return _note


def load_hook(name):
    """Importa un script de .claude/hooks/ como módulo (los nombres llevan guion)."""
    path = HOOKS / (name + ".py")
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    mod = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(HOOKS))
    try:
        spec.loader.exec_module(mod)
    finally:
        sys.path.remove(str(HOOKS))
    return mod


def fake_secrets():
    """Tokens con FORMATO de secreto, armados en runtime (ver docstring del módulo)."""
    a = "A"
    return {
        "aws": "AKI" + a + "IOSFODNN7" + "EXAMPLE",
        "github": "gh" + "p_" + "a1B2" * 9,
        "github_pat": "github" + "_pat_" + "x9" * 12,
        "slack": "xox" + "b-" + "1234567890-abcdef",
        "google": "AI" + "za" + "b" * 35,
        "pem": "-----BEGIN RSA " + "PRIVATE KEY-----",
        "openssh": "-----BEGIN OPENSSH " + "PRIVATE KEY-----",
    }


@pytest.fixture(name="fake_secrets")
def _fake_secrets():
    return fake_secrets()
