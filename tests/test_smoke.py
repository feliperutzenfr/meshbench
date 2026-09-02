import meshbench


def test_versao():
    assert meshbench.__version__ == "0.1.1"


def test_dependencias_importam():
    import ezdxf  # noqa: F401
    import numpy  # noqa: F401
    import scipy  # noqa: F401
    import shapely  # noqa: F401
    import trimesh  # noqa: F401
