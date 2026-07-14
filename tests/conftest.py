import numpy as np
import pytest
import trimesh
from shapely.geometry import Point, Polygon


@pytest.fixture
def box():
    """Caixa maciça 10 x 20 x 30 mm."""
    return trimesh.creation.box(extents=[10.0, 20.0, 30.0])


@pytest.fixture
def small_sphere():
    """Esfera pequena (r=3mm) — proxy de ponto de solda."""
    return trimesh.creation.icosphere(subdivisions=2, radius=3.0)


@pytest.fixture
def c_channel():
    """Perfil C (canal aberto no topo), 20x10 de seção, parede 2, comprimento 100 em Z."""
    poly = Polygon(
        [(0, 0), (20, 0), (20, 10), (18, 10), (18, 2), (2, 2), (2, 10), (0, 10)]
    )
    return trimesh.creation.extrude_polygon(poly, 100.0)


@pytest.fixture
def wire_arc():
    """Arame curvo: círculo r=2 varrido num arco de 90° com raio 50 — proxy de haste."""
    t = np.linspace(0.0, np.pi / 2.0, 40)
    path = np.column_stack([50.0 * np.cos(t), 50.0 * np.sin(t), np.zeros_like(t)])
    circle = Point(0, 0).buffer(2.0, quad_segs=8)
    return trimesh.creation.sweep_polygon(circle, path)
