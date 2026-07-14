"""Orquestra a pilha de transformação (§4 do doc — a ordem NÃO é negociável):

 1. IMPORT   2. SCALE (primeiro!)   3. SPLIT   4. OPS   5. GROUP
 6. ORIENT   7. ORIGIN (por último!)   8. EXPORT
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from meshbench.core.analyze.components import split_components
from meshbench.core.io.readers import read_mesh
from meshbench.core.io.writers import write_meshes
from meshbench.core.ops import apply_op
from meshbench.core.transform.axes import remap_axes
from meshbench.core.transform.mirror import mirror
from meshbench.core.transform.origin import _bounds_of, place_origin
from meshbench.core.transform.rotate import rotate_90, rotate_free
from meshbench.core.transform.scale import apply_scale

FACE_BUDGET = 15000  # empírico: acima disso o Promob pode não abrir

_SIG_RE = re.compile(r"^f(\d+):v(\d+):b\[([^,\]]+),([^,\]]+),([^\]]+)\]$")


def _signature_at_scale(entry, factor):
    """Recalcula a assinatura esperada de uma peça da receita após a escala do run.

    `entry.signature` foi capturado com `split_components` sobre o mesh cru
    (fator 1, em `new_project`); aqui o SPLIT roda sobre o mesh já escalado
    (§4 — SCALE vem antes de SPLIT), então o bbox embutido na assinatura
    precisa ser reescalado na mesma proporção antes de comparar, senão nenhuma
    peça casa quando `scale` não for identidade.
    """
    m = _SIG_RE.match(entry.signature)
    if not m:
        return entry.signature
    faces, verts, dx, dy, dz = m.groups()
    d = np.round(
        [float(dx) * factor[0], float(dy) * factor[1], float(dz) * factor[2]], 1
    )
    return f"f{faces}:v{verts}:b[{d[0]},{d[1]},{d[2]}]"


@dataclass
class PipelineResult:
    files: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def apply_orient(mesh, orient):
    """remap de eixos → rotações (em ordem) → espelhos."""
    spec = orient.get("custom_remap") or orient.get("axis_remap", "identidade")
    m = remap_axes(mesh, spec)
    for r in orient.get("rotations", []):
        deg = float(r["deg"])
        if deg % 90 == 0:
            m = rotate_90(m, r["axis"], int(deg // 90))
        else:
            args = {"rx": 0.0, "ry": 0.0, "rz": 0.0, "r" + r["axis"]: deg}
            m = rotate_free(m, args["rx"], args["ry"], args["rz"])
    for ax in orient.get("mirror", []):
        m = mirror(m, ax)
    return m


def run(project, base_dir):
    """Executa a receita e exporta um arquivo por grupo. Retorna caminhos + avisos."""
    base_dir = Path(base_dir)
    warnings = []

    # 1. IMPORT
    src = Path(project.source["path"])
    if not src.is_absolute():
        src = base_dir / src
    mesh = read_mesh(src)

    # 2. SCALE — sempre primeiro: parâmetros das ops são em mm absolutos
    mesh, factor = apply_scale(mesh, project.scale)
    project.scale["factor"] = list(factor)
    dims = mesh.bounds[1] - mesh.bounds[0]
    if float(np.max(dims)) > 5000 or float(np.min(dims)) < 1:
        warnings.append(
            f"dimensão final suspeita ({dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} mm) "
            "— confira a unidade"
        )

    # 3. SPLIT
    families = split_components(mesh)
    by_sig = {_signature_at_scale(c, factor): c for c in project.components}

    # 4. OPS + 5. GROUP
    group_names = [g["name"] for g in project.groups] or ["saida"]
    grouped = {g: [] for g in group_names}
    feature_meshes = {}  # component id -> meshes processadas (p/ feature_ref da origem)
    for fam in families:
        entry = by_sig.get(fam.signature)
        if entry is None:
            warnings.append(
                f"componente {fam.signature} não está na receita — fora da saída"
            )
            continue
        if entry.operation.get("type") == "remove":
            continue
        if entry.operation.get("type") == "hull" and entry.auto_class == "profile":
            rotulo = entry.user_label or entry.id
            warnings.append(f"hull em perfil aberto ({rotulo}) — isto vai fechar o perfil")
        processed = []
        for m in fam.meshes:
            out = apply_op(m, entry.operation)
            if out is not None:
                processed.append(out)
        feature_meshes[entry.id] = processed
        if entry.group is None:
            rotulo = entry.user_label or entry.auto_class
            warnings.append(
                f"peça sem grupo e não removida: {entry.id} ({rotulo}) — vai sumir do resultado"
            )
            continue
        if entry.group not in grouped:
            grouped[entry.group] = []
        grouped[entry.group].extend(processed)

    # 6. ORIENT
    grouped = {
        g: [apply_orient(m, project.orient) for m in ms] for g, ms in grouped.items()
    }

    # 7. ORIGIN — sempre por último: a âncora só faz sentido na orientação final
    grouped = {g: ms for g, ms in grouped.items() if ms}
    if grouped:  # tudo removido/sem grupo → nada a ancorar nem exportar
        feature_bounds = None
        ref = project.origin.get("feature_ref")
        if ref and feature_meshes.get(ref):
            oriented_ref = [apply_orient(m, project.orient) for m in feature_meshes[ref]]
            feature_bounds = _bounds_of(oriented_ref)
        grouped = place_origin(
            grouped,
            mode=project.origin.get("mode", "common"),
            anchor=project.origin.get("anchor", "bbox_min"),
            snap_point=project.origin.get("snap_point"),
            feature_bounds=feature_bounds,
            offset=project.origin.get("offset", [0, 0, 0]),
        )

    # 8. EXPORT — um arquivo por grupo
    result = PipelineResult(warnings=warnings)
    out_dir = Path(project.export.get("out_dir", "out/"))
    if not out_dir.is_absolute():
        out_dir = base_dir / out_dir
    fmt = project.export.get("format", "dxf_r12")
    ext = {"dxf_r12": "dxf", "stl": "stl", "obj": "obj"}[fmt]
    naming = project.export.get("naming", "{project}_{group}." + ext)
    for g, ms in grouped.items():
        if not ms:
            continue
        name = naming.format(project=project.name, group=g)
        path = out_dir / name
        write_meshes(ms, path, fmt)
        faces = sum(len(m.faces) for m in ms)
        if faces > FACE_BUDGET:
            warnings.append(
                f"grupo '{g}' tem {faces} faces (> {FACE_BUDGET}) — pode não abrir no Promob"
            )
        result.files.append({"path": str(path), "group": g, "faces": faces})
    return result
