"""Split em componentes conectados e agrupamento de peças idênticas por assinatura."""

from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import trimesh


def signature_of(mesh):
    """Assinatura geométrica estável — usada para reidentificar peças após re-export.

    Arredonda o bbox a 1 casa decimal para tolerar ruído de tesselação.
    """
    d = np.round(mesh.bounds[1] - mesh.bounds[0], 1)
    return f"f{len(mesh.faces)}:v{len(mesh.vertices)}:b[{d[0]},{d[1]},{d[2]}]"


@dataclass
class ComponentFamily:
    """Uma família de peças idênticas (ex.: 64 esferas de solda iguais)."""

    id: str
    signature: str
    meshes: list

    @property
    def instances(self):
        return len(self.meshes)

    @property
    def face_count(self):
        return len(self.meshes[0].faces)

    @property
    def bbox(self):
        return [list(map(float, b)) for b in self.meshes[0].bounds]


def split_components(mesh):
    """Separa a malha em componentes conectados e agrupa os idênticos.

    Retorna famílias em ordem determinística (faces desc, assinatura asc),
    com ids c0, c1, …
    """
    mesh = mesh.copy()
    mesh.merge_vertices()
    groups = defaultdict(list)
    for c in mesh.split(only_watertight=False):
        groups[signature_of(c)].append(c)
    ordered = sorted(groups.items(), key=lambda kv: (-len(kv[1][0].faces), kv[0]))
    return [
        ComponentFamily(id=f"c{i}", signature=sig, meshes=ms)
        for i, (sig, ms) in enumerate(ordered)
    ]
