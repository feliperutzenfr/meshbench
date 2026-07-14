"""Operações simples: keep, remove, decimate (quádrica), hull.

⚠️ decimate NÃO serve para arame curvo (destrói as pontas — use tube).
⚠️ hull FECHA perfis abertos (o pipeline avisa quando detecta isso).
"""

from meshbench.core.ops.registry import register


def op_keep(mesh):
    """Passa direto, intacta."""
    return mesh.copy()


def op_remove(mesh):
    """Descarta: solda, peças internas invisíveis, ferragens que o alvo já tem."""
    return None


def op_decimate(mesh, face_count=None, percent=None):
    """Decimação quádrica. Alvo absoluto (face_count) ou % do original (percent)."""
    if face_count is None:
        face_count = max(4, int(len(mesh.faces) * (percent or 25.0) / 100.0))
    return mesh.simplify_quadric_decimation(face_count=int(face_count))


def op_hull(mesh):
    """Convex hull — só para ferragens pequenas MACIÇAS."""
    return mesh.convex_hull


register("keep", op_keep)
register("remove", op_remove)
register("decimate", op_decimate)
register("hull", op_hull)
