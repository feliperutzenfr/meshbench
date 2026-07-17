"""Operações simples: keep, remove, decimate (quádrica), hull.

⚠️ decimate NÃO serve para arame curvo (destrói as pontas — use tube).
⚠️ hull FECHA perfis abertos (o pipeline avisa quando detecta isso).
"""

import numpy as np
import trimesh

from meshbench.core.ops.registry import register


def op_keep(mesh):
    """Passa direto, intacta."""
    return mesh.copy()


def op_remove(mesh):
    """Descarta: solda, peças internas invisíveis, ferragens que o alvo já tem."""
    return None


def _decimate_squashed(mesh, face_count):
    """Resgate para malha alongada. O fast_simplification (algoritmo sp4cerat)
    veta qualquer colapso que crie triângulo com ângulo < ~2.6° (|cos| > 0.999);
    tesselação comprida (ex.: tubo exportado do CAD, com triângulos laterais de
    comprimento total) congela intacta — independe de escala, agg ou alvo.
    Comprimir o eixo longo antes de decimar deixa os triângulos bem formados no
    espaço onde os colapsos são avaliados; a escada de fatores cobre tesselação
    radial fina, que pede squash além da isotropia do bbox."""
    ext = mesh.extents
    if float(np.max(ext)) <= 0:
        return None
    axis = int(np.argmax(ext))
    base = max(float(np.min(ext)), 1e-12) / float(np.max(ext))
    for strength in (1.0, 0.25, 0.0625):
        squash = np.ones(3)
        squash[axis] = base * strength
        squashed = trimesh.Trimesh(mesh.vertices * squash, mesh.faces, process=False)
        out = squashed.simplify_quadric_decimation(face_count=face_count)
        if len(out.faces) < len(mesh.faces):
            return trimesh.Trimesh(out.vertices / squash, out.faces)
    return None


def op_decimate(mesh, face_count=None, percent=None):
    """Decimação quádrica. Alvo absoluto (face_count) ou % do original (percent)."""
    if face_count is None:
        pct = 25.0 if percent is None else percent
        face_count = len(mesh.faces) * pct / 100.0
    face_count = max(4, int(face_count))
    if face_count >= len(mesh.faces):
        # fast_simplification levanta ValueError com alvo >= contagem atual
        return mesh.copy()
    out = mesh.simplify_quadric_decimation(face_count=face_count)
    if len(out.faces) >= len(mesh.faces):
        rescued = _decimate_squashed(mesh, face_count)
        if rescued is not None:
            out = rescued
    return out


def op_hull(mesh):
    """Convex hull — só para ferragens pequenas MACIÇAS."""
    return mesh.convex_hull


register("keep", op_keep)
register("remove", op_remove)
register("decimate", op_decimate)
register("hull", op_hull)
