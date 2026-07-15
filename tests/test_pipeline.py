import numpy as np
import trimesh

from meshbench.core.analyze.components import split_components
from meshbench.core.io.readers import read_dxf_3dface
from meshbench.core.pipeline import run
from meshbench.core.project import new_project


def _setup(tmp_path, box, small_sphere):
    """Cena: caixa (fica) + esfera de solda (remove) + caixa pequena sem grupo."""
    s = small_sphere.copy()
    s.apply_translation([100, 0, 0])
    orfa = trimesh.creation.box(extents=[5, 5, 5])
    orfa.apply_translation([0, 100, 0])
    scene = trimesh.util.concatenate([box, s, orfa])
    src = tmp_path / "cena.stl"
    scene.export(str(src))
    p = new_project("teste", src, scene, split_components(scene))
    p.source["path"] = "cena.stl"  # relativo ao base_dir
    # caixa 5x5x5 fica sem grupo de propósito (validador deve avisar)
    orfa_entry = [c for c in p.components if "b[5.0,5.0,5.0]" in c.signature][0]
    orfa_entry.group = None
    orfa_entry.operation = {"type": "keep", "params": {}}
    return p


def test_pipeline_exporta_dxf(tmp_path, box, small_sphere):
    p = _setup(tmp_path, box, small_sphere)
    res = run(p, tmp_path)
    assert len(res.files) == 1
    out = tmp_path / "out" / "teste_saida.dxf"
    assert out.exists()
    m = read_dxf_3dface(out)
    assert len(m.faces) == 12  # só a caixa (esfera removida, órfã sem grupo)


def test_pipeline_origem_zerada(tmp_path, box, small_sphere):
    p = _setup(tmp_path, box, small_sphere)
    run(p, tmp_path)
    m = read_dxf_3dface(tmp_path / "out" / "teste_saida.dxf")
    assert np.allclose(m.bounds[0], [0, 0, 0], atol=1e-6)


def test_pipeline_avisa_peca_sem_grupo(tmp_path, box, small_sphere):
    p = _setup(tmp_path, box, small_sphere)
    res = run(p, tmp_path)
    assert any("sem grupo" in w for w in res.warnings)


def test_pipeline_escala_antes_de_tudo(tmp_path, box, small_sphere):
    p = _setup(tmp_path, box, small_sphere)
    p.scale = {"mode": "uniform", "value": 2.0}
    run(p, tmp_path)
    m = read_dxf_3dface(tmp_path / "out" / "teste_saida.dxf")
    assert np.allclose(m.extents, [20, 40, 60])


def test_pipeline_orient_e_origem_por_ultimo(tmp_path, box, small_sphere):
    p = _setup(tmp_path, box, small_sphere)
    p.orient = {
        "axis_remap": "identidade",
        "custom_remap": None,
        "rotations": [{"axis": "x", "deg": 90}],
        "mirror": [],
    }
    run(p, tmp_path)
    m = read_dxf_3dface(tmp_path / "out" / "teste_saida.dxf")
    # caixa 10x20x30 girada 90° em X → 10x30x20, e AINDA zerada na origem
    assert np.allclose(m.extents, [10, 30, 20])
    assert np.allclose(m.bounds[0], [0, 0, 0], atol=1e-6)


def test_pipeline_avisa_dimensao_absurda(tmp_path, box, small_sphere):
    p = _setup(tmp_path, box, small_sphere)
    p.scale = {"mode": "uniform", "value": 1000.0}
    res = run(p, tmp_path)
    assert any("confira a unidade" in w for w in res.warnings)


def test_pipeline_escala_com_dimensao_fracionaria(tmp_path):
    # Regressão: a assinatura da receita guarda o bbox JÁ arredondado a 1 casa;
    # com fator grande (in→mm 25.4) round(cru,1)*fator ≠ round(cru*fator,1) e o
    # match exato por string derrubava a peça silenciosamente.
    caixa = trimesh.creation.box(extents=[12.34, 20.0, 30.0])
    src = tmp_path / "caixa.stl"
    caixa.export(str(src))
    p = new_project("teste", src, caixa, split_components(caixa))
    p.source["path"] = "caixa.stl"
    p.scale = {"mode": "unit_convert", "from_unit": "in", "to_unit": "mm"}
    res = run(p, tmp_path)
    assert len(res.files) == 1
    assert not any("não está na receita" in w for w in res.warnings)
