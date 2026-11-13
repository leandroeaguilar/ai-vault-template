"""secret-scan: capa 3 (gate de commit y de PR). Bloquea = exit 1."""
import string

import pytest
from hypothesis import HealthCheck, given, settings, strategies as st

from conftest import build_vault, fake_secrets, out

SECRETS = fake_secrets()


def scan(vault, *args):
    return vault.hook("secret-scan.sh", args=args)


# ── Contrato ─────────────────────────────────────────────────────────────────

@pytest.mark.parametrize("kind", sorted(SECRETS))
def test_bloquea_por_contenido(vault, kind):
    vault.write("src/config.py", "TOKEN = '%s'\n" % SECRETS[kind])
    vault.git("add", "-A", check=True)
    p = scan(vault)
    assert p.returncode == 1, out(p)
    assert b"src/config.py" in p.stderr


@pytest.mark.parametrize("name", [
    ".env", ".env.production", "deploy/.env", "server.pem", "id_rsa", "ssh/id_ed25519",
    "credentials.json", "tls.key", "cert.p12", ".aws/credentials",
])
def test_bloquea_por_nombre(vault, name):
    vault.write(name, "x=1\n")
    vault.git("add", "-f", "--", name, check=True)   # -f: el .gitignore ya los frena
    p = scan(vault)
    assert p.returncode == 1, out(p)


@pytest.mark.parametrize("name", [".env.example", "owner.env.example", "notas.txt",
                                  "src/keyboard.py", "04 Knowledge/Entorno.md"])
def test_permite_nombres_inofensivos(vault, name):
    vault.write(name, "hola\n")
    vault.git("add", "-f", "--", name, check=True)
    assert scan(vault).returncode == 0


def test_sin_nada_staged(vault):
    assert scan(vault).returncode == 0


def test_solo_mira_lo_staged(vault):
    """Un secreto en el working tree que NO se va a commitear no bloquea."""
    vault.write("borrador.txt", SECRETS["aws"])
    assert scan(vault).returncode == 0


def test_escanea_la_version_staged_no_la_del_disco(vault):
    vault.write("a.txt", SECRETS["github"] + "\n")
    vault.git("add", "-A", check=True)
    vault.write("a.txt", "limpio\n")          # se "arregla" en disco, no en el index
    assert scan(vault).returncode == 1


def test_kill_switch(vault):
    vault.write("a.txt", SECRETS["aws"])
    vault.git("add", "-A", check=True)
    vault.write(".vault-meta/secret-scan.disabled", "")
    assert scan(vault).returncode == 0


def test_bloquea_el_commit_real(vault):
    """De punta a punta: `git commit` falla y el secreto no entra a la historia."""
    before = vault.head()
    vault.write("a.txt", SECRETS["aws"])
    vault.git("add", "-A", check=True)
    p = vault.commit("intento")
    assert p.returncode != 0, out(p)
    assert vault.head() == before


def test_modo_range(vault):
    base = vault.head()
    vault.write("a.txt", SECRETS["slack"])
    vault.commit_all("con secreto")
    assert scan(vault, "--range", base, "HEAD").returncode == 1
    assert scan(vault, "--range", "HEAD", "HEAD").returncode == 0


# ── Adversarial ──────────────────────────────────────────────────────────────

def test_ruta_con_tilde_y_espacios(vault):
    vault.write("04 Knowledge/Automatización/contraseña nueva.txt", SECRETS["aws"])
    vault.git("add", "-A", check=True)
    assert scan(vault).returncode == 1


def test_secreto_agregado_en_un_archivo_renombrado(vault):
    """`git mv` + agregar el secreto: git lo reporta como R(ename), no como M.
    Un filtro ACM lo dejaba pasar sin escanear."""
    vault.write("config.txt", "".join("linea %d\n" % i for i in range(40)))
    vault.commit_all("config")
    vault.git("mv", "config.txt", "ajustes.txt", check=True)
    with open(vault.root / "ajustes.txt", "a", encoding="utf-8") as fh:
        fh.write("clave = %s\n" % SECRETS["aws"])
    vault.git("add", "-A", check=True)
    assert b"R" in vault.git("diff", "--cached", "--name-status").stdout  # precondición
    p = scan(vault)
    assert p.returncode == 1, out(p)


def test_archivo_sensible_renombrado(vault):
    vault.write("notas.txt", "".join("linea %d\n" % i for i in range(40)))
    vault.commit_all("notas")
    vault.git("mv", "notas.txt", "server.pem", check=True)
    assert scan(vault).returncode == 1


@pytest.mark.parametrize("name", [
    "tools/mi-secret-scan.sh",          # se hacía pasar por el scanner
    "src/security-guard.py",
    "x/security-audit.sh",
])
def test_la_exencion_de_los_scanners_no_es_por_nombre_suelto(vault, name):
    """Solo los scanners REALES (rutas exactas) están exentos del chequeo de contenido."""
    vault.write(name, "K=%s\n" % SECRETS["github"])
    vault.git("add", "-A", check=True)
    assert scan(vault).returncode == 1


def test_los_scanners_reales_siguen_exentos(vault):
    """Los scanners contienen los patrones a propósito: tocarlos no debe bloquear."""
    for rel in (".claude/hooks/secret-scan.sh", ".claude/hooks/security-audit.sh"):
        with open(vault.root / rel, "a", encoding="utf-8", newline="\n") as fh:
            fh.write("# tocado\n")
    vault.git("add", "-A", check=True)
    assert scan(vault).returncode == 0


def test_secreto_en_markdown_con_formato_de_clave_privada(vault):
    """Los .md hablan de secretos (por eso no se escanean por patrón de token),
    pero una clave privada pegada entera en una nota no es prosa."""
    vault.write("04 Knowledge/Servidor.md",
                "# Servidor\n\n%s\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASC\n" % SECRETS["pem"])
    vault.git("add", "-A", check=True)
    assert scan(vault).returncode == 1


def test_markdown_que_menciona_tokens_no_bloquea(vault):
    vault.write("04 Knowledge/Tokens.md",
                "# Tokens\n\nUn token de GitHub empieza con `ghp_` y uno de AWS con `AKIA`.\n")
    vault.git("add", "-A", check=True)
    assert scan(vault).returncode == 0


# ── Propiedad: el contexto no esconde el secreto ─────────────────────────────

relleno = st.text(alphabet=string.ascii_letters + string.digits + " =:'\"/._-{}[]",
                  max_size=60)


@pytest.fixture(scope="module")
def shared_vault(tmp_path_factory):
    return build_vault(tmp_path_factory.mktemp("scan") / "vault")


@settings(max_examples=8, deadline=None,
          suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(kind=st.sampled_from(sorted(SECRETS)), antes=relleno, despues=relleno,
       arriba=st.lists(relleno, max_size=5))
def test_un_secreto_se_detecta_con_cualquier_contexto(shared_vault, kind, antes, despues, arriba):
    v = shared_vault
    # Separador no alfanumérico: pegado a más letras el token dejaría de ser ese token.
    linea = antes + " " + SECRETS[kind] + " " + despues
    v.write("datos.txt", "\n".join(arriba + [linea]) + "\n")
    v.git("add", "-A", check=True)
    try:
        p = v.hook("secret-scan.sh")
        assert p.returncode == 1, out(p)
    finally:
        v.git("reset", "-q", "--hard", check=True)
