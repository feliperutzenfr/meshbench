import numpy as np
import trimesh

from meshbench.core.analyze.components import (
    ComponentFamily,
    signature_of,
    split_components,
)


def test_signature_formato(box):
    sig = signature_of(box)
    assert sig == "f12:v8:b[10.0,20.0,30.0]"


def test_split_agrupa_identicos(box, small_sphere):
    b2 = box.copy()
    b2.apply_translation([100, 0, 0])
    s = small_sphere.copy()
    s.apply_translation([0, 100, 0])
    scene = trimesh.util.concatenate([box, b2, s])

    fams = split_components(scene)
    assert len(fams) == 2
    # ordem determinística: mais faces primeiro (esfera icosfera sub2 = 320 faces)
    assert fams[0].face_count > fams[1].face_count
    assert fams[0].id == "c0" and fams[1].id == "c1"
    caixa_fam = [f for f in fams if f.face_count == 12][0]
    assert caixa_fam.instances == 2


def test_familia_bbox_por_instancia(box):
    fams = split_components(box)
    assert fams[0].bbox == [[-5.0, -10.0, -15.0], [5.0, 10.0, 15.0]]


def test_split_solda_vertices_de_sopa_de_triangulos(box):
    # sopa não-soldada: 36 vértices duplicados, nenhum compartilhado entre faces
    soup = trimesh.Trimesh(
        vertices=box.triangles.reshape(-1, 3),
        faces=np.arange(36).reshape(-1, 3),
        process=False,
    )
    fams = split_components(soup)
    assert len(fams) == 1
    assert fams[0].instances == 1
