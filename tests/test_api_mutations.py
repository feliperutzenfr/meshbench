import json

from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session
from meshbench.core.project import Project


def _client(tmp_path, small_sphere):
    p = tmp_path / "esfera.stl"
    small_sphere.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_patch_atualiza_e_retorna_estado(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    state0 = client.get("/api/project").json()
    comp = state0["components"][0]["id"]
    r = client.patch(
        f"/api/component/{comp}",
        json={
            "operation": {"type": "decimate", "params": {"face_count": 80}},
            "group": "saida",
        },
    )
    assert r.status_code == 200
    state = r.json()
    assert state["components"][0]["operation"]["type"] == "decimate"
    assert 0 < state["group_faces"]["saida"] <= 100
    assert state["revision"] == state0["revision"] + 1


def test_patch_cria_grupo_novo(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    comp = session.project.components[0].id
    r = client.patch(f"/api/component/{comp}", json={"group": "novo_grupo"})
    assert r.status_code == 200
    state = r.json()
    assert "novo_grupo" in [g["name"] for g in state["groups"]]


def test_patch_id_inexistente_404(tmp_path, small_sphere):
    client, _ = _client(tmp_path, small_sphere)
    r = client.patch("/api/component/c99", json={"user_label": "x"})
    assert r.status_code == 404
    assert "c99" in r.json()["detail"]


def test_patch_operacao_invalida_422(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    comp = session.project.components[0].id
    r = client.patch(
        f"/api/component/{comp}", json={"operation": {"type": "explodir"}}
    )
    assert r.status_code == 422
    assert "explodir" in r.json()["detail"]


def test_preview_retorna_glb_sem_mutar(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    comp = session.project.components[0].id
    client.patch(
        f"/api/component/{comp}",
        json={"operation": {"type": "keep", "params": {}}, "group": "saida"},
    )
    rev = session.revision
    r = client.post(
        f"/api/preview/{comp}",
        json={"operation": {"type": "decimate", "params": {"face_count": 80}}},
    )
    assert r.status_code == 200
    assert r.content[:4] == b"glTF"
    assert r.headers["X-Faces-Before"] == "320"
    assert 0 < int(r.headers["X-Faces-After"]) <= 100
    assert session.revision == rev  # preview não muta


def test_preview_sem_operation_422(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    comp = session.project.components[0].id
    r = client.post(f"/api/preview/{comp}", json={})
    assert r.status_code == 422
    assert "operation" in r.json()["detail"]


def test_preview_remove_404(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    comp = session.project.components[0].id
    client.patch(
        f"/api/component/{comp}",
        json={"operation": {"type": "keep", "params": {}}, "group": "saida"},
    )
    r = client.post(
        f"/api/preview/{comp}", json={"operation": {"type": "remove", "params": {}}}
    )
    assert r.status_code == 404
    assert "não produziu" in r.json()["detail"]


def test_get_geometry_cache_invalida_apos_patch(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    comp = session.project.components[0].id
    client.patch(
        f"/api/component/{comp}",
        json={"operation": {"type": "keep", "params": {}}, "group": "saida"},
    )
    r1 = client.get("/api/project/geometry")
    assert r1.status_code == 200
    assert session.glb_cache[0] == session.revision
    glb_antes = r1.content

    client.patch(
        f"/api/component/{comp}",
        json={"operation": {"type": "decimate", "params": {"face_count": 80}}},
    )
    r2 = client.get("/api/project/geometry")
    assert r2.status_code == 200
    assert r2.content != glb_antes  # cache velho não vazou pro GLB novo
    assert session.glb_cache[0] == session.revision  # cache acompanha a revision nova


def test_save_grava_receita(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    r = client.post("/api/project/save")
    assert r.status_code == 200
    path = r.json()["path"]
    assert path.endswith("esfera.meshbench.json")
    p = Project.load(path)
    assert p.name == "esfera"
