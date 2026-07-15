# MeshBench Fase 2 — Viewport read-only (FastAPI + Three.js) — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `meshbench serve <receita.json|malha>` sobe um servidor local e abre um viewport 3D read-only mostrando o preview fiel do resultado do pipeline: malha colorida por grupo, lista lateral de componentes, marcador de origem e orçamento de faces (critério de aceite da Fase 2, §14 do doc de arquitetura).

**Architecture:** O pipeline ganha um `process()` que retorna as malhas processadas (pós-ORIGIN) sem exportar — `run()` passa a usá-lo e a API também. Um pacote `meshbench.api` (FastAPI) expõe o estado do projeto em JSON e a geometria como **GLB** (binário, exportado pelo trimesh, decimado para exibição se passar de 200k faces). O frontend React + Vite (em `web/`, na raiz do repo) builda para `src/meshbench/api/static/`, que o FastAPI serve; em dev, o Vite proxy-a `/api` para o uvicorn.

**Tech Stack:** FastAPI + uvicorn + httpx (testes) · React 19 + Vite + Three.js (GLTFLoader, OrbitControls) + vitest · trimesh (export GLB)

## Global Constraints

- Servidor local apenas: host `127.0.0.1`, porta padrão **8765** (§9.2 do doc). Nunca `0.0.0.0`.
- Transporte de geometria: **GLB** (`model/gltf-binary`); nomes de nó `"{component_id}.{i}"` (ex.: `c0.0`) — o frontend resolve componente → grupo → cor; não depender de materiais do GLB.
- Orçamento de exibição: se o total passar de **200.000 faces**, decimar proporcionalmente só para display (o doc §13 manda; a exportação real não muda).
- Convenção visual: **Z para cima** (`camera.up = (0,0,1)`), como o Promob espera; grid no plano XY; marcador de origem = **quadrado vermelho** em (0,0,0), como o Promob mostra.
- Semáforo de faces por grupo: verde ≤ 8.000 · amarelo ≤ 15.000 · vermelho > 15.000 (limites do §3.3).
- UI em **pt-BR**; identificadores de código em inglês; docstrings pt-BR.
- Read-only: nenhuma rota de mutação nesta fase (sem POST/PATCH); upload pela UI fica para a Fase 3.
- Frontend: fonte em `web/` (raiz do repo); build para `src/meshbench/api/static/` (**gitignored**, junto com `web/node_modules/`). Testes pytest NÃO dependem do build (testes que precisam dele levam `skipif`).
- Comandos: venv Python `.venv/Scripts/python`; npm via `npm --prefix web <cmd>`.
- TDD no backend (RED real antes do GREEN); vitest para a lógica pura do frontend (palette/format). Conventional Commits.
- `docs/peças exemplo/` continua fora do git; verificação e2e usa RM-416.STL se existir, senão cena sintética.

---

### Task 1: Extrair `process()` do pipeline

**Files:**
- Modify: `src/meshbench/core/pipeline.py`
- Test: `tests/test_pipeline_process.py`

**Interfaces:**
- Consumes: tudo que `run()` já usa (nada novo).
- Produces: `ProcessedComponent` (dataclass: `component_id: str`, `label: str`, `group: str`, `mesh: trimesh.Trimesh`); `process(project, base_dir) -> tuple[list[ProcessedComponent], list[str]]` — executa IMPORT→SCALE→SPLIT→OPS→GROUP→ORIENT→ORIGIN e retorna os registros finais + warnings, **sem exportar**. `run()` passa a chamar `process()` e só faz a etapa 8 (EXPORT). `PipelineResult` e todos os testes existentes ficam intactos.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_pipeline_process.py`:
```python
import numpy as np
import trimesh

from meshbench.core.analyze.components import split_components
from meshbench.core.pipeline import ProcessedComponent, process
from meshbench.core.project import new_project


def _project(tmp_path, box, small_sphere):
    s = small_sphere.copy()
    s.apply_translation([100, 0, 0])
    scene = trimesh.util.concatenate([box, s])
    src = tmp_path / "cena.stl"
    scene.export(str(src))
    p = new_project("teste", src, scene, split_components(scene))
    p.source["path"] = "cena.stl"
    return p


def test_process_retorna_registros(tmp_path, box, small_sphere):
    p = _project(tmp_path, box, small_sphere)
    records, warnings = process(p, tmp_path)
    # esfera é weld_sphere -> remove; sobra só a caixa
    assert len(records) == 1
    r = records[0]
    assert isinstance(r, ProcessedComponent)
    assert r.group == "saida"
    assert r.component_id in {c.id for c in p.components}
    assert len(r.mesh.faces) == 12


def test_process_aplica_origem(tmp_path, box, small_sphere):
    p = _project(tmp_path, box, small_sphere)
    records, _ = process(p, tmp_path)
    assert np.allclose(records[0].mesh.bounds[0], [0, 0, 0], atol=1e-6)


def test_process_nao_exporta(tmp_path, box, small_sphere):
    p = _project(tmp_path, box, small_sphere)
    process(p, tmp_path)
    assert not (tmp_path / "out").exists()


def test_process_label(tmp_path, box, small_sphere):
    p = _project(tmp_path, box, small_sphere)
    caixa = [c for c in p.components if c.face_count == 12][0]
    caixa.user_label = "metalon"
    records, _ = process(p, tmp_path)
    assert records[0].label == "metalon"
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_process.py -v`
Expected: FAIL — `ImportError: cannot import name 'ProcessedComponent'`

- [ ] **Step 3: Refatorar pipeline.py**

Em `src/meshbench/core/pipeline.py`, adicionar o dataclass e dividir `run()`:

```python
@dataclass
class ProcessedComponent:
    """Uma instância de peça já processada (pós-ops, pós-orientação, pós-origem)."""

    component_id: str
    label: str
    group: str
    mesh: object  # trimesh.Trimesh


def process(project, base_dir):
    """Executa as etapas 1-7 do pipeline e retorna (registros, warnings), sem exportar."""
    ...


def run(project, base_dir):
    """Executa a receita completa e exporta um arquivo por grupo."""
    records, warnings = process(project, base_dir)
    ...
```

Mover para `process()` TODO o corpo atual de `run()` até (inclusive) a etapa 7 (ORIGIN), com estas adaptações mecânicas:
1. No loop de OPS, em vez de `grouped[entry.group].extend(processed)`, criar registros: `records.append(ProcessedComponent(component_id=entry.id, label=entry.user_label or entry.auto_class, group=entry.group, mesh=m))` para cada `m` em `processed` (mantendo `feature_meshes[entry.id] = processed` como está).
2. Na etapa 6 (ORIENT), aplicar `apply_orient` ao `mesh` de cada registro (recriando os registros com `dataclasses.replace(r, mesh=apply_orient(r.mesh, project.orient))`).
3. Na etapa 7 (ORIGIN), montar `grouped = {g: [r.mesh for r in records if r.group == g] ...}` na ordem dos registros, chamar `place_origin` como hoje, e re-associar as malhas transladadas aos registros na mesma ordem (zip por grupo). Preservar o guard `if grouped:`.
4. `process()` retorna `(records, warnings)`.

`run()` vira: chamar `process()`, agrupar `records` por grupo (dict ordenado por ordem de aparição) e executar a etapa 8 (EXPORT) exatamente como hoje (naming, formato, face budget warning), retornando `PipelineResult`.

Importar `replace` de `dataclasses` no topo se ainda não estiver.

- [ ] **Step 4: Rodar os novos testes E a suíte inteira**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_process.py tests/test_pipeline.py -v && .venv/Scripts/python -m pytest -q`
Expected: novos testes passam; os 7 testes existentes de `test_pipeline.py` continuam passando sem nenhuma alteração neles; suíte toda verde.

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/core/pipeline.py tests/test_pipeline_process.py
git commit -m "refactor: extrai process() do pipeline para reuso pela API"
```

---

### Task 2: Geometria para o viewport (`api/geometry.py` — GLB + orçamento de exibição)

**Files:**
- Create: `src/meshbench/api/__init__.py` (vazio)
- Create: `src/meshbench/api/geometry.py`
- Test: `tests/test_api_geometry.py`

**Interfaces:**
- Consumes: `ProcessedComponent` (Task 1).
- Produces: `DISPLAY_BUDGET = 200_000`; `display_records(records, budget=DISPLAY_BUDGET) -> list[ProcessedComponent]` (decima proporcionalmente para exibição quando o total passa do orçamento; malhas originais intactas); `build_scene_glb(records) -> bytes` (GLB com um nó por instância, nome `"{component_id}.{i}"`).

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_api_geometry.py`:
```python
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
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_api_geometry.py -v`
Expected: FAIL — módulo `meshbench.api.geometry` não existe

- [ ] **Step 3: Implementar**

`src/meshbench/api/geometry.py`:
```python
"""Prepara a geometria processada para o viewport: GLB + orçamento de exibição.

O doc de arquitetura (§13) manda enviar uma versão decimada quando o viewport
receberia mais de ~200k triângulos — a exportação real nunca é afetada.
"""

from dataclasses import replace

import trimesh

DISPLAY_BUDGET = 200_000


def display_records(records, budget=DISPLAY_BUDGET):
    """Decima proporcionalmente para exibição se o total passar do orçamento."""
    total = sum(len(r.mesh.faces) for r in records)
    if total <= budget:
        return records
    ratio = budget / total
    out = []
    for r in records:
        target = max(100, int(len(r.mesh.faces) * ratio))
        try:
            m = r.mesh.simplify_quadric_decimation(face_count=target)
        except Exception:
            m = r.mesh  # exibir cheio é melhor que não exibir
        out.append(replace(r, mesh=m))
    return out


def build_scene_glb(records):
    """Monta um GLB com um nó por instância; nome do nó = '{component_id}.{i}'.

    O frontend usa o nome para mapear componente -> grupo -> cor; não dependemos
    de materiais do GLB.
    """
    scene = trimesh.Scene()
    for i, r in enumerate(records):
        name = f"{r.component_id}.{i}"
        scene.add_geometry(r.mesh, node_name=name, geom_name=name)
    return scene.export(file_type="glb")
```

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_api_geometry.py -v`
Expected: 3 passed. Se o roundtrip de nomes falhar porque o trimesh renomeou nós duplicados, os nomes já são únicos por construção — investigar antes de mexer.

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/api/__init__.py src/meshbench/api/geometry.py tests/test_api_geometry.py
git commit -m "feat: geometria GLB para o viewport com orçamento de exibição"
```

---

### Task 3: Servidor FastAPI (`api/server.py`)

**Files:**
- Modify: `pyproject.toml` (deps: `fastapi`, `uvicorn`; dev: `httpx`)
- Create: `src/meshbench/api/server.py`
- Test: `tests/test_api_server.py`

**Interfaces:**
- Consumes: `process` (Task 1); `build_scene_glb`, `display_records` (Task 2); `Project`, `new_project`, `read_mesh`, `split_components`, `FACE_BUDGET`.
- Produces: `ProjectSession` (dataclass: `project`, `base_dir`, `records`, `warnings`); `load_session(path) -> ProjectSession` (aceita `.meshbench.json` OU arquivo de malha — neste caso monta um projeto virtual via `new_project` sem salvar); `create_app(session) -> FastAPI` com `GET /api/project` (estado JSON) e `GET /api/project/geometry` (GLB); monta estático de `STATIC_DIR` se existir, senão `GET /` responde dica de build.

- [ ] **Step 1: Adicionar dependências**

Em `pyproject.toml`, acrescentar a `dependencies`: `"fastapi>=0.110"`, `"uvicorn>=0.30"`; e a `dev`: `"httpx>=0.27"`. Instalar:

Run: `.venv/Scripts/python -m pip install -e ".[dev]"`
Expected: instala fastapi/uvicorn/httpx sem erro.

- [ ] **Step 2: Escrever os testes que falham**

`tests/test_api_server.py`:
```python
import trimesh
from fastapi.testclient import TestClient

from meshbench.core.analyze.components import split_components
from meshbench.core.project import new_project
from meshbench.api import server
from meshbench.api.server import create_app, load_session


def _stl(tmp_path, box, small_sphere):
    s = small_sphere.copy()
    s.apply_translation([100, 0, 0])
    scene = trimesh.util.concatenate([box, s])
    p = tmp_path / "cena.stl"
    scene.export(str(p))
    return p


def _client(tmp_path, box, small_sphere):
    session = load_session(_stl(tmp_path, box, small_sphere))
    return TestClient(create_app(session))


def test_load_session_de_malha(tmp_path, box, small_sphere):
    session = load_session(_stl(tmp_path, box, small_sphere))
    assert session.project.name == "cena"
    assert len(session.project.components) == 2
    assert len(session.records) == 1  # esfera sugerida como remove


def test_load_session_de_receita(tmp_path, box, small_sphere):
    src = _stl(tmp_path, box, small_sphere)
    mesh = trimesh.load(str(src), force="mesh")
    p = new_project("cena", src, mesh, split_components(mesh))
    p.source["path"] = "cena.stl"
    recipe = tmp_path / "cena.meshbench.json"
    p.save(recipe)
    session = load_session(recipe)
    assert session.project.name == "cena"


def test_get_project_estado(tmp_path, box, small_sphere):
    client = _client(tmp_path, box, small_sphere)
    r = client.get("/api/project")
    assert r.status_code == 200
    d = r.json()
    assert d["name"] == "cena"
    assert len(d["components"]) == 2
    assert d["groups"] == [{"name": "saida", "role": "fixed"}]
    assert d["group_faces"] == {"saida": 12}
    assert d["face_budget"] == 15000
    assert len(d["dims_mm"]) == 3


def test_get_geometry_glb(tmp_path, box, small_sphere):
    client = _client(tmp_path, box, small_sphere)
    r = client.get("/api/project/geometry")
    assert r.status_code == 200
    assert r.headers["content-type"] == "model/gltf-binary"
    assert r.content[:4] == b"glTF"


def test_raiz_sem_build_da_dica(tmp_path, box, small_sphere, monkeypatch):
    monkeypatch.setattr(server, "STATIC_DIR", tmp_path / "nao_existe")
    client = _client(tmp_path, box, small_sphere)
    r = client.get("/")
    assert r.status_code == 200
    assert "npm" in r.json()["detail"]
```

- [ ] **Step 3: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_api_server.py -v`
Expected: FAIL — módulo `meshbench.api.server` não existe

- [ ] **Step 4: Implementar**

`src/meshbench/api/server.py`:
```python
"""Servidor local do MeshBench. Fase 2: viewport READ-ONLY (nenhuma rota de mutação)."""

from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np
from fastapi import FastAPI
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from meshbench.api.geometry import build_scene_glb, display_records
from meshbench.core.analyze.components import split_components
from meshbench.core.io.readers import read_mesh
from meshbench.core.pipeline import FACE_BUDGET, process
from meshbench.core.project import Project, new_project

STATIC_DIR = Path(__file__).parent / "static"


@dataclass
class ProjectSession:
    """Um projeto carregado em memória (um por servidor, conforme §13)."""

    project: Project
    base_dir: Path
    records: list
    warnings: list = field(default_factory=list)


def load_session(path):
    """Carrega uma receita .meshbench.json OU um arquivo de malha (projeto virtual)."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        project = Project.load(path)
    else:
        mesh = read_mesh(path)
        project = new_project(path.stem, path, mesh, split_components(mesh))
        project.source["path"] = path.name
    base_dir = path.resolve().parent
    records, warnings = process(project, base_dir)
    return ProjectSession(
        project=project, base_dir=base_dir, records=records, warnings=warnings
    )


def _project_state(session):
    totals = {}
    for r in session.records:
        totals[r.group] = totals.get(r.group, 0) + len(r.mesh.faces)
    dims = None
    if session.records:
        pts = np.vstack([r.mesh.bounds for r in session.records])
        dims = (pts.max(axis=0) - pts.min(axis=0)).tolist()
    return {
        "name": session.project.name,
        "source": session.project.source,
        "scale": session.project.scale,
        "groups": session.project.groups,
        "components": [asdict(c) for c in session.project.components],
        "warnings": session.warnings,
        "group_faces": totals,
        "face_budget": FACE_BUDGET,
        "dims_mm": dims,
    }


def create_app(session):
    app = FastAPI(title="MeshBench")

    @app.get("/api/project")
    def get_project():
        return JSONResponse(_project_state(session))

    @app.get("/api/project/geometry")
    def get_geometry():
        glb = build_scene_glb(display_records(session.records))
        return Response(content=glb, media_type="model/gltf-binary")

    if STATIC_DIR.exists():
        app.mount("/", StaticFiles(directory=str(STATIC_DIR), html=True), name="static")
    else:

        @app.get("/")
        def index_hint():
            return JSONResponse(
                {
                    "detail": "frontend não buildado — rode: "
                    "npm --prefix web install && npm --prefix web run build"
                }
            )

    return app
```

**Nota:** `monkeypatch.setattr(server, "STATIC_DIR", ...)` exige que `create_app` leia `STATIC_DIR` no momento da chamada (como acima) — não capturar em default de parâmetro.

- [ ] **Step 5: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_api_server.py -v && .venv/Scripts/python -m pytest -q`
Expected: 6 passed; suíte toda verde.

- [ ] **Step 6: Commit**

```bash
git add pyproject.toml src/meshbench/api/server.py tests/test_api_server.py
git commit -m "feat: servidor FastAPI read-only (estado do projeto + geometria GLB)"
```

---

### Task 4: Subcomando `meshbench serve`

**Files:**
- Modify: `src/meshbench/cli.py`
- Test: `tests/test_cli_serve.py`

**Interfaces:**
- Consumes: `load_session`, `create_app` (Task 3).
- Produces: `meshbench serve ALVO [--port 8765] [--no-browser]` — carrega a sessão, imprime a URL, abre o navegador (a menos de `--no-browser`) e roda uvicorn em `127.0.0.1`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_cli_serve.py`:
```python
import trimesh

from meshbench.cli import main


def _stl(tmp_path, box):
    p = tmp_path / "peca.stl"
    box.export(str(p))
    return p


def test_serve_monta_app_e_roda_uvicorn(tmp_path, box, monkeypatch, capsys):
    captured = {}

    def fake_run(app, **kwargs):
        captured["app"] = app
        captured["kwargs"] = kwargs

    monkeypatch.setattr("uvicorn.run", fake_run)
    aberturas = []
    monkeypatch.setattr("webbrowser.open", lambda url: aberturas.append(url))

    rc = main(["serve", str(_stl(tmp_path, box)), "--no-browser", "--port", "8770"])
    assert rc == 0
    assert captured["kwargs"]["host"] == "127.0.0.1"
    assert captured["kwargs"]["port"] == 8770
    paths = {r.path for r in captured["app"].routes}
    assert "/api/project" in paths and "/api/project/geometry" in paths
    assert aberturas == []  # --no-browser
    assert "http://127.0.0.1:8770" in capsys.readouterr().out


def test_serve_abre_navegador_por_padrao(tmp_path, box, monkeypatch):
    monkeypatch.setattr("uvicorn.run", lambda app, **k: None)
    aberturas = []
    # o timer dispara webbrowser.open depois; interceptamos o próprio Timer
    import threading

    class FakeTimer:
        def __init__(self, delay, fn, args=()):
            self.fn, self.args = fn, args

        def start(self):
            self.fn(*self.args)

    monkeypatch.setattr(threading, "Timer", FakeTimer)
    monkeypatch.setattr("webbrowser.open", lambda url: aberturas.append(url))
    main(["serve", str(_stl(tmp_path, box))])
    assert aberturas == ["http://127.0.0.1:8765"]


def test_serve_arquivo_inexistente_erro_amigavel(capsys):
    rc = main(["serve", "nao_existe.stl"])
    assert rc == 1
    assert "erro:" in capsys.readouterr().out
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_cli_serve.py -v`
Expected: FAIL — argparse: `invalid choice: 'serve'`

- [ ] **Step 3: Implementar**

Em `src/meshbench/cli.py`, adicionar (imports `threading`/`webbrowser`/`uvicorn` são tardios, dentro da função, para a CLI básica não pagar o custo):

```python
def _cmd_serve(args):
    import threading
    import webbrowser

    import uvicorn

    from meshbench.api.server import create_app, load_session

    session = load_session(args.alvo)
    app = create_app(session)
    url = f"http://127.0.0.1:{args.port}"
    print(f"MeshBench em {url} — Ctrl+C para sair")
    if not args.no_browser:
        threading.Timer(1.0, webbrowser.open, args=(url,)).start()
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    return 0
```

E no `main()`, junto dos outros subparsers:

```python
    p_serve = sub.add_parser("serve", help="abre o viewport 3D read-only no navegador")
    p_serve.add_argument("alvo", help="receita .meshbench.json ou arquivo de malha")
    p_serve.add_argument("--port", type=int, default=8765)
    p_serve.add_argument("--no-browser", action="store_true", help="não abrir o navegador")
    p_serve.set_defaults(fn=_cmd_serve)
```

O handler de erros existente (`FileNotFoundError, ValueError` → `erro: …`, rc 1) já cobre o alvo inexistente.

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_cli_serve.py tests/test_cli.py -v`
Expected: todos passam (CLI existente sem regressão)

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/cli.py tests/test_cli_serve.py
git commit -m "feat: subcomando serve (uvicorn local + navegador)"
```

---

### Task 5: Scaffold do frontend (Vite + React) e lógica pura testada

**Files:**
- Create: `web/package.json`
- Create: `web/vite.config.js`
- Create: `web/index.html`
- Create: `web/src/main.jsx`
- Create: `web/src/App.jsx`
- Create: `web/src/styles.css`
- Create: `web/src/lib/palette.js`
- Create: `web/src/lib/format.js`
- Test: `web/src/lib/palette.test.js`, `web/src/lib/format.test.js`
- Test: `tests/test_api_static.py`
- Modify: `.gitignore`

**Interfaces:**
- Consumes: `GET /api/project` (Task 3).
- Produces: `groupColor(groupName, groupNames) -> "#rrggbb"` (determinística); `formatFaces(n)` (pt-BR: `4978 → "4.978"`); `formatDims(dims)` (`"450.0 × 234.0 × 457.3 mm"` ou `"—"`); `budgetLevel(faces) -> "verde"|"amarelo"|"vermelho"`; `App` busca `/api/project` e renderiza `Sidebar` + `Viewport` + `StatusBar` (componentes criados nas Tasks 6–7 — nesta task, placeholders mínimos). Build para `src/meshbench/api/static/`.

- [ ] **Step 1: Criar o projeto npm**

`web/package.json`:
```json
{
  "name": "meshbench-web",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "test": "vitest run"
  },
  "dependencies": {
    "react": "^19.0.0",
    "react-dom": "^19.0.0",
    "three": "^0.182.0"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^5.0.0",
    "vite": "^7.0.0",
    "vitest": "^3.0.0"
  }
}
```

`web/vite.config.js`:
```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: {
    proxy: { "/api": "http://127.0.0.1:8765" },
  },
  build: {
    outDir: "../src/meshbench/api/static",
    emptyOutDir: true,
  },
  test: { environment: "node" },
});
```

Adicionar ao `.gitignore`:
```gitignore
web/node_modules/
src/meshbench/api/static/
```

Run: `npm --prefix web install`
Expected: instala sem erro (Node 24 local).

- [ ] **Step 2: Escrever os testes vitest que falham**

`web/src/lib/palette.test.js`:
```js
import { describe, expect, it } from "vitest";
import { GROUP_COLORS, groupColor } from "./palette.js";

describe("groupColor", () => {
  it("é determinística pela ordem dos grupos", () => {
    const groups = ["fixa", "movel"];
    expect(groupColor("fixa", groups)).toBe(GROUP_COLORS[0]);
    expect(groupColor("movel", groups)).toBe(GROUP_COLORS[1]);
  });
  it("grupo desconhecido cai na primeira cor", () => {
    expect(groupColor("fantasma", ["a"])).toBe(GROUP_COLORS[0]);
  });
  it("dá a volta quando há mais grupos que cores", () => {
    const groups = Array.from({ length: GROUP_COLORS.length + 1 }, (_, i) => `g${i}`);
    expect(groupColor(`g${GROUP_COLORS.length}`, groups)).toBe(GROUP_COLORS[0]);
  });
});
```

`web/src/lib/format.test.js`:
```js
import { describe, expect, it } from "vitest";
import { budgetLevel, formatDims, formatFaces } from "./format.js";

describe("formatFaces", () => {
  it("usa separador de milhar pt-BR", () => {
    expect(formatFaces(4978)).toBe("4.978");
  });
});

describe("formatDims", () => {
  it("formata mm com 1 casa", () => {
    expect(formatDims([450, 234, 457.31])).toBe("450.0 × 234.0 × 457.3 mm");
  });
  it("null vira travessão", () => {
    expect(formatDims(null)).toBe("—");
  });
});

describe("budgetLevel", () => {
  it("verde até 8k, amarelo até 15k, vermelho acima", () => {
    expect(budgetLevel(2000)).toBe("verde");
    expect(budgetLevel(12000)).toBe("amarelo");
    expect(budgetLevel(15001)).toBe("vermelho");
  });
});
```

Run: `npm --prefix web test`
Expected: FAIL — módulos não existem

- [ ] **Step 3: Implementar a lógica pura**

`web/src/lib/palette.js`:
```js
// Cores por grupo — determinísticas pela ordem de declaração dos grupos na receita.
export const GROUP_COLORS = [
  "#4e79a7",
  "#f28e2b",
  "#59a14f",
  "#e15759",
  "#b07aa1",
  "#76b7b2",
  "#edc948",
  "#ff9da7",
];

export function groupColor(groupName, groupNames) {
  const i = groupNames.indexOf(groupName);
  return GROUP_COLORS[(i >= 0 ? i : 0) % GROUP_COLORS.length];
}
```

`web/src/lib/format.js`:
```js
export function formatFaces(n) {
  return n.toLocaleString("pt-BR");
}

export function formatDims(dims) {
  if (!dims) return "—";
  return `${dims[0].toFixed(1)} × ${dims[1].toFixed(1)} × ${dims[2].toFixed(1)} mm`;
}

// Semáforo do orçamento de faces (§3.3): verde ≤8k, amarelo ≤15k, vermelho >15k.
export function budgetLevel(faces) {
  if (faces > 15000) return "vermelho";
  if (faces > 8000) return "amarelo";
  return "verde";
}
```

Run: `npm --prefix web test`
Expected: todos passam

- [ ] **Step 4: Criar casca do app**

`web/index.html`:
```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>MeshBench</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

`web/src/main.jsx`:
```jsx
import React from "react";
import { createRoot } from "react-dom/client";
import App from "./App.jsx";
import "./styles.css";

createRoot(document.getElementById("root")).render(<App />);
```

`web/src/App.jsx` (Viewport/Sidebar/StatusBar chegam nas Tasks 6–7; por ora placeholders inline para o build passar):
```jsx
import { useEffect, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import StatusBar from "./components/StatusBar.jsx";
import Viewport from "./components/Viewport.jsx";

export default function App() {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetch("/api/project")
      .then((r) => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.json();
      })
      .then(setState)
      .catch((e) => setError(String(e)));
  }, []);

  if (error) return <div className="tela-aviso">Erro ao carregar o projeto: {error}</div>;
  if (!state) return <div className="tela-aviso">Carregando…</div>;
  return (
    <div className="app">
      <Sidebar state={state} />
      <main className="viewport-wrap">
        <Viewport state={state} />
      </main>
      <StatusBar state={state} />
    </div>
  );
}
```

Criar placeholders mínimos (serão substituídos nas Tasks 6–7):

`web/src/components/Viewport.jsx`:
```jsx
export default function Viewport() {
  return <div className="viewport" />;
}
```

`web/src/components/Sidebar.jsx`:
```jsx
export default function Sidebar({ state }) {
  return <aside className="sidebar">{state.name}</aside>;
}
```

`web/src/components/StatusBar.jsx`:
```jsx
export default function StatusBar() {
  return <footer className="statusbar" />;
}
```

`web/src/styles.css`:
```css
* { margin: 0; padding: 0; box-sizing: border-box; }
html, body, #root { height: 100%; }
body { font-family: system-ui, sans-serif; background: #16161a; color: #e8e8ec; }

.app {
  display: grid;
  grid-template-columns: 300px 1fr;
  grid-template-rows: 1fr auto;
  grid-template-areas: "sidebar viewport" "sidebar statusbar";
  height: 100%;
}
.sidebar { grid-area: sidebar; overflow-y: auto; background: #1e1e24; padding: 12px; border-right: 1px solid #2c2c34; }
.viewport-wrap { grid-area: viewport; position: relative; min-width: 0; min-height: 0; }
.viewport { position: absolute; inset: 0; }
.statusbar { grid-area: statusbar; background: #1e1e24; border-top: 1px solid #2c2c34; padding: 10px 14px; display: flex; gap: 24px; align-items: center; flex-wrap: wrap; }
.tela-aviso { display: grid; place-items: center; height: 100%; font-size: 1.1rem; }

.sidebar h2 { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; color: #9a9aa5; margin: 14px 0 6px; }
.familia { display: flex; align-items: center; gap: 8px; padding: 5px 6px; border-radius: 6px; font-size: 0.88rem; }
.familia .cor { width: 10px; height: 10px; border-radius: 3px; flex: none; }
.familia .op { margin-left: auto; font-size: 0.72rem; color: #9a9aa5; }
.familia.removida { opacity: 0.45; }
.familia .alerta { color: #f2b84b; }

.dims { font-size: 1.05rem; font-weight: 600; }
.budget { display: flex; align-items: center; gap: 6px; font-size: 0.85rem; }
.budget .luz { width: 10px; height: 10px; border-radius: 50%; }
.luz.verde { background: #4caf50; }
.luz.amarelo { background: #f2b84b; }
.luz.vermelho { background: #e15759; }
.avisos { font-size: 0.8rem; color: #f2b84b; }
```

- [ ] **Step 5: Buildar e testar o serviço do estático**

Run: `npm --prefix web run build`
Expected: gera `src/meshbench/api/static/index.html` + assets.

`tests/test_api_static.py`:
```python
import pytest
import trimesh
from fastapi.testclient import TestClient

from meshbench.api.server import STATIC_DIR, create_app, load_session


@pytest.mark.skipif(not STATIC_DIR.exists(), reason="frontend não buildado")
def test_raiz_serve_index(tmp_path, box):
    p = tmp_path / "peca.stl"
    box.export(str(p))
    client = TestClient(create_app(load_session(p)))
    r = client.get("/")
    assert r.status_code == 200
    assert "text/html" in r.headers["content-type"]
    assert "MeshBench" in r.text
```

Run: `.venv/Scripts/python -m pytest tests/test_api_static.py -v && .venv/Scripts/python -m pytest -q && npm --prefix web test`
Expected: tudo verde.

- [ ] **Step 6: Commit**

```bash
git add web .gitignore tests/test_api_static.py
git commit -m "feat: scaffold do frontend React+Vite com paleta e formatação testadas"
```

---

### Task 6: Viewport Three.js (malha colorida, origem, câmera Z-up)

**Files:**
- Modify: `web/src/components/Viewport.jsx` (substituir o placeholder)

**Interfaces:**
- Consumes: `GET /api/project/geometry` (GLB, nós `"{component_id}.{i}"`); `state.components[].{id,group}`; `state.groups[].name`; `groupColor` (Task 5).
- Produces: viewport com: GLB carregado, cor por grupo, `camera.up=(0,0,1)` (Z para cima, como o Promob), grid no plano XY dimensionado pelo bbox, `AxesHelper`, marcador de origem (quadrado vermelho em (0,0,0)), `OrbitControls`, câmera enquadrando a cena, resize automático.

- [ ] **Step 1: Implementar o Viewport**

`web/src/components/Viewport.jsx`:
```jsx
import { useEffect, useRef } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { groupColor } from "../lib/palette.js";

export default function Viewport({ state }) {
  const mountRef = useRef(null);

  useEffect(() => {
    const mount = mountRef.current;
    const scene = new THREE.Scene();
    scene.background = new THREE.Color(0x16161a);

    const camera = new THREE.PerspectiveCamera(
      50,
      mount.clientWidth / mount.clientHeight,
      1,
      100000,
    );
    camera.up.set(0, 0, 1); // convenção do domínio: Z = altura (Promob)

    const renderer = new THREE.WebGLRenderer({ antialias: true });
    renderer.setSize(mount.clientWidth, mount.clientHeight);
    mount.appendChild(renderer.domElement);

    const controls = new OrbitControls(camera, renderer.domElement);

    scene.add(new THREE.HemisphereLight(0xffffff, 0x444455, 1.1));
    const dir = new THREE.DirectionalLight(0xffffff, 1.6);
    dir.position.set(1, -2, 3);
    scene.add(dir);

    const groupNames = state.groups.map((g) => g.name);
    const groupOf = {};
    for (const c of state.components) groupOf[c.id] = c.group;

    new GLTFLoader().load("/api/project/geometry", (gltf) => {
      gltf.scene.traverse((obj) => {
        if (obj.isMesh) {
          const compId = obj.name.split(".")[0];
          obj.material = new THREE.MeshStandardMaterial({
            color: groupColor(groupOf[compId], groupNames),
            metalness: 0.1,
            roughness: 0.75,
            side: THREE.DoubleSide,
          });
        }
      });
      scene.add(gltf.scene);

      const box = new THREE.Box3().setFromObject(gltf.scene);
      const size = box.getSize(new THREE.Vector3());
      const center = box.getCenter(new THREE.Vector3());
      const radius = Math.max(size.x, size.y, size.z, 1);

      // grid no plano XY (chão da convenção Z-up)
      const grid = new THREE.GridHelper(radius * 3, 30, 0x3a3a46, 0x26262e);
      grid.rotation.x = Math.PI / 2; // GridHelper nasce em XZ; deitar para XY
      scene.add(grid);

      // marcador de origem: quadrado vermelho em (0,0,0), como o Promob mostra
      const marker = new THREE.Mesh(
        new THREE.PlaneGeometry(radius * 0.04, radius * 0.04),
        new THREE.MeshBasicMaterial({
          color: 0xff2222,
          side: THREE.DoubleSide,
          depthTest: false,
        }),
      );
      marker.renderOrder = 999;
      scene.add(marker);

      scene.add(new THREE.AxesHelper(radius * 0.5));

      camera.position.set(
        center.x + radius * 1.2,
        center.y - radius * 1.2,
        center.z + radius * 0.9,
      );
      controls.target.copy(center);
      controls.update();
    });

    let frame;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      controls.update();
      renderer.render(scene, camera);
    };
    animate();

    const onResize = () => {
      camera.aspect = mount.clientWidth / mount.clientHeight;
      camera.updateProjectionMatrix();
      renderer.setSize(mount.clientWidth, mount.clientHeight);
    };
    const ro = new ResizeObserver(onResize);
    ro.observe(mount);

    return () => {
      cancelAnimationFrame(frame);
      ro.disconnect();
      controls.dispose();
      renderer.dispose();
      mount.removeChild(renderer.domElement);
    };
  }, [state]);

  return <div className="viewport" ref={mountRef} />;
}
```

- [ ] **Step 2: Buildar e verificar sem regressão**

Run: `npm --prefix web run build && npm --prefix web test && .venv/Scripts/python -m pytest -q`
Expected: build ok; tudo verde.

- [ ] **Step 3: Fumaça visual**

Run (em background): `.venv/Scripts/python -m meshbench serve <caminho de um STL de teste — usar "docs/peças exemplo/RM-416.STL" se existir, senão exportar a fixture box num tmp> --no-browser`
Abrir `http://127.0.0.1:8765` no browser de preview e conferir: malha visível, colorida, grid, eixos, quadrado vermelho na origem, órbita com o mouse funciona. Encerrar o servidor.

- [ ] **Step 4: Commit**

```bash
git add web/src/components/Viewport.jsx
git commit -m "feat: viewport three.js com cores por grupo, origem e camera Z-up"
```

---

### Task 7: Lista lateral e barra de status

**Files:**
- Modify: `web/src/components/Sidebar.jsx` (substituir o placeholder)
- Modify: `web/src/components/StatusBar.jsx` (substituir o placeholder)

**Interfaces:**
- Consumes: `state.{name,components,groups,warnings,group_faces,face_budget,dims_mm}`; `groupColor`, `formatFaces`, `formatDims`, `budgetLevel` (Task 5).
- Produces: Sidebar com seções por grupo (linha "12× haste (4.978 f cada)" com bolinha de cor e badge da operação), seção "Removidas" e "Sem grupo ⚠" (needs_review com ⚠); StatusBar com dimensões em mm grandes, semáforo por grupo e avisos.

- [ ] **Step 1: Implementar Sidebar**

`web/src/components/Sidebar.jsx`:
```jsx
import { formatFaces } from "../lib/format.js";
import { groupColor } from "../lib/palette.js";

function Familia({ c, cor, removida }) {
  const label = c.user_label || c.auto_class;
  return (
    <div className={"familia" + (removida ? " removida" : "")}>
      <span className="cor" style={{ background: cor }} />
      <span>
        {c.instances}× {label} ({formatFaces(c.face_count)} f cada)
        {c.needs_review ? <span className="alerta"> ⚠ novo — revisar</span> : null}
      </span>
      <span className="op">{c.operation.type}</span>
    </div>
  );
}

export default function Sidebar({ state }) {
  const groupNames = state.groups.map((g) => g.name);
  const porGrupo = new Map(groupNames.map((n) => [n, []]));
  const removidas = [];
  const semGrupo = [];
  for (const c of state.components) {
    if (c.operation.type === "remove") removidas.push(c);
    else if (c.group && porGrupo.has(c.group)) porGrupo.get(c.group).push(c);
    else semGrupo.push(c);
  }

  return (
    <aside className="sidebar">
      <h1 style={{ fontSize: "1rem" }}>{state.name}</h1>
      {groupNames.map((g) => (
        <section key={g}>
          <h2>▸ {g}</h2>
          {porGrupo.get(g).map((c) => (
            <Familia key={c.id} c={c} cor={groupColor(g, groupNames)} />
          ))}
        </section>
      ))}
      {semGrupo.length > 0 && (
        <section>
          <h2>▸ sem grupo ⚠</h2>
          {semGrupo.map((c) => (
            <Familia key={c.id} c={c} cor="#666" />
          ))}
        </section>
      )}
      {removidas.length > 0 && (
        <section>
          <h2>▸ removidas</h2>
          {removidas.map((c) => (
            <Familia key={c.id} c={c} cor="#666" removida />
          ))}
        </section>
      )}
    </aside>
  );
}
```

- [ ] **Step 2: Implementar StatusBar**

`web/src/components/StatusBar.jsx`:
```jsx
import { budgetLevel, formatDims, formatFaces } from "../lib/format.js";

export default function StatusBar({ state }) {
  return (
    <footer className="statusbar">
      <span className="dims">{formatDims(state.dims_mm)}</span>
      {Object.entries(state.group_faces).map(([g, faces]) => (
        <span key={g} className="budget">
          <span className={"luz " + budgetLevel(faces)} />
          {g}: {formatFaces(faces)} f
        </span>
      ))}
      {state.warnings.length > 0 && (
        <span className="avisos">
          {state.warnings.map((w, i) => (
            <div key={i}>⚠ {w}</div>
          ))}
        </span>
      )}
    </footer>
  );
}
```

- [ ] **Step 3: Buildar e verificar**

Run: `npm --prefix web run build && npm --prefix web test && .venv/Scripts/python -m pytest -q`
Expected: tudo verde.

- [ ] **Step 4: Fumaça visual**

Servir de novo (como na Task 6 Step 3) e conferir: lista lateral com grupos/instâncias/faces/ops, badge ⚠ quando houver, dimensões em mm na barra, semáforo verde/amarelo/vermelho coerente com `group_faces`, avisos exibidos. Encerrar o servidor.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/Sidebar.jsx web/src/components/StatusBar.jsx
git commit -m "feat: lista lateral de componentes e barra de status com semaforo"
```

---

### Task 8: Verificação e2e com peça real + documentação

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

**Interfaces:**
- Consumes: tudo.

- [ ] **Step 1: Verificação e2e com a peça real**

1. `npm --prefix web run build`
2. Se `docs/peças exemplo/RM-416.STL` existir: `.venv/Scripts/python -m meshbench serve "docs/peças exemplo/RM-416.STL" --no-browser` (em background). Senão, gerar um STL sintético (duas caixas) num tmp e servi-lo.
3. Abrir `http://127.0.0.1:8765` no browser de preview e validar o critério de aceite da Fase 2 (§14): **malha aparece** · **componentes coloridos** · **lista lateral** · **marcador de origem visível**. Tirar screenshot como evidência no relatório.
4. Conferir também `GET /api/project` no browser (JSON coerente) e o console do browser sem erros.
5. Encerrar o servidor.

- [ ] **Step 2: Atualizar README.md**

Acrescentar ao `README.md`, depois da seção "Uso":

```markdown
## Viewport 3D (Fase 2)

    meshbench serve peça.stl              # abre o preview 3D no navegador
    meshbench serve receita.meshbench.json

Read-only nesta fase: o viewport mostra o resultado do pipeline (cores por
grupo, origem, orçamento de faces). Edição interativa vem nas próximas fases.

### Desenvolvimento do frontend

    npm --prefix web install
    npm --prefix web run build   # builda para src/meshbench/api/static/
    npm --prefix web run dev     # dev server com proxy para :8765
    npm --prefix web test        # vitest
```

- [ ] **Step 3: Atualizar CLAUDE.md**

Na seção **Commands**, acrescentar:
```markdown
- Viewport (fase 2): `.venv/Scripts/python -m meshbench serve <arquivo>` (porta 8765)
- Frontend: `npm --prefix web install|run build|run dev|test` (build vai para `src/meshbench/api/static/`, gitignored)
```
E trocar a linha "Phase 1 (core engine + CLI) is implemented. Phases 2+ (FastAPI + Three.js viewport) are not yet." por "Phases 1 (core+CLI) and 2 (read-only viewport: FastAPI + React/Three.js in `web/`) are implemented. Phases 3+ (selection, interactive ops, gizmos) are not yet."

- [ ] **Step 4: Rodar tudo**

Run: `.venv/Scripts/python -m pytest -q && npm --prefix web test`
Expected: tudo verde (regressão de ouro `-m slow` não é necessária — o core não mudou de comportamento; rodar apenas se a Task 1 tiver alterado algo além do refactor).

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: fase 2 — viewport read-only documentado"
```
