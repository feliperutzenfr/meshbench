from meshbench.core.analyze.classify import SUGGESTED_OP, classify


def test_esfera_pequena_e_solda(small_sphere):
    assert classify(small_sphere) == "weld_sphere"


def test_canal_longo_e_perfil(c_channel):
    assert classify(c_channel) == "profile"


def test_arame_curvo(wire_arc):
    assert classify(wire_arc) == "wire_or_frame"


def test_caixa_macica_e_ferragem(box):
    assert classify(box) == "hardware"


def test_operacoes_sugeridas_sao_conservadoras():
    assert SUGGESTED_OP["weld_sphere"] == "remove"
    assert SUGGESTED_OP["profile"] == "reextrude"
    assert SUGGESTED_OP["wire_or_frame"] == "decimate"
    assert SUGGESTED_OP["hardware"] == "keep"
