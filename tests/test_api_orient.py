import pytest
from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session
from meshbench.api.session_ops import normalize_rotations, update_orient


def _client(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_normalize_rotations():
    assert normalize_rotations([]) == []
    assert normalize_rotations([{"axis": "z", "deg": 450}]) == [{"axis": "z", "deg": 90.0}]
    assert normalize_rotations([{"axis": "z", "deg": 360}]) == []
    # consecutivas no mesmo eixo fundem; eixos alternados não
    assert normalize_rotations(
        [{"axis": "x", "deg": 90}, {"axis": "x", "deg": 90}, {"axis": "y", "deg": 90}]
    ) == [{"axis": "x", "deg": 180.0}, {"axis": "y", "deg": 90.0}]
    assert normalize_rotations(
        [{"axis": "x", "deg": 90}, {"axis": "x", "deg": 270}]
    ) == []
    with pytest.raises(ValueError, match="eixo"):
        normalize_rotations([{"axis": "w", "deg": 90}])
    with pytest.raises(ValueError, match="graus"):
        normalize_rotations([{"axis": "x", "deg": "muito"}])
    with pytest.raises(ValueError, match="graus"):
        normalize_rotations([{"axis": "x", "deg": float("inf")}])
    with pytest.raises(ValueError, match="graus"):
        normalize_rotations([{"axis": "x", "deg": float("nan")}])


def test_patch_orient_rotacao_90(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch(
        "/api/orient",
        json={"rotations": [{"axis": "x", "deg": 90}]},
    )
    assert r.status_code == 200
    state = r.json()
    # caixa 10x20x30 girada 90 em X -> 10x30x20
    assert state["dims_mm"] == pytest.approx([10.0, 30.0, 20.0])
    assert state["orient"]["rotations"] == [{"axis": "x", "deg": 90.0}]


def test_patch_orient_preset_e_espelho(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch(
        "/api/orient",
        json={"axis_remap": "cad_to_promob", "mirror": ["x"]},
    )
    assert r.status_code == 200
    state = r.json()
    # troca y<->z: 10x20x30 -> 10x30x20 (espelho não muda dims)
    assert state["dims_mm"] == pytest.approx([10.0, 30.0, 20.0])
    assert state["orient"]["axis_remap"] == "cad_to_promob"
    assert state["orient"]["mirror"] == ["x"]


def test_patch_orient_custom_remap(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch(
        "/api/orient",
        json={"axis_remap": "custom", "custom_remap": ["x", "-z", "y"]},
    )
    assert r.status_code == 200
    assert r.json()["dims_mm"] == pytest.approx([10.0, 30.0, 20.0])


def test_patch_orient_validacoes_422(tmp_path, box):
    client, _ = _client(tmp_path, box)
    casos = [
        ({"axis_remap": "magico"}, "remap"),
        ({"axis_remap": "custom"}, "custom_remap"),
        ({"axis_remap": "custom", "custom_remap": ["x", "y"]}, "custom_remap"),
        ({"axis_remap": "custom", "custom_remap": ["x", "x", "y"]}, "custom_remap"),
        ({"axis_remap": "custom", "custom_remap": "xzy"}, "custom_remap"),
        ({"mirror": ["x", "x"]}, "mirror"),
        ({"mirror": ["w"]}, "mirror"),
        ({"rotations": [{"axis": "q", "deg": 90}]}, "eixo"),
    ]
    for body, trecho in casos:
        r = client.patch("/api/orient", json=body)
        assert r.status_code == 422, body
        assert trecho in r.json()["detail"], body


def test_rollback_orient(tmp_path, box, monkeypatch):
    _, session = _client(tmp_path, box)
    orient_antes = session.project.orient
    rev = session.revision

    import meshbench.api.session_ops as so

    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(so, "process", explode)
    with pytest.raises(RuntimeError):
        update_orient(session, {"rotations": [{"axis": "x", "deg": 90}]})
    assert session.project.orient == orient_antes
    assert session.revision == rev
