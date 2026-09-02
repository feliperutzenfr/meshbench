import numpy as np
import pytest

from meshbench.core.ops import apply_op


def test_reextrude_preserva_forma_e_perfil_aberto(c_channel):
    out = apply_op(c_channel, {"type": "reextrude"})
    assert out is not None
    # volume preservado (era prismático limpo)
    assert out.volume == pytest.approx(c_channel.volume, rel=0.15)
    # PERFIL CONTINUA ABERTO: se tivesse fechado (efeito hull), o volume
    # saltaria para perto do volume do hull
    assert out.volume < 0.6 * out.convex_hull.volume
    # comprimento preservado no eixo de extrusão (z = 100)
    assert out.bounds[1][2] - out.bounds[0][2] == pytest.approx(100.0, abs=0.5)


def test_reextrude_eixo_explicito(c_channel):
    out = apply_op(c_channel, {"type": "reextrude", "params": {"axis": 2}})
    assert out.volume == pytest.approx(c_channel.volume, rel=0.15)


def test_reextrude_achata_faces(c_channel):
    # o canal reto já é low-poly; subdividir simula a tesselação densa do CAD
    denso = c_channel.subdivide().subdivide()
    out = apply_op(denso, {"type": "reextrude"})
    assert len(out.faces) < len(denso.faces) / 4


def test_reextrude_devolve_none_em_sliver_degenerado():
    # Malha achatada (2 faces) como as que aparecem em DXF de CAD: a seção
    # perpendicular ao eixo maior não tem área, então não há perfil a extrudar.
    # Deve devolver None (peça sai da saída com aviso), nunca erguer.
    import trimesh

    sliver = trimesh.Trimesh(
        vertices=np.array(
            [
                [0.0, 0.0, 0.0],
                [1.313, 0.0, 0.0],
                [1.313, 0.02, 0.00026],
                [0.0, 0.02, 0.00026],
            ]
        ),
        faces=np.array([[0, 1, 2], [0, 2, 3]]),
        process=False,
    )
    assert apply_op(sliver, {"type": "reextrude"}) is None
