"""Re-extrusão de perfil prismático.

Por que existe: convex_hull FECHA o perfil C aberto (rejeitado pelo usuário).
Isto tira os furos e achata as faces MANTENDO o perfil aberto:
fatia perpendicular ao eixo em N posições e escolhe a fatia de MAIOR ÁREA
(a seção limpa, sem furo/rasgo passando).
"""

import numpy as np
import trimesh
from shapely.ops import unary_union
from trimesh.creation import triangulate_polygon

from meshbench.core.ops.registry import register


def _section_2d(mesh, origin, normal):
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    if sec is None:
        return None
    if hasattr(sec, "to_2D"):
        return sec.to_2D()
    return sec.to_planar()


def op_reextrude(mesh, axis=None, n_probe=25, tol=0.4):
    """Re-extruda o perfil prismático da peça. axis=None → maior dimensão do bbox."""
    dims = mesh.bounds[1] - mesh.bounds[0]
    if axis is None:
        axis = int(np.argmax(dims))
    normal = [0, 0, 0]
    normal[axis] = 1
    amin, amax = mesh.bounds[0, axis], mesh.bounds[1, axis]

    best, best_area = None, -1
    for ap in np.linspace(
        amin + (amax - amin) * 0.1, amax - (amax - amin) * 0.1, n_probe
    ):
        o = [0, 0, 0]
        o[axis] = ap
        try:
            planar = _section_2d(mesh, o, normal)
            if planar is None:
                continue
            p2d, to3d = planar
            area = sum(pp.area for pp in p2d.polygons_full)
        except Exception:
            continue
        if area > best_area:  # a fatia de MAIOR área = seção sem furo
            best_area, best = area, (p2d, to3d)
    if best is None:
        return None

    p2d, to3d = best
    geom = unary_union(list(p2d.polygons_full)).simplify(tol)
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area)
    v2d, fcap = triangulate_polygon(geom, engine="earcut")

    def to_world(p2):
        h = np.column_stack([p2, np.zeros(len(p2)), np.ones(len(p2))])
        return (to3d @ h.T).T[:, :3]

    other = [i for i in range(3) if i != axis]
    V, F = [], []

    def ring(aval, pts):
        base = len(V)
        for p in pts:
            xyz = [0.0, 0.0, 0.0]
            xyz[axis] = aval
            xyz[other[0]] = p[0]
            xyz[other[1]] = p[1]
            V.append(xyz)
        return base

    prof = to_world(v2d)[:, other]
    b0 = ring(amin, prof)
    for f in fcap:
        F.append([b0 + f[0], b0 + f[2], b0 + f[1]])  # tampa (winding invertido)
    b1 = ring(amax, prof)
    for f in fcap:
        F.append([b1 + f[0], b1 + f[1], b1 + f[2]])  # tampa
    ext = np.array(geom.exterior.coords)[:-1]
    extw = to_world(ext)[:, other]
    ne = len(ext)
    r0 = ring(amin, extw)
    r1 = ring(amax, extw)
    for i in range(ne):  # parede lateral
        a = r0 + i
        b = r0 + (i + 1) % ne
        c = r1 + i
        d = r1 + (i + 1) % ne
        F += [[a, b, d], [a, d, c]]
    return trimesh.Trimesh(
        vertices=np.array(V, float), faces=np.array(F), process=False
    )


register("reextrude", op_reextrude)
