import pytest
from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session
from meshbench.api.session_ops import update_scale


def _client(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_source_dims_no_estado(tmp_path, box):
    client, _ = _client(tmp_path, box)
    state = client.get("/api/project").json()
    assert state["source_dims"] == pytest.approx([10.0, 20.0, 30.0])


def test_unit_convert_in_para_mm(tmp_path, box):
    client, session = _client(tmp_path, box)
    rev0 = client.get("/api/project").json()["revision"]
    r = client.patch(
        "/api/scale",
        json={"scale": {"mode": "unit_convert", "from_unit": "in", "to_unit": "mm"}},
    )
    assert r.status_code == 200
    state = r.json()
    assert state["dims_mm"] == pytest.approx([254.0, 508.0, 762.0])
    assert state["scale"]["factor"] == pytest.approx([25.4, 25.4, 25.4])
    assert state["revision"] == rev0 + 1
    # o match por tolerância sobrevive à conversão: o componente não some
    assert sum(state["group_faces"].values()) == 12


def test_fit_dimension(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch(
        "/api/scale",
        json={"scale": {"mode": "fit_dimension", "fit": {"axis": "x", "target_mm": 450}}},
    )
    assert r.status_code == 200
    assert r.json()["dims_mm"][0] == pytest.approx(450.0)


def test_uniform_e_per_axis(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch("/api/scale", json={"scale": {"mode": "uniform", "value": 2}})
    assert r.json()["dims_mm"] == pytest.approx([20.0, 40.0, 60.0])
    r = client.patch(
        "/api/scale", json={"scale": {"mode": "per_axis", "per_axis": [1, 2, 3]}}
    )
    assert r.json()["dims_mm"] == pytest.approx([10.0, 40.0, 90.0])


def test_confirmacao_de_unidade(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch("/api/scale", json={"units": "in"})
    assert r.status_code == 200
    src = r.json()["source"]
    assert src["units"] == "in"
    assert src["units_confirmed"] is True


def test_validacoes_422(tmp_path, box):
    client, _ = _client(tmp_path, box)
    casos = [
        ({"scale": {"mode": "magico"}}, "modo de escala"),
        ({"scale": {"mode": "unit_convert", "from_unit": "jardas"}}, "unidade"),
        ({"scale": {"mode": "uniform", "value": -2}}, "positivo"),
        ({"scale": {"mode": "per_axis", "per_axis": [1, 2]}}, "per_axis"),
        ({"scale": {"mode": "fit_dimension", "fit": {"axis": "w", "target_mm": 10}}}, "fit.axis"),
        ({"units": "jardas"}, "unidade"),
    ]
    for body, trecho in casos:
        r = client.patch("/api/scale", json=body)
        assert r.status_code == 422, body
        assert trecho in r.json()["detail"], body


def test_rollback_se_reprocesso_falha(tmp_path, box, monkeypatch):
    _, session = _client(tmp_path, box)
    scale_antes = session.project.scale
    units_antes = session.project.source.get("units")
    rev_antes = session.revision

    import meshbench.api.session_ops as so

    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(so, "process", explode)
    with pytest.raises(RuntimeError):
        update_scale(
            session,
            {"scale": {"mode": "uniform", "value": 2}, "units": "in"},
        )
    assert session.project.scale == scale_antes
    assert session.project.source.get("units") == units_antes
    assert "units_confirmed" not in session.project.source
    assert session.revision == rev_antes


def test_rollback_units_only_restaura_scale_mutado(tmp_path, box, monkeypatch):
    """Só 'units' no changes: process() muta project.scale IN PLACE antes de
    falhar — o rollback precisa restaurar uma CÓPIA, não a referência viva."""
    _, session = _client(tmp_path, box)
    session.project.scale["factor"] = [9, 9, 9]  # fator "velho" simulado

    import meshbench.api.session_ops as so

    def muta_e_explode(*a, **k):
        a[0].scale["factor"] = [1, 1, 1]  # process() muta in place, depois falha
        raise RuntimeError("boom")

    monkeypatch.setattr(so, "process", muta_e_explode)
    with pytest.raises(RuntimeError):
        update_scale(session, {"units": "in"})
    assert session.project.scale["factor"] == [9, 9, 9]
