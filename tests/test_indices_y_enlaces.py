"""generate-index y harden-links: propiedades sobre vaults generados al azar.

Son los scripts que REESCRIBEN notas e índices. Lo que importa de ellos no es un
ejemplo puntual sino invariantes: correrlos dos veces no cambia nada, y nunca
tocan lo que no les corresponde.
"""
import os
import tempfile
from pathlib import Path

from hypothesis import given, settings, strategies as st

from conftest import load_hook

gen = load_hook("generate-index")
harden = load_hook("harden-links")

# Nombres válidos en Windows y Linux, con espacios y tildes como los del vault real.
ALFABETO = "abcdefghijklmnopqrstuvwxyzáéíóúñ ABCDEFG0123456789-_()"
nombre = (st.text(alphabet=ALFABETO, min_size=1, max_size=18)
          .map(str.strip).filter(lambda s: s and not s.endswith(".")
                                 and s.lower() not in ("index", "log", "con", "nul", "aux", "prn")))
# Una línea de texto libre (título, descripción): cualquier cosa imprimible sin saltos.
linea = st.text(alphabet=st.characters(blacklist_categories=("Cs", "Cc", "Zl", "Zp")),
                max_size=40).map(str.strip)
tipo = st.sampled_from(["nota", "sop", "moc", "", "Guía"])


@st.composite
def nota(draw):
    fm = []
    t, titulo, desc = draw(tipo), draw(linea), draw(linea)
    if t:
        fm.append("type: " + t)
    if titulo and draw(st.booleans()):
        fm.append("title: " + titulo)
    if desc and draw(st.booleans()):
        fm.append("description: " + desc)
    cabecera = "---\n" + "\n".join(fm) + "\n---\n" if draw(st.booleans()) else ""
    h1 = "# " + draw(linea) + "\n" if draw(st.booleans()) else ""
    return cabecera + h1 + "\ncuerpo\n"


@st.composite
def arbol(draw):
    """{ruta relativa: contenido} con hasta dos niveles de carpetas."""
    carpetas = draw(st.lists(nombre, min_size=1, max_size=3, unique_by=str.casefold))
    archivos = {}
    for c in carpetas:
        base = c
        if draw(st.booleans()):
            base = c + "/" + draw(nombre)
        for n in draw(st.lists(nombre, min_size=0, max_size=3, unique_by=str.casefold)):
            archivos[base + "/" + n + ".md"] = draw(nota())
    return archivos


def materializar(root, archivos):
    for rel, texto in archivos.items():
        p = Path(root, rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(texto.encode("utf-8"))


def snapshot(root, solo=None):
    out = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            if solo is None or solo(f):
                p = Path(base, f)
                out[p.relative_to(root).as_posix()] = p.read_bytes()
    return out


def run_generate(root, monkeypatch_target=gen):
    """Regenera todos los índices de `root` (en proceso)."""
    monkeypatch_target.VAULT = str(root)
    monkeypatch_target.has_knowledge.__defaults__[0].clear()   # caché entre corridas
    for d in monkeypatch_target.all_dirs():
        nuevo = monkeypatch_target.build_index(
            d, is_root=os.path.normpath(d) == os.path.normpath(str(root)))
        Path(d, "index.md").write_bytes(nuevo.encode("utf-8"))


es_indice = lambda f: f.lower() == "index.md"      # noqa: E731
no_es_indice = lambda f: f.lower() != "index.md"   # noqa: E731


# ── generate-index ───────────────────────────────────────────────────────────

@settings(max_examples=60, deadline=None)
@given(arbol())
def test_generate_index_es_idempotente(archivos):
    """Regenerar sobre un vault ya indexado da exactamente los mismos index.md."""
    with tempfile.TemporaryDirectory() as root:
        materializar(root, archivos)
        run_generate(root)
        primera = snapshot(root, es_indice)
        run_generate(root)
        assert snapshot(root, es_indice) == primera


@settings(max_examples=60, deadline=None)
@given(arbol())
def test_generate_index_no_toca_las_notas(archivos):
    with tempfile.TemporaryDirectory() as root:
        materializar(root, archivos)
        antes = snapshot(root, no_es_indice)
        run_generate(root)
        assert snapshot(root, no_es_indice) == antes


@settings(max_examples=60, deadline=None)
@given(arbol())
def test_generate_index_lista_cada_nota_una_vez_y_solo_las_que_existen(archivos):
    with tempfile.TemporaryDirectory() as root:
        materializar(root, archivos)
        run_generate(root)
        for rel in archivos:
            carpeta, archivo = os.path.split(rel)
            indice = Path(root, carpeta, "index.md").read_text(encoding="utf-8")
            destinos = [m.group("target") for m in map(gen.ENTRY_RE.match, indice.splitlines()) if m]
            assert destinos.count(archivo) == 1, (rel, indice)
        for rel, data in snapshot(root, es_indice).items():
            carpeta = os.path.dirname(rel)
            for ln in data.decode("utf-8").splitlines():
                m = gen.ENTRY_RE.match(ln)
                if m:
                    assert Path(root, carpeta, m.group("target")).exists(), (rel, ln)


@settings(max_examples=40, deadline=None)
@given(arbol(), linea.filter(bool))
def test_generate_index_preserva_la_descripcion_curada_de_subcarpetas(archivos, curada):
    """La descripción de un subdirectorio se escribe a mano y debe sobrevivir."""
    with tempfile.TemporaryDirectory() as root:
        materializar(root, archivos)
        run_generate(root)
        raiz = Path(root, "index.md")
        lineas = raiz.read_text(encoding="utf-8").split("\n")
        idx = [i for i, ln in enumerate(lineas) if ln.endswith("/index.md>)")]
        if not idx:
            return
        lineas[idx[0]] += " - " + curada
        raiz.write_bytes("\n".join(lineas).encode("utf-8"))
        run_generate(root)
        assert lineas[idx[0]] in raiz.read_text(encoding="utf-8").split("\n")


def test_generate_index_staged_solo_regenera_carpetas_con_md_staged(vault, note):
    vault.write("04 Knowledge/A.md", note("A"))
    vault.write("03 Proyectos/B.md", note("B"))
    vault.git("add", "04 Knowledge/A.md", check=True)
    p = vault.hook("generate-index.py", args=["--staged"])
    # En Windows la ruta sale con «\»; `git add` del pre-commit acepta las dos.
    assert p.stdout.decode().strip().replace("\\", "/") == "04 Knowledge/index.md"
    assert not (vault.root / "03 Proyectos" / "index.md").exists()


def test_generate_index_kill_switch(vault, note):
    vault.write(".vault-meta/index-gen.disabled", "")
    vault.write("04 Knowledge/A.md", note("A"))
    assert vault.hook("generate-index.py").returncode == 0
    assert not (vault.root / "04 Knowledge" / "index.md").exists()


# ── harden-links ─────────────────────────────────────────────────────────────

def run_harden(vault, *args):
    return vault.hook("harden-links.py", args=list(args))


def test_harden_convierte_nombre_pelado_en_ruta_relativa(vault):
    vault.write("04 Knowledge/Temas/Destino.md", "# Destino\n")
    vault.write("02 MOCs/Mapa.md", "Ver [Destino](<Destino.md>).\n")
    assert run_harden(vault).returncode == 0
    assert "[Destino](<../04 Knowledge/Temas/Destino.md>)" in vault.read("02 MOCs/Mapa.md")


def test_harden_repara_un_link_a_una_nota_que_se_mudo(vault):
    vault.write("04 Knowledge/Nuevo lugar/Destino.md", "# Destino\n")
    vault.write("02 MOCs/Mapa.md", "Ver [D](<../04 Knowledge/Viejo/Destino.md>).\n")
    run_harden(vault)
    assert "(<../04 Knowledge/Nuevo lugar/Destino.md>)" in vault.read("02 MOCs/Mapa.md")


def test_harden_no_adivina_si_el_destino_es_ambiguo_o_no_existe(vault):
    vault.write("04 Knowledge/A/Destino.md", "# 1\n")
    vault.write("04 Knowledge/B/Destino.md", "# 2\n")
    texto = "Ver [D](<Destino.md>) y [X](<No existe.md>) y [[Promesa]].\n"
    vault.write("02 MOCs/Mapa.md", texto)
    run_harden(vault)
    assert vault.read("02 MOCs/Mapa.md") == texto


def test_harden_no_toca_el_frontmatter(vault):
    vault.write("04 Knowledge/Destino.md", "# Destino\n")
    fm = "---\nrelacionado: \"[D](<Destino.md>)\"\nfuente: \"[[Destino]]\"\n---\n"
    vault.write("02 MOCs/Mapa.md", fm + "Ver [D](<Destino.md>).\n")
    run_harden(vault, "--wiki")
    assert vault.read("02 MOCs/Mapa.md").startswith(fm)


def test_harden_dry_no_escribe(vault):
    vault.write("04 Knowledge/Destino.md", "# Destino\n")
    texto = "Ver [D](<Destino.md>).\n"
    vault.write("02 MOCs/Mapa.md", texto)
    p = run_harden(vault, "--dry")
    assert b"DRY" in p.stdout
    assert vault.read("02 MOCs/Mapa.md") == texto


@st.composite
def vault_con_links(draw):
    """Notas en varias carpetas cuyos cuerpos se enlazan entre sí de todas las formas."""
    archivos = draw(arbol())
    rutas = sorted(archivos)
    nombres = [os.path.basename(r) for r in rutas] + ["No existe.md"]
    out = {}
    for rel in rutas:
        partes = [draw(linea)]
        for _ in range(draw(st.integers(0, 4))):
            n = draw(st.sampled_from(nombres))
            forma = draw(st.sampled_from(["pelado", "ruta", "wiki", "wiki_alias"]))
            if forma == "pelado":
                partes.append("[t](<%s>)" % n)
            elif forma == "ruta":
                partes.append("[t](<../otra carpeta/%s>)" % n)
            elif forma == "wiki":
                partes.append("[[%s]]" % n[:-3])
            else:
                partes.append("[[%s|alias]]" % n[:-3])
            partes.append(draw(linea))
        fm = "---\ntitle: x\nrel: \"[[%s]]\"\n---\n" % nombres[0][:-3] if draw(st.booleans()) else ""
        out[rel] = fm + "\n".join(partes) + "\n"
    return out


def run_harden_inproc(root, wiki):
    import sys
    harden.VAULT = str(root)
    argv = sys.argv
    sys.argv = ["harden-links.py"] + (["--wiki"] if wiki else [])
    try:
        import contextlib
        import io
        with contextlib.redirect_stdout(io.StringIO()):
            assert harden.main() == 0
    finally:
        sys.argv = argv


@settings(max_examples=60, deadline=None)
@given(vault_con_links(), st.booleans())
def test_harden_es_idempotente(archivos, wiki):
    """Una segunda pasada no encuentra nada más que endurecer."""
    with tempfile.TemporaryDirectory() as root:
        materializar(root, archivos)
        run_harden_inproc(root, wiki)
        primera = snapshot(root)
        run_harden_inproc(root, wiki)
        assert snapshot(root) == primera


@settings(max_examples=60, deadline=None)
@given(vault_con_links(), st.booleans())
def test_harden_solo_cambia_destinos_de_links(archivos, wiki):
    """Fuera de los links nada cambia: mismo frontmatter, mismo texto, mismos
    títulos de link; y todo link que el script reescribe apunta a un archivo que existe."""
    import re
    link = re.compile(r"\[([^\]]+)\]\(<([^<>]+\.md)>\)|\[\[[^\]]+\]\]")
    with tempfile.TemporaryDirectory() as root:
        materializar(root, archivos)
        antes = snapshot(root)
        run_harden_inproc(root, wiki)
        despues = snapshot(root)
        assert set(antes) == set(despues)
        for rel in antes:
            a, d = antes[rel].decode("utf-8"), despues[rel].decode("utf-8")
            assert harden.split_frontmatter(a)[0] == harden.split_frontmatter(d)[0]
            assert link.sub("§", a) == link.sub("§", d), rel
            if a == d:
                continue
            viejos = {m.group(0) for m in link.finditer(a)}
            for m in link.finditer(d):
                if m.group(0) not in viejos and m.group(2):
                    destino = Path(root, os.path.dirname(rel), m.group(2))
                    assert destino.is_file(), (rel, m.group(0))
