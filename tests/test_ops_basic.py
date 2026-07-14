import pytest

from meshbench.core.ops import OPS, apply_op


def test_keep_copia(box):
    m = apply_op(box, {"type": "keep"})
    assert m is not box
    assert len(m.faces) == 12


def test_remove_retorna_none(box):
    assert apply_op(box, {"type": "remove"}) is None


def test_decimate_face_count(small_sphere):
    # icosfera subdivisions=2 tem 320 faces
    m = apply_op(small_sphere, {"type": "decimate", "params": {"face_count": 80}})
    assert len(m.faces) <= 100
    assert m.volume == pytest.approx(small_sphere.volume, rel=0.2)


def test_decimate_percent(small_sphere):
    m = apply_op(small_sphere, {"type": "decimate", "params": {"percent": 25.0}})
    assert len(m.faces) <= 320 * 0.35


def test_hull_fecha_perfil(c_channel):
    m = apply_op(c_channel, {"type": "hull"})
    # é exatamente por isso que hull em perfil aberto precisa de aviso:
    assert m.volume > 2 * c_channel.volume


def test_operacao_desconhecida(box):
    with pytest.raises(ValueError, match="operação"):
        apply_op(box, {"type": "explodir"})
