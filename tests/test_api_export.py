from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session


def _client(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_export_no_estado(tmp_path, box):
    client, _ = _client(tmp_path, box)
    state = client.get("/api/project").json()
    assert state["export"]["format"] == "dxf_r12"
    assert state["export"]["out_dir"] == "out/"
    assert "{group}" in state["export"]["naming"]


def test_patch_export_config(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch(
        "/api/export",
        json={"format": "stl", "out_dir": "saida_x/", "naming": "{project}_{group}.stl"},
    )
    assert r.status_code == 200
    exp = r.json()["export"]
    assert exp == {"format": "stl", "out_dir": "saida_x/", "naming": "{project}_{group}.stl"}


def test_patch_export_validacoes_422(tmp_path, box):
    client, _ = _client(tmp_path, box)
    casos = [
        ({"format": "png"}, "formato"),
        ({"out_dir": "   "}, "out_dir"),
        ({"out_dir": 5}, "out_dir"),
        ({"naming": "fixo.dxf"}, "{group}"),
    ]
    for body, trecho in casos:
        r = client.patch("/api/export", json=body)
        assert r.status_code == 422, body
        assert trecho in r.json()["detail"], body


def test_post_export_grava_arquivos(tmp_path, box):
    client, _ = _client(tmp_path, box)
    out = tmp_path / "exportado"
    client.patch("/api/export", json={"out_dir": str(out), "naming": "{group}.dxf"})
    r = client.post("/api/export")
    assert r.status_code == 200
    body = r.json()
    assert len(body["files"]) == 1
    f = body["files"][0]
    assert f["group"] == "saida"
    assert f["faces"] == 12
    assert Path(f["path"]).exists()
    assert Path(f["path"]) == out / "saida.dxf"


def test_post_export_sem_saida(tmp_path, box):
    client, session = _client(tmp_path, box)
    # remove a única peça → nada a exportar
    comp = session.project.components[0].id
    client.patch(f"/api/component/{comp}", json={"operation": {"type": "remove"}})
    r = client.post("/api/export")
    assert r.status_code == 200
    assert r.json()["files"] == []
