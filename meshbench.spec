# -*- mode: python ; coding: utf-8 -*-
"""Spec do PyInstaller — empacota a MeshBench one-dir, sem console (--windowed).

Usa collect_all para o stack científico (que carrega dados/binários nativos e
submódulos por string, invisíveis à análise estática) e inclui o frontend
buildado (api/static) como data.
"""
from PyInstaller.utils.hooks import collect_all

datas = [("src/meshbench/api/static", "meshbench/api/static")]
binaries = []
hiddenimports = []

for pkg in [
    "trimesh",
    "shapely",
    "rtree",
    "scipy",
    "fast_simplification",
    "mapbox_earcut",
    "networkx",
    "ezdxf",
    "lxml",
    "uvicorn",
]:
    d, b, h = collect_all(pkg)
    datas += d
    binaries += b
    hiddenimports += h

# uvicorn resolve loop/protocolos por string em runtime
hiddenimports += [
    "uvicorn.logging",
    "uvicorn.loops.auto",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan.on",
]

a = Analysis(
    ["src/meshbench/desktop.py"],
    pathex=["src"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["tkinter.test"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="MeshBench",
    console=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    name="MeshBench",
)
