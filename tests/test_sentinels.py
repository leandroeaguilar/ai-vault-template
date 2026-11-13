"""Centinelas @user: guard (PreToolUse, solo Claude Code) y verify (commit/PR, universal).

Lo que se protege: el texto dentro de `<!-- @user --> ... <!-- /@user -->` es
propiedad humana. Tiene que seguir ahí, textual y TODAVÍA PROTEGIDO.
"""
import pytest
from hypothesis import given, strategies as st

from conftest import load_hook, out

common = load_hook("sentinels_common")

OPEN, CLOSE = "<!-- @user -->", "<!-- /@user -->"
DOC = """# Nota

Texto del agente.

%s
Decisión humana: no migrar a Notion.
%s

Más texto del agente.
""" % (OPEN, CLOSE)
PROTEGIDO = "Decisión humana: no migrar a Notion."


@pytest.fixture
def doc(vault):
    vault.write("04 Knowledge/Nota.md", DOC)
    vault.commit_all("nota con centinela")
    return "04 Knowledge/Nota.md"


def verify(vault, *args, env=None):
    return vault.hook("sentinels-verify.py", args=args, env=env)


def stage(vault, rel, text):
    vault.write(rel, text)
    vault.git("add", "-A", check=True)


# ── verify (commit) ──────────────────────────────────────────────────────────

def test_editar_fuera_del_bloque_pasa(vault, doc):
    stage(vault, doc, DOC.replace("Texto del agente.", "Texto reescrito."))
    assert verify(vault).returncode == 0


def test_editar_dentro_del_bloque_bloquea(vault, doc):
    stage(vault, doc, DOC.replace("no migrar", "sí migrar"))
    p = verify(vault)
    assert p.returncode == 1, out(p)
    assert b"Nota.md" in p.stderr


def test_borrar_el_bloque_bloquea(vault, doc):
    stage(vault, doc, "# Nota\n\nTodo nuevo.\n")
    assert verify(vault).returncode == 1


def test_borrar_el_archivo_bloquea(vault, doc):
    vault.git("rm", "-q", doc, check=True)
    assert verify(vault).returncode == 1


def test_mover_el_bloque_dentro_del_archivo_pasa(vault, doc):
    bloque = "%s\n%s\n%s\n" % (OPEN, PROTEGIDO, CLOSE)
    stage(vault, doc, "# Nota\n\n" + bloque + "\nTexto del agente.\n")
    assert verify(vault).returncode == 0


def test_archivo_nuevo_con_bloque_pasa(vault):
    stage(vault, "04 Knowledge/Otra.md", DOC)
    assert verify(vault).returncode == 0


def test_escapes_humanos(vault, doc):
    stage(vault, doc, DOC.replace("no migrar", "sí migrar"))
    assert verify(vault, env={"SENTINELS_OK": "1"}).returncode == 0
    vault.write(".vault-meta/sentinels.disabled", "")
    assert verify(vault).returncode == 0


def test_bloquea_el_commit_real(vault, doc):
    before = vault.head()
    stage(vault, doc, DOC.replace("no migrar", "sí migrar"))
    assert vault.commit("intento").returncode != 0
    assert vault.head() == before


def test_modo_range(vault, doc):
    base = vault.head()
    vault.write(doc, DOC.replace("no migrar", "sí migrar"))
    vault.commit_all("altera")
    assert verify(vault, "--range", base, "HEAD").returncode == 1


def test_ruta_con_tilde(vault):
    rel = "04 Knowledge/Automatización/Decisión.md"
    vault.write(rel, DOC)
    vault.commit_all("nota acentuada")
    stage(vault, rel, DOC.replace("no migrar", "sí migrar"))
    assert verify(vault).returncode == 1


# ── verify: adversarial ──────────────────────────────────────────────────────

def test_quitar_los_marcadores_dejando_el_texto_bloquea(vault, doc):
    """Evasión en dos pasos: commit 1 saca los marcadores (el texto sigue, así
    que "está presente"); commit 2 lo edita libremente porque ya nadie lo protege."""
    stage(vault, doc, DOC.replace(OPEN + "\n", "").replace(CLOSE + "\n", ""))
    assert verify(vault).returncode == 1


def test_convertir_el_bloque_en_ejemplo_de_codigo_bloquea(vault, doc):
    """Envolver el bloque en un fence lo vuelve 'un ejemplo': deja de estar protegido."""
    bloque = "%s\n%s\n%s\n" % (OPEN, PROTEGIDO, CLOSE)
    stage(vault, doc, DOC.replace(bloque, "```\n" + bloque + "```\n"))
    assert verify(vault).returncode == 1


def test_renombrar_y_alterar_bloquea(vault, doc):
    """git reporta R(ename): ni la ruta vieja ni la nueva caían en el filtro ACMD."""
    nuevo = "04 Knowledge/Nota renombrada.md"
    vault.git("mv", doc, nuevo, check=True)
    stage(vault, nuevo, DOC.replace("no migrar", "sí migrar"))
    assert b"R" in vault.git("diff", "--cached", "--name-status").stdout  # precondición
    p = verify(vault)
    assert p.returncode == 1, out(p)


def test_renombrar_sin_tocar_el_bloque_pasa(vault, doc):
    vault.git("mv", doc, "04 Knowledge/Nota renombrada.md", check=True)
    assert verify(vault).returncode == 0


def test_mover_el_bloque_a_otro_archivo_bloquea(vault, doc):
    """El contenido humano no se muda de nota sin que el humano lo decida."""
    stage(vault, doc, "# Nota\n\nvaciada\n")
    vault.write("04 Knowledge/Otra.md", DOC)
    vault.git("add", "-A", check=True)
    assert verify(vault).returncode == 1


def test_marcador_en_ejemplo_inline_no_crea_region_fantasma(vault):
    guia = "# Guía\n\nEl marcador es `<!--@user-->` (espacios flexibles).\n\nTexto libre.\n\n" + \
           "%s\nprotegido\n%s\n" % (OPEN, CLOSE)
    vault.write("00 Sistema/Guía.md", guia)
    vault.commit_all("guía")
    stage(vault, "00 Sistema/Guía.md", guia.replace("Texto libre.", "Texto editado."))
    assert verify(vault).returncode == 0


# ── guard (PreToolUse Write|Edit) ────────────────────────────────────────────

def guard(vault, tool, **ti):
    ti.setdefault("file_path", str(vault.root / "04 Knowledge" / "Nota.md"))
    return vault.tool("sentinels-guard.sh", tool, **ti)


def test_guard_edit_fuera_permite(vault, doc):
    assert guard(vault, "Edit", old_string="Texto del agente.", new_string="x").returncode == 0


def test_guard_edit_dentro_bloquea(vault, doc):
    p = guard(vault, "Edit", old_string="no migrar", new_string="sí migrar")
    assert p.returncode == 2, out(p)
    assert "CENTINELA".encode() in p.stderr


def test_guard_write_que_preserva_permite(vault, doc):
    assert guard(vault, "Write", content=DOC + "\nagregado\n").returncode == 0


def test_guard_write_que_pierde_el_bloque_bloquea(vault, doc):
    assert guard(vault, "Write", content="# Nota\n").returncode == 2


def test_guard_archivo_nuevo_o_sin_centinelas(vault, doc):
    assert guard(vault, "Write", file_path=str(vault.root / "nueva.md"), content="x").returncode == 0
    assert guard(vault, "Edit", file_path=str(vault.root / "01 Index" / "Nota base.md"),
                 old_string="Cuerpo.", new_string="x").returncode == 0


def test_guard_ruta_relativa(vault, doc):
    assert guard(vault, "Edit", file_path="04 Knowledge/Nota.md",
                 old_string="no migrar", new_string="x").returncode == 2


def test_guard_kill_switch(vault, doc):
    vault.write(".vault-meta/sentinels.disabled", "")
    assert guard(vault, "Edit", old_string="no migrar", new_string="x").returncode == 0


# ── guard: adversarial ───────────────────────────────────────────────────────

def test_guard_edit_que_abarca_el_bloque_entero_bloquea(vault, doc):
    """old_string incluye los marcadores: no está "dentro" del bloque, lo CONTIENE.
    El chequeo `old in region` lo dejaba pasar."""
    entero = "%s\n%s\n%s" % (OPEN, PROTEGIDO, CLOSE)
    assert guard(vault, "Edit", old_string=entero, new_string="reemplazado").returncode == 2


def test_guard_edit_que_cruza_el_borde_bloquea(vault, doc):
    cruza = "Texto del agente.\n\n%s\nDecisión humana" % OPEN
    assert guard(vault, "Edit", old_string=cruza, new_string="x").returncode == 2


def test_guard_edit_que_solo_quita_el_marcador_bloquea(vault, doc):
    assert guard(vault, "Edit", old_string=OPEN + "\n", new_string="").returncode == 2
    assert guard(vault, "Edit", old_string=CLOSE, new_string="").returncode == 2


def test_guard_replace_all_que_alcanza_al_bloque_bloquea(vault):
    texto = "migrar afuera\n\n%s\nmigrar adentro\n%s\n" % (OPEN, CLOSE)
    vault.write("04 Knowledge/Nota.md", texto)
    assert guard(vault, "Edit", old_string="migrar", new_string="x",
                 replace_all=True).returncode == 2


def test_guard_edit_con_texto_repetido_fuera_y_dentro(vault):
    """Sin replace_all el Edit toca la PRIMERA aparición: si es la de afuera, pasa."""
    texto = "migrar afuera\n\n%s\nmigrar adentro\n%s\n" % (OPEN, CLOSE)
    vault.write("04 Knowledge/Nota.md", texto)
    assert guard(vault, "Edit", old_string="migrar afuera", new_string="x").returncode == 0


def test_guard_write_que_deja_el_texto_sin_marcadores_bloquea(vault, doc):
    sin = DOC.replace(OPEN + "\n", "").replace(CLOSE + "\n", "")
    assert guard(vault, "Write", content=sin).returncode == 2


@pytest.mark.parametrize("stdin", ["", "basura", "[]", '{"tool_input": 3}'])
def test_guard_entrada_malformada_es_fail_open(vault, stdin):
    assert vault.hook("sentinels-guard.sh", stdin=stdin).returncode == 0


# ── Propiedades (funciones puras de sentinels_common) ────────────────────────

# Texto libre SIN marcadores ni backticks (los backticks cambian qué es código).
libre = st.text(alphabet=st.characters(blacklist_characters="`<>~\r",
                                       blacklist_categories=("Cs",)), max_size=80)
contenido = libre.filter(lambda s: s.strip())


def armar(partes, bloques):
    """Intercala texto libre y bloques protegidos: p0 [b0] p1 [b1] ... pn"""
    out_ = [partes[0]]
    for b, p in zip(bloques, partes[1:]):
        out_ += ["\n%s\n%s\n%s\n" % (OPEN, b, CLOSE), p]
    return "".join(out_)


@st.composite
def documentos(draw):
    bloques = draw(st.lists(contenido, min_size=1, max_size=4))
    partes = draw(st.lists(libre, min_size=len(bloques) + 1, max_size=len(bloques) + 1))
    return partes, bloques


@given(documentos())
def test_user_regions_encuentra_cada_bloque(doc_):
    partes, bloques = doc_
    regiones = common.user_regions(armar(partes, bloques))
    assert [r.strip("\n") for r in regiones] == [b.strip("\n") for b in bloques]


@given(documentos(), st.data())
def test_editar_fuera_nunca_es_violacion(doc_, data):
    partes, bloques = doc_
    nuevas = data.draw(st.lists(libre, min_size=len(partes), max_size=len(partes)))
    viejo, nuevo = armar(partes, bloques), armar(nuevas, bloques)
    assert common.lost_regions(viejo, nuevo) == []


@given(documentos(), st.data())
def test_editar_dentro_siempre_es_violacion(doc_, data):
    partes, bloques = doc_
    i = data.draw(st.integers(0, len(bloques) - 1))
    otro = data.draw(contenido.filter(lambda s: s.strip("\n") != bloques[i].strip("\n")
                                      and bloques[i] not in s))
    alterados = bloques[:i] + [otro] + bloques[i + 1:]
    viejo, nuevo = armar(partes, bloques), armar(partes, alterados)
    # Salvo que el bloque alterado sea idéntico a otro que sí sobrevive.
    if bloques[i].strip() and not any(bloques[i] in b for b in alterados):
        assert common.lost_regions(viejo, nuevo) != []


@given(st.text(max_size=300))
def test_funciones_puras_nunca_revientan(texto):
    common.user_regions(texto)
    common.code_spans(texto)
    assert common.lost_regions(texto, texto) == []
