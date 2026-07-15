# MeshBench Fase 1 — Motor (core) + CLI — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir o motor de processamento de malhas do MeshBench (`core/`) e uma CLI (`inspect` / `init` / `apply`), capaz de reproduzir as 3 conversões reais do Anexo B de `docs/ARQUITETURA-MESHPREP.md`.

**Architecture:** Pacote Python `meshbench` com layout `src/`, núcleo puro (sem UI) dividido em `io/`, `analyze/`, `ops/`, `transform/`, mais `pipeline.py` (orquestra a ordem fixa IMPORT→SCALE→SPLIT→OPS→GROUP→ORIENT→ORIGIN→EXPORT) e `project.py` (receita JSON reprodutível). A CLI gera receitas com sugestões e as aplica. Os algoritmos do Anexo A do documento de arquitetura são **portados como estão** — foram validados visualmente; não reescrever a lógica.

**Tech Stack:** Python ≥3.11 (dev local: 3.14) · trimesh · numpy · scipy · shapely · mapbox-earcut · rtree · ezdxf · fast-simplification · pytest

## Global Constraints

- Nome do pacote: `meshbench` (o doc de arquitetura usa "meshprep" como nome de trabalho — **substituir por meshbench em tudo**). Extensão de receita: `.meshbench.json`.
- Unidade canônica interna: **milímetros**. A escala é SEMPRE a primeira transformação; a origem é SEMPRE a última (§4 do doc — ordem não negociável).
- Heurísticas (classificação, unidade) **só sugerem** — nunca decidem. Campos `auto_class` vs `user_label` são separados no JSON.
- Orçamento de faces: cada arquivo de saída deve ficar **< 15.000 faces** — validador emite aviso, não bloqueia.
- Sempre `mesh.merge_vertices()` após ler qualquer arquivo (sem isso `split()` não acha componentes).
- Espelho e remaps com determinante negativo exigem `mesh.invert()` (correção de winding).
- Identificadores de código em inglês; docstrings, mensagens de CLI e avisos em **português brasileiro**.
- Caminhos relativos dentro de uma receita são relativos **à pasta do arquivo da receita**.
- Os arquivos reais de `docs/peças exemplo/` NÃO entram no git (estão no `.gitignore`); testes de regressão que os usam levam `@pytest.mark.slow` e são pulados se os arquivos não existirem. `pytest` padrão roda com `-m "not slow"`.
- Commits: Conventional Commits (`feat:`, `test:`, `chore:`…).
- Comandos nos passos usam o Python do venv: `.venv/Scripts/python` (Windows).
- Formatos de import da Fase 1: STL, OBJ, PLY, 3MF, DXF(3DFACE). VRML (.wrl) fica para fase futura — o leitor deve dar erro amigável.

---

### Task 1: Scaffold do projeto

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `src/meshbench/__init__.py`
- Create: `src/meshbench/core/__init__.py`
- Create: `src/meshbench/core/io/__init__.py`
- Create: `src/meshbench/core/analyze/__init__.py`
- Create: `src/meshbench/core/ops/__init__.py`
- Create: `src/meshbench/core/transform/__init__.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Produces: pacote importável `meshbench` com `__version__ = "0.1.0"`; venv em `.venv/`; pytest configurado com marker `slow` excluído por padrão.

- [ ] **Step 1: Inicializar git e criar .gitignore**

```bash
git init -b main
```

`.gitignore`:
```gitignore
.venv/
__pycache__/
*.pyc
*.egg-info/
dist/
build/
out/
docs/peças exemplo/
.pytest_cache/
```

- [ ] **Step 2: Criar pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "meshbench"
version = "0.1.0"
description = "Editor e conversor de malha 3D para software de projeto de móveis (Promob e outros)"
requires-python = ">=3.11"
dependencies = [
    "trimesh>=4.0",
    "numpy>=1.26",
    "scipy>=1.11",
    "shapely>=2.0",
    "mapbox-earcut>=1.0",
    "rtree>=1.1",
    "ezdxf>=1.1",
    "fast-simplification>=0.1.7",
    "lxml>=5.0",
]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[project.scripts]
meshbench = "meshbench.cli:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-m 'not slow'"
markers = [
    "slow: testes de regressão com os arquivos reais (rode com: pytest -m slow)",
]
```

- [ ] **Step 3: Criar o esqueleto do pacote**

`src/meshbench/__init__.py`:
```python
"""MeshBench — prepara malhas 3D exportadas de CAD para software de projeto de móveis."""

__version__ = "0.1.0"
```

Os demais `__init__.py` (`core/`, `core/io/`, `core/analyze/`, `core/ops/`, `core/transform/`) começam vazios.

- [ ] **Step 4: Criar venv e instalar**

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

Esperado: instalação sem erro. **Contingência:** se `fast-simplification`, `rtree` ou `mapbox-earcut` não tiverem wheel para o Python local (3.14), reportar ao usuário antes de prosseguir — a alternativa é criar o venv com um Python mais antigo (`py -3.12 -m venv .venv`) se disponível.

- [ ] **Step 5: Escrever o teste de fumaça**

`tests/test_smoke.py`:
```python
import meshbench


def test_versao():
    assert meshbench.__version__ == "0.1.0"


def test_dependencias_importam():
    import ezdxf  # noqa: F401
    import numpy  # noqa: F401
    import scipy  # noqa: F401
    import shapely  # noqa: F401
    import trimesh  # noqa: F401
```

- [ ] **Step 6: Rodar os testes**

Run: `.venv/Scripts/python -m pytest -v`
Expected: 2 passed

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml .gitignore src tests
git commit -m "chore: scaffold do pacote meshbench com layout src e pytest"
```

---

### Task 2: Leitores de malha (`io/readers.py`) + fixtures compartilhadas

**Files:**
- Create: `src/meshbench/core/io/readers.py`
- Create: `tests/conftest.py`
- Test: `tests/test_io_readers.py`

**Interfaces:**
- Produces: `read_mesh(path) -> trimesh.Trimesh` (dispatch por extensão, sempre com `merge_vertices()` aplicado); `read_dxf_3dface(path) -> trimesh.Trimesh`.
- Produces (conftest): fixtures pytest `box` (caixa 10×20×30), `small_sphere` (icosfera r=3mm), `c_channel` (perfil C extrudado 100mm, aberto no topo), `wire_arc` (tubo varrido num arco de 90°, raio do arco 50, raio do tubo 2).

- [ ] **Step 1: Escrever fixtures compartilhadas**

`tests/conftest.py`:
```python
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
```

- [ ] **Step 2: Escrever os testes que falham**

`tests/test_io_readers.py`:
```python
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
```

- [ ] **Step 3: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_io_readers.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'meshbench.core.io.readers'`

- [ ] **Step 4: Implementar**

`src/meshbench/core/io/readers.py` (o leitor DXF é o Anexo A.1 do doc de arquitetura — portar como está):
```python
"""Leitura de malhas. STL/OBJ/PLY/3MF via trimesh; DXF (3DFACE) via ezdxf."""

from pathlib import Path

import ezdxf
import numpy as np
import trimesh

TRIMESH_EXTS = {".stl", ".obj", ".ply", ".3mf"}


def read_mesh(path):
    """Lê um arquivo de malha e retorna um trimesh.Trimesh com vértices já mesclados."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".dxf":
        return read_dxf_3dface(path)
    if ext in TRIMESH_EXTS:
        m = trimesh.load(str(path), force="mesh")
        m.merge_vertices()
        return m
    raise ValueError(
        f"formato '{ext}' não suportado (aceitos: STL, OBJ, PLY, 3MF, DXF com 3DFACE)"
    )


def read_dxf_3dface(path):
    """Lê entidades 3DFACE de um DXF e monta uma malha triangular."""
    doc = ezdxf.readfile(str(path))
    verts, tris = [], []
    for f in doc.modelspace().query("3DFACE"):
        p = [f.dxf.vtx0, f.dxf.vtx1, f.dxf.vtx2, f.dxf.vtx3]
        base = len(verts)
        is_quad = p[2] != p[3]
        for pp in p[:4] if is_quad else p[:3]:
            verts.append((pp[0], pp[1], pp[2]))
        if is_quad:
            tris += [(base, base + 1, base + 2), (base, base + 2, base + 3)]
        else:
            tris.append((base, base + 1, base + 2))
    m = trimesh.Trimesh(vertices=np.array(verts), faces=np.array(tris), process=False)
    m.merge_vertices()  # ESSENCIAL — sem isso o split() não acha componentes
    return m
```

- [ ] **Step 5: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_io_readers.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/core/io/readers.py tests/conftest.py tests/test_io_readers.py
git commit -m "feat: leitores de malha (STL/OBJ/PLY/3MF via trimesh, DXF 3DFACE via ezdxf)"
```

---

### Task 3: Escritores (`io/writers.py`) com roundtrip DXF

**Files:**
- Create: `src/meshbench/core/io/writers.py`
- Test: `tests/test_io_writers.py`

**Interfaces:**
- Consumes: `read_dxf_3dface` (Task 2).
- Produces: `write_dxf_r12(meshes: list[trimesh.Trimesh], path) -> None`; `write_meshes(meshes, path, fmt) -> None` com `fmt` em `{"dxf_r12", "stl", "obj"}`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_io_writers.py`:
```python
import numpy as np
import pytest

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
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_io_writers.py -v`
Expected: FAIL — módulo `writers` não existe

- [ ] **Step 3: Implementar**

`src/meshbench/core/io/writers.py` (o escritor DXF é o Anexo A.2 — portar como está):
```python
"""Escrita de malhas. DXF R12 (3DFACE) é o alvo principal — validado no Promob."""

from pathlib import Path

import ezdxf
import trimesh


def write_dxf_r12(meshes, path):
    """Escreve malhas como entidades 3DFACE num DXF R12 (AC1009)."""
    doc = ezdxf.new(dxfversion="AC1009")
    msp = doc.modelspace()
    for m in meshes:
        v = m.vertices
        for tri in m.faces:
            a, b, c = v[tri[0]], v[tri[1]], v[tri[2]]
            msp.add_3dface([tuple(a), tuple(b), tuple(c), tuple(c)])
    doc.saveas(str(path))


def write_meshes(meshes, path, fmt):
    """Escreve uma lista de malhas num único arquivo, no formato pedido."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fmt == "dxf_r12":
        write_dxf_r12(meshes, path)
    elif fmt in ("stl", "obj"):
        combined = trimesh.util.concatenate(meshes) if len(meshes) > 1 else meshes[0]
        combined.export(str(path))
    else:
        raise ValueError(f"formato de exportação '{fmt}' não suportado")
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_io_writers.py -v`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/core/io/writers.py tests/test_io_writers.py
git commit -m "feat: escritores DXF R12 3DFACE, STL e OBJ com roundtrip testado"
```

---

### Task 4: Split e agrupamento de idênticos (`analyze/components.py`)

**Files:**
- Create: `src/meshbench/core/analyze/components.py`
- Test: `tests/test_analyze_components.py`

**Interfaces:**
- Produces: `signature_of(mesh) -> str` (formato `"f{faces}:v{verts}:b[{dx},{dy},{dz}]"`, dims arredondadas a 1 casa); `ComponentFamily` (dataclass: `id: str`, `signature: str`, `meshes: list[trimesh.Trimesh]`; propriedades `instances`, `face_count`, `bbox`); `split_components(mesh) -> list[ComponentFamily]` (ordem determinística: faces desc, depois assinatura; ids `c0, c1, …`).

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_analyze_components.py`:
```python
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
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_analyze_components.py -v`
Expected: FAIL — módulo `components` não existe

- [ ] **Step 3: Implementar**

`src/meshbench/core/analyze/components.py` (lógica do Anexo A.3, com assinatura em string para o JSON do projeto):
```python
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
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_analyze_components.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/core/analyze/components.py tests/test_analyze_components.py
git commit -m "feat: split em componentes e agrupamento de idênticos por assinatura"
```

---

### Task 5: Heurística de unidades (`analyze/units.py`)

**Files:**
- Create: `src/meshbench/core/analyze/units.py`
- Test: `tests/test_analyze_units.py`

**Interfaces:**
- Produces: `UNIT_MM: dict[str, float]` (mm/cm/m/in/ft); `guess_unit(mesh) -> tuple[str | None, str]` (unidade sugerida ou None se ambíguo, + justificativa); `human_dimensions(mesh) -> str` (dimensões formatadas em mm para exibição).

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_analyze_units.py`:
```python
from meshbench.core.analyze.units import UNIT_MM, guess_unit, human_dimensions


def _scaled(box, factor):
    m = box.copy()
    m.apply_scale(factor)
    return m


def test_tabela_unidades():
    assert UNIT_MM["in"] == 25.4
    assert UNIT_MM["m"] == 1000.0


def test_mm_provavel(box):
    m = _scaled(box, 10)  # maior dim = 300
    unit, motivo = guess_unit(m)
    assert unit == "mm"
    assert "provável" in motivo


def test_ambiguo(box):
    unit, motivo = guess_unit(box)  # maior dim = 30 → 30mm ou 30"?
    assert unit is None
    assert "ambíguo" in motivo


def test_metros_provavel(box):
    m = _scaled(box, 0.01)  # maior dim = 0.3
    unit, _ = guess_unit(m)
    assert unit == "m"


def test_suspeito_grande(box):
    m = _scaled(box, 1000)  # maior dim = 30000
    unit, motivo = guess_unit(m)
    assert unit == "mm"
    assert "suspeito" in motivo


def test_human_dimensions(box):
    assert human_dimensions(box) == "10.0 × 20.0 × 30.0 mm"
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_analyze_units.py -v`
Expected: FAIL — módulo `units` não existe

- [ ] **Step 3: Implementar**

`src/meshbench/core/analyze/units.py` (limiares do §5.2 / Anexo A.4 — sugestão, nunca imposição):
```python
"""Detecção heurística de unidade. Só SUGERE — o usuário sempre confirma."""

import numpy as np

UNIT_MM = {"mm": 1.0, "cm": 10.0, "m": 1000.0, "in": 25.4, "ft": 304.8}


def guess_unit(mesh):
    """Sugere a unidade provável a partir da maior dimensão do bbox.

    Retorna (unidade | None, justificativa). None = ambíguo, perguntar ao usuário.
    """
    d = float(np.max(mesh.bounds[1] - mesh.bounds[0]))
    if d > 5000:
        return "mm", "suspeito: muito grande — confira se já não está em mm"
    if d >= 100:
        return "mm", "provável: faixa típica de componente de móvel em mm"
    if d >= 5:
        return None, "ambíguo: pode ser polegada ou cm — perguntar ao usuário"
    return "m", "provável: dimensão pequena demais para mm"


def human_dimensions(mesh):
    """Dimensões do bbox formatadas em mm, para o erro de escala saltar aos olhos."""
    d = mesh.bounds[1] - mesh.bounds[0]
    return f"{d[0]:.1f} × {d[1]:.1f} × {d[2]:.1f} mm"
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_analyze_units.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/core/analyze/units.py tests/test_analyze_units.py
git commit -m "feat: heurística de detecção de unidade (sugestão com justificativa)"
```

---

### Task 6: Classificação sugestiva (`analyze/classify.py`)

**Files:**
- Create: `src/meshbench/core/analyze/classify.py`
- Test: `tests/test_analyze_classify.py`

**Interfaces:**
- Produces: `classify(mesh) -> str` retornando uma de `{"weld_sphere", "profile", "wire_or_frame", "hardware"}`; `SUGGESTED_OP: dict[str, str]` mapeando classe → operação sugerida (`weld_sphere→remove`, `profile→reextrude`, `wire_or_frame→decimate`, `hardware→keep`).

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_analyze_classify.py`:
```python
from meshbench.core.analyze.classify import SUGGESTED_OP, classify


def test_esfera_pequena_e_solda(small_sphere):
    assert classify(small_sphere) == "weld_sphere"


def test_canal_longo_e_perfil(c_channel):
    assert classify(c_channel) == "profile"


def test_arame_curvo(wire_arc):
    assert classify(wire_arc) == "wire_or_frame"


def test_caixa_macica_e_ferragem(box):
    assert classify(box) == "hardware"


def test_operacoes_sugeridas_sao_conservadoras():
    assert SUGGESTED_OP["weld_sphere"] == "remove"
    assert SUGGESTED_OP["profile"] == "reextrude"
    assert SUGGESTED_OP["wire_or_frame"] == "decimate"
    assert SUGGESTED_OP["hardware"] == "keep"
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_analyze_classify.py -v`
Expected: FAIL — módulo `classify` não existe

- [ ] **Step 3: Implementar**

`src/meshbench/core/analyze/classify.py`:
```python
"""Classificação heurística de peças (taxonomia da §6.1 do doc de arquitetura).

IMPORTANTE: isto só pré-preenche SUGESTÕES. O usuário decide o que cada peça é.
Formatos de malha não carregam nomes nem cores — a heurística não tem como saber.
"""

import numpy as np

# classe sugerida -> operação sugerida (conservadora: em dúvida, manter)
SUGGESTED_OP = {
    "weld_sphere": "remove",
    "profile": "reextrude",
    "wire_or_frame": "decimate",
    "hardware": "keep",
}


def classify(mesh):
    """Sugere uma classe pela forma do bbox e taxa de preenchimento.

    Regras (dims ordenadas ascendente, tudo em mm):
    - weld_sphere: pequena (<15mm), ~cúbica, maciça (fill > 0.3)
    - profile: prismática — maior dimensão > 3x a segunda maior
    - wire_or_frame: quase nada do bbox preenchido (fill < 0.15)
    - hardware: o resto (peças pequenas maciças: buchas, clipes, tampas)
    """
    dims = np.sort(mesh.bounds[1] - mesh.bounds[0])
    bbox_vol = float(np.prod(np.maximum(dims, 1e-9)))
    fill = abs(float(mesh.volume)) / bbox_vol
    if dims[2] < 15 and dims[2] / max(dims[0], 1e-9) < 2 and fill > 0.3:
        return "weld_sphere"
    if dims[2] > 3 * dims[1]:
        return "profile"
    if fill < 0.15:
        return "wire_or_frame"
    return "hardware"
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_analyze_classify.py -v`
Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/core/analyze/classify.py tests/test_analyze_classify.py
git commit -m "feat: classificação heurística sugestiva de peças"
```

---

### Task 7: Escala (`transform/scale.py`)

**Files:**
- Create: `src/meshbench/core/transform/scale.py`
- Test: `tests/test_transform_scale.py`

**Interfaces:**
- Consumes: `UNIT_MM` (Task 5).
- Produces: `scale_uniform(mesh, f) -> Trimesh`; `scale_per_axis(mesh, sx, sy, sz) -> Trimesh`; `fit_dimension(mesh, axis, target_mm) -> tuple[Trimesh, float]`; `apply_scale(mesh, spec: dict) -> tuple[Trimesh, list[float]]` onde `spec` segue o JSON do projeto (`mode` em `{"unit_convert","uniform","per_axis","fit_dimension"}`) e o retorno inclui o fator resultante `[fx, fy, fz]` (sempre gravado de volta na receita).

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_transform_scale.py`:
```python
import numpy as np
import pytest

from meshbench.core.transform.scale import (
    apply_scale,
    fit_dimension,
    scale_per_axis,
    scale_uniform,
)


def test_uniform_nao_muta_original(box):
    m = scale_uniform(box, 2.0)
    assert np.allclose(m.extents, [20, 40, 60])
    assert np.allclose(box.extents, [10, 20, 30])


def test_per_axis(box):
    m = scale_per_axis(box, 1.0, 2.0, 3.0)
    assert np.allclose(m.extents, [10, 40, 90])


def test_fit_dimension(box):
    m, f = fit_dimension(box, "x", 450.0)
    assert np.allclose(m.extents[0], 450.0)
    assert f == pytest.approx(45.0)
    # escala uniforme: as outras dimensões acompanham
    assert np.allclose(m.extents, [450, 900, 1350])


def test_fit_dimension_nula():
    import trimesh

    plano = trimesh.Trimesh(
        vertices=[[0, 0, 0], [1, 0, 0], [0, 1, 0]], faces=[[0, 1, 2]]
    )
    with pytest.raises(ValueError, match="nula"):
        fit_dimension(plano, "z", 100.0)


def test_apply_scale_unit_convert(box):
    m, factor = apply_scale(box, {"mode": "unit_convert", "from_unit": "in", "to_unit": "mm"})
    assert np.allclose(m.extents, [254, 508, 762])
    assert factor == [25.4, 25.4, 25.4]


def test_apply_scale_uniform(box):
    m, factor = apply_scale(box, {"mode": "uniform", "value": 0.5})
    assert np.allclose(m.extents, [5, 10, 15])
    assert factor == [0.5, 0.5, 0.5]


def test_apply_scale_fit(box):
    m, factor = apply_scale(
        box, {"mode": "fit_dimension", "fit": {"axis": "x", "target_mm": 450.0}}
    )
    assert np.allclose(m.extents[0], 450.0)
    assert factor == [45.0, 45.0, 45.0]


def test_apply_scale_modo_invalido(box):
    with pytest.raises(ValueError, match="modo de escala"):
        apply_scale(box, {"mode": "magico"})
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_transform_scale.py -v`
Expected: FAIL — módulo `scale` não existe

- [ ] **Step 3: Implementar**

`src/meshbench/core/transform/scale.py` (Anexo A.4; a escala é SEMPRE a primeira etapa do pipeline):
```python
"""Escala e conversão de unidades. SEMPRE a primeira transformação do pipeline:
os parâmetros das operações (bin_mm, tol…) são em mm absolutos."""

from meshbench.core.analyze.units import UNIT_MM


def scale_uniform(mesh, f):
    m = mesh.copy()
    m.apply_scale(f)
    return m


def scale_per_axis(mesh, sx, sy, sz):
    """⚠️ escala não-uniforme distorce raios de tubo/perfil — usar só para corrigir distorções."""
    m = mesh.copy()
    m.apply_scale([sx, sy, sz])
    return m


def fit_dimension(mesh, axis, target_mm):
    """Escala uniforme para que a dimensão `axis` fique exatamente target_mm."""
    i = "xyz".index(axis)
    cur = float(mesh.bounds[1][i] - mesh.bounds[0][i])
    if cur <= 0:
        raise ValueError(f"dimensão '{axis}' nula — não dá para ajustar")
    f = target_mm / cur
    return scale_uniform(mesh, f), f


def apply_scale(mesh, spec):
    """Aplica a escala descrita na receita. Retorna (malha, fator_resultante_xyz)."""
    mode = spec.get("mode", "unit_convert")
    if mode == "unit_convert":
        f = UNIT_MM[spec["from_unit"]] / UNIT_MM[spec.get("to_unit", "mm")]
        return scale_uniform(mesh, f), [f, f, f]
    if mode == "uniform":
        f = float(spec["value"])
        return scale_uniform(mesh, f), [f, f, f]
    if mode == "per_axis":
        sx, sy, sz = spec["per_axis"]
        return scale_per_axis(mesh, sx, sy, sz), [sx, sy, sz]
    if mode == "fit_dimension":
        m, f = fit_dimension(mesh, spec["fit"]["axis"], spec["fit"]["target_mm"])
        return m, [f, f, f]
    raise ValueError(f"modo de escala '{mode}' desconhecido")
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_transform_scale.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/core/transform/scale.py tests/test_transform_scale.py
git commit -m "feat: escala (conversão de unidade, uniforme, por eixo, fit-to-dimension)"
```

---

### Task 8: Remap de eixos e rotação (`transform/axes.py`, `transform/rotate.py`)

**Files:**
- Create: `src/meshbench/core/transform/axes.py`
- Create: `src/meshbench/core/transform/rotate.py`
- Test: `tests/test_transform_orient.py`

**Interfaces:**
- Produces (axes): `REMAPS: dict[str, tuple[str, str, str]]` com presets `identidade`, `cad_to_promob` (`("x","z","y")`), `z_up_to_y_up`, `y_up_to_z_up`; `remap_axes(mesh, spec) -> Trimesh` onde `spec` é nome de preset ou lista custom tipo `["x","-z","y"]`; corrige winding automaticamente quando o determinante é negativo.
- Produces (rotate): `rotate_90(mesh, axis: str, steps: int) -> Trimesh` (steps = múltiplos de +90°, CCW olhando do lado + do eixo); `rotate_free(mesh, rx, ry, rz) -> Trimesh` (graus, ordem X→Y→Z).

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_transform_orient.py`:
```python
import numpy as np
import pytest
import trimesh

from meshbench.core.transform.axes import REMAPS, remap_axes
from meshbench.core.transform.rotate import rotate_90, rotate_free


def _ponto_unico():
    return trimesh.Trimesh(
        vertices=[[1, 2, 3], [1, 2, 3.001], [1.001, 2, 3]], faces=[[0, 1, 2]]
    )


def test_preset_cad_to_promob_troca_y_z():
    m = remap_axes(_ponto_unico(), "cad_to_promob")
    assert np.allclose(m.vertices[0], [1, 3, 2])


def test_remap_corrige_winding(box):
    # trocar Y por Z tem determinante -1 → sem invert() o volume ficaria negativo
    m = remap_axes(box, "cad_to_promob")
    assert m.volume > 0
    assert m.volume == pytest.approx(box.volume)


def test_remap_custom_com_sinal():
    m = remap_axes(_ponto_unico(), ["x", "-z", "y"])
    assert np.allclose(m.vertices[0], [1, -3, 2])


def test_remap_preset_desconhecido(box):
    with pytest.raises(KeyError):
        remap_axes(box, "nao_existe")


def test_rotate_90_z():
    m = rotate_90(_ponto_unico(), "z", 1)
    assert np.allclose(m.vertices[0], [-2, 1, 3])


def test_rotate_90_bbox(box):
    m = rotate_90(box, "x", 1)
    assert np.allclose(m.extents, [10, 30, 20])
    assert m.volume == pytest.approx(box.volume)


def test_rotate_90_quatro_vezes_e_identidade(box):
    m = rotate_90(box, "y", 4)
    assert np.allclose(m.vertices, box.vertices)


def test_rotate_free_equivale_a_90(box):
    a = rotate_90(box, "z", 1)
    b = rotate_free(box, 0, 0, 90)
    assert np.allclose(a.bounds, b.bounds, atol=1e-6)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_transform_orient.py -v`
Expected: FAIL — módulos não existem

- [ ] **Step 3: Implementar axes.py**

`src/meshbench/core/transform/axes.py`:
```python
"""Remap de eixos por presets. NUNCA hardcodar: o preset é selecionável e o
usuário confirma olhando o preview (§3.2 do doc de arquitetura)."""

import numpy as np

REMAPS = {
    "identidade": ("x", "y", "z"),
    # CAD comum: Y=altura, Z=profundidade → Promob: Z=altura, Y=profundidade
    "cad_to_promob": ("x", "z", "y"),
    "z_up_to_y_up": ("x", "z", "-y"),
    "y_up_to_z_up": ("x", "-z", "y"),
}


def remap_axes(mesh, spec):
    """Aplica um remap de eixos. `spec` = nome de preset ou lista custom ["x","-z","y"].

    Se a permutação inverte a orientação (determinante negativo), corrige o
    winding com mesh.invert() — senão a peça renderiza pelo avesso.
    """
    axes = REMAPS[spec] if isinstance(spec, str) else tuple(spec)
    M = np.zeros((3, 3))
    for i, a in enumerate(axes):
        sign = -1.0 if a.startswith("-") else 1.0
        M[i, "xyz".index(a.lstrip("+-"))] = sign
    m = mesh.copy()
    m.vertices = mesh.vertices @ M.T
    if np.linalg.det(M) < 0:
        m.invert()
    return m
```

- [ ] **Step 4: Implementar rotate.py**

`src/meshbench/core/transform/rotate.py` (Anexo A.7 — portar como está, embrulhado para Trimesh):
```python
"""Rotação: snap de 90° (o caminho padrão — ver > deduzir) e rotação livre."""

import numpy as np
import trimesh


def _rotate_90_verts(v, axis, steps):
    for _ in range(steps % 4):
        if axis == "z":
            v = np.column_stack([-v[:, 1], v[:, 0], v[:, 2]])
        elif axis == "x":
            v = np.column_stack([v[:, 0], -v[:, 2], v[:, 1]])
        elif axis == "y":
            v = np.column_stack([v[:, 2], v[:, 1], -v[:, 0]])
        else:
            raise ValueError(f"eixo '{axis}' inválido")
    return v


def rotate_90(mesh, axis, steps=1):
    """steps = múltiplos de +90° (CCW olhando do lado + do eixo)."""
    m = mesh.copy()
    m.vertices = _rotate_90_verts(np.asarray(m.vertices), axis, steps)
    return m


def rotate_free(mesh, rx, ry, rz):
    """Graus, ordem X→Y→Z. Para o gizmo / entrada numérica."""
    m = mesh.copy()
    for ang, ax in ((rx, [1, 0, 0]), (ry, [0, 1, 0]), (rz, [0, 0, 1])):
        if ang:
            m.apply_transform(
                trimesh.transformations.rotation_matrix(np.deg2rad(ang), ax)
            )
    return m
```

- [ ] **Step 5: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_transform_orient.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/core/transform/axes.py src/meshbench/core/transform/rotate.py tests/test_transform_orient.py
git commit -m "feat: remap de eixos com presets e rotação (snap 90 + livre)"
```

---

### Task 9: Espelho e origem (`transform/mirror.py`, `transform/origin.py`)

**Files:**
- Create: `src/meshbench/core/transform/mirror.py`
- Create: `src/meshbench/core/transform/origin.py`
- Test: `tests/test_transform_mirror_origin.py`

**Interfaces:**
- Produces (mirror): `mirror(mesh, axis: str) -> Trimesh` — espelha e corrige winding com `invert()`.
- Produces (origin): `compute_anchor(bounds, anchor: str) -> np.ndarray` com `anchor` em `{"bbox_min", "center"}` ou `"corner_ABC"` (A,B,C ∈ {0,1} = min/max por eixo, ex. `corner_010`); `place_origin(groups: dict[str, list[Trimesh]], mode="common", anchor="bbox_min", snap_point=None, feature_bounds=None, offset=(0,0,0)) -> dict[str, list[Trimesh]]` — origem final = âncora + offset; `snap_point` (ponto clicado) tem precedência sobre tudo; `feature_bounds` (bounds de um componente de referência) tem precedência sobre o bbox do conjunto.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_transform_mirror_origin.py`:
```python
import numpy as np
import pytest

from meshbench.core.transform.mirror import mirror
from meshbench.core.transform.origin import compute_anchor, place_origin


def test_mirror_corrige_winding(box):
    m = mirror(box, "x")
    assert m.volume > 0  # sem invert() o volume sairia negativo
    assert m.volume == pytest.approx(box.volume)


def test_mirror_espelha(box):
    b = box.copy()
    b.apply_translation([100, 0, 0])  # bbox x: [95, 105]
    m = mirror(b, "x")
    assert np.allclose(m.bounds[:, 0], [-105, -95])


def test_compute_anchor():
    bounds = np.array([[0.0, 0.0, 0.0], [10.0, 20.0, 30.0]])
    assert np.allclose(compute_anchor(bounds, "bbox_min"), [0, 0, 0])
    assert np.allclose(compute_anchor(bounds, "center"), [5, 10, 15])
    assert np.allclose(compute_anchor(bounds, "corner_101"), [10, 0, 30])
    with pytest.raises(ValueError, match="âncora"):
        compute_anchor(bounds, "canto_magico")


def _dois_grupos(box):
    a = box.copy()
    a.apply_translation([100, 100, 100])  # bbox min = [95, 90, 85]
    b = box.copy()
    b.apply_translation([200, 100, 100])  # bbox min = [195, 90, 85]
    return {"fixa": [a], "movel": [b]}


def test_origem_comum_grupos_encaixam(box):
    out = place_origin(_dois_grupos(box), mode="common", anchor="bbox_min")
    # referencial único: o mínimo global [95, 90, 85] vira o zero
    assert np.allclose(out["fixa"][0].bounds[0], [0, 0, 0])
    assert np.allclose(out["movel"][0].bounds[0], [100, 0, 0])


def test_origem_por_grupo(box):
    out = place_origin(_dois_grupos(box), mode="per_group", anchor="bbox_min")
    assert np.allclose(out["fixa"][0].bounds[0], [0, 0, 0])
    assert np.allclose(out["movel"][0].bounds[0], [0, 0, 0])


def test_snap_point_tem_precedencia(box):
    out = place_origin(_dois_grupos(box), snap_point=[95, 90, 85])
    assert np.allclose(out["fixa"][0].bounds[0], [0, 0, 0])


def test_feature_bounds(box):
    fb = np.array([[100.0, 100.0, 100.0], [110.0, 110.0, 110.0]])
    out = place_origin(_dois_grupos(box), anchor="bbox_min", feature_bounds=fb)
    assert np.allclose(out["fixa"][0].bounds[0], [-5, -10, -15])


def test_offset(box):
    out = place_origin(
        _dois_grupos(box), mode="common", anchor="bbox_min", offset=[10, 0, 0]
    )
    assert np.allclose(out["fixa"][0].bounds[0], [-10, 0, 0])
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_transform_mirror_origin.py -v`
Expected: FAIL — módulos não existem

- [ ] **Step 3: Implementar mirror.py**

`src/meshbench/core/transform/mirror.py` (Anexo A.7):
```python
"""Espelho por eixo, com correção automática de winding."""


def mirror(mesh, axis):
    """Espelha no eixo dado. invert() corrige o winding — senão renderiza pelo avesso."""
    m = mesh.copy()
    s = [1, 1, 1]
    s["xyz".index(axis)] = -1
    m.apply_scale(s)
    m.invert()
    return m
```

- [ ] **Step 4: Implementar origin.py**

`src/meshbench/core/transform/origin.py`:
```python
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
```

- [ ] **Step 5: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_transform_mirror_origin.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/core/transform/mirror.py src/meshbench/core/transform/origin.py tests/test_transform_mirror_origin.py
git commit -m "feat: espelho com correção de winding e ancoragem de origem (comum/por grupo)"
```

---

### Task 10: Operações básicas + registry (`ops/basic.py`, `ops/registry.py`)

**Files:**
- Create: `src/meshbench/core/ops/registry.py`
- Create: `src/meshbench/core/ops/basic.py`
- Modify: `src/meshbench/core/ops/__init__.py`
- Test: `tests/test_ops_basic.py`

**Interfaces:**
- Produces: `registry.OPS: dict[str, callable]`; `registry.register(name, fn)`; `registry.apply_op(mesh, op: dict) -> Trimesh | None` onde `op = {"type": "keep|remove|decimate|hull|tube|reextrude", "params": {...}}` e `None` significa "peça removida"; `op_keep(mesh)`, `op_remove(mesh)`, `op_decimate(mesh, face_count=None, percent=None)`, `op_hull(mesh)`.
- Importar `meshbench.core.ops` registra keep/remove/decimate/hull (tube e reextrude entram nas Tasks 11 e 12).

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_ops_basic.py`:
```python
import pytest

from meshbench.core.ops import OPS, apply_op


def test_keep_copia(box):
    m = apply_op(box, {"type": "keep"})
    assert m is not box
    assert len(m.faces) == 12


def test_remove_retorna_none(box):
    assert apply_op(box, {"type": "remove"}) is None


def test_decimate_face_count(small_sphere):
    # icosfera subdivisions=2 tem 320 faces
    m = apply_op(small_sphere, {"type": "decimate", "params": {"face_count": 80}})
    assert len(m.faces) <= 100
    assert m.volume == pytest.approx(small_sphere.volume, rel=0.2)


def test_decimate_percent(small_sphere):
    m = apply_op(small_sphere, {"type": "decimate", "params": {"percent": 25.0}})
    assert len(m.faces) <= 320 * 0.35


def test_hull_fecha_perfil(c_channel):
    m = apply_op(c_channel, {"type": "hull"})
    # é exatamente por isso que hull em perfil aberto precisa de aviso:
    assert m.volume > 2 * c_channel.volume


def test_operacao_desconhecida(box):
    with pytest.raises(ValueError, match="operação"):
        apply_op(box, {"type": "explodir"})
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_ops_basic.py -v`
Expected: FAIL — `ImportError` (OPS não existe)

- [ ] **Step 3: Implementar**

`src/meshbench/core/ops/registry.py`:
```python
"""Registro central de operações de malha. Toda operação recebe uma malha e
params explícitos (todos expostos na UI) e retorna a malha nova, ou None = removida."""

OPS = {}


def register(name, fn):
    OPS[name] = fn


def apply_op(mesh, op):
    """Aplica a operação descrita na receita: {"type": ..., "params": {...}}."""
    kind = op.get("type", "keep")
    if kind not in OPS:
        raise ValueError(f"operação '{kind}' desconhecida (disponíveis: {sorted(OPS)})")
    return OPS[kind](mesh, **(op.get("params") or {}))
```

`src/meshbench/core/ops/basic.py`:
```python
"""Operações simples: keep, remove, decimate (quádrica), hull.

⚠️ decimate NÃO serve para arame curvo (destrói as pontas — use tube).
⚠️ hull FECHA perfis abertos (o pipeline avisa quando detecta isso).
"""

from meshbench.core.ops.registry import register


def op_keep(mesh):
    """Passa direto, intacta."""
    return mesh.copy()


def op_remove(mesh):
    """Descarta: solda, peças internas invisíveis, ferragens que o alvo já tem."""
    return None


def op_decimate(mesh, face_count=None, percent=None):
    """Decimação quádrica. Alvo absoluto (face_count) ou % do original (percent)."""
    if face_count is None:
        face_count = max(4, int(len(mesh.faces) * (percent or 25.0) / 100.0))
    return mesh.simplify_quadric_decimation(face_count=int(face_count))


def op_hull(mesh):
    """Convex hull — só para ferragens pequenas MACIÇAS."""
    return mesh.convex_hull


register("keep", op_keep)
register("remove", op_remove)
register("decimate", op_decimate)
register("hull", op_hull)
```

`src/meshbench/core/ops/__init__.py`:
```python
from meshbench.core.ops.registry import OPS, apply_op, register
from meshbench.core.ops import basic  # noqa: F401  (registra keep/remove/decimate/hull)

__all__ = ["OPS", "apply_op", "register"]
```

**Nota:** se `simplify_quadric_decimation` reclamar de argumento (a API do trimesh 4 usa `face_count`; versões mais novas podem preferir `percent`), ajustar a chamada — o teste dita o comportamento.

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_ops_basic.py -v`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/core/ops tests/test_ops_basic.py
git commit -m "feat: registry de operações + keep/remove/decimate/hull"
```

---

### Task 11: Reconstrução de arame (`ops/tube.py`)

**Files:**
- Create: `src/meshbench/core/ops/tube.py`
- Modify: `src/meshbench/core/ops/__init__.py`
- Test: `tests/test_ops_tube.py`

**Interfaces:**
- Consumes: `register` (Task 10).
- Produces: `extract_centerline(mesh, bin_mm=3.0) -> tuple[np.ndarray, float]` (linha de centro Nx3 + raio mediano); `tube_from_centerline(cl, radius, sides=8) -> Trimesh`; `op_tube(mesh, sides=8, bin_mm=3.0, radius=None) -> Trimesh` registrado como `"tube"`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_ops_tube.py`:
```python
import numpy as np
import pytest

from meshbench.core.ops import apply_op
from meshbench.core.ops.tube import extract_centerline, tube_from_centerline


def test_centerline_recupera_raio(wire_arc):
    cl, radius = extract_centerline(wire_arc, bin_mm=3.0)
    assert radius == pytest.approx(2.0, rel=0.3)
    assert len(cl) > 10
    # comprimento da linha ~ arco de 90° com raio 50 (~78.5)
    comp = np.linalg.norm(np.diff(cl, axis=0), axis=1).sum()
    assert comp == pytest.approx(50 * np.pi / 2, rel=0.25)


def test_tube_from_centerline_conta_faces():
    t = np.linspace(0, np.pi / 2, 20)
    cl = np.column_stack([50 * np.cos(t), 50 * np.sin(t), np.zeros_like(t)])
    m = tube_from_centerline(cl, radius=2.0, sides=8)
    # 2 triângulos por lado por segmento + tampas
    assert len(m.faces) == 8 * 2 * 19 + 2 * 8
    assert m.is_watertight


def test_op_tube_reduz_faces(wire_arc):
    out = apply_op(wire_arc, {"type": "tube", "params": {"sides": 8, "bin_mm": 3.0}})
    assert len(out.faces) < len(wire_arc.faces) / 2
    # o tubo reconstruído ocupa aproximadamente o mesmo espaço
    assert np.allclose(out.bounds, wire_arc.bounds, atol=5.0)


def test_op_tube_raio_sobrescrito(wire_arc):
    out = apply_op(wire_arc, {"type": "tube", "params": {"radius": 4.0}})
    # raio dobrado → bbox um pouco maior no eixo fino (z: era ~4, vira ~8)
    dz = out.bounds[1][2] - out.bounds[0][2]
    assert dz == pytest.approx(8.0, rel=0.3)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_ops_tube.py -v`
Expected: FAIL — módulo `tube` não existe

- [ ] **Step 3: Implementar**

`src/meshbench/core/ops/tube.py` (Anexo A.5 — portar como está; a linha de centro usa distância GEODÉSICA porque fatiar por plano falha em curvas de 180°):
```python
"""Reconstrução de arame como tubo low-poly.

Por que existe: a decimação quádrica destrói as pontas curvas do arame.
Linha de centro por distância geodésica (Dijkstra) — robusto até em U de 180°,
onde fatiar por plano cortaria as duas pernas e o centroide sairia no vazio.
Perfil varrido com parallel transport frames (evita torção ao longo da curva).
"""

import numpy as np
import trimesh
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from meshbench.core.ops.registry import register


def extract_centerline(mesh, bin_mm=3.0):
    v = mesh.vertices
    e = mesh.edges_unique
    el = np.linalg.norm(v[e[:, 0]] - v[e[:, 1]], axis=1)
    n = len(v)
    W = csr_matrix(
        (
            np.concatenate([el, el]),
            (
                np.concatenate([e[:, 0], e[:, 1]]),
                np.concatenate([e[:, 1], e[:, 0]]),
            ),
        ),
        shape=(n, n),
    )
    c0 = v - v.mean(0)
    _, vec = np.linalg.eigh(np.cov(c0.T))
    t = c0 @ vec[:, -1]
    g = dijkstra(W, indices=int(np.argmax(t)), directed=False)
    g[~np.isfinite(g)] = g[np.isfinite(g)].max()
    nb = max(4, int(g.max() / bin_mm))
    bins = np.linspace(0, g.max(), nb + 1)
    idx = np.digitize(g, bins) - 1
    cl, rad = [], []
    for b in range(nb):
        m = idx == b
        if m.sum() < 3:
            continue
        cen = v[m].mean(0)
        cl.append(cen)
        rad.append(np.linalg.norm(v[m] - cen, axis=1).mean())
    return np.array(cl), float(np.median(rad))


def tube_from_centerline(cl, radius, sides=8):
    P = np.asarray(cl)
    T = np.gradient(P, axis=0)
    T /= np.linalg.norm(T, axis=1, keepdims=True) + 1e-9
    ref = np.array([0, 0, 1.0]) if abs(T[0, 2]) < 0.9 else np.array([0, 1.0, 0])
    n0 = np.cross(T[0], ref)
    n0 /= np.linalg.norm(n0) + 1e-9
    normals = [n0]
    for i in range(1, len(P)):  # parallel transport (Rodrigues)
        pn = normals[-1]
        vx = np.cross(T[i - 1], T[i])
        cs = np.dot(T[i - 1], T[i])
        if np.linalg.norm(vx) < 1e-6:
            nn = pn
        else:
            vx /= np.linalg.norm(vx)
            a = np.arccos(np.clip(cs, -1, 1))
            nn = (
                pn * np.cos(a)
                + np.cross(vx, pn) * np.sin(a)
                + vx * np.dot(vx, pn) * (1 - np.cos(a))
            )
        nn = nn - np.dot(nn, T[i]) * T[i]
        nn /= np.linalg.norm(nn) + 1e-9
        normals.append(nn)
    normals = np.array(normals)
    B = np.cross(T, normals)
    ang = np.linspace(0, 2 * np.pi, sides, endpoint=False)
    rings = np.array(
        [
            P[i]
            + radius
            * (np.cos(ang)[:, None] * normals[i] + np.sin(ang)[:, None] * B[i])
            for i in range(len(P))
        ]
    )
    ns = len(P)
    V = rings.reshape(-1, 3)
    F = []
    for i in range(ns - 1):
        for j in range(sides):
            a = i * sides + j
            b = i * sides + (j + 1) % sides
            c = (i + 1) * sides + j
            d = (i + 1) * sides + (j + 1) % sides
            F += [[a, b, d], [a, d, c]]
    for ci, flip in [(0, False), (ns - 1, True)]:  # tampas
        idx = len(V)
        V = np.vstack([V, P[ci]])
        for j in range(sides):
            a = ci * sides + j
            b = ci * sides + (j + 1) % sides
            F.append([idx, b, a] if flip else [idx, a, b])
    return trimesh.Trimesh(vertices=V, faces=np.array(F), process=False)


def op_tube(mesh, sides=8, bin_mm=3.0, radius=None):
    """Reconstrói um arame/haste como tubo de N lados. radius=None → auto-detectado."""
    cl, detected = extract_centerline(mesh, bin_mm=bin_mm)
    return tube_from_centerline(cl, radius if radius is not None else detected, sides=sides)


register("tube", op_tube)
```

Adicionar ao `src/meshbench/core/ops/__init__.py`:
```python
from meshbench.core.ops.registry import OPS, apply_op, register
from meshbench.core.ops import basic  # noqa: F401
from meshbench.core.ops import tube  # noqa: F401  (registra "tube")

__all__ = ["OPS", "apply_op", "register"]
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_ops_tube.py -v`
Expected: 4 passed. Se `test_tube_from_centerline_conta_faces` falhar por `is_watertight`, verificar o winding das tampas antes de mexer na contagem — a contagem de faces é determinística.

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/core/ops/tube.py src/meshbench/core/ops/__init__.py tests/test_ops_tube.py
git commit -m "feat: op tube — centerline geodésica + parallel transport"
```

---

### Task 12: Re-extrusão de perfil (`ops/reextrude.py`)

**Files:**
- Create: `src/meshbench/core/ops/reextrude.py`
- Modify: `src/meshbench/core/ops/__init__.py`
- Test: `tests/test_ops_reextrude.py`

**Interfaces:**
- Consumes: `register` (Task 10).
- Produces: `op_reextrude(mesh, axis=None, n_probe=25, tol=0.4) -> Trimesh | None` registrado como `"reextrude"` (`axis=None` → auto: maior dimensão do bbox; retorna None se nenhuma seção válida for encontrada).

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_ops_reextrude.py`:
```python
import numpy as np
import pytest

from meshbench.core.ops import apply_op


def test_reextrude_preserva_forma_e_perfil_aberto(c_channel):
    out = apply_op(c_channel, {"type": "reextrude"})
    assert out is not None
    # volume preservado (era prismático limpo)
    assert out.volume == pytest.approx(c_channel.volume, rel=0.15)
    # PERFIL CONTINUA ABERTO: se tivesse fechado (efeito hull), o volume
    # saltaria para perto do volume do hull
    assert out.volume < 0.6 * out.convex_hull.volume
    # comprimento preservado no eixo de extrusão (z = 100)
    assert out.bounds[1][2] - out.bounds[0][2] == pytest.approx(100.0, abs=0.5)


def test_reextrude_eixo_explicito(c_channel):
    out = apply_op(c_channel, {"type": "reextrude", "params": {"axis": 2}})
    assert out.volume == pytest.approx(c_channel.volume, rel=0.15)


def test_reextrude_achata_faces(c_channel):
    # o canal reto já é low-poly; subdividir simula a tesselação densa do CAD
    denso = c_channel.subdivide().subdivide()
    out = apply_op(denso, {"type": "reextrude"})
    assert len(out.faces) < len(denso.faces) / 4
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_ops_reextrude.py -v`
Expected: FAIL — operação "reextrude" desconhecida

- [ ] **Step 3: Implementar**

`src/meshbench/core/ops/reextrude.py` (Anexo A.6 — portar como está; a única adaptação permitida é o nome do método `to_2D`/`to_planar` conforme a versão do trimesh):
```python
"""Re-extrusão de perfil prismático.

Por que existe: convex_hull FECHA o perfil C aberto (rejeitado pelo usuário).
Isto tira os furos e achata as faces MANTENDO o perfil aberto:
fatia perpendicular ao eixo em N posições e escolhe a fatia de MAIOR ÁREA
(a seção limpa, sem furo/rasgo passando).
"""

import numpy as np
import trimesh
from shapely.ops import unary_union
from trimesh.creation import triangulate_polygon

from meshbench.core.ops.registry import register


def _section_2d(mesh, origin, normal):
    sec = mesh.section(plane_origin=origin, plane_normal=normal)
    if sec is None:
        return None
    if hasattr(sec, "to_planar"):
        return sec.to_planar()
    return sec.to_2D()


def op_reextrude(mesh, axis=None, n_probe=25, tol=0.4):
    """Re-extruda o perfil prismático da peça. axis=None → maior dimensão do bbox."""
    dims = mesh.bounds[1] - mesh.bounds[0]
    if axis is None:
        axis = int(np.argmax(dims))
    normal = [0, 0, 0]
    normal[axis] = 1
    amin, amax = mesh.bounds[0, axis], mesh.bounds[1, axis]

    best, best_area = None, -1
    for ap in np.linspace(
        amin + (amax - amin) * 0.1, amax - (amax - amin) * 0.1, n_probe
    ):
        o = [0, 0, 0]
        o[axis] = ap
        try:
            planar = _section_2d(mesh, o, normal)
            if planar is None:
                continue
            p2d, to3d = planar
            area = sum(pp.area for pp in p2d.polygons_full)
        except Exception:
            continue
        if area > best_area:  # a fatia de MAIOR área = seção sem furo
            best_area, best = area, (p2d, to3d)
    if best is None:
        return None

    p2d, to3d = best
    geom = unary_union(list(p2d.polygons_full)).simplify(tol)
    if geom.geom_type == "MultiPolygon":
        geom = max(geom.geoms, key=lambda g: g.area)
    v2d, fcap = triangulate_polygon(geom, engine="earcut")

    def to_world(p2):
        h = np.column_stack([p2, np.zeros(len(p2)), np.ones(len(p2))])
        return (to3d @ h.T).T[:, :3]

    other = [i for i in range(3) if i != axis]
    V, F = [], []

    def ring(aval, pts):
        base = len(V)
        for p in pts:
            xyz = [0.0, 0.0, 0.0]
            xyz[axis] = aval
            xyz[other[0]] = p[0]
            xyz[other[1]] = p[1]
            V.append(xyz)
        return base

    prof = to_world(v2d)[:, other]
    b0 = ring(amin, prof)
    for f in fcap:
        F.append([b0 + f[0], b0 + f[2], b0 + f[1]])  # tampa (winding invertido)
    b1 = ring(amax, prof)
    for f in fcap:
        F.append([b1 + f[0], b1 + f[1], b1 + f[2]])  # tampa
    ext = np.array(geom.exterior.coords)[:-1]
    extw = to_world(ext)[:, other]
    ne = len(ext)
    r0 = ring(amin, extw)
    r1 = ring(amax, extw)
    for i in range(ne):  # parede lateral
        a = r0 + i
        b = r0 + (i + 1) % ne
        c = r1 + i
        d = r1 + (i + 1) % ne
        F += [[a, b, d], [a, d, c]]
    return trimesh.Trimesh(
        vertices=np.array(V, float), faces=np.array(F), process=False
    )


register("reextrude", op_reextrude)
```

Adicionar ao `src/meshbench/core/ops/__init__.py`:
```python
from meshbench.core.ops import reextrude  # noqa: F401  (registra "reextrude")
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_ops_reextrude.py -v`
Expected: 3 passed

- [ ] **Step 5: Rodar a suíte inteira**

Run: `.venv/Scripts/python -m pytest -v`
Expected: todos passam (nenhuma regressão)

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/core/ops/reextrude.py src/meshbench/core/ops/__init__.py tests/test_ops_reextrude.py
git commit -m "feat: op reextrude — seção de maior área, mantém perfil aberto"
```

---

### Task 13: Modelo de projeto (`project.py`)

**Files:**
- Create: `src/meshbench/core/project.py`
- Test: `tests/test_project.py`

**Interfaces:**
- Consumes: `split_components`, `signature_of`, `ComponentFamily` (Task 4); `guess_unit` (Task 5); `classify`, `SUGGESTED_OP` (Task 6).
- Produces:
  - `ComponentEntry` (dataclass): `id, signature, instances, face_count, bbox, auto_class, user_label=None, operation={"type":"keep","params":{}}, group=None, needs_review=False`.
  - `Project` (dataclass): `version=1, name, source: dict, scale: dict, components: list[ComponentEntry], groups: list[dict], orient: dict, origin: dict, export: dict` + `to_dict()`, `from_dict(d)`, `save(path)`, `load(path)`.
  - `sha256_of(path) -> str`.
  - `new_project(name, source_path, mesh, families) -> Project` — receita inicial com sugestões preenchidas, grupo padrão `"saida"`.
  - `rematch(project, families) -> tuple[Project, list[str]]` — casa por assinatura preservando escolhas do usuário; novos entram com `needs_review=True`; desaparecidos são reportados nos avisos.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_project.py`:
```python
import trimesh

from meshbench.core.analyze.components import split_components
from meshbench.core.project import Project, new_project, rematch, sha256_of


def _scene(box, small_sphere):
    s = small_sphere.copy()
    s.apply_translation([100, 0, 0])
    return trimesh.util.concatenate([box, s])


def test_new_project_preenche_sugestoes(tmp_path, box, small_sphere):
    scene = _scene(box, small_sphere)
    src = tmp_path / "cena.stl"
    scene.export(str(src))
    fams = split_components(scene)

    p = new_project("teste", src, scene, fams)
    assert p.name == "teste"
    assert p.source["sha256"] == sha256_of(src)
    assert len(p.components) == 2
    esfera = [c for c in p.components if c.face_count == 320][0]
    assert esfera.auto_class == "weld_sphere"
    assert esfera.operation == {"type": "remove", "params": {}}
    assert esfera.user_label is None  # heurística NUNCA vira rótulo do usuário
    caixa = [c for c in p.components if c.face_count == 12][0]
    assert caixa.group == "saida"
    assert p.groups == [{"name": "saida", "role": "fixed"}]


def test_roundtrip_json(tmp_path, box, small_sphere):
    scene = _scene(box, small_sphere)
    src = tmp_path / "cena.stl"
    scene.export(str(src))
    p = new_project("teste", src, scene, split_components(scene))
    f = tmp_path / "teste.meshbench.json"
    p.save(f)
    p2 = Project.load(f)
    assert p2.to_dict() == p.to_dict()


def test_rematch_preserva_escolhas(tmp_path, box, small_sphere):
    scene = _scene(box, small_sphere)
    src = tmp_path / "cena.stl"
    scene.export(str(src))
    p = new_project("teste", src, scene, split_components(scene))
    caixa = [c for c in p.components if c.face_count == 12][0]
    caixa.user_label = "metalon"
    caixa.operation = {"type": "hull", "params": {}}
    caixa.group = "fixa"

    # re-export: a esfera sumiu, a caixa continua, entrou um cilindro novo
    cyl = trimesh.creation.cylinder(radius=5, height=40)
    cyl.apply_translation([0, 200, 0])
    scene2 = trimesh.util.concatenate([box.copy(), cyl])
    p2, avisos = rematch(p, split_components(scene2))

    caixa2 = [c for c in p2.components if c.face_count == 12][0]
    assert caixa2.user_label == "metalon"
    assert caixa2.operation["type"] == "hull"
    assert caixa2.group == "fixa"
    assert caixa2.needs_review is False

    novos = [c for c in p2.components if c.needs_review]
    assert len(novos) == 1  # o cilindro

    assert any("sumiu" in a for a in avisos)  # a esfera desapareceu
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_project.py -v`
Expected: FAIL — módulo `project` não existe

- [ ] **Step 3: Implementar**

`src/meshbench/core/project.py`:
```python
"""Modelo de dados do projeto — a receita .meshbench.json (§10 do doc).

Reprodutível, diffável, versionável no git. Campos auto_* são sugestões da
heurística; campos user_* e as escolhas de operação/grupo são do USUÁRIO —
o rematch por assinatura preserva essas escolhas após re-export do CAD.
"""

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

from meshbench.core.analyze.classify import SUGGESTED_OP, classify
from meshbench.core.analyze.units import guess_unit

DEFAULT_SCALE = {
    "mode": "unit_convert",
    "from_unit": "mm",
    "to_unit": "mm",
    "value": None,
    "per_axis": None,
    "fit": None,
    "factor": [1, 1, 1],
}
DEFAULT_ORIENT = {
    "axis_remap": "identidade",
    "custom_remap": None,
    "rotations": [],
    "mirror": [],
}
DEFAULT_ORIGIN = {
    "mode": "common",
    "anchor": "bbox_min",
    "feature_ref": None,
    "snap_point": None,
    "offset": [0, 0, 0],
}
DEFAULT_EXPORT = {
    "format": "dxf_r12",
    "out_dir": "out/",
    "naming": "{project}_{group}.dxf",
}


def sha256_of(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


@dataclass
class ComponentEntry:
    id: str
    signature: str
    instances: int
    face_count: int
    bbox: list
    auto_class: str
    user_label: str | None = None
    operation: dict = field(default_factory=lambda: {"type": "keep", "params": {}})
    group: str | None = None
    needs_review: bool = False


@dataclass
class Project:
    name: str
    source: dict
    scale: dict = field(default_factory=lambda: dict(DEFAULT_SCALE))
    components: list = field(default_factory=list)
    groups: list = field(default_factory=list)
    orient: dict = field(default_factory=lambda: dict(DEFAULT_ORIENT))
    origin: dict = field(default_factory=lambda: dict(DEFAULT_ORIGIN))
    export: dict = field(default_factory=lambda: dict(DEFAULT_EXPORT))
    version: int = 1

    def to_dict(self):
        d = asdict(self)
        d["components"] = [asdict(c) if not isinstance(c, dict) else c for c in self.components]
        return d

    @classmethod
    def from_dict(cls, d):
        d = dict(d)
        d["components"] = [ComponentEntry(**c) for c in d.get("components", [])]
        return cls(**d)

    def save(self, path):
        Path(path).write_text(
            json.dumps(self.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )

    @classmethod
    def load(cls, path):
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _entry_from_family(fam, group):
    auto = classify(fam.meshes[0])
    return ComponentEntry(
        id=fam.id,
        signature=fam.signature,
        instances=fam.instances,
        face_count=fam.face_count,
        bbox=fam.bbox,
        auto_class=auto,
        operation={"type": SUGGESTED_OP[auto], "params": {}},
        group=None if SUGGESTED_OP[auto] == "remove" else group,
    )


def new_project(name, source_path, mesh, families):
    """Receita inicial: sugestões preenchidas, tudo num grupo 'saida'. O usuário edita."""
    unit, motivo = guess_unit(mesh)
    detected = unit or "mm"
    return Project(
        name=name,
        source={
            "path": str(source_path),
            "sha256": sha256_of(source_path),
            "detected_units": detected,
            "detection_note": motivo,
            "units": detected,  # o que o USUÁRIO confirmou (editável)
        },
        scale={**DEFAULT_SCALE, "from_unit": detected},
        components=[_entry_from_family(f, "saida") for f in families],
        groups=[{"name": "saida", "role": "fixed"}],
    )


def rematch(project, families):
    """Casa famílias novas com a receita por assinatura, preservando escolhas do usuário.

    Retorna (projeto_atualizado, avisos). Famílias sem par entram como
    needs_review=True; entradas cuja peça sumiu são removidas e reportadas.
    """
    avisos = []
    by_sig = {c.signature: c for c in project.components}
    new_components = []
    matched = set()
    for fam in families:
        old = by_sig.get(fam.signature)
        if old is not None:
            matched.add(old.signature)
            new_components.append(
                ComponentEntry(
                    id=fam.id,
                    signature=fam.signature,
                    instances=fam.instances,
                    face_count=fam.face_count,
                    bbox=fam.bbox,
                    auto_class=old.auto_class,
                    user_label=old.user_label,
                    operation=old.operation,
                    group=old.group,
                    needs_review=False,
                )
            )
        else:
            e = _entry_from_family(fam, group=None)
            e.needs_review = True
            new_components.append(e)
            avisos.append(f"componente novo — revisar: {fam.signature}")
    for c in project.components:
        if c.signature not in matched:
            rotulo = c.user_label or c.auto_class
            avisos.append(f"componente sumiu do source: {rotulo} ({c.signature})")
    project.components = new_components
    return project, avisos
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_project.py -v`
Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/core/project.py tests/test_project.py
git commit -m "feat: modelo de projeto .meshbench.json com rematch por assinatura"
```

---

### Task 14: Pipeline (`pipeline.py`)

**Files:**
- Create: `src/meshbench/core/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: tudo das Tasks 2–13.
- Produces:
  - `PipelineResult` (dataclass): `files: list[dict]` (cada um `{"path": str, "group": str, "faces": int}`), `warnings: list[str]`.
  - `run(project: Project, base_dir: Path) -> PipelineResult` — executa a pilha completa na ordem fixa: IMPORT → SCALE → SPLIT → OPS → GROUP → ORIENT → ORIGIN → EXPORT. Caminhos relativos da receita resolvem contra `base_dir`.
  - `apply_orient(mesh, orient: dict) -> Trimesh` (remap → rotações em ordem → espelhos).
  - Validadores (viram warnings, nunca bloqueiam): peça sem grupo e não removida; hull em peça classificada como profile; grupo > 15.000 faces; dimensão absurda (< 1 mm ou > 5000 mm) após a escala.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_pipeline.py`:
```python
import numpy as np
import trimesh

from meshbench.core.analyze.components import split_components
from meshbench.core.io.readers import read_dxf_3dface
from meshbench.core.pipeline import run
from meshbench.core.project import new_project


def _setup(tmp_path, box, small_sphere):
    """Cena: caixa (fica) + esfera de solda (remove) + caixa pequena sem grupo."""
    s = small_sphere.copy()
    s.apply_translation([100, 0, 0])
    orfa = trimesh.creation.box(extents=[5, 5, 5])
    orfa.apply_translation([0, 100, 0])
    scene = trimesh.util.concatenate([box, s, orfa])
    src = tmp_path / "cena.stl"
    scene.export(str(src))
    p = new_project("teste", src, scene, split_components(scene))
    p.source["path"] = "cena.stl"  # relativo ao base_dir
    # caixa 5x5x5 fica sem grupo de propósito (validador deve avisar)
    orfa_entry = [c for c in p.components if "b[5.0,5.0,5.0]" in c.signature][0]
    orfa_entry.group = None
    orfa_entry.operation = {"type": "keep", "params": {}}
    return p


def test_pipeline_exporta_dxf(tmp_path, box, small_sphere):
    p = _setup(tmp_path, box, small_sphere)
    res = run(p, tmp_path)
    assert len(res.files) == 1
    out = tmp_path / "out" / "teste_saida.dxf"
    assert out.exists()
    m = read_dxf_3dface(out)
    assert len(m.faces) == 12  # só a caixa (esfera removida, órfã sem grupo)


def test_pipeline_origem_zerada(tmp_path, box, small_sphere):
    p = _setup(tmp_path, box, small_sphere)
    run(p, tmp_path)
    m = read_dxf_3dface(tmp_path / "out" / "teste_saida.dxf")
    assert np.allclose(m.bounds[0], [0, 0, 0], atol=1e-6)


def test_pipeline_avisa_peca_sem_grupo(tmp_path, box, small_sphere):
    p = _setup(tmp_path, box, small_sphere)
    res = run(p, tmp_path)
    assert any("sem grupo" in w for w in res.warnings)


def test_pipeline_escala_antes_de_tudo(tmp_path, box, small_sphere):
    p = _setup(tmp_path, box, small_sphere)
    p.scale = {"mode": "uniform", "value": 2.0}
    run(p, tmp_path)
    m = read_dxf_3dface(tmp_path / "out" / "teste_saida.dxf")
    assert np.allclose(m.extents, [20, 40, 60])


def test_pipeline_orient_e_origem_por_ultimo(tmp_path, box, small_sphere):
    p = _setup(tmp_path, box, small_sphere)
    p.orient = {
        "axis_remap": "identidade",
        "custom_remap": None,
        "rotations": [{"axis": "x", "deg": 90}],
        "mirror": [],
    }
    run(p, tmp_path)
    m = read_dxf_3dface(tmp_path / "out" / "teste_saida.dxf")
    # caixa 10x20x30 girada 90° em X → 10x30x20, e AINDA zerada na origem
    assert np.allclose(m.extents, [10, 30, 20])
    assert np.allclose(m.bounds[0], [0, 0, 0], atol=1e-6)


def test_pipeline_avisa_dimensao_absurda(tmp_path, box, small_sphere):
    p = _setup(tmp_path, box, small_sphere)
    p.scale = {"mode": "uniform", "value": 1000.0}
    res = run(p, tmp_path)
    assert any("confira a unidade" in w for w in res.warnings)
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py -v`
Expected: FAIL — módulo `pipeline` não existe

- [ ] **Step 3: Implementar**

`src/meshbench/core/pipeline.py`:
```python
"""Orquestra a pilha de transformação (§4 do doc — a ordem NÃO é negociável):

 1. IMPORT   2. SCALE (primeiro!)   3. SPLIT   4. OPS   5. GROUP
 6. ORIENT   7. ORIGIN (por último!)   8. EXPORT
"""

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from meshbench.core.analyze.components import split_components
from meshbench.core.io.readers import read_mesh
from meshbench.core.io.writers import write_meshes
from meshbench.core.ops import apply_op
from meshbench.core.transform.axes import remap_axes
from meshbench.core.transform.mirror import mirror
from meshbench.core.transform.origin import _bounds_of, place_origin
from meshbench.core.transform.rotate import rotate_90, rotate_free
from meshbench.core.transform.scale import apply_scale

FACE_BUDGET = 15000  # empírico: acima disso o Promob pode não abrir


@dataclass
class PipelineResult:
    files: list = field(default_factory=list)
    warnings: list = field(default_factory=list)


def apply_orient(mesh, orient):
    """remap de eixos → rotações (em ordem) → espelhos."""
    spec = orient.get("custom_remap") or orient.get("axis_remap", "identidade")
    m = remap_axes(mesh, spec)
    for r in orient.get("rotations", []):
        deg = float(r["deg"])
        if deg % 90 == 0:
            m = rotate_90(m, r["axis"], int(deg // 90))
        else:
            args = {"rx": 0.0, "ry": 0.0, "rz": 0.0, "r" + r["axis"]: deg}
            m = rotate_free(m, args["rx"], args["ry"], args["rz"])
    for ax in orient.get("mirror", []):
        m = mirror(m, ax)
    return m


def run(project, base_dir):
    """Executa a receita e exporta um arquivo por grupo. Retorna caminhos + avisos."""
    base_dir = Path(base_dir)
    warnings = []

    # 1. IMPORT
    src = Path(project.source["path"])
    if not src.is_absolute():
        src = base_dir / src
    mesh = read_mesh(src)

    # 2. SCALE — sempre primeiro: parâmetros das ops são em mm absolutos
    mesh, factor = apply_scale(mesh, project.scale)
    project.scale["factor"] = list(factor)
    dims = mesh.bounds[1] - mesh.bounds[0]
    if float(np.max(dims)) > 5000 or float(np.min(dims)) < 1:
        warnings.append(
            f"dimensão final suspeita ({dims[0]:.1f} × {dims[1]:.1f} × {dims[2]:.1f} mm) "
            "— confira a unidade"
        )

    # 3. SPLIT
    families = split_components(mesh)
    by_sig = {c.signature: c for c in project.components}

    # 4. OPS + 5. GROUP
    group_names = [g["name"] for g in project.groups] or ["saida"]
    grouped = {g: [] for g in group_names}
    feature_meshes = {}  # component id -> meshes processadas (p/ feature_ref da origem)
    for fam in families:
        entry = by_sig.get(fam.signature)
        if entry is None:
            warnings.append(
                f"componente {fam.signature} não está na receita — fora da saída"
            )
            continue
        if entry.operation.get("type") == "remove":
            continue
        if entry.operation.get("type") == "hull" and entry.auto_class == "profile":
            rotulo = entry.user_label or entry.id
            warnings.append(f"hull em perfil aberto ({rotulo}) — isto vai fechar o perfil")
        processed = []
        for m in fam.meshes:
            out = apply_op(m, entry.operation)
            if out is not None:
                processed.append(out)
        feature_meshes[entry.id] = processed
        if entry.group is None:
            rotulo = entry.user_label or entry.auto_class
            warnings.append(
                f"peça sem grupo e não removida: {entry.id} ({rotulo}) — vai sumir do resultado"
            )
            continue
        if entry.group not in grouped:
            grouped[entry.group] = []
        grouped[entry.group].extend(processed)

    # 6. ORIENT
    grouped = {
        g: [apply_orient(m, project.orient) for m in ms] for g, ms in grouped.items()
    }

    # 7. ORIGIN — sempre por último: a âncora só faz sentido na orientação final
    grouped = {g: ms for g, ms in grouped.items() if ms}
    if grouped:  # tudo removido/sem grupo → nada a ancorar nem exportar
        feature_bounds = None
        ref = project.origin.get("feature_ref")
        if ref and feature_meshes.get(ref):
            oriented_ref = [apply_orient(m, project.orient) for m in feature_meshes[ref]]
            feature_bounds = _bounds_of(oriented_ref)
        grouped = place_origin(
            grouped,
            mode=project.origin.get("mode", "common"),
            anchor=project.origin.get("anchor", "bbox_min"),
            snap_point=project.origin.get("snap_point"),
            feature_bounds=feature_bounds,
            offset=project.origin.get("offset", [0, 0, 0]),
        )

    # 8. EXPORT — um arquivo por grupo
    result = PipelineResult(warnings=warnings)
    out_dir = Path(project.export.get("out_dir", "out/"))
    if not out_dir.is_absolute():
        out_dir = base_dir / out_dir
    fmt = project.export.get("format", "dxf_r12")
    ext = {"dxf_r12": "dxf", "stl": "stl", "obj": "obj"}[fmt]
    naming = project.export.get("naming", "{project}_{group}." + ext)
    for g, ms in grouped.items():
        if not ms:
            continue
        name = naming.format(project=project.name, group=g)
        path = out_dir / name
        write_meshes(ms, path, fmt)
        faces = sum(len(m.faces) for m in ms)
        if faces > FACE_BUDGET:
            warnings.append(
                f"grupo '{g}' tem {faces} faces (> {FACE_BUDGET}) — pode não abrir no Promob"
            )
        result.files.append({"path": str(path), "group": g, "faces": faces})
    return result
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline.py -v`
Expected: 6 passed

- [ ] **Step 5: Rodar a suíte inteira**

Run: `.venv/Scripts/python -m pytest`
Expected: todos passam

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/core/pipeline.py tests/test_pipeline.py
git commit -m "feat: pipeline completo com ordem fixa e validadores"
```

---

### Task 15: CLI (`cli.py`, `__main__.py`)

**Files:**
- Create: `src/meshbench/cli.py`
- Create: `src/meshbench/__main__.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `read_mesh`, `split_components`, `classify`, `SUGGESTED_OP`, `guess_unit`, `human_dimensions`, `new_project`, `Project`, `rematch`, `run`.
- Produces: `main(argv=None) -> int` com subcomandos:
  - `meshbench inspect ARQUIVO` — bbox, unidade sugerida, tabela de famílias (id, instâncias, faces, classe sugerida, operação sugerida).
  - `meshbench init ARQUIVO [-o SAIDA] [--nome NOME]` — gera receita inicial `.meshbench.json` (padrão: `NOME.meshbench.json` ao lado do arquivo).
  - `meshbench apply RECEITA [--reimport]` — aplica a receita e exporta; `--reimport` re-casa componentes por assinatura antes (avisos de novos/sumidos) e salva a receita atualizada.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_cli.py`:
```python
import json

import trimesh

from meshbench.cli import main


def _stl(tmp_path, box, small_sphere):
    s = small_sphere.copy()
    s.apply_translation([100, 0, 0])
    scene = trimesh.util.concatenate([box, s])
    p = tmp_path / "cena.stl"
    scene.export(str(p))
    return p


def test_inspect(tmp_path, box, small_sphere, capsys):
    src = _stl(tmp_path, box, small_sphere)
    assert main(["inspect", str(src)]) == 0
    out = capsys.readouterr().out
    assert "c0" in out and "c1" in out
    assert "weld_sphere" in out
    assert "mm" in out  # dimensões e/ou unidade sugerida


def test_init_cria_receita(tmp_path, box, small_sphere):
    src = _stl(tmp_path, box, small_sphere)
    receita = tmp_path / "cena.meshbench.json"
    assert main(["init", str(src)]) == 0
    assert receita.exists()
    d = json.loads(receita.read_text(encoding="utf-8"))
    assert d["name"] == "cena"
    assert len(d["components"]) == 2
    assert d["source"]["path"] == "cena.stl"  # relativo à pasta da receita


def test_apply_exporta(tmp_path, box, small_sphere, capsys):
    src = _stl(tmp_path, box, small_sphere)
    main(["init", str(src)])
    receita = tmp_path / "cena.meshbench.json"
    assert main(["apply", str(receita)]) == 0
    out = capsys.readouterr().out
    assert (tmp_path / "out" / "cena_saida.dxf").exists()
    assert "faces" in out


def test_apply_mostra_avisos(tmp_path, box, small_sphere, capsys):
    src = _stl(tmp_path, box, small_sphere)
    main(["init", str(src)])
    receita = tmp_path / "cena.meshbench.json"
    d = json.loads(receita.read_text(encoding="utf-8"))
    for c in d["components"]:
        c["group"] = None
        c["operation"] = {"type": "keep", "params": {}}
    receita.write_text(json.dumps(d), encoding="utf-8")
    main(["apply", str(receita)])
    out = capsys.readouterr().out
    assert "⚠" in out and "sem grupo" in out


def test_apply_reimport_rematch(tmp_path, box, small_sphere, capsys):
    src = _stl(tmp_path, box, small_sphere)
    main(["init", str(src)])
    receita = tmp_path / "cena.meshbench.json"
    # o source mudou: só a caixa agora
    box.export(str(src))
    assert main(["apply", str(receita), "--reimport"]) == 0
    out = capsys.readouterr().out
    assert "sumiu" in out
    d = json.loads(receita.read_text(encoding="utf-8"))
    assert len(d["components"]) == 1  # receita atualizada e salva
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_cli.py -v`
Expected: FAIL — módulo `cli` não existe

- [ ] **Step 3: Implementar**

`src/meshbench/cli.py`:
```python
"""CLI do MeshBench: inspect (analisa), init (gera receita), apply (exporta)."""

import argparse
import sys
from pathlib import Path

from meshbench.core.analyze.classify import SUGGESTED_OP, classify
from meshbench.core.analyze.components import split_components
from meshbench.core.analyze.units import guess_unit, human_dimensions
from meshbench.core.io.readers import read_mesh
from meshbench.core.pipeline import run
from meshbench.core.project import Project, new_project, rematch


def _cmd_inspect(args):
    mesh = read_mesh(args.arquivo)
    unit, motivo = guess_unit(mesh)
    print(f"Arquivo: {args.arquivo}")
    print(f"Dimensões (na unidade do arquivo): {human_dimensions(mesh)}")
    print(f"Unidade sugerida: {unit or 'ambígua'} — {motivo}")
    fams = split_components(mesh)
    print(f"\n{len(fams)} famílias de componentes:")
    print(f"{'id':<5} {'inst':>4} {'faces':>7}  {'classe sugerida':<15} {'op sugerida'}")
    for f in fams:
        cls = classify(f.meshes[0])
        print(f"{f.id:<5} {f.instances:>4} {f.face_count:>7}  {cls:<15} {SUGGESTED_OP[cls]}")
    total = sum(f.instances * f.face_count for f in fams)
    print(f"\nTotal: {total} faces")
    return 0


def _cmd_init(args):
    src = Path(args.arquivo)
    nome = args.nome or src.stem
    mesh = read_mesh(src)
    fams = split_components(mesh)
    p = new_project(nome, src, mesh, fams)
    saida = Path(args.saida) if args.saida else src.parent / f"{nome}.meshbench.json"
    # caminho do source relativo à pasta da receita, quando possível
    try:
        p.source["path"] = str(src.resolve().relative_to(saida.resolve().parent))
    except ValueError:
        p.source["path"] = str(src.resolve())
    p.save(saida)
    print(f"Receita criada: {saida}")
    print("Revise as operações e grupos sugeridos antes de aplicar — a heurística só sugere.")
    return 0


def _cmd_apply(args):
    receita = Path(args.receita)
    p = Project.load(receita)
    base_dir = receita.resolve().parent
    if args.reimport:
        src = Path(p.source["path"])
        if not src.is_absolute():
            src = base_dir / src
        mesh = read_mesh(src)
        p, avisos = rematch(p, split_components(mesh))
        for a in avisos:
            print(f"⚠ {a}")
        p.save(receita)
    res = run(p, base_dir)
    p.save(receita)  # grava o fator de escala resultante
    for w in res.warnings:
        print(f"⚠ {w}")
    for f in res.files:
        ok = "✓" if f["faces"] <= 15000 else "⚠"
        print(f"{ok} {f['group']}: {f['path']} ({f['faces']} faces)")
    if not res.files:
        print("nenhum arquivo exportado — confira grupos e operações na receita")
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="meshbench",
        description="Prepara malhas 3D exportadas de CAD para software de projeto (Promob e outros).",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ins = sub.add_parser("inspect", help="analisa um arquivo e lista os componentes")
    p_ins.add_argument("arquivo")
    p_ins.set_defaults(fn=_cmd_inspect)

    p_init = sub.add_parser("init", help="cria uma receita .meshbench.json com sugestões")
    p_init.add_argument("arquivo")
    p_init.add_argument("-o", "--saida", default=None, help="caminho da receita gerada")
    p_init.add_argument("--nome", default=None, help="nome do projeto (padrão: nome do arquivo)")
    p_init.set_defaults(fn=_cmd_init)

    p_apply = sub.add_parser("apply", help="aplica uma receita e exporta os arquivos")
    p_apply.add_argument("receita")
    p_apply.add_argument(
        "--reimport",
        action="store_true",
        help="re-lê o source e re-casa componentes por assinatura antes de aplicar",
    )
    p_apply.set_defaults(fn=_cmd_apply)

    args = parser.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
```

`src/meshbench/__main__.py`:
```python
import sys

from meshbench.cli import main

sys.exit(main())
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_cli.py -v`
Expected: 5 passed

- [ ] **Step 5: Fumaça manual da CLI**

Run: `.venv/Scripts/python -m meshbench --help`
Expected: ajuda com os 3 subcomandos, sem traceback

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/cli.py src/meshbench/__main__.py tests/test_cli.py
git commit -m "feat: CLI inspect/init/apply"
```

---

### Task 16: Regressão de ouro + exemplo + docs

**Files:**
- Create: `tests/test_regression_real.py`
- Create: `examples/rm-416.meshbench.json`
- Create: `README.md`
- Modify: `CLAUDE.md` (seção de comandos)

**Interfaces:**
- Consumes: tudo. Os arquivos reais em `docs/peças exemplo/` (fora do git; testes pulam se ausentes).

- [ ] **Step 1: Escrever os testes de regressão**

`tests/test_regression_real.py`:
```python
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

    out = apply_op(m, {"type": "reextrude", "params": {"tol": 0.4}})
    assert out is not None
    assert len(out.faces) < 120  # 536 → ~50
    # perfil aberto preservado (não virou bloco maciço)
    assert out.volume < 0.6 * out.convex_hull.volume


def test_fruteira_2191():
    """B.1: 455.804 3DFACE, 112 componentes, 64 esferas de solda de 5.852 faces."""
    m = read_mesh(EXEMPLOS / "2191-0400.dxf")
    fams = split_components(m)
    n_componentes = sum(f.instances for f in fams)
    assert n_componentes == 112
    soldas = [f for f in fams if f.face_count == 5852]
    assert soldas and soldas[0].instances == 64


def test_calceiro_3214_0400():
    """B.2: 12 hastes de 4.978 faces, 1 frame de 7.380 faces."""
    m = read_mesh(EXEMPLOS / "3214-0400-CL-00.dxf")
    fams = split_components(m)
    hastes = [f for f in fams if f.face_count == 4978]
    assert hastes and hastes[0].instances == 12
    frames = [f for f in fams if f.face_count == 7380]
    assert frames and frames[0].instances == 1
```

- [ ] **Step 2: Rodar a regressão**

Run: `.venv/Scripts/python -m pytest -m slow -v` (os DXFs têm até 99MB — pode levar minutos)
Expected: 3 passed. **Se algum número não bater** (contagem de componentes/faces), NÃO ajustar o teste às cegas: os números vêm do Anexo B do doc de arquitetura; investigar com `meshbench inspect` e reportar a diferença ao usuário no checkpoint.

- [ ] **Step 3: Criar a receita de exemplo**

`examples/rm-416.meshbench.json` (caminhos relativos à pasta `examples/`):
```json
{
  "version": 1,
  "name": "rm-416",
  "source": {
    "path": "../docs/peças exemplo/RM-416.STL",
    "sha256": "",
    "detected_units": "mm",
    "detection_note": "provável: faixa típica de componente de móvel em mm",
    "units": "mm"
  },
  "scale": {
    "mode": "unit_convert",
    "from_unit": "mm",
    "to_unit": "mm",
    "value": null,
    "per_axis": null,
    "fit": null,
    "factor": [1, 1, 1]
  },
  "components": [
    {
      "id": "c0",
      "signature": "",
      "instances": 1,
      "face_count": 536,
      "bbox": [[0, 0, 0], [54.5, 15.1, 1000.0]],
      "auto_class": "profile",
      "user_label": "perfil cava",
      "operation": { "type": "reextrude", "params": { "tol": 0.4 } },
      "group": "saida",
      "needs_review": false
    }
  ],
  "groups": [{ "name": "saida", "role": "fixed" }],
  "orient": {
    "axis_remap": "cad_to_promob",
    "custom_remap": null,
    "rotations": [],
    "mirror": []
  },
  "origin": {
    "mode": "common",
    "anchor": "bbox_min",
    "feature_ref": null,
    "snap_point": null,
    "offset": [0, 0, 0]
  },
  "export": {
    "format": "dxf_r12",
    "out_dir": "../out/",
    "naming": "{project}_{group}.dxf"
  }
}
```

**Nota:** a `signature` real depende da malha — depois de criar o arquivo, rodar `meshbench init "docs/peças exemplo/RM-416.STL" -o examples/rm-416.meshbench.json --nome rm-416` e então **reeditar** o JSON gerado para: `user_label` "perfil cava", `operation` reextrude com tol 0.4, `axis_remap` "cad_to_promob", `out_dir` "../out/". Assim signature e sha256 ficam corretos.

- [ ] **Step 4: Validar o exemplo de ponta a ponta**

Run: `.venv/Scripts/python -m meshbench apply examples/rm-416.meshbench.json`
Expected: `✓ saida: ...out/rm-416_saida.dxf (N faces)` com N < 120, sem avisos ⚠

- [ ] **Step 5: Escrever o README**

`README.md`:
```markdown
# MeshBench

Prepara malhas 3D exportadas de CAD (SolidWorks, Rhino, Inventor…) para uso em
software de projeto de móveis (Promob e outros): simplifica, escala, orienta,
ancora a origem e exporta DXF R12 (3DFACE).

**Princípio central: nada é automático e irreversível.** As heurísticas só
sugerem — o usuário decide o que cada peça é e o que fazer com ela.

## Instalação (desenvolvimento)

    python -m venv .venv
    .venv\Scripts\python -m pip install -e ".[dev]"

## Uso

    meshbench inspect peça.stl          # analisa: componentes, sugestões, unidade
    meshbench init peça.stl             # gera a receita peça.meshbench.json
    # ... edite a receita: operações, grupos, orientação, origem ...
    meshbench apply peça.meshbench.json # aplica e exporta (out/)
    meshbench apply peça.meshbench.json --reimport  # após reexportar do CAD

## Testes

    .venv\Scripts\python -m pytest              # suíte rápida (sintética)
    .venv\Scripts\python -m pytest -m slow      # regressão com as peças reais

A regressão usa os arquivos de `docs/peças exemplo/` (fora do git).

## Arquitetura

Ver `docs/ARQUITETURA-MESHPREP.md` — documento completo com o conhecimento de
domínio, os algoritmos validados e as armadilhas conhecidas.
```

- [ ] **Step 6: Atualizar CLAUDE.md**

Em `CLAUDE.md`, substituir o parágrafo "There is no `pyproject.toml`, build, or test setup yet…" da seção **Project status** por:

```markdown
## Commands

- Setup: `python -m venv .venv` then `.venv/Scripts/python -m pip install -e ".[dev]"`
- Tests (fast, synthetic fixtures): `.venv/Scripts/python -m pytest`
- Single test: `.venv/Scripts/python -m pytest tests/test_ops_tube.py::test_op_tube_reduz_faces -v`
- Gold regression (needs `docs/peças exemplo/`, slow): `.venv/Scripts/python -m pytest -m slow`
- CLI: `.venv/Scripts/python -m meshbench inspect|init|apply …`

Phase 1 (core engine + CLI) is implemented. Phases 2+ (FastAPI + Three.js viewport) are not yet.
```

(Manter o restante do CLAUDE.md; ajustar o primeiro parágrafo de "Project status" para dizer que a Fase 1 existe.)

- [ ] **Step 7: Rodar tudo**

Run: `.venv/Scripts/python -m pytest && .venv/Scripts/python -m pytest -m slow`
Expected: tudo verde

- [ ] **Step 8: Commit**

```bash
git add tests/test_regression_real.py examples/rm-416.meshbench.json README.md CLAUDE.md
git commit -m "test: regressão de ouro com as peças reais + receita de exemplo + docs"
```
