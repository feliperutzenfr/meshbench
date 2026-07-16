"""Mutações da sessão (fase 3). Toda mudança é ação explícita do usuário
(Aplicar/Salvar); o preview clona o projeto e NUNCA toca na sessão; o
reprocesso usa a malha crua em cache — nunca relê o arquivo fonte."""

from meshbench.api.geometry import build_scene_glb, display_records
from meshbench.core.ops import OPS
from meshbench.core.pipeline import process
from meshbench.core.project import Project


def reprocess(session):
    """Reexecuta o pipeline (etapas 2-7) com a malha crua em cache."""
    records, warnings = process(
        session.project, session.base_dir, mesh=session.raw_mesh
    )
    session.records = records
    session.warnings = warnings
    session.revision += 1


def _find_entry(project, comp_id):
    entry = next((c for c in project.components if c.id == comp_id), None)
    if entry is None:
        raise KeyError(f"componente '{comp_id}' não existe")
    return entry


def _validated_op(op):
    kind = (op or {}).get("type")
    if kind not in OPS:
        raise ValueError(
            f"operação '{kind}' desconhecida (disponíveis: {sorted(OPS)})"
        )
    return {"type": kind, "params": (op or {}).get("params") or {}}


def update_component(session, comp_id, changes):
    """Aplica mudanças de operação/grupo/rótulo a uma família e reprocessa.

    Grupo inexistente é acrescentado a project.groups (role "fixed").
    Editar uma família limpa needs_review — o usuário acabou de revisá-la.
    """
    with session.lock:
        entry = _find_entry(session.project, comp_id)
        if "operation" in changes:
            entry.operation = _validated_op(changes["operation"])
        if "group" in changes:
            group = changes["group"]
            entry.group = group
            names = [g["name"] for g in session.project.groups]
            if group is not None and group not in names:
                session.project.groups.append({"name": group, "role": "fixed"})
        if "user_label" in changes:
            entry.user_label = changes["user_label"] or None
        entry.needs_review = False
        reprocess(session)


def preview_op(session, comp_id, operation):
    """Pré-visualiza uma operação SEM tocar na sessão.

    Clona o projeto (to_dict/from_dict = cópia profunda), troca a operação da
    família, reprocessa o clone e retorna (glb | None, faces_antes,
    faces_depois) só com as malhas da família pré-visualizada.
    """
    with session.lock:
        op = _validated_op(operation)
        _find_entry(session.project, comp_id)
        clone = Project.from_dict(session.project.to_dict())
        _find_entry(clone, comp_id).operation = op
        faces_before = sum(
            len(r.mesh.faces)
            for r in session.records
            if r.component_id == comp_id
        )
        records, _ = process(clone, session.base_dir, mesh=session.raw_mesh)
        preview_records = [r for r in records if r.component_id == comp_id]
        faces_after = sum(len(r.mesh.faces) for r in preview_records)
        glb = None
        if preview_records:
            glb = build_scene_glb(display_records(preview_records))
        return glb, faces_before, faces_after


def save_recipe(session):
    """Grava a receita no caminho da sessão. Explícito — nunca automático."""
    with session.lock:
        session.project.save(session.recipe_path)
        return session.recipe_path
