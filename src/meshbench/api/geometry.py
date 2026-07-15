"""Prepara a geometria processada para o viewport: GLB + orçamento de exibição.

O doc de arquitetura (§13) manda enviar uma versão decimada quando o viewport
receberia mais de ~200k triângulos — a exportação real nunca é afetada.
"""

from dataclasses import replace

import trimesh

DISPLAY_BUDGET = 200_000


def display_records(records, budget=DISPLAY_BUDGET):
    """Decima proporcionalmente para exibição se o total passar do orçamento."""
    total = sum(len(r.mesh.faces) for r in records)
    if total <= budget:
        return records
    ratio = budget / total
    out = []
    for r in records:
        target = max(100, int(len(r.mesh.faces) * ratio))
        try:
            m = r.mesh.simplify_quadric_decimation(face_count=target)
        except Exception:
            m = r.mesh  # exibir cheio é melhor que não exibir
        out.append(replace(r, mesh=m))
    return out


def build_scene_glb(records):
    """Monta um GLB com um nó por instância; nome do nó = '{component_id}.{i}'.

    O frontend usa o nome para mapear componente -> grupo -> cor; não dependemos
    de materiais do GLB.
    """
    scene = trimesh.Scene()
    for i, r in enumerate(records):
        name = f"{r.component_id}.{i}"
        scene.add_geometry(r.mesh, node_name=name, geom_name=name)
    return scene.export(file_type="glb")
