import numpy as np
import pytest

from meshbench.core.transform.scale import (
    apply_scale,
    fit_dimension,
    scale_per_axis,
    scale_uniform,
)


def test_uniform_nao_muta_original(box):
    m = scale_uniform(box, 2.0)
    assert np.allclose(m.extents, [20, 40, 60])
    assert np.allclose(box.extents, [10, 20, 30])


def test_per_axis(box):
    m = scale_per_axis(box, 1.0, 2.0, 3.0)
    assert np.allclose(m.extents, [10, 40, 90])


def test_fit_dimension(box):
    m, f = fit_dimension(box, "x", 450.0)
    assert np.allclose(m.extents[0], 450.0)
    assert f == pytest.approx(45.0)
    # escala uniforme: as outras dimensões acompanham
    assert np.allclose(m.extents, [450, 900, 1350])


def test_fit_dimension_nula():
    import trimesh

    plano = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces=[[0, 1, 2]]
    )
    with pytest.raises(ValueError, match="nula"):
        fit_dimension(plano, "z", 100.0)


def test_apply_scale_unit_convert(box):
    m, factor = apply_scale(box, {"mode": "unit_convert", "from_unit": "in", "to_unit": "mm"})
    assert np.allclose(m.extents, [254, 508, 762])
    assert factor == [25.4, 25.4, 25.4]


def test_apply_scale_uniform(box):
    m, factor = apply_scale(box, {"mode": "uniform", "value": 0.5})
    assert np.allclose(m.extents, [5, 10, 15])
    assert factor == [0.5, 0.5, 0.5]


def test_apply_scale_fit(box):
    m, factor = apply_scale(
        box, {"mode": "fit_dimension", "fit": {"axis": "x", "target_mm": 450.0}}
    )
    assert np.allclose(m.extents[0], 450.0)
    assert factor == [45.0, 45.0, 45.0]


def test_apply_scale_modo_invalido(box):
    with pytest.raises(ValueError, match="modo de escala"):
        apply_scale(box, {"mode": "magico"})
