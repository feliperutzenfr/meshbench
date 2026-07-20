import numpy as np
import pytest

from meshbench.core.transform.mirror import mirror
from meshbench.core.transform.origin import compute_anchor, place_origin


def test_mirror_corrige_winding(box):
    m = mirror(box, "x")
    assert m.volume > 0  # sem invert() o volume sairia negativo
    assert m.volume == pytest.approx(box.volume)


def test_mirror_espelha(box):
    b = box.copy()
    b.apply_translation([100, 0, 0])  # bbox x: [95, 105]
    m = mirror(b, "x")
    assert np.allclose(m.bounds[:, 0], [-105, -95])


def test_compute_anchor():
    bounds = np.array([[0.0, 0.0, 0.0], [10.0, 20.0, 30.0]])
    assert np.allclose(compute_anchor(bounds, "bbox_min"), [0, 0, 0])
    assert np.allclose(compute_anchor(bounds, "center"), [5, 10, 15])
    assert np.allclose(compute_anchor(bounds, "corner_101"), [10, 0, 30])
    with pytest.raises(ValueError, match="âncora"):
        compute_anchor(bounds, "canto_magico")


def _dois_grupos(box):
    a = box.copy()
    a.apply_translation([100, 100, 100])  # bbox min = [95, 90, 85]
    b = box.copy()
    b.apply_translation([200, 100, 100])  # bbox min = [195, 90, 85]
    return {"fixa": [a], "movel": [b]}


def test_origem_comum_grupos_encaixam(box):
    out = place_origin(_dois_grupos(box), mode="common", anchor="bbox_min")
    # referencial único: o mínimo global [95, 90, 85] vira o zero
    assert np.allclose(out["fixa"][0].bounds[0], [0, 0, 0])
    assert np.allclose(out["movel"][0].bounds[0], [100, 0, 0])


def test_origem_por_grupo(box):
    out = place_origin(_dois_grupos(box), mode="per_group", anchor="bbox_min")
    assert np.allclose(out["fixa"][0].bounds[0], [0, 0, 0])
    assert np.allclose(out["movel"][0].bounds[0], [0, 0, 0])


def test_snap_point_tem_precedencia(box):
    out = place_origin(_dois_grupos(box), snap_point=[95, 90, 85])
    assert np.allclose(out["fixa"][0].bounds[0], [0, 0, 0])


def test_feature_bounds(box):
    fb = np.array([[100.0, 100.0, 100.0], [110.0, 110.0, 110.0]])
    out = place_origin(_dois_grupos(box), anchor="bbox_min", feature_bounds=fb)
    assert np.allclose(out["fixa"][0].bounds[0], [-5, -10, -15])


def test_offset(box):
    out = place_origin(
        _dois_grupos(box), mode="common", anchor="bbox_min", offset=[10, 0, 0]
    )
    assert np.allclose(out["fixa"][0].bounds[0], [-10, 0, 0])


def test_origin_distance_vertice_mais_proximo(box):
    from meshbench.core.transform.origin import origin_distance

    m = box.copy()  # caixa centrada na origem: x∈[-5,5], y∈[-10,10], z∈[-15,15]
    m.apply_translation([100.0, 0.0, 0.0])  # x∈[95,105]
    d = origin_distance([m])
    assert d == pytest.approx(float(np.linalg.norm([95.0, 10.0, 15.0])))


def test_origin_distance_zero_e_vazio(box):
    from meshbench.core.transform.origin import origin_distance

    m = box.copy()
    m.apply_translation([5.0, 10.0, 15.0])  # canto mínimo exatamente na origem
    assert origin_distance([m]) == pytest.approx(0.0)
    assert origin_distance([]) is None
