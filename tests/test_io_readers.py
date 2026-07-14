import ezdxf
import pytest

from meshbench.core.io.readers import read_dxf_3dface, read_mesh


def test_read_stl(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    m = read_mesh(p)
    assert len(m.faces) == 12
    assert len(m.vertices) == 8  # merge_vertices aplicado


def test_read_dxf_triangulo_e_quad(tmp_path):
    doc = ezdxf.new(dxfversion="AC1009")
    msp = doc.modelspace()
    # triângulo: 4º vértice repete o 3º
    msp.add_3dface([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 1, 0)])
    # quad: vira 2 triângulos
    msp.add_3dface([(5, 0, 0), (6, 0, 0), (6, 1, 0), (5, 1, 0)])
    p = tmp_path / "faces.dxf"
    doc.saveas(str(p))

    m = read_dxf_3dface(p)
    assert len(m.faces) == 3  # 1 do triângulo + 2 do quad
    assert len(m.vertices) == 7  # 3 + 4 após merge


def test_read_mesh_dispatch_dxf(tmp_path):
    doc = ezdxf.new(dxfversion="AC1009")
    doc.modelspace().add_3dface([(0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 1, 0)])
    p = tmp_path / "t.dxf"
    doc.saveas(str(p))
    assert len(read_mesh(p).faces) == 1


def test_formato_nao_suportado(tmp_path):
    p = tmp_path / "cena.wrl"
    p.write_text("#VRML V2.0 utf8")
    with pytest.raises(ValueError, match="não suportado"):
        read_mesh(p)
