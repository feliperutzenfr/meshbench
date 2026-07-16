"""Mutações da sessão (fase 3). Toda mudança é ação explícita do usuário
(Aplicar/Salvar); o preview clona o projeto e NUNCA toca na sessão; o
reprocesso usa a malha crua em cache — nunca relê o arquivo fonte."""

from meshbench.api.geometry import build_scene_glb, display_records
from meshbench.core.ops import OPS
from meshbench.core.pipeline import process
from meshbench.core.project import Project


def reprocess(session):
    """Reexecuta o pipeline (etapas 2-7) com a malha crua em cache."""
    with session.lock:  # RLock — seguro também quando chamado de update_component
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
    if not isinstance(op, dict):
        raise ValueError(
            "corpo sem 'operation' — envie {\"operation\": {...}}"
        )
    kind = op.get("type")
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
        groups_len = len(session.project.groups)  # p/ desfazer grupo novo no rollback
        snapshot = (
            entry.operation,
            entry.group,
            entry.user_label,
            entry.needs_review,
        )
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
        try:
            reprocess(session)
        except Exception:
            # reprocesso falhou — restaura a família E o grupo recém-criado
            # (se houver), nada fica meio-editado
            del session.project.groups[groups_len:]
            (
                entry.operation,
                entry.group,
                entry.user_label,
                entry.needs_review,
            ) = snapshot
            raise


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
        clone_entry = _find_entry(clone, comp_id)
        clone_entry.operation = op
        if clone_entry.group is None:
            # process() descarta (sem exportar) qualquer família com group=None
            # (peça recém-importada sugerida para remover ou ainda não
            # revisada) — no preview isso faria a operação "sumir" mesmo
            # tendo rodado com sucesso. Só no CLONE (nunca na sessão real):
            # atribui um grupo provisório só para o processo não descartar a
            # malha; o preview usa só as malhas da família, ignora grupo.
            clone_entry.group = "_preview"
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
