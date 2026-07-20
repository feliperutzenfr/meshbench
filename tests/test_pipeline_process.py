import numpy as np
import trimesh

from meshbench.core.analyze.components import split_components
from meshbench.core.pipeline import ProcessedComponent, process
from meshbench.core.project import new_project


def _project(tmp_path, box, small_sphere):
    s = small_sphere.copy()
    s.apply_translation([100, 0, 0])
    scene = trimesh.util.concatenate([box, s])
    src = tmp_path / "cena.stl"
    scene.export(str(src))
    p = new_project("teste", src, scene, split_components(scene))
    p.source["path"] = "cena.stl"
    return p


def test_process_retorna_registros(tmp_path, box, small_sphere):
    p = _project(tmp_path, box, small_sphere)
    records, warnings = process(p, tmp_path)
    # esfera é weld_sphere -> remove; sobra só a caixa
    assert len(records) == 1
    r = records[0]
    assert isinstance(r, ProcessedComponent)
    assert r.group == "saida"
    assert r.component_id in {c.id for c in p.components}
    assert len(r.mesh.faces) == 12


def test_process_aplica_origem(tmp_path, box, small_sphere):
    p = _project(tmp_path, box, small_sphere)
    records, _ = process(p, tmp_path)
    assert np.allclose(records[0].mesh.bounds[0], [0, 0, 0], atol=1e-6)


def test_process_nao_exporta(tmp_path, box, small_sphere):
    p = _project(tmp_path, box, small_sphere)
    process(p, tmp_path)
    assert not (tmp_path / "out").exists()


def test_process_avisa_decimacao_sem_efeito(tmp_path, box, small_sphere):
    p = _project(tmp_path, box, small_sphere)
    caixa = [c for c in p.components if c.face_count == 12][0]
    # alvo acima da contagem atual: decimação garantidamente não reduz nada
    caixa.operation = {"type": "decimate", "params": {"face_count": 200}}
    _, warnings = process(p, tmp_path)
    assert any("decimação não reduziu as faces" in w for w in warnings)


def test_process_label(tmp_path, box, small_sphere):
    p = _project(tmp_path, box, small_sphere)
    caixa = [c for c in p.components if c.face_count == 12][0]
    caixa.user_label = "metalon"
    records, _ = process(p, tmp_path)
    assert records[0].label == "metalon"


def test_process_com_malha_pre_carregada(tmp_path, box):
    """Com mesh= fornecido, process() não relê o arquivo fonte (cache da sessão)."""
    from meshbench.core.analyze.components import split_components
    from meshbench.core.pipeline import process
    from meshbench.core.project import new_project

    src = tmp_path / "caixa.stl"
    box.export(str(src))
    p = new_project("t", src, box, split_components(box))
    p.source["path"] = "caixa.stl"

    src.unlink()  # o arquivo some — só o cache pode servir a malha

    records, warnings = process(p, tmp_path, mesh=box)
    assert len(records) == 1
    assert len(records[0].mesh.faces) == 12
    # a malha fornecida não foi mutada
    import numpy as np
    assert np.allclose(box.extents, [10, 20, 30])


def test_warning_origem_flutuando(tmp_path, box):
    """Offset grande deixa a geometria longe da origem → aviso do validador §8.3."""
    from meshbench.api.server import load_session
    from meshbench.core.pipeline import process

    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)

    session.project.origin["offset"] = [100.0, 0.0, 0.0]
    _, warnings = process(session.project, session.base_dir, mesh=session.raw_mesh)
    assert any("origem flutuando" in w for w in warnings)

    session.project.origin["offset"] = [0.0, 0.0, 0.0]
    _, warnings = process(session.project, session.base_dir, mesh=session.raw_mesh)
    assert not any("origem flutuando" in w for w in warnings)
