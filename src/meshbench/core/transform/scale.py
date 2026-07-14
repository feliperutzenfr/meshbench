"""Escala e conversão de unidades. SEMPRE a primeira transformação do pipeline:
os parâmetros das operações (bin_mm, tol…) são em mm absolutos."""

from meshbench.core.analyze.units import UNIT_MM


def scale_uniform(mesh, f):
    m = mesh.copy()
    m.apply_scale(f)
    return m


def scale_per_axis(mesh, sx, sy, sz):
    """⚠️ escala não-uniforme distorce raios de tubo/perfil — usar só para corrigir distorções."""
    m = mesh.copy()
    m.apply_scale([sx, sy, sz])
    return m


def fit_dimension(mesh, axis, target_mm):
    """Escala uniforme para que a dimensão `axis` fique exatamente target_mm."""
    i = "xyz".index(axis)
    cur = float(mesh.bounds[1][i] - mesh.bounds[0][i])
    if cur <= 0:
        raise ValueError(f"dimensão '{axis}' nula — não dá para ajustar")
    f = target_mm / cur
    return scale_uniform(mesh, f), f


def apply_scale(mesh, spec):
    """Aplica a escala descrita na receita. Retorna (malha, fator_resultante_xyz)."""
    mode = spec.get("mode", "unit_convert")
    if mode == "unit_convert":
        f = UNIT_MM[spec["from_unit"]] / UNIT_MM[spec.get("to_unit", "mm")]
        return scale_uniform(mesh, f), [f, f, f]
    if mode == "uniform":
        f = float(spec["value"])
        return scale_uniform(mesh, f), [f, f, f]
    if mode == "per_axis":
        sx, sy, sz = spec["per_axis"]
        return scale_per_axis(mesh, sx, sy, sz), [sx, sy, sz]
    if mode == "fit_dimension":
        m, f = fit_dimension(mesh, spec["fit"]["axis"], spec["fit"]["target_mm"])
        return m, [f, f, f]
    raise ValueError(f"modo de escala '{mode}' desconhecido")
