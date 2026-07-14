"""Remap de eixos por presets. NUNCA hardcodar: o preset é selecionável e o
usuário confirma olhando o preview (§3.2 do doc de arquitetura)."""

import numpy as np

REMAPS = {
    "identidade": ("x", "y", "z"),
    # CAD comum: Y=altura, Z=profundidade → Promob: Z=altura, Y=profundidade
    "cad_to_promob": ("x", "z", "y"),
    "z_up_to_y_up": ("x", "z", "-y"),
    "y_up_to_z_up": ("x", "-z", "y"),
}


def remap_axes(mesh, spec):
    """Aplica um remap de eixos. `spec` = nome de preset ou lista custom ["x","-z","y"].

    Se a permutação inverte a orientação (determinante negativo), corrige o
    winding com mesh.invert() — senão a peça renderiza pelo avesso.
    """
    axes = REMAPS[spec] if isinstance(spec, str) else tuple(spec)
    M = np.zeros((3, 3))
    for i, a in enumerate(axes):
        sign = -1.0 if a.startswith("-") else 1.0
        M[i, "xyz".index(a.lstrip("+-"))] = sign
    m = mesh.copy()
    m.vertices = mesh.vertices @ M.T
    if np.linalg.det(M) < 0:
        m.invert()
    return m
