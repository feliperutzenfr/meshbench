import numpy as np

from meshbench.api.server import load_session
from meshbench.api.session_ops import (
    preview_op,
    reprocess,
    save_recipe,
    update_component,
)
from meshbench.core.project import Project


def _session(tmp_path, small_sphere):
    p = tmp_path / "esfera.stl"
    small_sphere.export(str(p))
    return load_session(p)


def test_load_session_cacheia_malha_e_recipe_path(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    assert s.raw_mesh is not None and len(s.raw_mesh.faces) == 320
    assert s.recipe_path == (tmp_path / "esfera.meshbench.json").resolve()
    assert s.revision == 0


def test_update_component_reprocessa_e_incrementa_revision(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    # esfera pequena é sugerida como remove/sem grupo — trazer para a saída
    comp = s.project.components[0].id
    update_component(
        s,
        comp,
        {
            "operation": {"type": "decimate", "params": {"face_count": 80}},
            "group": "saida",
        },
    )
    assert s.revision == 1
    assert s.project.components[0].operation["type"] == "decimate"
    total = sum(len(r.mesh.faces) for r in s.records)
    assert 0 < total <= 100


def test_update_component_cria_grupo_novo(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    update_component(s, s.project.components[0].id, {"group": "movel"})
    assert {"name": "movel", "role": "fixed"} in s.project.groups


def test_update_component_limpa_needs_review(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    s.project.components[0].needs_review = True
    update_component(s, s.project.components[0].id, {"user_label": "solda"})
    assert s.project.components[0].needs_review is False
    assert s.project.components[0].user_label == "solda"


def test_update_component_valida(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    import pytest

    with pytest.raises(KeyError):
        update_component(s, "c99", {"user_label": "x"})
    with pytest.raises(ValueError, match="operação"):
        update_component(
            s, s.project.components[0].id, {"operation": {"type": "explodir"}}
        )


def test_preview_nao_muta_sessao(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    comp = s.project.components[0].id
    update_component(s, comp, {"operation": {"type": "keep", "params": {}}, "group": "saida"})
    rev = s.revision
    glb, before, after = preview_op(
        s, comp, {"type": "decimate", "params": {"face_count": 80}}
    )
    assert glb[:4] == b"glTF"
    assert before == 320
    assert 0 < after <= 100
    # sessão intocada
    assert s.revision == rev
    assert s.project.components[0].operation["type"] == "keep"
    assert sum(len(r.mesh.faces) for r in s.records) == 320


def test_preview_op_que_remove_retorna_none(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    comp = s.project.components[0].id
    update_component(s, comp, {"operation": {"type": "keep", "params": {}}, "group": "saida"})
    glb, before, after = preview_op(s, comp, {"type": "remove", "params": {}})
    assert glb is None
    assert before == 320 and after == 0


def test_save_recipe_grava_e_recarrega(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    update_component(s, s.project.components[0].id, {"user_label": "bolinha"})
    path = save_recipe(s)
    assert path.exists()
    p2 = Project.load(path)
    assert p2.components[0].user_label == "bolinha"
