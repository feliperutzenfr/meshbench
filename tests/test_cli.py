import json

import trimesh

from meshbench.cli import main


def test_inspect_arquivo_inexistente_erro_amigavel(tmp_path, capsys):
    assert main(["inspect", str(tmp_path / "nao_existe.stl")]) == 1
    out = capsys.readouterr().out
    assert "erro:" in out
    assert "Traceback" not in out


def _stl(tmp_path, box, small_sphere):
    s = small_sphere.copy()
    s.apply_translation([100, 0, 0])
    scene = trimesh.util.concatenate([box, s])
    p = tmp_path / "cena.stl"
    scene.export(str(p))
    return p


def test_inspect(tmp_path, box, small_sphere, capsys):
    src = _stl(tmp_path, box, small_sphere)
    assert main(["inspect", str(src)]) == 0
    out = capsys.readouterr().out
    assert "c0" in out and "c1" in out
    assert "weld_sphere" in out
    assert "mm" in out  # dimensões e/ou unidade sugerida


def test_init_cria_receita(tmp_path, box, small_sphere):
    src = _stl(tmp_path, box, small_sphere)
    receita = tmp_path / "cena.meshbench.json"
    assert main(["init", str(src)]) == 0
    assert receita.exists()
    d = json.loads(receita.read_text(encoding="utf-8"))
    assert d["name"] == "cena"
    assert len(d["components"]) == 2
    assert d["source"]["path"] == "cena.stl"  # relativo à pasta da receita


def test_apply_exporta(tmp_path, box, small_sphere, capsys):
    src = _stl(tmp_path, box, small_sphere)
    main(["init", str(src)])
    receita = tmp_path / "cena.meshbench.json"
    assert main(["apply", str(receita)]) == 0
    out = capsys.readouterr().out
    assert (tmp_path / "out" / "cena_saida.dxf").exists()
    assert "faces" in out


def test_apply_mostra_avisos(tmp_path, box, small_sphere, capsys):
    src = _stl(tmp_path, box, small_sphere)
    main(["init", str(src)])
    receita = tmp_path / "cena.meshbench.json"
    d = json.loads(receita.read_text(encoding="utf-8"))
    for c in d["components"]:
        c["group"] = None
        c["operation"] = {"type": "keep", "params": {}}
    receita.write_text(json.dumps(d), encoding="utf-8")
    main(["apply", str(receita)])
    out = capsys.readouterr().out
    assert "⚠" in out and "sem grupo" in out
    assert "nenhum arquivo exportado" in out


def test_apply_reimport_rematch(tmp_path, box, small_sphere, capsys):
    src = _stl(tmp_path, box, small_sphere)
    main(["init", str(src)])
    receita = tmp_path / "cena.meshbench.json"
    # o source mudou: só a caixa agora
    box.export(str(src))
    assert main(["apply", str(receita), "--reimport"]) == 0
    out = capsys.readouterr().out
    assert "sumiu" in out
    d = json.loads(receita.read_text(encoding="utf-8"))
    assert len(d["components"]) == 1  # receita atualizada e salva
