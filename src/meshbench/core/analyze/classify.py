"""Classificação heurística de peças (taxonomia da §6.1 do doc de arquitetura).

IMPORTANTE: isto só pré-preenche SUGESTÕES. O usuário decide o que cada peça é.
Formatos de malha não carregam nomes nem cores — a heurística não tem como saber.
"""

import numpy as np

# Abaixo disto não existe peça: é mais fino que uma folha de papel (0,1 mm).
# Limiar de realidade física, não ajustado a nenhum arquivo — acima dele a peça
# é fina mas plausível (chapa) e a heurística mantém, conforme "em dúvida, manter".
DEGENERATE_MIN_MM = 0.1

# classe sugerida -> operação sugerida (conservadora: em dúvida, manter)
SUGGESTED_OP = {
    "degenerate_shell": "remove",
    "weld_sphere": "remove",
    "profile": "reextrude",
    "wire_or_frame": "decimate",
    "hardware": "keep",
}


def classify(mesh):
    """Sugere uma classe pela forma do bbox e taxa de preenchimento.

    Regras (dims ordenadas ascendente, tudo em mm):
    - degenerate_shell: sem espessura (< 0,1mm) — retalho de superfície, não peça
    - weld_sphere: pequena (<15mm), ~cúbica, maciça (fill > 0.3)
    - profile: prismática — maior dimensão > 3x a segunda maior
    - wire_or_frame: quase nada do bbox preenchido (fill < 0.15)
    - hardware: o resto (peças pequenas maciças: buchas, clipes, tampas)
    """
    dims = np.sort(mesh.bounds[1] - mesh.bounds[0])
    # Antes de tudo: casca sem espessura. Precisa vir primeiro porque um retalho
    # plano e alongado passa no teste de "profile" e vai parar no reextrude, que
    # não tem seção nenhuma para extrudar. Não dá para usar `fill` aqui — casca
    # aberta não é estanque e mesh.volume devolve lixo (ordem de 1e11).
    if dims[0] < DEGENERATE_MIN_MM:
        return "degenerate_shell"
    bbox_vol = float(np.prod(np.maximum(dims, 1e-9)))
    fill = abs(float(mesh.volume)) / bbox_vol
    if dims[2] < 15 and dims[2] / max(dims[0], 1e-9) < 2 and fill > 0.3:
        return "weld_sphere"
    if dims[2] > 3 * dims[1]:
        return "profile"
    if fill < 0.15:
        return "wire_or_frame"
    return "hardware"
