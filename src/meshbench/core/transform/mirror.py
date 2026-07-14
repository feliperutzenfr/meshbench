"""Espelho por eixo, com correção automática de winding."""


def mirror(mesh, axis):
    """Espelha no eixo dado. invert() corrige o winding — senão renderiza pelo avesso."""
    m = mesh.copy()
    s = [1, 1, 1]
    s["xyz".index(axis)] = -1
    m.apply_scale(s)
    return m
