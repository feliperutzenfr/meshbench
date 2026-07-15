import trimesh

from meshbench.core.pipeline import ProcessedComponent
from meshbench.api.geometry import DISPLAY_BUDGET, build_scene_glb, display_records


def _record(mesh, cid="c0", group="saida"):
    return ProcessedComponent(component_id=cid, label="peça", group=group, mesh=mesh)


def test_display_abaixo_do_orcamento_nao_mexe(box):
    records = [_record(box)]
    out = display_records(records)
    assert out[0].mesh is box  # sem cópia desnecessária


def test_display_decima_quando_estoura(small_sphere):
    dense = small_sphere.subdivide().subdivide()  # 320*16 = 5120 faces
    records = [_record(dense)]
    out = display_records(records, budget=1000)
    assert len(out[0].mesh.faces) <= 1200
    assert len(dense.faces) == 5120  # original intacto


def test_glb_magic_e_nos(box, small_sphere):
    records = [_record(box, "c0"), _record(small_sphere, "c1")]
    glb = build_scene_glb(records)
    assert glb[:4] == b"glTF"
    # roundtrip: os nós preservam os nomes componente.instancia
    scene = trimesh.load(trimesh.util.wrap_as_stream(glb), file_type="glb")
    names = set(scene.geometry.keys())
    assert names == {"c0.0", "c1.1"}
