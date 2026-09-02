import numpy as np
import pytest

from meshbench.api.server import load_session
from meshbench.api.session_ops import (
    preview_op,
    reprocess,
    save_recipe,
    undo,
    update_component,
    update_components,
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


def test_preview_funciona_em_familia_sem_grupo(tmp_path, small_sphere):
    # esfera recém-importada: sugerida pra remover, group=None — o preview
    # não pode confundir isso com "operação não produziu malha" (a operação
    # rodou normalmente, só a família nunca teve grupo atribuído)
    s = _session(tmp_path, small_sphere)
    comp = s.project.components[0].id
    assert s.project.components[0].group is None
    glb, before, after = preview_op(s, comp, {"type": "keep", "params": {}})
    assert glb is not None and glb[:4] == b"glTF"
    assert after == 320


def test_preview_op_que_remove_retorna_none(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    comp = s.project.components[0].id
    update_component(s, comp, {"operation": {"type": "keep", "params": {}}, "group": "saida"})
    glb, before, after = preview_op(s, comp, {"type": "remove", "params": {}})
    assert glb is None
    assert before == 320 and after == 0


def test_update_component_reverte_se_reprocesso_falha(
    tmp_path, small_sphere, monkeypatch
):
    import pytest

    import meshbench.api.session_ops as session_ops

    s = _session(tmp_path, small_sphere)
    entry = s.project.components[0]
    op_antes = entry.operation
    grupo_antes = entry.group
    review_antes = entry.needs_review
    rev_antes = s.revision
    groups_antes = list(s.project.groups)

    def _explode(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(session_ops, "process", _explode)
    with pytest.raises(RuntimeError, match="boom"):
        update_component(
            s,
            entry.id,
            {
                "operation": {"type": "keep", "params": {}},
                "group": "grupo_novo_que_nao_deve_sobreviver",
            },
        )
    # sessão restaurada — nada meio-editado
    assert entry.operation == op_antes
    assert entry.group == grupo_antes
    assert entry.needs_review == review_antes
    # grupo novo criado antes do reprocesso falhar não deve vazar
    assert s.project.groups == groups_antes
    assert s.revision == rev_antes


def test_save_recipe_grava_e_recarrega(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    update_component(s, s.project.components[0].id, {"user_label": "bolinha"})
    path = save_recipe(s)
    assert path.exists()
    p2 = Project.load(path)
    assert p2.components[0].user_label == "bolinha"


def _session_2_pecas(tmp_path, small_sphere, box):
    """Sessão com duas famílias distintas (esfera + caixa afastadas)."""
    import trimesh

    b = box.copy()
    b.apply_translation([200.0, 0.0, 0.0])
    p = tmp_path / "duas.stl"
    trimesh.util.concatenate([small_sphere, b]).export(str(p))
    return load_session(p)


def test_update_components_aplica_em_lote_com_um_so_reprocesso(
    tmp_path, small_sphere, box
):
    s = _session_2_pecas(tmp_path, small_sphere, box)
    ids = [c.id for c in s.project.components]
    assert len(ids) == 2
    rev = s.revision
    update_components(s, ids, {"operation": {"type": "remove", "params": {}}})
    # UM reprocesso para as duas peças — não um por peça
    assert s.revision == rev + 1
    assert all(c.operation["type"] == "remove" for c in s.project.components)


def test_update_components_empilha_um_unico_desfazer(tmp_path, small_sphere, box):
    s = _session_2_pecas(tmp_path, small_sphere, box)
    antes = [c.operation["type"] for c in s.project.components]
    update_components(
        s,
        [c.id for c in s.project.components],
        {"operation": {"type": "remove", "params": {}}},
    )
    assert len(s.undo_stack) == 1
    undo(s)  # um só desfazer devolve as duas peças ao estado original
    assert [c.operation["type"] for c in s.project.components] == antes


def test_update_components_id_inexistente_nao_muta_nada(tmp_path, small_sphere, box):
    s = _session_2_pecas(tmp_path, small_sphere, box)
    ids = [c.id for c in s.project.components]
    antes = s.project.to_dict()
    with pytest.raises(KeyError):
        update_components(s, [ids[0], "naoexiste"], {"group": "movel"})
    assert s.project.to_dict() == antes
    assert s.undo_stack == []


def test_update_components_grupo_novo_uma_vez_so(tmp_path, small_sphere, box):
    s = _session_2_pecas(tmp_path, small_sphere, box)
    update_components(s, [c.id for c in s.project.components], {"group": "movel"})
    nomes = [g["name"] for g in s.project.groups]
    assert nomes.count("movel") == 1


def test_update_components_lista_vazia_e_erro(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    with pytest.raises(ValueError):
        update_components(s, [], {"group": "movel"})
