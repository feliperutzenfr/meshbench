"""Reconstrução de arame como tubo low-poly.

Por que existe: a decimação quádrica destrói as pontas curvas do arame.
Linha de centro por distância geodésica (Dijkstra) — robusto até em U de 180°,
onde fatiar por plano cortaria as duas pernas e o centroide sairia no vazio.
Perfil varrido com parallel transport frames (evita torção ao longo da curva).
"""

import numpy as np
import trimesh
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from meshbench.core.ops.registry import register


def extract_centerline(mesh, bin_mm=3.0):
    v = mesh.vertices
    e = mesh.edges_unique
    el = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
    n = len(v)
    W = csr_matrix(
        (
            np.concatenate([el, el]),
            (
                np.concatenate([e[:, 0], e[:, 1]]),
                np.concatenate([e[:, 1], e[:, 0]]),
            ),
        ),
        shape=(n, n),
    )
    c0 = v - v.mean(0)
    _, vec = np.linalg.eigh(np.cov(c0.T))
    t = c0 @ vec[:, -1]
    g = dijkstra(W, indices=int(np.argmax(t)), directed=False)
    g[~np.isfinite(g)] = g[np.isfinite(g)].max()
    nb = max(4, int(g.max() / bin_mm))
    bins = np.linspace(0, g.max(), nb + 1)
    idx = np.digitize(g, bins) - 1
    cl, rad = [], []
    for b in range(nb):
        m = idx == b
        if m.sum() < 3:
            continue
        cen = v[m].mean(0)
        cl.append(cen)
        rad.append(np.linalg.norm(v[m] - cen, axis=1).mean())
    return np.array(cl), float(np.median(rad))


def tube_from_centerline(cl, radius, sides=8):
    P = np.asarray(cl)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    ref = np.array([0, 0, 1.0]) if abs(T[0, 2]) < 0.9 else np.array([0, 1.0, 0])
    n0 = np.cross(T[0], ref)
    n0 /= np.linalg.norm(n0) + 1e-9
    normals = [n0]
    for i in range(1, len(P)):  # parallel transport (Rodrigues)
        pn = normals[-1]
        vx = np.cross(T[i - 1], T[i])
        cs = np.dot(T[i - 1], T[i])
        if np.linalg.norm(vx) < 1e-6:
            nn = pn
        else:
            vx /= np.linalg.norm(vx)
            a = np.arccos(np.clip(cs, -1, 1))
            nn = (
                pn * np.cos(a)
                + np.cross(vx, pn) * np.sin(a)
                + vx * np.dot(vx, pn) * (1 - np.cos(a))
            )
        nn = nn - np.dot(nn, T[i]) * T[i]
        nn /= np.linalg.norm(nn) + 1e-9
        normals.append(nn)
    normals = np.array(normals)
    B = np.cross(T, normals)
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    rings = np.array(
        [
            P[i]
            + radius
            * (np.cos(ang)[:, None] * normals[i] + np.sin(ang)[:, None] * B[i])
            for i in range(len(P))
        ]
    )
    ns = len(P)
    V = rings.reshape(-1, 3)
    F = []
    for i in range(ns - 1):
        for j in range(sides):
            a = i * sides + j
            b = i * sides + (j + 1) % sides
            c = (i + 1) * sides + j
            d = (i + 1) * sides + (j + 1) % sides
            F += [[a, b, d], [a, d, c]]
    for ci, flip in [(0, False), (ns - 1, True)]:  # tampas
        idx = len(V)
        V = np.vstack([V, P[ci]])
        for j in range(sides):
            a = ci * sides + j
            b = ci * sides + (j + 1) % sides
            F.append([idx, b, a] if flip else [idx, a, b])
    return trimesh.Trimesh(vertices=V, faces=np.array(F), process=False)


def op_tube(mesh, sides=8, bin_mm=3.0, radius=None):
    """Reconstrói um arame/haste como tubo de N lados. radius=None → auto-detectado."""
    cl, detected = extract_centerline(mesh, bin_mm=bin_mm)
    return tube_from_centerline(cl, radius if radius is not None else detected, sides=sides)


register("tube", op_tube)
