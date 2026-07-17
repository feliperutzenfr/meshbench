"""Mutações da sessão (fase 3). Toda mudança é ação explícita do usuário
(Aplicar/Salvar); o preview clona o projeto e NUNCA toca na sessão; o
reprocesso usa a malha crua em cache — nunca relê o arquivo fonte."""

import math

from meshbench.api.geometry import build_scene_glb, display_records
from meshbench.core.analyze.units import UNIT_MM
from meshbench.core.ops import OPS
from meshbench.core.pipeline import process
from meshbench.core.project import Project
from meshbench.core.transform.axes import REMAPS


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


_SCALE_MODES = ("unit_convert", "uniform", "per_axis", "fit_dimension")


def _validated_scale(spec):
    """Valida e normaliza o spec de escala vindo da UI. Levanta ValueError pt-BR."""
    if not isinstance(spec, dict):
        raise ValueError("'scale' inválido — envie {\"scale\": {...}}")
    mode = spec.get("mode")
    if mode not in _SCALE_MODES:
        raise ValueError(
            f"modo de escala '{mode}' desconhecido (disponíveis: {sorted(_SCALE_MODES)})"
        )
    out = {
        "mode": mode,
        "from_unit": "mm",
        "to_unit": "mm",
        "value": None,
        "per_axis": None,
        "fit": None,
        "factor": [1, 1, 1],
    }
    if mode == "unit_convert":
        from_unit = spec.get("from_unit")
        to_unit = spec.get("to_unit", "mm")
        if from_unit not in UNIT_MM or to_unit not in UNIT_MM:
            raise ValueError(f"unidade inválida (aceitas: {sorted(UNIT_MM)})")
        out["from_unit"], out["to_unit"] = from_unit, to_unit
    elif mode == "uniform":
        value = spec.get("value")
        if not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0:
            raise ValueError("fator uniforme deve ser um número positivo")
        out["value"] = float(value)
    elif mode == "per_axis":
        per_axis = spec.get("per_axis")
        if (
            not isinstance(per_axis, list)
            or len(per_axis) != 3
            or not all(
                isinstance(x, (int, float)) and not isinstance(x, bool) and x > 0
                for x in per_axis
            )
        ):
            raise ValueError("per_axis deve ser uma lista de 3 números positivos")
        out["per_axis"] = [float(x) for x in per_axis]
    else:  # fit_dimension
        fit = spec.get("fit") or {}
        axis = fit.get("axis")
        target = fit.get("target_mm")
        if axis not in ("x", "y", "z"):
            raise ValueError("fit.axis deve ser x, y ou z")
        if not isinstance(target, (int, float)) or isinstance(target, bool) or target <= 0:
            raise ValueError("fit.target_mm deve ser um número positivo")
        out["fit"] = {"axis": axis, "target_mm": float(target)}
    return out


def update_scale(session, changes):
    """Aplica mudança de escala e/ou confirmação de unidade e reprocessa.

    Valida TUDO antes de atribuir qualquer coisa; rollback completo se o
    reprocesso falhar — nada fica meio-editado.
    """
    with session.lock:
        new_scale = None
        new_units = None
        if "scale" in changes:
            new_scale = _validated_scale(changes["scale"])
        if "units" in changes:
            new_units = changes["units"]
            if new_units not in UNIT_MM:
                raise ValueError(f"unidade '{new_units}' inválida (aceitas: {sorted(UNIT_MM)})")

        source = session.project.source
        # CÓPIA do scale, não a referência: process() muta scale["factor"] in
        # place antes de estágios que podem falhar — a referência viva
        # "restauraria" o próprio dict já mutado
        snapshot = (
            dict(session.project.scale),
            source.get("units"),
            "units_confirmed" in source,
            source.get("units_confirmed"),
        )
        if new_scale is not None:
            session.project.scale = new_scale
        if new_units is not None:
            source["units"] = new_units
            source["units_confirmed"] = True
        try:
            reprocess(session)
        except Exception:
            session.project.scale = snapshot[0]
            source["units"] = snapshot[1]
            if snapshot[2]:
                source["units_confirmed"] = snapshot[3]
            else:
                source.pop("units_confirmed", None)
            raise


def normalize_rotations(rotations):
    """Valida e normaliza a lista de rotações da receita.

    deg % 360; zeros descartados; consecutivas no mesmo eixo fundidas —
    a receita fica limpa mesmo com o usuário clicando X+90 quatro vezes.
    """
    if not isinstance(rotations, list):
        raise ValueError("rotations deve ser uma lista de {axis, deg}")
    out = []
    for r in rotations:
        if not isinstance(r, dict) or r.get("axis") not in ("x", "y", "z"):
            raise ValueError("eixo de rotação inválido (use x, y ou z)")
        deg = r.get("deg")
        if (
            isinstance(deg, bool)
            or not isinstance(deg, (int, float))
            or not math.isfinite(deg)
        ):
            raise ValueError("graus de rotação devem ser numéricos")
        deg = float(deg) % 360.0
        if deg == 0.0:
            continue
        if out and out[-1]["axis"] == r["axis"]:
            fused = (out[-1]["deg"] + deg) % 360.0
            if fused == 0.0:
                out.pop()
            else:
                out[-1]["deg"] = fused
        else:
            out.append({"axis": r["axis"], "deg": deg})
    return out


def _validated_orient(current, changes):
    """Monta o dict de orient completo a partir do atual + mudanças. ValueError pt-BR."""
    axis_remap = changes.get("axis_remap", current.get("axis_remap", "identidade"))
    custom_remap = changes.get("custom_remap", current.get("custom_remap"))
    if axis_remap == "custom":
        if not isinstance(custom_remap, (list, tuple)):
            raise ValueError(
                "custom_remap deve ter os 3 eixos (±x, ±y, ±z), cada um uma vez"
            )
        base = [str(a).lstrip("+-") for a in (custom_remap or [])]
        if sorted(base) != ["x", "y", "z"]:
            raise ValueError(
                "custom_remap deve ter os 3 eixos (±x, ±y, ±z), cada um uma vez"
            )
    elif axis_remap in REMAPS:
        custom_remap = None
    else:
        raise ValueError(
            f"remap '{axis_remap}' desconhecido (disponíveis: {sorted(REMAPS)} ou custom)"
        )
    if "rotations" in changes:
        rotations = normalize_rotations(changes["rotations"])
    else:
        rotations = current.get("rotations", [])
    mirror = changes.get("mirror", current.get("mirror", []))
    if (
        not isinstance(mirror, list)
        or len(set(mirror)) != len(mirror)
        or not all(m in ("x", "y", "z") for m in mirror)
    ):
        raise ValueError("mirror deve ser um subconjunto de x/y/z sem repetição")
    return {
        "axis_remap": axis_remap,
        "custom_remap": list(custom_remap) if custom_remap else None,
        "rotations": list(rotations),
        "mirror": list(mirror),
    }


def update_orient(session, changes):
    """Aplica mudança de orientação e reprocessa. Rollback se o reprocesso falhar."""
    with session.lock:
        new_orient = _validated_orient(session.project.orient, changes)
        # referência basta como snapshot: process() não muta orient in place
        # (ao contrário de scale["factor"]) e nós substituímos o dict inteiro
        snapshot = session.project.orient
        session.project.orient = new_orient
        try:
            reprocess(session)
        except Exception:
            session.project.orient = snapshot
            raise
