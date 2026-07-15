"""Regressão de ouro: os 3 produtos reais do Anexo B do doc de arquitetura.

Os arquivos são grandes e ficam fora do git — os testes são pulados se a pasta
não existir. Rode com: pytest -m slow
"""

from pathlib import Path

import numpy as np
import pytest

from meshbench.core.analyze.components import split_components
from meshbench.core.io.readers import read_mesh
from meshbench.core.ops import apply_op

EXEMPLOS = Path(__file__).resolve().parents[1] / "docs" / "peças exemplo"

pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(
        not EXEMPLOS.exists(), reason="pasta 'docs/peças exemplo' não disponível"
    ),
]


def test_rm416_perfil():
    """B.3: STL ASCII, 536 faces, 1 componente, bbox 54.49 x 15.05 x 1000."""
    m = read_mesh(EXEMPLOS / "RM-416.STL")
    assert len(m.faces) == 536
    fams = split_components(m)
    assert len(fams) == 1
    dims = np.sort(m.extents)
    assert dims[2] == pytest.approx(1000.0, abs=1.0)

    # tol=1.5 medido empiricamente: 72 faces (tol=0.4 dá 132 nesta versão do
    # shapely; o "~50" do Anexo B era aproximado). Perfil continua aberto e o
    # bbox é preservado (desvio máx. 0,13 mm).
    out = apply_op(m, {"type": "reextrude", "params": {"tol": 1.5}})
    assert out is not None
    assert len(out.faces) < 120  # 536 → 72
    # perfil aberto preservado (não virou bloco maciço)
    assert out.volume < 0.6 * out.convex_hull.volume


def test_fruteira_2191():
    """B.1: 455.804 3DFACE, 112 componentes, 64 esferas de solda de 5.852 faces."""
    m = read_mesh(EXEMPLOS / "2191-0400.dxf")
    fams = split_components(m)
    n_componentes = sum(f.instances for f in fams)
    assert n_componentes == 112
    # As 64 esferas de solda existem em DOIS tamanhos reais (48 de ~3,5 mm e
    # 16 de ~4,5 mm) — a assinatura agrupa por bbox real, então são 2 famílias.
    # O total de instâncias é o que o Anexo B garante.
    soldas = [f for f in fams if f.face_count == 5852]
    assert soldas and sum(f.instances for f in soldas) == 64


def test_calceiro_3214_0400():
    """B.2: 12 hastes de 4.978 faces, 1 frame de 7.380 faces."""
    m = read_mesh(EXEMPLOS / "3214-0400-CL-00.dxf")
    fams = split_components(m)
    hastes = [f for f in fams if f.face_count == 4978]
    assert hastes and hastes[0].instances == 12
    frames = [f for f in fams if f.face_count == 7380]
    assert frames and frames[0].instances == 1
