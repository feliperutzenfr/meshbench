import math

import pytest
from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session
from meshbench.api.session_ops import update_origin


def _client(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_origin_no_estado(tmp_path, box):
    client, _ = _client(tmp_path, box)
    state = client.get("/api/project").json()
    assert state["origin"]["mode"] == "common"
    assert state["origin"]["anchor"] == "bbox_min"
    # bbox_min ancorado → um vértice exatamente na origem
    assert state["origin_distance_mm"] == pytest.approx(0.0, abs=1e-6)


def test_patch_anchor_center(tmp_path, box):
    client, _ = _client(tmp_path, box)
    rev0 = client.get("/api/project").json()["revision"]
    r = client.patch("/api/origin", json={"anchor": "center"})
    assert r.status_code == 200
    state = r.json()
    assert state["origin"]["anchor"] == "center"
    assert state["revision"] == rev0 + 1
    assert state["dims_mm"] == pytest.approx([10.0, 20.0, 30.0])
    # caixa centrada: vértice mais próximo é um canto (5,10,15)
    assert state["origin_distance_mm"] == pytest.approx(math.sqrt(350.0))


def test_offset_e_origem_flutuando(tmp_path, box):
    client, _ = _client(tmp_path, box)
    state = client.patch("/api/origin", json={"offset": [100, 0, 0]}).json()
    # bbox_min + offset 100 em x → geometria em x∈[-100,-90]; canto (-90,0,0)
    assert state["origin_distance_mm"] == pytest.approx(90.0)
    assert any("origem flutuando" in w for w in state["warnings"])
    state = client.patch("/api/origin", json={"offset": [0, 0, 0]}).json()
    assert not any("origem flutuando" in w for w in state["warnings"])


def test_snap_point_precedencia(tmp_path, box):
    client, _ = _client(tmp_path, box)
    # snap_point é raro (a UI usa offset), mas a receita pode carregar — precedência máxima
    state = client.patch("/api/origin", json={"snap_point": [-5, -10, -15]}).json()
    assert state["origin_distance_mm"] == pytest.approx(0.0, abs=1e-6)


def test_per_group_e_validacoes_422(tmp_path, box):
    client, _ = _client(tmp_path, box)
    assert client.patch("/api/origin", json={"mode": "per_group"}).status_code == 200
    casos = [
        ({"mode": "magico"}, "modo de origem"),
        ({"anchor": "canto"}, "âncora"),
        ({"anchor": "corner_012"}, "âncora"),
        ({"offset": [1, 2]}, "offset"),
        ({"offset": [1, 2, "a"]}, "offset"),
        ({"snap_point": "x"}, "snap_point"),
        ({"feature_ref": 5}, "feature_ref"),
    ]
    for body, trecho in casos:
        r = client.patch("/api/origin", json=body)
        assert r.status_code == 422, body
        assert trecho in r.json()["detail"], body


def test_rollback_se_reprocesso_falha(tmp_path, box, monkeypatch):
    _, session = _client(tmp_path, box)
    origin_antes = dict(session.project.origin)
    rev_antes = session.revision

    import meshbench.api.session_ops as so

    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(so, "process", explode)
    with pytest.raises(RuntimeError):
        update_origin(session, {"anchor": "center"})
    assert session.project.origin == origin_antes
    assert session.revision == rev_antes
    assert len(session.undo_stack) == 0


def test_undo_redo_de_origem(tmp_path, box):
    client, _ = _client(tmp_path, box)
    client.patch("/api/origin", json={"anchor": "center"})
    state = client.post("/api/undo").json()
    assert state["origin"]["anchor"] == "bbox_min"
    assert state["origin_distance_mm"] == pytest.approx(0.0, abs=1e-6)
    assert state["can_redo"] is True
    state = client.post("/api/redo").json()
    assert state["origin"]["anchor"] == "center"
