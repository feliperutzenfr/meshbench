from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session


def _client(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_reimport_preserva_escolhas_e_reseta_undo(tmp_path, box):
    client, session = _client(tmp_path, box)
    comp = session.project.components[0].id
    client.patch(f"/api/component/{comp}", json={"user_label": "tampo"})
    assert len(session.undo_stack) == 1
    rev0 = session.revision

    r = client.post("/api/project/reimport")
    assert r.status_code == 200
    state = r.json()
    # o rematch por assinatura preserva o rótulo do usuário
    assert state["components"][0]["user_label"] == "tampo"
    # re-baseline: histórico descartado, revision avança
    assert state["can_undo"] is False and state["can_redo"] is False
    assert len(session.undo_stack) == 0
    assert state["revision"] > rev0


def test_open_troca_projeto_e_reseta(tmp_path, box, c_channel):
    client, session = _client(tmp_path, box)
    comp = session.project.components[0].id
    client.patch(f"/api/component/{comp}", json={"user_label": "x"})
    assert len(session.undo_stack) == 1

    p2 = tmp_path / "perfil.stl"
    c_channel.export(str(p2))
    r = client.post("/api/project/open", json={"path": str(p2)})
    assert r.status_code == 200
    state = r.json()
    assert state["name"] == "perfil"
    assert state["can_undo"] is False
    assert len(session.undo_stack) == 0
    assert session.recipe_path.name == "perfil.meshbench.json"
    # a geometria da nova sessão carrega
    assert client.get("/api/project/geometry").status_code == 200


def test_open_arquivo_inexistente_404(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.post("/api/project/open", json={"path": str(tmp_path / "nao_existe.stl")})
    assert r.status_code == 404
    assert "não encontrado" in r.json()["detail"]


def test_open_path_invalido_422(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.post("/api/project/open", json={"path": ""})
    assert r.status_code == 422
    assert "path" in r.json()["detail"]


def test_reimport_source_sumido_404(tmp_path, box):
    client, session = _client(tmp_path, box)
    # apaga o source em disco → reimport deve dar 404 amigável
    import os
    os.remove(session.base_dir / session.project.source["path"])
    r = client.post("/api/project/reimport")
    assert r.status_code == 404
    assert "não encontrado" in r.json()["detail"]
