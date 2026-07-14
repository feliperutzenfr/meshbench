from meshbench.core.analyze.units import UNIT_MM, guess_unit, human_dimensions


def _scaled(box, factor):
    m = box.copy()
    m.apply_scale(factor)
    return m


def test_tabela_unidades():
    assert UNIT_MM["in"] == 25.4
    assert UNIT_MM["m"] == 1000.0


def test_mm_provavel(box):
    m = _scaled(box, 10)  # maior dim = 300
    unit, motivo = guess_unit(m)
    assert unit == "mm"
    assert "provável" in motivo


def test_ambiguo(box):
    unit, motivo = guess_unit(box)  # maior dim = 30 → 30mm ou 30"?
    assert unit is None
    assert "ambíguo" in motivo


def test_metros_provavel(box):
    m = _scaled(box, 0.01)  # maior dim = 0.3
    unit, _ = guess_unit(m)
    assert unit == "m"


def test_suspeito_grande(box):
    m = _scaled(box, 1000)  # maior dim = 30000
    unit, motivo = guess_unit(m)
    assert unit == "mm"
    assert "suspeito" in motivo


def test_human_dimensions(box):
    assert human_dimensions(box) == "10.0 × 20.0 × 30.0 mm"
