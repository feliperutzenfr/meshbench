import trimesh

from meshbench.cli import main


def _stl(tmp_path, box):
    p = tmp_path / "peca.stl"
    box.export(str(p))
    return p


def test_serve_monta_app_e_roda_uvicorn(tmp_path, box, monkeypatch, capsys):
    captured = {}

    def fake_run(app, **kwargs):
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr("uvicorn.run", fake_run)
    aberturas = []
    monkeypatch.setattr("webbrowser.open", lambda url: aberturas.append(url))

    rc = main(["serve", str(_stl(tmp_path, box)), "--no-browser", "--port", "8770"])
    assert rc == 0
    assert captured["kwargs"]["host"] == "127.0.0.1"
    assert captured["kwargs"]["port"] == 8770
    paths = {r.path for r in captured["app"].routes}
    assert "/api/project" in paths and "/api/project/geometry" in paths
    assert aberturas == []  # --no-browser
    assert "http://127.0.0.1:8770" in capsys.readouterr().out


def test_serve_abre_navegador_por_padrao(tmp_path, box, monkeypatch):
    monkeypatch.setattr("uvicorn.run", lambda app, **k: None)
    aberturas = []
    # o timer dispara webbrowser.open depois; interceptamos o próprio Timer
    import threading

    class FakeTimer:
        def __init__(self, delay, fn, args=()):
            self.fn, self.args = fn, args

        def start(self):
            self.fn(*self.args)

    monkeypatch.setattr(threading, "Timer", FakeTimer)
    monkeypatch.setattr("webbrowser.open", lambda url: aberturas.append(url))
    main(["serve", str(_stl(tmp_path, box))])
    assert aberturas == ["http://127.0.0.1:8765"]


def test_serve_arquivo_inexistente_erro_amigavel(capsys):
    rc = main(["serve", "nao_existe.stl"])
    assert rc == 1
    assert "erro:" in capsys.readouterr().out
