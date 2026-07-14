import numpy as np
import pytest
import trimesh

from meshbench.core.transform.axes import REMAPS, remap_axes
from meshbench.core.transform.rotate import rotate_90, rotate_free


def _ponto_unico():
    return trimesh.Trimesh(
        vertices=[[1, 2, 3], [1, 2, 3.001], [1.001, 2, 3]], faces=[[0, 1, 2]]
    )


def test_preset_cad_to_promob_troca_y_z():
    m = remap_axes(_ponto_unico(), "cad_to_promob")
    assert np.allclose(m.vertices[0], [1, 3, 2])


def test_remap_corrige_winding(box):
    # trocar Y por Z tem determinante -1 → sem invert() o volume ficaria negativo
    m = remap_axes(box, "cad_to_promob")
    assert m.volume > 0
    assert m.volume == pytest.approx(box.volume)


def test_remap_custom_com_sinal():
    m = remap_axes(_ponto_unico(), ["x", "-z", "y"])
    assert np.allclose(m.vertices[0], [1, -3, 2])


def test_remap_preset_desconhecido(box):
    with pytest.raises(KeyError):
        remap_axes(box, "nao_existe")


def test_rotate_90_z():
    m = rotate_90(_ponto_unico(), "z", 1)
    assert np.allclose(m.vertices[0], [-2, 1, 3])


def test_rotate_90_bbox(box):
    m = rotate_90(box, "x", 1)
    assert np.allclose(m.extents, [10, 30, 20])
    assert m.volume == pytest.approx(box.volume)


def test_rotate_90_quatro_vezes_e_identidade(box):
    m = rotate_90(box, "y", 4)
    assert np.allclose(m.vertices, box.vertices)


def test_rotate_free_equivale_a_90(box):
    a = rotate_90(box, "z", 1)
    b = rotate_free(box, 0, 0, 90)
    assert np.allclose(a.bounds, b.bounds, atol=1e-6)
