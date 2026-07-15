import pytest
import trimesh
from fastapi.testclient import TestClient

from meshbench.api.server import STATIC_DIR, create_app, load_session


@pytest.mark.skipif(not STATIC_DIR.exists(), reason="frontend não buildado")
def test_raiz_serve_index(tmp_path, box):
    p = tmp_path / "peca.stl"
    box.export(str(p))
    client = TestClient(create_app(load_session(p)))
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "MeshBench" in r.text
