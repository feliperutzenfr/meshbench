"""Ancoragem da origem. SEMPRE a última etapa do pipeline: ancorar antes de
orientar joga a origem para o lugar errado (erro real da sessão anterior)."""

import numpy as np


def compute_anchor(bounds, anchor):
    """Ponto de âncora a partir de bounds (2x3).

    anchor: "bbox_min" | "center" | "corner_ABC" (A,B,C em {0,1}: 0=min, 1=max).
    Ex.: corner_000 == bbox_min; corner_111 = canto máximo.
    """
    mn, mx = np.asarray(bounds[0], float), np.asarray(bounds[1], float)
    if anchor == "bbox_min":
        return mn
    if anchor == "center":
        return (mn + mx) / 2.0
    if anchor.startswith("corner_"):
        bits = anchor.split("_", 1)[1]
        if len(bits) == 3 and set(bits) <= {"0", "1"}:
            return np.array(
                [mx[i] if b == "1" else mn[i] for i, b in enumerate(bits)]
            )
    raise ValueError(f"âncora '{anchor}' desconhecida")


def _bounds_of(meshes):
    pts = np.vstack([m.bounds for m in meshes])
    return np.array([pts.min(axis=0), pts.max(axis=0)])


def place_origin(
    groups,
    mode="common",
    anchor="bbox_min",
    snap_point=None,
    feature_bounds=None,
    offset=(0, 0, 0),
):
    """Translada os grupos para que a origem fique na âncora escolhida.

    - common: todos os grupos compartilham o mesmo referencial (mínimo global) —
      ao carregar os arquivos no alvo, eles caem encaixados sozinhos.
    - per_group: cada arquivo zera no seu próprio canto; o usuário posiciona no alvo.
    - snap_point: ponto explícito (clique no viewport) — precedência máxima.
    - feature_bounds: bounds de um componente de referência (âncora calculada nele).
    - offset: deslocamento adicional da origem em relação à âncora.
    """
    offset = np.asarray(offset, float)

    def shift(meshes, pt):
        out = []
        for m in meshes:
            c = m.copy()
            c.apply_translation(-np.asarray(pt, float))
            out.append(c)
        return out

    if snap_point is not None:
        pt = np.asarray(snap_point, float) + offset
        return {g: shift(ms, pt) for g, ms in groups.items()}
    if feature_bounds is not None:
        pt = compute_anchor(feature_bounds, anchor) + offset
        return {g: shift(ms, pt) for g, ms in groups.items()}
    if mode == "common":
        pt = compute_anchor(_bounds_of([m for ms in groups.values() for m in ms]), anchor) + offset
        return {g: shift(ms, pt) for g, ms in groups.items()}
    if mode == "per_group":
        return {
            g: shift(ms, compute_anchor(_bounds_of(ms), anchor) + offset)
            for g, ms in groups.items()
        }
    raise ValueError(f"modo de origem '{mode}' desconhecido")
