from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session, set_dialog_broker


def _app(tmp_path, box):
    p = tmp_path / "box.stl"
    box.export(p)
    return create_app(load_session(p))


def test_pick_sem_broker_retorna_409(tmp_path, box):
    set_dialog_broker(None)
    client = TestClient(_app(tmp_path, box))
    r = client.post("/api/pick/file")
    assert r.status_code == 409
    assert "desktop" in r.json()["detail"]


def test_pick_file_com_broker_retorna_path(tmp_path, box):
    set_dialog_broker(lambda kind: "C:/escolhido.stl" if kind == "file" else None)
    try:
        client = TestClient(_app(tmp_path, box))
        r = client.post("/api/pick/file")
        assert r.status_code == 200
        assert r.json() == {"path": "C:/escolhido.stl"}
    finally:
        set_dialog_broker(None)


def test_pick_folder_cancelado_retorna_null(tmp_path, box):
    set_dialog_broker(lambda kind: None)  # cancelou
    try:
        client = TestClient(_app(tmp_path, box))
        r = client.post("/api/pick/folder")
        assert r.status_code == 200
        assert r.json() == {"path": None}
    finally:
        set_dialog_broker(None)
