import pytest
import trimesh

from meshbench.core.analyze.components import split_components
from meshbench.core.project import Project, new_project, rematch, sha256_of


def _scene(box, small_sphere):
    s = small_sphere.copy()
    s.apply_translation([100, 0, 0])
    return trimesh.util.concatenate([box, s])


def test_new_project_preenche_sugestoes(tmp_path, box, small_sphere):
    scene = _scene(box, small_sphere)
    src = tmp_path / "cena.stl"
    scene.export(str(src))
    fams = split_components(scene)

    p = new_project("teste", src, scene, fams)
    assert p.name == "teste"
    assert p.source["sha256"] == sha256_of(src)
    assert len(p.components) == 2
    esfera = [c for c in p.components if c.face_count == 320][0]
    assert esfera.auto_class == "weld_sphere"
    assert esfera.operation == {"type": "remove", "params": {}}
    assert esfera.user_label is None  # heurística NUNCA vira rótulo do usuário
    caixa = [c for c in p.components if c.face_count == 12][0]
    assert caixa.group == "saida"
    assert p.groups == [{"name": "saida", "role": "fixed"}]


def test_roundtrip_json(tmp_path, box, small_sphere):
    scene = _scene(box, small_sphere)
    src = tmp_path / "cena.stl"
    scene.export(str(src))
    p = new_project("teste", src, scene, split_components(scene))
    f = tmp_path / "teste.meshbench.json"
    p.save(f)
    p2 = Project.load(f)
    assert p2.to_dict() == p.to_dict()


def test_rematch_preserva_escolhas(tmp_path, box, small_sphere):
    scene = _scene(box, small_sphere)
    src = tmp_path / "cena.stl"
    scene.export(str(src))
    p = new_project("teste", src, scene, split_components(scene))
    caixa = [c for c in p.components if c.face_count == 12][0]
    caixa.user_label = "metalon"
    caixa.operation = {"type": "hull", "params": {}}
    caixa.group = "fixa"

    # re-export: a esfera sumiu, a caixa continua, entrou um cilindro novo
    cyl = trimesh.creation.cylinder(radius=5, height=40)
    cyl.apply_translation([0, 200, 0])
    scene2 = trimesh.util.concatenate([box.copy(), cyl])
    n_antes = len(p.components)
    p2, avisos = rematch(p, split_components(scene2))
    assert len(p.components) == n_antes  # rematch não muta o projeto original

    caixa2 = [c for c in p2.components if c.face_count == 12][0]
    assert caixa2.user_label == "metalon"
    assert caixa2.operation["type"] == "hull"
    assert caixa2.group == "fixa"
    assert caixa2.needs_review is False

    novos = [c for c in p2.components if c.needs_review]
    assert len(novos) == 1  # o cilindro

    assert any("sumiu" in a for a in avisos)  # a esfera desapareceu


def test_from_dict_orient_parcial_ganha_shape_completo():
    """Receita editada à mão com orient parcial (só axis_remap) não pode quebrar
    o frontend (OrientBar acessa orient.rotations/orient.mirror) — from_dict
    completa o dict com os defaults."""
    d = {
        "name": "teste",
        "source": {"path": "x.stl"},
        "orient": {"axis_remap": "cad_to_promob"},
    }
    p = Project.from_dict(d)
    assert p.orient == {
        "axis_remap": "cad_to_promob",
        "custom_remap": None,
        "rotations": [],
        "mirror": [],
    }


def test_from_dict_orient_custom_sem_custom_remap_levanta_erro_pt_br():
    d = {
        "name": "teste",
        "source": {"path": "x.stl"},
        "orient": {"axis_remap": "custom", "custom_remap": None},
    }
    with pytest.raises(ValueError, match="custom"):
        Project.from_dict(d)


def test_from_dict_scale_parcial_ganha_shape_completo():
    d = {
        "name": "teste",
        "source": {"path": "x.stl"},
        "scale": {"mode": "uniform", "value": 2},
    }
    p = Project.from_dict(d)
    assert p.scale == {
        "mode": "uniform",
        "from_unit": "mm",
        "to_unit": "mm",
        "value": 2,
        "per_axis": None,
        "fit": None,
        "factor": [1, 1, 1],
    }
