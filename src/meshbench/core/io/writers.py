"""Escrita de malhas. DXF R12 (3DFACE) é o alvo principal — validado no Promob."""

from pathlib import Path

import ezdxf
import trimesh


def write_dxf_r12(meshes, path):
    """Escreve malhas como entidades 3DFACE num DXF R12 (AC1009)."""
    doc = ezdxf.new(dxfversion="AC1009")
    msp = doc.modelspace()
    for m in meshes:
        v = m.vertices
        for tri in m.faces:
            a, b, c = v[tri[0]], v[tri[1]], v[tri[2]]
            msp.add_3dface([tuple(a), tuple(b), tuple(c), tuple(c)])
    doc.saveas(str(path))


def write_meshes(meshes, path, fmt):
    """Escreve uma lista de malhas num único arquivo, no formato pedido."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "dxf_r12":
        write_dxf_r12(meshes, path)
    elif fmt in ("stl", "obj"):
        combined = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
        # file_type explícito: sem isso o trimesh infere do sufixo do path, que
        # pode não bater com fmt (ex.: exportar STL para um arquivo .dxf).
        combined.export(str(path), file_type=fmt)
    else:
        raise ValueError(f"formato de exportação '{fmt}' não suportado")
