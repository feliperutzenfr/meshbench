import numpy as np
import trimesh

from meshbench.core.analyze.classify import SUGGESTED_OP, classify


def _chapa(thickness):
    """Chapa plana 20 x 100 mm com a espessura dada — só a espessura é pequena."""
    return trimesh.Trimesh(
        vertices=np.array(
            [
                [0.0, 0.0, 0.0],
                [20.0, 0.0, 0.0],
                [20.0, 100.0, thickness],
                [0.0, 100.0, thickness],
            ]
        ),
        faces=np.array([[0, 1, 2], [0, 2, 3]]),
        process=False,
    )


def test_esfera_pequena_e_solda(small_sphere):
    assert classify(small_sphere) == "weld_sphere"


def test_canal_longo_e_perfil(c_channel):
    assert classify(c_channel) == "profile"


def test_arame_curvo(wire_arc):
    assert classify(wire_arc) == "wire_or_frame"


def test_caixa_macica_e_ferragem(box):
    assert classify(box) == "hardware"


def test_casca_degenerada_nao_e_perfil():
    # Retalho sem espessura: o "perfil" que a heurística via aqui não tem seção
    # a extrudar. Vinha de DXF de CAD e fazia o reextrude falhar.
    assert classify(_chapa(0.00026)) == "degenerate_shell"


def test_casca_fina_mas_real_continua_perfil():
    # Chapa de 1 mm ainda é peça de verdade — em dúvida, manter.
    assert classify(_chapa(1.0)) == "profile"


def test_operacoes_sugeridas_sao_conservadoras():
    assert SUGGESTED_OP["degenerate_shell"] == "remove"
    assert SUGGESTED_OP["weld_sphere"] == "remove"
    assert SUGGESTED_OP["profile"] == "reextrude"
    assert SUGGESTED_OP["wire_or_frame"] == "decimate"
    assert SUGGESTED_OP["hardware"] == "keep"
