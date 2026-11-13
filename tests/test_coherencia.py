"""Coherencia del repo: cosas que tienen que seguir siendo ciertas a la vez.

No prueban una función: prueban que dos lugares que deben decir lo mismo lo
sigan diciendo. Son los tests que atrapan el "arreglé uno y me olvidé del otro".
"""
import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from conftest import BASH, HOOKS, REPO

BASELINE = REPO / "baseline-seguridad"


def texto(p):
    return Path(p).read_bytes().decode("utf-8").replace("\r\n", "\n")


def scripts_bash():
    out = sorted(HOOKS.glob("*.sh")) + sorted((REPO / ".githooks").iterdir())
    out += [REPO / n for n in ("install.sh", "update.sh", "personalize.sh")]
    out += sorted(BASELINE.glob("*.sh")) + [BASELINE / "pre-commit"]
    return [p for p in out if p.is_file()]


def scripts_python():
    return (sorted(HOOKS.glob("*.py")) + sorted((REPO / ".claude" / "scripts").glob("*.py"))
            + sorted(BASELINE.glob("*.py")))


# ── Sintaxis: un hook que no parsea "pasa" en silencio (fail-open) ───────────

@pytest.mark.parametrize("script", scripts_bash(), ids=lambda p: p.relative_to(REPO).as_posix())
def test_bash_parsea(script):
    p = subprocess.run([BASH, "-n", str(script)], capture_output=True)
    assert p.returncode == 0, p.stderr.decode("utf-8", "replace")


@pytest.mark.parametrize("script", scripts_python(), ids=lambda p: p.relative_to(REPO).as_posix())
def test_python_compila(script):
    compile(texto(script), str(script), "exec")


@pytest.mark.parametrize("script", scripts_bash(), ids=lambda p: p.relative_to(REPO).as_posix())
def test_bash_sin_crlf_en_el_repo(script):
    """Con CRLF el shebang no arranca. Se mira lo que git GUARDA y lo que .gitattributes
    promete para el checkout, no el disco (que depende del autocrlf de cada máquina)."""
    rel = script.relative_to(REPO).as_posix()
    p = subprocess.run(["git", "ls-files", "--eol", "--", rel], cwd=REPO, capture_output=True)
    info = p.stdout.decode()
    if not info.strip():
        pytest.skip("archivo nuevo, todavía sin trackear")
    assert "i/lf" in info, info
    assert "eol=lf" in info, "%s no está cubierto por un `eol=lf` en .gitattributes" % rel


# ── El kit portable no se desfasa del original ───────────────────────────────

def test_baseline_security_guard_es_el_mismo_codigo():
    """baseline-seguridad/security-guard.py = el original, cambiando solo la
    redacción de los mensajes (no hay "sección Seguridad" ni "vault" en otro repo)."""
    esperado = (texto(HOOKS / "security-guard.py")
                .replace("el README, sección Seguridad", "el README del repositorio")
                .replace("dueño del vault", "dueño del repo"))
    assert texto(BASELINE / "security-guard.py") == esperado, (
        "el baseline se desfasó: regeneralo desde .claude/hooks/security-guard.py")


@pytest.mark.parametrize("var", ["NAME_RE", "CONTENT_RE", "MD_RE"])
def test_baseline_secret_scan_usa_los_mismos_patrones(var):
    def valor(p):
        m = re.search(r"^%s='(.*)'$" % var, texto(p), re.M)
        assert m, "%s no está en %s" % (var, p)
        return m.group(1)
    assert valor(BASELINE / "secret-scan.sh") == valor(HOOKS / "secret-scan.sh")


def test_baseline_secret_scan_exime_las_mismas_rutas():
    def exentas(p):
        return re.findall(r"^\s+([\w./|-]+)\) continue ;;$", texto(p), re.M)
    assert exentas(BASELINE / "secret-scan.sh") == exentas(HOOKS / "secret-scan.sh") != []


# ── Cableado: lo que settings.json invoca existe ─────────────────────────────

def hooks_de(settings_path):
    data = json.loads(texto(settings_path))
    for evento, grupos in data.get("hooks", {}).items():
        for g in grupos:
            for h in g.get("hooks", []):
                yield evento, g.get("matcher", ""), h["command"]


def test_settings_invoca_scripts_que_existen():
    for evento, _m, cmd in hooks_de(REPO / ".claude" / "settings.json"):
        m = re.search(r"/\.claude/hooks/([\w.-]+)", cmd)
        assert m, cmd
        assert (HOOKS / m.group(1)).is_file(), "%s invoca un hook inexistente: %s" % (evento, cmd)


@pytest.mark.parametrize("settings", [REPO / ".claude" / "settings.json", BASELINE / "settings.json"],
                         ids=["vault", "baseline"])
def test_security_guard_cubre_bash_read_write_edit(settings):
    """El guard ataja la creación de kill-switches por Write/Edit: si el matcher
    vuelve a ser solo Bash|Read, esa regla queda muerta sin que nada falle."""
    matchers = [m for ev, m, cmd in hooks_de(settings)
                if ev == "PreToolUse" and "security-guard.sh" in cmd]
    assert matchers, "security-guard no está cableado en PreToolUse"
    for herramienta in ("Bash", "Read", "Write", "Edit"):
        assert any(herramienta in m.split("|") for m in matchers), herramienta


def test_el_deny_de_settings_sigue_en_pie():
    deny = json.loads(texto(REPO / ".claude" / "settings.json"))["permissions"]["deny"]
    for regla in ("Read(**/.env)", "Bash(git push --force *)", "Read(../**)"):
        assert regla in deny


def test_manifest_es_json_y_distribuye_los_tests():
    man = json.loads(texto(REPO / "vault-manifest.json"))
    assert "tests/**" in man["infrastructure"]
    assert ".github/workflows/tests.yml" in man["infrastructure"]
    assert man["version"] == texto(REPO / "VERSION").strip()


# ── mapa-agentes: humo ───────────────────────────────────────────────────────

def cargar_mapa():
    src = REPO / ".claude" / "scripts" / "mapa-agentes.py"
    spec = importlib.util.spec_from_file_location("mapa_agentes", src)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_mapa_genera_html_completo(vault):
    """recolectar + construir no revienta sobre un vault mínimo y el HTML sale
    con los datos incrustados y sin marcadores de plantilla sin resolver."""
    mapa = cargar_mapa()
    datos = mapa.recolectar_datos(vault.root, sin_maquina=True, enlace="https://example.invalid/x")
    html = mapa.construir_html(datos)
    assert html.startswith("<!doctype html>") and html.rstrip().endswith("</html>")
    assert "__DATOS__" not in html and "__ENLACE__" not in html
    assert "const D = {" in html
    json.dumps(datos)          # los datos tienen que ser serializables tal cual


def test_mapa_es_compatible_con_python_310():
    """El script declara `requires-python >= 3.10`. Una f-string con comillas
    escapadas dentro de {} solo parsea en 3.12+, y pasó inadvertida."""
    src = texto(REPO / ".claude" / "scripts" / "mapa-agentes.py")
    assert 'requires-python = ">=3.10"' in src
    compile(src, "mapa-agentes.py", "exec", dont_inherit=True, feature_version=(3, 10)) \
        if sys.version_info >= (3, 13) else __import__("ast").parse(src, feature_version=(3, 10))
