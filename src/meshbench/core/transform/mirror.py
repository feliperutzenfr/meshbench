"""Espelho por eixo. O winding das faces é corrigido pelo próprio trimesh:
apply_scale/apply_transform (>=4.x) detecta transformações que invertem a
orientação (determinante negativo) e ajusta o winding automaticamente.
NÃO reintroduzir invert() depois do apply_scale — faria o flip duplo e o
volume sairia negativo (o teste test_mirror_corrige_winding guarda isso)."""


def mirror(mesh, axis):
    """Espelha no eixo dado ("x", "y" ou "z").

    O apply_scale com fator negativo já corrige o winding das faces
    (comportamento do trimesh >=4.x); nenhum invert() é necessário.
    """
    m = mesh.copy()
    s = [1, 1, 1]
    s["xyz".index(axis)] = -1
    # trimesh >=4.x corrige o winding sozinho em transformações de
    # determinante negativo — comportamento dependente da versão.
    m.apply_scale(s)
    return m
