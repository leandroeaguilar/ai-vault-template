"""El gate universal de git (pre-commit / pre-push) y el auto-commit del harness.

Tests de INTEGRACIÓN: se ejecuta `git commit` / `git push` de verdad contra un
vault descartable y se mira el estado resultante del repo.
"""
import json

import pytest

from conftest import BASH, out


# ── pre-commit: orquestación ─────────────────────────────────────────────────

def test_commit_limpio_pasa_y_regenera_el_indice(vault, note):
    vault.write("04 Knowledge/Tema.md", note("Tema", "KN-001"))
    vault.git("add", "-A", check=True)
    p = vault.commit("nota")
    assert p.returncode == 0, out(p)
    archivos = vault.git("show", "--name-only", "--format=", "HEAD").stdout.decode()
    assert "04 Knowledge/Tema.md" in archivos
    assert "04 Knowledge/index.md" in archivos, "el index.md generado no entró al commit"
    assert "[Tema](<Tema.md>)" in vault.read("04 Knowledge/index.md")
    assert vault.status() == "", "el commit tiene que dejar el árbol limpio"


def test_indice_en_carpeta_con_tilde(vault, note):
    vault.write("04 Knowledge/Automatización/Guía.md", note("Guía", "KN-002"))
    vault.git("add", "-A", check=True)
    assert vault.commit("nota").returncode == 0
    assert "Guía" in vault.read("04 Knowledge/Automatización/index.md")
    assert vault.status() == ""


def test_avisa_si_toca_archivos_de_control(vault):
    vault.write(".claude/hooks/nuevo.sh", "#!/usr/bin/env bash\n")
    vault.git("add", "-A", check=True)
    p = vault.commit("hook")
    assert p.returncode == 0, out(p)
    assert "CONTROL" in out(p)


# ── verify-commit: frontmatter ───────────────────────────────────────────────

def verify(vault, *args, env=None):
    return vault.hook("verify-commit.sh", args=args, env=env)


SIN_FM = "# Sin frontmatter\n\ntexto\n"


def test_frontmatter_completo_ok(vault, note):
    vault.write("04 Knowledge/Tema.md", note())
    vault.git("add", "-A", check=True)
    p = verify(vault)
    assert p.returncode == 0 and b"OK" in p.stdout, out(p)


def test_sin_frontmatter_avisa_pero_no_bloquea(vault):
    vault.write("04 Knowledge/Tema.md", SIN_FM)
    vault.git("add", "-A", check=True)
    p = verify(vault)
    assert p.returncode == 0
    assert b"sin frontmatter" in p.stdout


def test_modo_estricto_bloquea(vault):
    vault.write("04 Knowledge/Tema.md", SIN_FM)
    vault.git("add", "-A", check=True)
    assert verify(vault, env={"VERIFIER_STRICT": "1"}).returncode == 1
    vault.write(".vault-meta/verifier.strict", "")
    assert verify(vault).returncode == 1
    assert vault.commit("intento").returncode != 0


@pytest.mark.parametrize("campo,reportado", [
    ("type", "type"), ("estado", "estado"), ("generated", "generated"), ("id", "id")])
def test_reporta_cada_campo_obligatorio_faltante(vault, note, campo, reportado):
    lineas = [ln for ln in note().split("\n")
              if not ln.startswith(campo + ":") and not ln.startswith("  ")]
    vault.write("04 Knowledge/Tema.md", "\n".join(lineas))
    vault.git("add", "-A", check=True)
    p = verify(vault, env={"VERIFIER_STRICT": "1"})
    assert p.returncode == 1
    assert ("falta(n) campo(s): " + reportado).encode() in p.stdout, out(p)


@pytest.mark.parametrize("campo", ["title", "description"])
def test_title_y_description_son_solo_aviso(vault, note, campo):
    """SOP Documentación §4.1: title y description son warn-only, también en estricto."""
    texto = "\n".join(ln for ln in note().split("\n") if not ln.startswith(campo + ":"))
    vault.write("04 Knowledge/Tema.md", texto)
    vault.git("add", "-A", check=True)
    p = verify(vault, env={"VERIFIER_STRICT": "1"})
    assert p.returncode == 0
    assert ("sin " + campo).encode() in p.stdout, out(p)


def test_acepta_las_claves_previas_a_okf(vault):
    vault.write("04 Knowledge/Vieja.md",
                "---\ntipo_doc: nota\ntitle: V\ndescription: d\nestado: x\n"
                "ultima_revision: 2026-01-01\nid: KN-9\n---\n# V\n")
    vault.git("add", "-A", check=True)
    assert verify(vault, env={"VERIFIER_STRICT": "1"}).returncode == 0


def test_tags_con_numeral_avisa(vault, note):
    vault.write("04 Knowledge/Tema.md", note().replace("id: ", "tags: [#malo]\nid: "))
    vault.git("add", "-A", check=True)
    assert b"tags con '#'" in verify(vault).stdout


@pytest.mark.parametrize("rel", ["03 Proyectos/Libre.md", "05 Diario/2026-01-01.md",
                                 "04 Knowledge/index.md", "00 Sistema/001_plantillas/P.md",
                                 "README.md"])
def test_fuera_de_zona_no_se_exige(vault, rel):
    vault.write(rel, SIN_FM)
    vault.git("add", "-A", check=True)
    assert verify(vault, env={"VERIFIER_STRICT": "1"}).returncode == 0


def test_carpeta_con_tilde_tambien_se_verifica(vault):
    """Sin core.quotepath=false git escapa la ruta y la nota se salteaba en silencio."""
    vault.write("04 Knowledge/Automatización/Tema.md", SIN_FM)
    vault.git("add", "-A", check=True)
    assert verify(vault, env={"VERIFIER_STRICT": "1"}).returncode == 1


def test_nota_renombrada_y_vaciada_se_verifica(vault, note):
    cuerpo = "".join("linea %d\n" % i for i in range(40))
    vault.write("04 Knowledge/A.md", note() + cuerpo)
    vault.commit_all("a")
    vault.git("mv", "04 Knowledge/A.md", "04 Knowledge/B.md", check=True)
    vault.write("04 Knowledge/B.md", "# sin frontmatter\n" + cuerpo)
    vault.git("add", "-A", check=True)
    assert b"R" in vault.git("diff", "--cached", "--name-status").stdout  # precondición
    assert verify(vault, env={"VERIFIER_STRICT": "1"}).returncode == 1


def test_verify_modo_range(vault):
    base = vault.head()
    vault.write("04 Knowledge/Tema.md", SIN_FM)
    vault.commit_all("sin fm")
    assert verify(vault, "--range", base, "HEAD", env={"VERIFIER_STRICT": "1"}).returncode == 1


# ── modo equipo: gate de rama y vault-conf ───────────────────────────────────

def set_conf(vault, linea):
    conf = "\n".join(ln for ln in vault.read("vault.conf").split("\n")
                     if not ln.startswith("VAULT_MODE"))
    vault.write("vault.conf", conf + "\n" + linea + "\n")
    vault.commit_all("conf")


@pytest.mark.parametrize("linea", [
    "VAULT_MODE=equipo", 'VAULT_MODE="equipo"', "VAULT_MODE = equipo",
    "  VAULT_MODE='equipo'  ", "VAULT_MODE=equipo\r"])
def test_gate_de_rama_bloquea_en_main(vault, note, linea):
    set_conf(vault, linea)
    vault.write("04 Knowledge/Tema.md", note())
    vault.git("add", "-A", check=True)
    p = vault.commit("en main")
    assert p.returncode != 0, out(p)
    assert "VAULT_MODE=equipo" in out(p)


def test_gate_de_rama_permite_en_rama_de_trabajo(vault, note):
    set_conf(vault, "VAULT_MODE=equipo")
    vault.git("switch", "-q", "-c", "le/tema", check=True)
    vault.write("04 Knowledge/Tema.md", note())
    vault.git("add", "-A", check=True)
    assert vault.commit("en rama").returncode == 0


def test_modo_personal_no_tiene_gate(vault, note):
    vault.write("04 Knowledge/Tema.md", note())
    vault.git("add", "-A", check=True)
    assert vault.commit("en main").returncode == 0


def test_vault_conf_no_ejecuta_codigo(vault, note):
    """vault.conf se PARSEA: un valor con sustitución de comandos es texto, no shell."""
    set_conf(vault, 'VAULT_MODE=$(touch PWNED)\nMAIN_BRANCH=`touch PWNED2`')
    vault.write("04 Knowledge/Tema.md", note())
    vault.git("add", "-A", check=True)
    vault.commit("x")
    assert not (vault.root / "PWNED").exists()
    assert not (vault.root / "PWNED2").exists()


def conf_value(vault, expr):
    script = '. .claude/hooks/vault-conf.sh; printf "%%s" "$(%s)"' % expr
    return vault.run([BASH, "-c", script]).stdout.decode()


def test_vault_conf_lectura(vault):
    vault.write("vault.conf", "# comentario\nA=1\nB = \"dos palabras\" \nC=''\nVAULT_MODE=equipo\r\n")
    assert conf_value(vault, "vault_conf A x") == "1"
    assert conf_value(vault, "vault_conf B x") == "dos palabras"
    assert conf_value(vault, "vault_conf C por-defecto") == "por-defecto"
    assert conf_value(vault, "vault_conf NO_ESTA por-defecto") == "por-defecto"
    assert conf_value(vault, "vault_mode") == "equipo"


def test_vault_mode_cae_a_owner_env_y_a_personal(vault):
    vault.write("vault.conf", "MAIN_BRANCH=main\n")
    assert conf_value(vault, "vault_mode") == "personal"
    vault.write("owner.env", 'VAULT_MODE="equipo"\n')
    assert conf_value(vault, "vault_mode") == "equipo"


# ── auto-commit (PostToolUse Write|Edit) ─────────────────────────────────────

def auto_commit(vault, rel, env=None):
    payload = json.dumps({"tool_name": "Write",
                          "tool_input": {"file_path": str(vault.root / rel)}})
    return vault.hook("auto-commit.sh", stdin=payload, env=env)


def last_commit(vault):
    return vault.git("log", "-1", "--format=%an|%ae|%s").stdout.decode().strip()


def test_auto_commit_commitea_solo_el_archivo_tocado(vault, note):
    vault.write("04 Knowledge/Tema.md", note("Tema"))
    vault.write("04 Knowledge/Otra.md", note("Otra"))        # cambio ajeno, sin tocar
    assert auto_commit(vault, "04 Knowledge/Tema.md").returncode == 0
    assert last_commit(vault) == "Claude Code|claude@agent.local|chore(agent): auto-commit Tema.md"
    archivos = vault.git("show", "--name-only", "--format=", "HEAD").stdout.decode()
    assert "Tema.md" in archivos and "Otra.md" not in archivos
    assert "Otra.md" in vault.status()


def test_auto_commit_deja_el_staging_limpio_con_indice_nuevo(vault, note):
    """Regresión: el commit parcial dejaba el index.md recién creado como
    `D` staged — el siguiente `git commit` manual lo borraba del repo."""
    vault.write("04 Knowledge/Tema.md", note("Tema"))
    auto_commit(vault, "04 Knowledge/Tema.md")
    assert "auto-commit Tema.md" in last_commit(vault)
    assert vault.status() == "", "staging sucio tras el auto-commit:\n" + vault.status()


def test_auto_commit_deja_el_staging_limpio_con_indice_existente(vault, note):
    """Regresión: con el índice ya existente quedaba `MM` — la versión vieja staged."""
    vault.write("04 Knowledge/Tema.md", note("Tema"))
    auto_commit(vault, "04 Knowledge/Tema.md")
    vault.write("04 Knowledge/Tema.md", note("Tema").replace("Nota de prueba.", "Otra descripción."))
    auto_commit(vault, "04 Knowledge/Tema.md")
    assert "Otra descripción." in vault.read("04 Knowledge/index.md")
    assert vault.status() == "", "staging sucio tras el auto-commit:\n" + vault.status()


def test_auto_commit_seguido_de_commit_manual_no_pierde_el_indice(vault, note):
    vault.write("04 Knowledge/Tema.md", note("Tema"))
    auto_commit(vault, "04 Knowledge/Tema.md")
    vault.write("03 Proyectos/Libre.md", "# Libre\n")
    vault.git("add", "03 Proyectos/Libre.md", check=True)
    assert vault.commit("manual").returncode == 0
    assert "04 Knowledge/index.md" in vault.git("ls-files").stdout.decode()
    assert "[Tema](<Tema.md>)" in vault.git("show", "HEAD:04 Knowledge/index.md").stdout.decode()


@pytest.mark.parametrize("rel", [".claude/commands/x.md", ".vault-meta/nota.md",
                                 "script.py", "datos.json"])
def test_auto_commit_ignora_lo_que_no_es_contenido(vault, rel):
    before = vault.head()
    vault.write(rel, "# x\n")
    auto_commit(vault, rel)
    assert vault.head() == before


def test_auto_commit_kill_switch_marca_la_sesion_igual(vault, note):
    before = vault.head()
    vault.write(".vault-meta/autocommit.disabled", "")
    vault.write("04 Knowledge/Tema.md", note())
    auto_commit(vault, "04 Knowledge/Tema.md")
    assert vault.head() == before
    assert (vault.root / ".vault-meta" / "session-touched").exists()


def test_auto_commit_respeta_secret_scan(vault, fake_secrets):
    """El auto-commit pasa por el pre-commit: una clave privada en una nota no entra."""
    before = vault.head()
    vault.write("04 Knowledge/Servidor.md", "# S\n\n%s\nMIIEvQIBADANBg\n" % fake_secrets["pem"])
    assert auto_commit(vault, "04 Knowledge/Servidor.md").returncode == 0
    assert vault.head() == before


def test_auto_commit_no_commitea_en_main_en_modo_equipo(vault, note):
    set_conf(vault, "VAULT_MODE = equipo")      # con espacios: antes el auto-commit no lo leía
    before = vault.head()
    vault.write("04 Knowledge/Tema.md", note())
    auto_commit(vault, "04 Knowledge/Tema.md")
    assert vault.head() == before


def test_auto_commit_ruta_fuera_del_vault_deja_rastro(vault, tmp_path):
    before = vault.head()
    afuera = tmp_path / "afuera.md"
    afuera.write_text("# x\n", encoding="utf-8")
    payload = json.dumps({"tool_input": {"file_path": str(afuera)}})
    assert vault.hook("auto-commit.sh", stdin=payload).returncode == 0
    assert vault.head() == before
    log = vault.root / ".vault-meta" / "guard-errors.log"
    assert log.is_file() and "auto-commit" in log.read_text(encoding="utf-8")


@pytest.mark.parametrize("stdin", ["", "{}", "basura", '{"tool_input":{}}'])
def test_auto_commit_entrada_malformada(vault, stdin):
    before = vault.head()
    assert vault.hook("auto-commit.sh", stdin=stdin).returncode == 0
    assert vault.head() == before


@pytest.mark.parametrize("nombre", ["Nota con espacios.md", "Decisión (v2) — año.md",
                                    "a&b.md", "100% listo.md", "it's.md"])
def test_auto_commit_nombres_raros(vault, note, nombre):
    rel = "04 Knowledge/" + nombre
    vault.write(rel, note("X"))
    auto_commit(vault, rel)
    assert nombre in vault.git("show", "--name-only", "--format=", "HEAD").stdout.decode()
    assert vault.status() == ""


# ── pre-push ─────────────────────────────────────────────────────────────────

@pytest.fixture
def pushable(vault, tmp_path):
    remoto = tmp_path / "remoto.git"
    vault.git("init", "-q", "--bare", str(remoto), check=True)
    vault.git("remote", "add", "origin", str(remoto), check=True)
    vault.git("push", "-q", "origin", "main", check=True)
    return vault


def nuevo_commit(vault, nombre):
    vault.write(nombre, "x\n")
    vault.commit_all(nombre)


def reescribir_historia(vault):
    vault.git("reset", "-q", "--hard", "HEAD~1", check=True)
    nuevo_commit(vault, "divergente.txt")


def test_push_fast_forward_pasa(pushable):
    nuevo_commit(pushable, "a.txt")
    assert pushable.git("push", "-q", "origin", "main").returncode == 0


def test_force_push_bloquea(pushable):
    nuevo_commit(pushable, "a.txt")
    pushable.git("push", "-q", "origin", "main", check=True)
    reescribir_historia(pushable)
    p = pushable.git("push", "--force", "origin", "main")
    assert p.returncode != 0
    assert b"NO fast-forward" in p.stderr, out(p)


@pytest.mark.parametrize("args", [["--force-with-lease", "origin", "main"],
                                  ["origin", "+main"],
                                  ["origin", "+HEAD:main"]])
def test_force_push_por_cualquier_via_bloquea(pushable, args):
    """Se detecta el EFECTO (no fast-forward), no cómo se escribió el flag."""
    nuevo_commit(pushable, "a.txt")
    pushable.git("push", "-q", "origin", "main", check=True)
    reescribir_historia(pushable)
    assert pushable.git("push", *args).returncode != 0


def test_force_que_resulta_fast_forward_pasa(pushable):
    nuevo_commit(pushable, "a.txt")
    assert pushable.git("push", "-q", "--force", "origin", "main").returncode == 0


def test_force_push_con_escape_explicito(pushable):
    nuevo_commit(pushable, "a.txt")
    pushable.git("push", "-q", "origin", "main", check=True)
    reescribir_historia(pushable)
    p = pushable.git("push", "-q", "--force", "origin", "main", env={"ALLOW_FORCE_PUSH": "1"})
    assert p.returncode == 0, out(p)


def test_rama_nueva_y_borrado_de_rama(pushable):
    pushable.git("switch", "-q", "-c", "le/tema", check=True)
    nuevo_commit(pushable, "a.txt")
    assert pushable.git("push", "-q", "origin", "le/tema").returncode == 0
    p = pushable.git("push", "origin", "--delete", "le/tema")
    assert p.returncode == 0
    assert "BORRANDO".encode() in p.stderr


@pytest.mark.parametrize("repo", ["ai-vault-template", "sistema-maestro-pro",
                                  "sistema-maestro-toolkit"])
def test_no_pushea_un_vault_personalizado_al_template(vault, tmp_path, repo):
    remoto = tmp_path / (repo + ".git")
    vault.git("init", "-q", "--bare", str(remoto), check=True)
    vault.git("remote", "add", "origin", str(remoto), check=True)
    vault.write("owner.env", "OWNER_NAME=Alguien\n")
    p = vault.git("push", "origin", "main")
    assert p.returncode != 0
    assert "TEMPLATE".encode() in p.stderr, out(p)
    assert vault.git("push", "-q", "origin", "main",
                     env={"ALLOW_TEMPLATE_PUSH": "1"}).returncode == 0


def test_el_mantenedor_sin_owner_env_si_pushea_al_template(vault, tmp_path):
    remoto = tmp_path / "ai-vault-template.git"
    vault.git("init", "-q", "--bare", str(remoto), check=True)
    vault.git("remote", "add", "origin", str(remoto), check=True)
    assert vault.git("push", "-q", "origin", "main").returncode == 0
