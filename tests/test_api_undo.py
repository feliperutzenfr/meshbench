import pytest
from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session


def _client(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_undo_redo_de_orientacao(tmp_path, box):
    client, _ = _client(tmp_path, box)
    state0 = client.get("/api/project").json()
    assert state0["can_undo"] is False and state0["can_redo"] is False

    client.patch("/api/orient", json={"rotations": [{"axis": "x", "deg": 90}]})
    state1 = client.get("/api/project").json()
    assert state1["dims_mm"] == pytest.approx([10.0, 30.0, 20.0])
    assert state1["can_undo"] is True

    r = client.post("/api/undo")
    assert r.status_code == 200
    state2 = r.json()
    assert state2["dims_mm"] == pytest.approx([10.0, 20.0, 30.0])
    assert state2["orient"]["rotations"] == []
    assert state2["can_redo"] is True

    r = client.post("/api/redo")
    assert r.json()["dims_mm"] == pytest.approx([10.0, 30.0, 20.0])


def test_undo_cobre_component_e_scale(tmp_path, box):
    client, session = _client(tmp_path, box)
    comp = session.project.components[0].id
    client.patch(f"/api/component/{comp}", json={"user_label": "tampo"})
    client.patch("/api/scale", json={"scale": {"mode": "uniform", "value": 2}})
    # desfaz a escala
    state = client.post("/api/undo").json()
    assert state["dims_mm"] == pytest.approx([10.0, 20.0, 30.0])
    assert state["components"][0]["user_label"] == "tampo"
    # desfaz o rótulo
    state = client.post("/api/undo").json()
    assert state["components"][0]["user_label"] is None
    assert state["can_undo"] is False


def test_undo_vazio_409(tmp_path, box):
    client, _ = _client(tmp_path, box)
    assert client.post("/api/undo").status_code == 409
    assert client.post("/api/redo").status_code == 409


def test_nova_mutacao_limpa_redo(tmp_path, box):
    client, _ = _client(tmp_path, box)
    client.patch("/api/orient", json={"rotations": [{"axis": "x", "deg": 90}]})
    client.post("/api/undo")
    assert client.get("/api/project").json()["can_redo"] is True
    client.patch("/api/orient", json={"mirror": ["x"]})
    assert client.get("/api/project").json()["can_redo"] is False


def test_cap_de_50(tmp_path, box):
    client, session = _client(tmp_path, box)
    comp = session.project.components[0].id
    for i in range(55):
        client.patch(f"/api/component/{comp}", json={"user_label": f"r{i}"})
    assert len(session.undo_stack) == 50


def test_mutacao_falha_nao_empilha(tmp_path, box):
    client, session = _client(tmp_path, box)
    n = len(session.undo_stack)
    r = client.patch("/api/orient", json={"mirror": ["w"]})
    assert r.status_code == 422
    assert len(session.undo_stack) == n


def test_undo_devolve_alvo_a_pilha_se_restore_falha(tmp_path, box, monkeypatch):
    """Se o reprocesso do undo falhar, o alvo volta para a pilha e a sessão
    fica intacta (projeto atual preservado, redo não ganha entrada)."""
    client, session = _client(tmp_path, box)
    client.patch("/api/orient", json={"rotations": [{"axis": "x", "deg": 90}]})
    n_undo = len(session.undo_stack)

    import meshbench.api.session_ops as so

    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(so, "process", explode)
    with pytest.raises(RuntimeError):
        so.undo(session)
    assert len(session.undo_stack) == n_undo
    assert len(session.redo_stack) == 0
    assert session.project.orient["rotations"] == [{"axis": "x", "deg": 90.0}]
