import numpy as np
import pytest

from meshbench.core.ops import apply_op
from meshbench.core.ops.tube import extract_centerline, tube_from_centerline


def test_centerline_recupera_raio(wire_arc):
    cl, radius = extract_centerline(wire_arc, bin_mm=3.0)
    assert radius == pytest.approx(2.0, rel=0.3)
    assert len(cl) > 10
    # comprimento da linha ~ arco de 90° com raio 50 (~78.5)
    comp = np.linalg.norm(np.diff(cl, axis=0), axis=1).sum()
    assert comp == pytest.approx(50 * np.pi / 2, rel=0.25)


def test_tube_from_centerline_conta_faces():
    t = np.linspace(0, np.pi / 2, 20)
    cl = np.column_stack([50 * np.cos(t), 50 * np.sin(t), np.zeros_like(t)])
    m = tube_from_centerline(cl, radius=2.0, sides=8)
    # 2 triângulos por lado por segmento + tampas
    assert len(m.faces) == 8 * 2 * 19 + 2 * 8
    assert m.is_watertight


def test_op_tube_reduz_faces(wire_arc):
    out = apply_op(wire_arc, {"type": "tube", "params": {"sides": 8, "bin_mm": 3.0}})
    assert len(out.faces) < len(wire_arc.faces) / 2
    # o tubo reconstruído ocupa aproximadamente o mesmo espaço
    assert np.allclose(out.bounds, wire_arc.bounds, atol=5.0)


def test_op_tube_raio_sobrescrito(wire_arc):
    out = apply_op(wire_arc, {"type": "tube", "params": {"radius": 4.0}})
    # raio dobrado → bbox um pouco maior no eixo fino (z: era ~4, vira ~8)
    dz = out.bounds[1][2] - out.bounds[0][2]
    assert dz == pytest.approx(8.0, rel=0.3)
