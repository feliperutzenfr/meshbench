import numpy as np
import pytest
import trimesh

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


def test_decimate_face_count_tem_piso(small_sphere):
    # face_count explícito abaixo do piso não pode gerar malha degenerada
    m = apply_op(small_sphere, {"type": "decimate", "params": {"face_count": 1}})
    assert len(m.faces) >= 4


def test_decimate_reduz_geometria_alongada():
    # cilindro 15x350 (proxy de tubo de móvel): a lateral vira triângulos de
    # comprimento total e o fast_simplification veta todo colapso (ver
    # _decimate_squashed) — sem o resgate, devolvia as 128 faces intactas
    cyl = trimesh.creation.cylinder(radius=15.0, height=350.0)
    m = apply_op(cyl, {"type": "decimate", "params": {"face_count": 64}})
    assert len(m.faces) < len(cyl.faces)
    assert np.allclose(m.extents, cyl.extents, atol=1.0)


def test_decimate_reduz_alongado_tesselacao_fina():
    # com 128 seções o squash até a isotropia do bbox ainda não basta —
    # exercita a escada de fatores do resgate
    cyl = trimesh.creation.cylinder(radius=15.0, height=350.0, sections=128)
    m = apply_op(cyl, {"type": "decimate", "params": {"face_count": 64}})
    assert len(m.faces) < len(cyl.faces)
    assert np.allclose(m.extents, cyl.extents, atol=1.0)


def test_hull_fecha_perfil(c_channel):
    m = apply_op(c_channel, {"type": "hull"})
    # é exatamente por isso que hull em perfil aberto precisa de aviso:
    assert m.volume > 2 * c_channel.volume


def test_operacao_desconhecida(box):
    with pytest.raises(ValueError, match="operação"):
        apply_op(box, {"type": "explodir"})
