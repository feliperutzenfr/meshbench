"""Classificação heurística de peças (taxonomia da §6.1 do doc de arquitetura).

IMPORTANTE: isto só pré-preenche SUGESTÕES. O usuário decide o que cada peça é.
Formatos de malha não carregam nomes nem cores — a heurística não tem como saber.
"""

import numpy as np

# classe sugerida -> operação sugerida (conservadora: em dúvida, manter)
SUGGESTED_OP = {
    "weld_sphere": "remove",
    "profile": "reextrude",
    "wire_or_frame": "decimate",
    "hardware": "keep",
}


def classify(mesh):
    """Sugere uma classe pela forma do bbox e taxa de preenchimento.

    Regras (dims ordenadas ascendente, tudo em mm):
    - weld_sphere: pequena (<15mm), ~cúbica, maciça (fill > 0.3)
    - profile: prismática — maior dimensão > 3x a segunda maior
    - wire_or_frame: quase nada do bbox preenchido (fill < 0.15)
    - hardware: o resto (peças pequenas maciças: buchas, clipes, tampas)
    """
    dims = np.sort(mesh.bounds[1] - mesh.bounds[0])
    bbox_vol = float(np.prod(np.maximum(dims, 1e-9)))
    fill = abs(float(mesh.volume)) / bbox_vol
    if dims[2] < 15 and dims[2] / max(dims[0], 1e-9) < 2 and fill > 0.3:
        return "weld_sphere"
    if dims[2] > 3 * dims[1]:
        return "profile"
    if fill < 0.15:
        return "wire_or_frame"
    return "hardware"
