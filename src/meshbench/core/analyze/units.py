"""Detecção heurística de unidade. Só SUGERE — o usuário sempre confirma."""

import numpy as np

UNIT_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}


def guess_unit(mesh):
    """Sugere a unidade provável a partir da maior dimensão do bbox.

    Retorna (unidade | None, justificativa). None = ambíguo, perguntar ao usuário.
    """
    d = float(np.max(mesh.bounds[1] - mesh.bounds[0]))
    if d > 5000:
        return "mm", "suspeito: muito grande — confira se já não está em mm"
    if d >= 100:
        return "mm", "provável: faixa típica de componente de móvel em mm"
    if d >= 5:
        return None, "ambíguo: pode ser polegada ou cm — perguntar ao usuário"
    return "m", "provável: dimensão pequena demais para mm"


def human_dimensions(mesh):
    """Dimensões do bbox formatadas em mm, para o erro de escala saltar aos olhos."""
    d = mesh.bounds[1] - mesh.bounds[0]
    return f"{d[0]:.1f} × {d[1]:.1f} × {d[2]:.1f} mm"
