"""Leitura de malhas. STL/OBJ/PLY/3MF via trimesh; DXF (3DFACE) via ezdxf."""

from pathlib import Path

import ezdxf
import numpy as np
import trimesh

TRIMESH_EXTS = {".stl", ".obj", ".ply", ".3mf"}


def read_mesh(path):
    """Lê um arquivo de malha e retorna um trimesh.Trimesh com vértices já mesclados."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".dxf":
        return read_dxf_3dface(path)
    if ext in TRIMESH_EXTS:
        m = trimesh.load(str(path), force="mesh")
        m.merge_vertices()
        return m
    raise ValueError(
        f"formato '{ext}' não suportado (aceitos: STL, OBJ, PLY, 3MF, DXF com 3DFACE)"
    )


def read_dxf_3dface(path):
    """Lê entidades 3DFACE de um DXF e monta uma malha triangular."""
    doc = ezdxf.readfile(str(path))
    verts, tris = [], []
    for f in doc.modelspace().query("3DFACE"):
        p = [f.dxf.vtx0, f.dxf.vtx1, f.dxf.vtx2, f.dxf.vtx3]
        base = len(verts)
        is_quad = p[2] != p[3]
        for pp in p[:4] if is_quad else p[:3]:
            verts.append((pp[0], pp[1], pp[2]))
        if is_quad:
            tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
        else:
            tris.append((base, base + 1, base + 2))
    if not tris:
        raise ValueError(f"nenhuma entidade 3DFACE encontrada em '{path}'")
    m = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(tris), process=False)
    m.merge_vertices()  # ESSENCIAL — sem isso o split() não acha componentes
    return m
