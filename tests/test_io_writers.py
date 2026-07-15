import numpy as np
import pytest
import trimesh

from meshbench.core.io.readers import read_dxf_3dface, read_mesh
from meshbench.core.io.writers import write_dxf_r12, write_meshes


def test_roundtrip_dxf(tmp_path, box):
    p = tmp_path / "caixa.dxf"
    write_dxf_r12([box], p)
    m = read_dxf_3dface(p)
    assert len(m.faces) == 12
    assert np.allclose(m.bounds, box.bounds)


def test_dxf_e_r12(tmp_path, box):
    p = tmp_path / "caixa.dxf"
    write_dxf_r12([box], p)
    import ezdxf

    doc = ezdxf.readfile(str(p))
    assert doc.dxfversion == "AC1009"


def test_write_meshes_stl(tmp_path, box):
    p = tmp_path / "caixa.stl"
    write_meshes([box], p, "stl")
    m = read_mesh(p)
    assert np.allclose(m.bounds, box.bounds)


def test_formato_invalido(tmp_path, box):
    with pytest.raises(ValueError, match="não suportado"):
        write_meshes([box], tmp_path / "x.step", "step")


def test_write_meshes_usa_fmt_nao_extensao_do_path(tmp_path, box):
    # nome de saída termina em .dxf mas o formato pedido é stl — o file_type
    # explícito garante que o conteúdo seja STL de verdade, não inferido do sufixo.
    p = tmp_path / "x.dxf"
    write_meshes([box], p, "stl")
    m = trimesh.load(str(p), file_type="stl", force="mesh")
    assert len(m.faces) == 12
