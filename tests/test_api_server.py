import trimesh
from fastapi.testclient import TestClient

from meshbench.core.analyze.components import split_components
from meshbench.core.project import new_project
from meshbench.api import server
from meshbench.api.server import create_app, load_session


def _stl(tmp_path, box, small_sphere):
    s = small_sphere.copy()
    s.apply_translation([100, 0, 0])
    scene = trimesh.util.concatenate([box, s])
    p = tmp_path / "cena.stl"
    scene.export(str(p))
    return p


def _client(tmp_path, box, small_sphere):
    session = load_session(_stl(tmp_path, box, small_sphere))
    return TestClient(create_app(session))


def test_load_session_de_malha(tmp_path, box, small_sphere):
    session = load_session(_stl(tmp_path, box, small_sphere))
    assert session.project.name == "cena"
    assert len(session.project.components) == 2
    assert len(session.records) == 1  # esfera sugerida como remove


def test_load_session_de_receita(tmp_path, box, small_sphere):
    src = _stl(tmp_path, box, small_sphere)
    mesh = trimesh.load(str(src), force="mesh")
    p = new_project("cena", src, mesh, split_components(mesh))
    p.source["path"] = "cena.stl"
    recipe = tmp_path / "cena.meshbench.json"
    p.save(recipe)
    session = load_session(recipe)
    assert session.project.name == "cena"


def test_get_project_estado(tmp_path, box, small_sphere):
    client = _client(tmp_path, box, small_sphere)
    r = client.get("/api/project")
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "cena"
    assert len(d["components"]) == 2
    assert d["groups"] == [{"name": "saida", "role": "fixed"}]
    assert d["group_faces"] == {"saida": 12}
    assert d["face_budget"] == 15000
    assert len(d["dims_mm"]) == 3


def test_get_geometry_glb(tmp_path, box, small_sphere):
    client = _client(tmp_path, box, small_sphere)
    r = client.get("/api/project/geometry")
    assert r.status_code == 200
    assert r.headers["content-type"] == "model/gltf-binary"
    assert r.content[:4] == b"glTF"


def test_raiz_sem_build_da_dica(tmp_path, box, small_sphere, monkeypatch):
    monkeypatch.setattr(server, "STATIC_DIR", tmp_path / "nao_existe")
    client = _client(tmp_path, box, small_sphere)
    r = client.get("/")
    assert r.status_code == 200
    assert "npm" in r.json()["detail"]
