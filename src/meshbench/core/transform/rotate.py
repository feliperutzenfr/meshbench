"""Rotação: snap de 90° (o caminho padrão — ver > deduzir) e rotação livre."""

import numpy as np
import trimesh


def _rotate_90_verts(v, axis, steps):
    for _ in range(steps % 4):
        if axis == "z":
            v = np.column_stack([-v[:, 1], v[:, 0], v[:, 2]])
        elif axis == "x":
            v = np.column_stack([v[:, 0], -v[:, 2], v[:, 1]])
        elif axis == "y":
            v = np.column_stack([v[:, 2], v[:, 1], -v[:, 0]])
        else:
            raise ValueError(f"eixo '{axis}' inválido")
    return v


def rotate_90(mesh, axis, steps=1):
    """steps = múltiplos de +90° (CCW olhando do lado + do eixo)."""
    m = mesh.copy()
    m.vertices = _rotate_90_verts(np.asarray(m.vertices), axis, steps)
    return m


def rotate_free(mesh, rx, ry, rz):
    """Graus, ordem X→Y→Z. Para o gizmo / entrada numérica."""
    m = mesh.copy()
    for ang, ax in ((rx, [1, 0, 0]), (ry, [0, 1, 0]), (rz, [0, 0, 1])):
        if ang:
            m.apply_transform(
                trimesh.transformations.rotation_matrix(np.deg2rad(ang), ax)
            )
    return m
