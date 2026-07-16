# MeshBench Fase 3 — Seleção + Operações Interativas + Preview — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformar o viewport read-only da Fase 2 em editor: clicar numa peça (viewport ou lista), atribuir operação/grupo/rótulo num painel inspetor, ver a contagem de faces ao vivo, pré-visualizar antes/depois e salvar a receita — critério de aceite da Fase 3 (§14 do doc de arquitetura).

**Architecture:** O backend ganha mutações de sessão (`api/session_ops.py`): PATCH de componente reprocessa o pipeline em memória (com a malha crua em cache — nunca relê o arquivo fonte), preview reprocessa um clone do projeto sem tocar na sessão, e salvar grava a receita explicitamente. O frontend ganha estado de seleção (uma família por vez — clicar seleciona as N instâncias idênticas juntas, §11.2), raycast no viewport, painel `Inspector` com formulários de parâmetros por operação, e overlay de preview antes/depois.

**Tech Stack:** FastAPI (rotas PATCH/POST) · trimesh · React 19 + Three.js 0.182 (Raycaster) · vitest · pytest

## Global Constraints

- Branch: `fase-3-selecao` criado a partir da `main`.
- **Nada é automático e irreversível**: toda mutação é ação explícita do usuário (botões "Aplicar" e "Salvar receita"); preview NUNCA altera a sessão; salvar NUNCA acontece sozinho.
- **Reprocesso jamais relê o arquivo fonte** — a malha crua fica em cache na sessão (`raw_mesh`); DXFs reais têm até 99 MB e levam minutos para ler.
- Servidor continua **local-only (127.0.0.1)**; um projeto por sessão; mutações protegidas por `threading.Lock` (FastAPI roda handlers sync em threadpool).
- Selecionar uma família = selecionar as N instâncias idênticas juntas (§11.2 — "12× haste" numa linha só).
- Contagem de faces ao vivo vem do **reprocesso no servidor** (`group_faces` no estado), nunca de conta no cliente.
- Editar uma família limpa `needs_review` (o usuário acabou de revisá-la).
- A exportação real (`run()`) permanece intocada — preview e exibição nunca afetam o resultado exportado.
- UI em pt-BR; identificadores de código em inglês; Conventional Commits; TDD com evidência RED real (rodar e colar a saída falhando).
- Gate de verificação por task: `.venv/Scripts/python -m pytest -q` + `npm --prefix web test` + `npm --prefix web run build` verdes.
- Armadilha conhecida do three.js: `obj.name` vem SANITIZADO no load de GLTF (perde `.`); usar sempre `obj.userData.name` para extrair o component id.

---

### Task 1: `process()` aceita malha pré-carregada

**Files:**
- Modify: `src/meshbench/core/pipeline.py` (assinatura de `process`)
- Test: `tests/test_pipeline_process.py` (acrescentar teste)

**Interfaces:**
- Consumes: `process(project, base_dir)` atual (lê o source do disco na etapa 1).
- Produces: `process(project, base_dir, mesh=None)` — com `mesh` fornecido, pula a leitura do arquivo (etapa IMPORT) e usa a malha dada; comportamento idêntico no resultado. A malha fornecida NÃO é mutada (apply_scale/split_components já copiam).

- [ ] **Step 1: Escrever o teste que falha**

Acrescentar ao final de `tests/test_pipeline_process.py`:
```python
def test_process_com_malha_pre_carregada(tmp_path, box):
    """Com mesh= fornecido, process() não relê o arquivo fonte (cache da sessão)."""
    from meshbench.core.analyze.components import split_components
    from meshbench.core.pipeline import process
    from meshbench.core.project import new_project

    src = tmp_path / "caixa.stl"
    box.export(str(src))
    p = new_project("t", src, box, split_components(box))
    p.source["path"] = "caixa.stl"

    src.unlink()  # o arquivo some — só o cache pode servir a malha

    records, warnings = process(p, tmp_path, mesh=box)
    assert len(records) == 1
    assert len(records[0].mesh.faces) == 12
    # a malha fornecida não foi mutada
    import numpy as np
    assert np.allclose(box.extents, [10, 20, 30])
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_process.py::test_process_com_malha_pre_carregada -v`
Expected: FAIL — `TypeError: process() got an unexpected keyword argument 'mesh'`

- [ ] **Step 3: Implementar**

Em `src/meshbench/core/pipeline.py`, trocar a assinatura e a etapa 1 de `process`:
```python
def process(project, base_dir, mesh=None):
    """Executa as etapas 1-7 do pipeline e retorna (registros, warnings), sem exportar.

    `mesh` pré-carregada pula a leitura do fonte (cache da sessão do servidor —
    DXFs reais levam minutos para ler). A malha fornecida não é mutada.
    """
    base_dir = Path(base_dir)
    warnings = []

    # 1. IMPORT (pulado quando a sessão já tem a malha crua em cache)
    if mesh is None:
        src = Path(project.source["path"])
        if not src.is_absolute():
            src = base_dir / src
        mesh = read_mesh(src)
```
(O restante da função permanece idêntico.)

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_pipeline_process.py -v`
Expected: todos passam

- [ ] **Step 5: Rodar a suíte inteira e commitar**

Run: `.venv/Scripts/python -m pytest -q`
Expected: 104 passed (103 + 1 novo), 3 deselected

```bash
git add src/meshbench/core/pipeline.py tests/test_pipeline_process.py
git commit -m "feat: process() aceita malha pré-carregada (cache da sessão)"
```

---

### Task 2: Sessão mutável + `session_ops.py`

**Files:**
- Modify: `src/meshbench/api/server.py` (ProjectSession + load_session + `_project_state`)
- Create: `src/meshbench/api/session_ops.py`
- Test: `tests/test_api_session_ops.py`

**Interfaces:**
- Consumes: `process(project, base_dir, mesh=None)` (Task 1); `Project.from_dict/to_dict/save`; `OPS` de `meshbench.core.ops`; `build_scene_glb`, `display_records`.
- Produces:
  - `ProjectSession` ganha: `raw_mesh: object = None`, `recipe_path: Path | None = None`, `revision: int = 0`, `lock: threading.Lock` (default_factory).
  - `load_session` popula `raw_mesh` (lida UMA vez) e `recipe_path` (o próprio .json, ou `<pasta>/<stem>.meshbench.json` para malha).
  - `_project_state` inclui `"revision": session.revision`.
  - `session_ops.reprocess(session)` — reprocessa com cache e incrementa `revision`.
  - `session_ops.update_component(session, comp_id, changes)` — `changes` com chaves opcionais `operation` (validada contra OPS), `group` (str|None; grupo novo é acrescentado a `project.groups` com role "fixed"), `user_label` (str|None); limpa `needs_review`; levanta `KeyError` (id inexistente) / `ValueError` (op inválida).
  - `session_ops.preview_op(session, comp_id, operation) -> (glb_bytes | None, faces_before, faces_after)` — clona o projeto via to_dict/from_dict, NÃO muta a sessão.
  - `session_ops.save_recipe(session) -> Path`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_api_session_ops.py`:
```python
import numpy as np

from meshbench.api.server import load_session
from meshbench.api.session_ops import (
    preview_op,
    reprocess,
    save_recipe,
    update_component,
)
from meshbench.core.project import Project


def _session(tmp_path, small_sphere):
    p = tmp_path / "esfera.stl"
    small_sphere.export(str(p))
    return load_session(p)


def test_load_session_cacheia_malha_e_recipe_path(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    assert s.raw_mesh is not None and len(s.raw_mesh.faces) == 320
    assert s.recipe_path == (tmp_path / "esfera.meshbench.json").resolve()
    assert s.revision == 0


def test_update_component_reprocessa_e_incrementa_revision(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    # esfera pequena é sugerida como remove/sem grupo — trazer para a saída
    comp = s.project.components[0].id
    update_component(
        s,
        comp,
        {
            "operation": {"type": "decimate", "params": {"face_count": 80}},
            "group": "saida",
        },
    )
    assert s.revision == 1
    assert s.project.components[0].operation["type"] == "decimate"
    total = sum(len(r.mesh.faces) for r in s.records)
    assert 0 < total <= 100


def test_update_component_cria_grupo_novo(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    update_component(s, s.project.components[0].id, {"group": "movel"})
    assert {"name": "movel", "role": "fixed"} in s.project.groups


def test_update_component_limpa_needs_review(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    s.project.components[0].needs_review = True
    update_component(s, s.project.components[0].id, {"user_label": "solda"})
    assert s.project.components[0].needs_review is False
    assert s.project.components[0].user_label == "solda"


def test_update_component_valida(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    import pytest

    with pytest.raises(KeyError):
        update_component(s, "c99", {"user_label": "x"})
    with pytest.raises(ValueError, match="operação"):
        update_component(
            s, s.project.components[0].id, {"operation": {"type": "explodir"}}
        )


def test_preview_nao_muta_sessao(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    comp = s.project.components[0].id
    update_component(s, comp, {"operation": {"type": "keep", "params": {}}, "group": "saida"})
    rev = s.revision
    glb, before, after = preview_op(
        s, comp, {"type": "decimate", "params": {"face_count": 80}}
    )
    assert glb[:4] == b"glTF"
    assert before == 320
    assert 0 < after <= 100
    # sessão intocada
    assert s.revision == rev
    assert s.project.components[0].operation["type"] == "keep"
    assert sum(len(r.mesh.faces) for r in s.records) == 320


def test_preview_op_que_remove_retorna_none(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    comp = s.project.components[0].id
    update_component(s, comp, {"operation": {"type": "keep", "params": {}}, "group": "saida"})
    glb, before, after = preview_op(s, comp, {"type": "remove", "params": {}})
    assert glb is None
    assert before == 320 and after == 0


def test_save_recipe_grava_e_recarrega(tmp_path, small_sphere):
    s = _session(tmp_path, small_sphere)
    update_component(s, s.project.components[0].id, {"user_label": "bolinha"})
    path = save_recipe(s)
    assert path.exists()
    p2 = Project.load(path)
    assert p2.components[0].user_label == "bolinha"
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_api_session_ops.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'meshbench.api.session_ops'`

- [ ] **Step 3: Atualizar `ProjectSession` e `load_session` em server.py**

Em `src/meshbench/api/server.py`, adicionar `import threading` no topo e substituir a dataclass e o `load_session`:
```python
@dataclass
class ProjectSession:
    """Um projeto carregado em memória (um por servidor, conforme §13)."""

    project: Project
    base_dir: Path
    records: list
    warnings: list = field(default_factory=list)
    raw_mesh: object = None  # malha crua em cache — reprocesso nunca relê o fonte
    recipe_path: Path | None = None
    revision: int = 0
    lock: threading.Lock = field(default_factory=threading.Lock)


def load_session(path):
    """Carrega uma receita .meshbench.json OU um arquivo de malha (projeto virtual)."""
    path = Path(path)
    if path.suffix.lower() == ".json":
        project = Project.load(path)
        base_dir = path.resolve().parent
        recipe_path = path.resolve()
        src = Path(project.source["path"])
        if not src.is_absolute():
            src = base_dir / src
        raw_mesh = read_mesh(src)
    else:
        raw_mesh = read_mesh(path)
        project = new_project(path.stem, path, raw_mesh, split_components(raw_mesh))
        project.source["path"] = path.name
        base_dir = path.resolve().parent
        recipe_path = (base_dir / f"{path.stem}.meshbench.json").resolve()
    records, warnings = process(project, base_dir, mesh=raw_mesh)
    return ProjectSession(
        project=project,
        base_dir=base_dir,
        records=records,
        warnings=warnings,
        raw_mesh=raw_mesh,
        recipe_path=recipe_path,
    )
```
E em `_project_state`, acrescentar ao dict retornado:
```python
        "revision": session.revision,
```

- [ ] **Step 4: Criar session_ops.py**

`src/meshbench/api/session_ops.py`:
```python
"""Mutações da sessão (fase 3). Toda mudança é ação explícita do usuário
(Aplicar/Salvar); o preview clona o projeto e NUNCA toca na sessão; o
reprocesso usa a malha crua em cache — nunca relê o arquivo fonte."""

from meshbench.api.geometry import build_scene_glb, display_records
from meshbench.core.ops import OPS
from meshbench.core.pipeline import process
from meshbench.core.project import Project


def reprocess(session):
    """Reexecuta o pipeline (etapas 2-7) com a malha crua em cache."""
    records, warnings = process(
        session.project, session.base_dir, mesh=session.raw_mesh
    )
    session.records = records
    session.warnings = warnings
    session.revision += 1


def _find_entry(project, comp_id):
    entry = next((c for c in project.components if c.id == comp_id), None)
    if entry is None:
        raise KeyError(f"componente '{comp_id}' não existe")
    return entry


def _validated_op(op):
    kind = (op or {}).get("type")
    if kind not in OPS:
        raise ValueError(
            f"operação '{kind}' desconhecida (disponíveis: {sorted(OPS)})"
        )
    return {"type": kind, "params": (op or {}).get("params") or {}}


def update_component(session, comp_id, changes):
    """Aplica mudanças de operação/grupo/rótulo a uma família e reprocessa.

    Grupo inexistente é acrescentado a project.groups (role "fixed").
    Editar uma família limpa needs_review — o usuário acabou de revisá-la.
    """
    with session.lock:
        entry = _find_entry(session.project, comp_id)
        if "operation" in changes:
            entry.operation = _validated_op(changes["operation"])
        if "group" in changes:
            group = changes["group"]
            entry.group = group
            names = [g["name"] for g in session.project.groups]
            if group is not None and group not in names:
                session.project.groups.append({"name": group, "role": "fixed"})
        if "user_label" in changes:
            entry.user_label = changes["user_label"] or None
        entry.needs_review = False
        reprocess(session)


def preview_op(session, comp_id, operation):
    """Pré-visualiza uma operação SEM tocar na sessão.

    Clona o projeto (to_dict/from_dict = cópia profunda), troca a operação da
    família, reprocessa o clone e retorna (glb | None, faces_antes,
    faces_depois) só com as malhas da família pré-visualizada.
    """
    with session.lock:
        op = _validated_op(operation)
        _find_entry(session.project, comp_id)
        clone = Project.from_dict(session.project.to_dict())
        _find_entry(clone, comp_id).operation = op
        faces_before = sum(
            len(r.mesh.faces)
            for r in session.records
            if r.component_id == comp_id
        )
        records, _ = process(clone, session.base_dir, mesh=session.raw_mesh)
        preview_records = [r for r in records if r.component_id == comp_id]
        faces_after = sum(len(r.mesh.faces) for r in preview_records)
        glb = None
        if preview_records:
            glb = build_scene_glb(display_records(preview_records))
        return glb, faces_before, faces_after


def save_recipe(session):
    """Grava a receita no caminho da sessão. Explícito — nunca automático."""
    with session.lock:
        session.project.save(session.recipe_path)
        return session.recipe_path
```

- [ ] **Step 5: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_api_session_ops.py -v`
Expected: 8 passed

- [ ] **Step 6: Rodar a suíte inteira e commitar**

Run: `.venv/Scripts/python -m pytest -q`
Expected: tudo verde (os testes existentes de server não quebram — os campos novos têm default)

```bash
git add src/meshbench/api/server.py src/meshbench/api/session_ops.py tests/test_api_session_ops.py
git commit -m "feat: mutações de sessão — update/preview/save com cache e lock"
```

---

### Task 3: Rotas PATCH/POST no servidor

**Files:**
- Modify: `src/meshbench/api/server.py` (novas rotas em `create_app`)
- Test: `tests/test_api_mutations.py`

**Interfaces:**
- Consumes: `update_component`, `preview_op`, `save_recipe` (Task 2).
- Produces:
  - `PATCH /api/component/{comp_id}` body `{"operation"?: {...}, "group"?: str|null, "user_label"?: str|null}` → 200 com o estado completo do projeto (mesmo shape do GET, com `revision` novo); 404 (id inexistente) / 422 (operação inválida) com `detail` pt-BR.
  - `POST /api/preview/{comp_id}` body `{"operation": {...}}` → 200 GLB `model/gltf-binary` com headers `X-Faces-Before` e `X-Faces-After`; 404 quando a operação não produz malha; 404/422 para id/op inválidos.
  - `POST /api/project/save` → 200 `{"path": "..."}`.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_api_mutations.py`:
```python
import json

from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session
from meshbench.core.project import Project


def _client(tmp_path, small_sphere):
    p = tmp_path / "esfera.stl"
    small_sphere.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_patch_atualiza_e_retorna_estado(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    state0 = client.get("/api/project").json()
    comp = state0["components"][0]["id"]
    r = client.patch(
        f"/api/component/{comp}",
        json={
            "operation": {"type": "decimate", "params": {"face_count": 80}},
            "group": "saida",
        },
    )
    assert r.status_code == 200
    state = r.json()
    assert state["components"][0]["operation"]["type"] == "decimate"
    assert 0 < state["group_faces"]["saida"] <= 100
    assert state["revision"] == state0["revision"] + 1


def test_patch_id_inexistente_404(tmp_path, small_sphere):
    client, _ = _client(tmp_path, small_sphere)
    r = client.patch("/api/component/c99", json={"user_label": "x"})
    assert r.status_code == 404
    assert "c99" in r.json()["detail"]


def test_patch_operacao_invalida_422(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    comp = session.project.components[0].id
    r = client.patch(
        f"/api/component/{comp}", json={"operation": {"type": "explodir"}}
    )
    assert r.status_code == 422
    assert "explodir" in r.json()["detail"]


def test_preview_retorna_glb_sem_mutar(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    comp = session.project.components[0].id
    client.patch(
        f"/api/component/{comp}",
        json={"operation": {"type": "keep", "params": {}}, "group": "saida"},
    )
    rev = session.revision
    r = client.post(
        f"/api/preview/{comp}",
        json={"operation": {"type": "decimate", "params": {"face_count": 80}}},
    )
    assert r.status_code == 200
    assert r.content[:4] == b"glTF"
    assert r.headers["X-Faces-Before"] == "320"
    assert 0 < int(r.headers["X-Faces-After"]) <= 100
    assert session.revision == rev  # preview não muta


def test_preview_remove_404(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    comp = session.project.components[0].id
    client.patch(
        f"/api/component/{comp}",
        json={"operation": {"type": "keep", "params": {}}, "group": "saida"},
    )
    r = client.post(
        f"/api/preview/{comp}", json={"operation": {"type": "remove", "params": {}}}
    )
    assert r.status_code == 404
    assert "não produziu" in r.json()["detail"]


def test_save_grava_receita(tmp_path, small_sphere):
    client, session = _client(tmp_path, small_sphere)
    r = client.post("/api/project/save")
    assert r.status_code == 200
    path = r.json()["path"]
    assert path.endswith("esfera.meshbench.json")
    p = Project.load(path)
    assert p.name == "esfera"
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_api_mutations.py -v`
Expected: FAIL — 405/404 (rotas não existem)

- [ ] **Step 3: Implementar as rotas**

Em `src/meshbench/api/server.py`: no topo, importar as mutações:
```python
from meshbench.api.session_ops import preview_op, save_recipe, update_component
```
Dentro de `create_app(session)`, ANTES do mount estático, acrescentar:
```python
    @app.patch("/api/component/{comp_id}")
    def patch_component(comp_id: str, changes: dict):
        try:
            update_component(session, comp_id, changes)
        except KeyError as e:
            return JSONResponse(status_code=404, content={"detail": str(e).strip("'\"")})
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.post("/api/preview/{comp_id}")
    def post_preview(comp_id: str, body: dict):
        try:
            glb, before, after = preview_op(session, comp_id, body.get("operation"))
        except KeyError as e:
            return JSONResponse(status_code=404, content={"detail": str(e).strip("'\"")})
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        if glb is None:
            return JSONResponse(
                status_code=404,
                content={"detail": "a operação não produziu malha para esta peça"},
            )
        return Response(
            content=glb,
            media_type="model/gltf-binary",
            headers={"X-Faces-Before": str(before), "X-Faces-After": str(after)},
        )

    @app.post("/api/project/save")
    def post_save():
        return JSONResponse({"path": str(save_recipe(session))})
```
Atualizar também a docstring do módulo: o servidor deixou de ser read-only na Fase 3 — mutações explícitas de componente, preview e salvar receita; continua local-only (127.0.0.1).

- [ ] **Step 4: Rodar para ver passar**

Run: `.venv/Scripts/python -m pytest tests/test_api_mutations.py -v`
Expected: 6 passed

- [ ] **Step 5: Rodar a suíte inteira e commitar**

Run: `.venv/Scripts/python -m pytest -q`
Expected: tudo verde

```bash
git add src/meshbench/api/server.py tests/test_api_mutations.py
git commit -m "feat: rotas PATCH componente, POST preview e POST save"
```

---

### Task 4: Helpers do frontend — `lib/ops.js` + `lib/client.js`

**Files:**
- Create: `web/src/lib/ops.js`
- Create: `web/src/lib/ops.test.js`
- Create: `web/src/lib/client.js`
- Modify: `web/src/components/Sidebar.jsx` (badge com rótulo pt-BR)
- Modify: `web/src/App.jsx` (usar `fetchProject` do client)

**Interfaces:**
- Produces (ops.js): `OP_TYPES` (`["keep","remove","decimate","hull","tube","reextrude"]`); `OP_LABELS` (pt-BR); `opDefaults(type) -> object` (decimate `{percent: 25}`; tube `{sides: 8, bin_mm: 3.0, radius: ""}`; reextrude `{axis: "auto", n_probe: 25, tol: 0.4}`; demais `{}`); `coerceParams(type, params) -> object` (strings do formulário → números; `radius` vazio omitido; `axis` "auto" omitido, senão convertido para índice 0/1/2; `face_count` preenchido tem precedência sobre `percent`).
- Produces (client.js): `fetchProject()`, `patchComponent(id, changes) -> state`, `previewComponent(id, operation) -> {url, facesBefore, facesAfter}` (objectURL de blob), `saveRecipe() -> {path}`, `geometryUrl(revision) -> string` (`/api/project/geometry?rev=N`). Erros HTTP viram `Error` com o `detail` do backend.

- [ ] **Step 1: Escrever os testes que falham**

`web/src/lib/ops.test.js`:
```js
import { describe, expect, it } from "vitest";
import { OP_LABELS, OP_TYPES, coerceParams, opDefaults } from "./ops.js";

describe("ops", () => {
  it("todo tipo tem rótulo pt-BR", () => {
    for (const t of OP_TYPES) expect(OP_LABELS[t]).toBeTruthy();
  });

  it("defaults por operação", () => {
    expect(opDefaults("decimate")).toEqual({ percent: 25 });
    expect(opDefaults("tube")).toEqual({ sides: 8, bin_mm: 3.0, radius: "" });
    expect(opDefaults("reextrude")).toEqual({ axis: "auto", n_probe: 25, tol: 0.4 });
    expect(opDefaults("keep")).toEqual({});
  });

  it("coerceParams: decimate com face_count tem precedência", () => {
    expect(coerceParams("decimate", { percent: "25", face_count: "80" })).toEqual({
      face_count: 80,
    });
    expect(coerceParams("decimate", { percent: "10" })).toEqual({ percent: 10 });
  });

  it("coerceParams: tube omite radius vazio", () => {
    expect(coerceParams("tube", { sides: "8", bin_mm: "3", radius: "" })).toEqual({
      sides: 8,
      bin_mm: 3,
    });
    expect(coerceParams("tube", { sides: "6", bin_mm: "2.5", radius: "4" })).toEqual({
      sides: 6,
      bin_mm: 2.5,
      radius: 4,
    });
  });

  it("coerceParams: reextrude converte eixo e omite auto", () => {
    expect(coerceParams("reextrude", { axis: "auto", n_probe: "25", tol: "0.4" })).toEqual({
      n_probe: 25,
      tol: 0.4,
    });
    expect(coerceParams("reextrude", { axis: "z", n_probe: "10", tol: "1.5" })).toEqual({
      axis: 2,
      n_probe: 10,
      tol: 1.5,
    });
  });

  it("coerceParams: keep/remove/hull sem params", () => {
    expect(coerceParams("keep", {})).toEqual({});
    expect(coerceParams("hull", { lixo: 1 })).toEqual({});
  });
});
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `npm --prefix web test`
Expected: FAIL — `Cannot find module './ops.js'` (ou equivalente do vitest)

- [ ] **Step 3: Implementar ops.js**

`web/src/lib/ops.js`:
```js
// Operações do motor e seus parâmetros — todos expostos na UI (§6 do doc).
export const OP_TYPES = ["keep", "remove", "decimate", "hull", "tube", "reextrude"];

export const OP_LABELS = {
  keep: "manter",
  remove: "remover",
  decimate: "decimar",
  hull: "casco convexo",
  tube: "tubo",
  reextrude: "re-extrudar",
};

// Defaults iguais aos do core (ops/basic.py, ops/tube.py, ops/reextrude.py).
export function opDefaults(type) {
  if (type === "decimate") return { percent: 25 };
  if (type === "tube") return { sides: 8, bin_mm: 3.0, radius: "" };
  if (type === "reextrude") return { axis: "auto", n_probe: 25, tol: 0.4 };
  return {};
}

// Converte params do formulário (strings) para o corpo do PATCH/preview.
export function coerceParams(type, params) {
  const out = {};
  if (type === "decimate") {
    if (params.face_count) out.face_count = Math.round(Number(params.face_count));
    else out.percent = Number(params.percent ?? 25);
  } else if (type === "tube") {
    out.sides = Math.round(Number(params.sides ?? 8));
    out.bin_mm = Number(params.bin_mm ?? 3.0);
    if (params.radius !== "" && params.radius != null) out.radius = Number(params.radius);
  } else if (type === "reextrude") {
    if (params.axis && params.axis !== "auto") out.axis = { x: 0, y: 1, z: 2 }[params.axis];
    out.n_probe = Math.round(Number(params.n_probe ?? 25));
    out.tol = Number(params.tol ?? 0.4);
  }
  return out;
}
```

- [ ] **Step 4: Implementar client.js**

`web/src/lib/client.js`:
```js
// Cliente HTTP da API local. Erros HTTP viram Error com o detail do backend.
async function checkOk(r) {
  if (!r.ok) {
    let detail = "";
    try {
      detail = (await r.json()).detail || "";
    } catch {
      /* corpo não-JSON */
    }
    throw new Error(detail || `HTTP ${r.status}`);
  }
  return r;
}

export async function fetchProject() {
  const r = await checkOk(await fetch("/api/project"));
  return r.json();
}

export async function patchComponent(id, changes) {
  const r = await checkOk(
    await fetch(`/api/component/${id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),
  );
  return r.json();
}

export async function previewComponent(id, operation) {
  const r = await checkOk(
    await fetch(`/api/preview/${id}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operation }),
    }),
  );
  const blob = await r.blob();
  return {
    url: URL.createObjectURL(blob),
    facesBefore: Number(r.headers.get("X-Faces-Before")),
    facesAfter: Number(r.headers.get("X-Faces-After")),
  };
}

export async function saveRecipe() {
  const r = await checkOk(await fetch("/api/project/save", { method: "POST" }));
  return r.json();
}

// rev na query só para furar cache do navegador quando a sessão muda
export function geometryUrl(revision) {
  return `/api/project/geometry?rev=${revision ?? 0}`;
}
```

- [ ] **Step 5: Badge pt-BR na Sidebar e client no App**

Em `web/src/components/Sidebar.jsx`: importar `import { OP_LABELS } from "../lib/ops.js";` e trocar a linha do badge:
```jsx
      <span className="op">{OP_LABELS[c.operation.type] || c.operation.type}</span>
```
Em `web/src/App.jsx`: importar `import { fetchProject } from "./lib/client.js";` e trocar o corpo do useEffect:
```jsx
  useEffect(() => {
    fetchProject().then(setState).catch((e) => setError(String(e)));
  }, []);
```

- [ ] **Step 6: Rodar para ver passar**

Run: `npm --prefix web test && npm --prefix web run build`
Expected: 13 testes (7 + 6 novos) passam; build OK

- [ ] **Step 7: Rodar pytest (inalterado) e commitar**

Run: `.venv/Scripts/python -m pytest -q`
Expected: verde

```bash
git add web/src/lib/ops.js web/src/lib/ops.test.js web/src/lib/client.js web/src/components/Sidebar.jsx web/src/App.jsx
git commit -m "feat: helpers de operações e cliente HTTP no frontend"
```

---

### Task 5: Seleção — App + Sidebar clicável + raycast no Viewport

**Files:**
- Modify: `web/src/App.jsx` (estado `selected` + `preview`, repasse de props)
- Modify: `web/src/components/Sidebar.jsx` (linhas clicáveis + destaque)
- Modify: `web/src/components/Viewport.jsx` (raycast por clique, destaque emissivo, `geometryUrl(revision)`)
- Modify: `web/src/styles.css` (classe `.familia.selecionada`, cursor)

**Interfaces:**
- Consumes: `geometryUrl` (Task 4).
- Produces: `App` mantém `selected: string|null` e `preview: object|null` e passa: `Sidebar {state, selected, onSelect}`, `Viewport {state, selected, onSelect, preview}`, `Inspector` chega na Task 6 (por ora App NÃO renderiza Inspector). Selecionar limpa o preview (revogando o objectURL). `Viewport` expõe clique: raycast → família (via `userData.name`), clique no vazio → `onSelect(null)`; peça selecionada ganha emissivo azulado; drag de órbita NÃO seleciona (limiar de 5px entre pointerdown/up).

- [ ] **Step 1: Atualizar App.jsx**

Substituir `web/src/App.jsx` por:
```jsx
import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import StatusBar from "./components/StatusBar.jsx";
import Viewport from "./components/Viewport.jsx";
import { fetchProject } from "./lib/client.js";

export default function App() {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null); // id da família selecionada
  const [preview, setPreview] = useState(null); // {componentId, url, facesBefore, facesAfter, mostrando}

  useEffect(() => {
    fetchProject().then(setState).catch((e) => setError(String(e)));
  }, []);

  const clearPreview = useCallback(() => {
    setPreview((p) => {
      if (p) URL.revokeObjectURL(p.url);
      return null;
    });
  }, []);

  const handleSelect = useCallback(
    (id) => {
      clearPreview();
      setSelected(id);
    },
    [clearPreview],
  );

  // resposta de um PATCH substitui o estado inteiro (o servidor reprocessou)
  const handleStateChange = useCallback(
    (novo) => {
      clearPreview();
      setState(novo);
    },
    [clearPreview],
  );

  if (error) return <div className="tela-aviso">Erro ao carregar o projeto: {error}</div>;
  if (!state) return <div className="tela-aviso">Carregando…</div>;
  return (
    <div className="app">
      <Sidebar state={state} selected={selected} onSelect={handleSelect} />
      <main className="viewport-wrap">
        <Viewport state={state} selected={selected} onSelect={handleSelect} preview={preview} />
      </main>
      <StatusBar state={state} />
    </div>
  );
}
```
(`handleStateChange`/`setPreview` ficam sem uso até a Task 6 — tudo bem, a Task 6 os conecta ao Inspector.)

- [ ] **Step 2: Sidebar clicável**

Substituir `web/src/components/Sidebar.jsx` por:
```jsx
import { formatFaces } from "../lib/format.js";
import { OP_LABELS } from "../lib/ops.js";
import { groupColor } from "../lib/palette.js";

function Familia({ c, cor, removida, selecionada, onSelect }) {
  const label = c.user_label || c.auto_class;
  return (
    <div
      className={
        "familia" + (removida ? " removida" : "") + (selecionada ? " selecionada" : "")
      }
      onClick={() => onSelect(c.id)}
    >
      <span className="cor" style={{ background: cor }} />
      <span>
        {c.instances}× {label} ({formatFaces(c.face_count)} f cada)
        {c.needs_review ? <span className="alerta"> ⚠ novo — revisar</span> : null}
      </span>
      <span className="op">{OP_LABELS[c.operation.type] || c.operation.type}</span>
    </div>
  );
}

export default function Sidebar({ state, selected, onSelect }) {
  const groupNames = state.groups.map((g) => g.name);
  const porGrupo = new Map(groupNames.map((n) => [n, []]));
  const removidas = [];
  const semGrupo = [];
  for (const c of state.components) {
    if (c.operation.type === "remove") removidas.push(c);
    else if (c.group && porGrupo.has(c.group)) porGrupo.get(c.group).push(c);
    else semGrupo.push(c);
  }

  const familia = (c, cor, removida) => (
    <Familia
      key={c.id}
      c={c}
      cor={cor}
      removida={removida}
      selecionada={c.id === selected}
      onSelect={onSelect}
    />
  );

  return (
    <aside className="sidebar">
      <h1 style={{ fontSize: "1rem" }}>{state.name}</h1>
      {groupNames.map((g) => (
        <section key={g}>
          <h2>▸ {g}</h2>
          {porGrupo.get(g).map((c) => familia(c, groupColor(g, groupNames), false))}
        </section>
      ))}
      {semGrupo.length > 0 && (
        <section>
          <h2>▸ sem grupo ⚠</h2>
          {semGrupo.map((c) => familia(c, "#666", false))}
        </section>
      )}
      {removidas.length > 0 && (
        <section>
          <h2>▸ removidas</h2>
          {removidas.map((c) => familia(c, "#666", true))}
        </section>
      )}
    </aside>
  );
}
```

- [ ] **Step 3: Raycast e destaque no Viewport**

Substituir `web/src/components/Viewport.jsx` por (mudanças: props novas, `meshesByCompRef`, clique com limiar, efeito de destaque, `geometryUrl(state.revision)`; o efeito de preview chega na Task 7):
```jsx
import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { geometryUrl } from "../lib/client.js";
import { groupColor } from "../lib/palette.js";

const SELECT_EMISSIVE = 0x2a4a6a;

// Libera geometrias e materiais de uma subárvore da cena (GLTF, helpers, marcador).
function disposeSceneResources(root) {
  root.traverse((obj) => {
    obj.geometry?.dispose();
    const m = obj.material;
    if (Array.isArray(m)) m.forEach((x) => x.dispose());
    else m?.dispose();
  });
}

// three.js sanitiza nomes de nó no load do GLTF (remove `.`/`:`/`/`) —
// o nome original (pré-sanitização) fica em userData.name. NUNCA usar obj.name.
function compIdOf(obj) {
  return (obj.userData.name || obj.name).split(".")[0];
}

export default function Viewport({ state, selected, onSelect, preview }) {
  const mountRef = useRef(null);
  const [erro, setErro] = useState(null);
  const [aviso, setAviso] = useState(null);
  const meshesByCompRef = useRef(new Map()); // compId -> [meshes]
  const selectedRef = useRef(selected);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;
  const semSaida = Object.keys(state.group_faces || {}).length === 0;

  useEffect(() => {
    setErro(null);
    setAviso(null);
    let cancelled = false;
    const mount = mountRef.current;
    const meshesByComp = new Map();
    meshesByCompRef.current = meshesByComp;
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
    renderer.setPixelRatio(window.devicePixelRatio); // nitidez em telas HiDPI
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

    // sem peças no resultado (tudo removido ou sem grupo): não há GLB para
    // buscar — o backend responde 404 — só avisa o usuário
    if (semSaida) {
      setAviso("nenhuma peça no resultado");
    } else {
      new GLTFLoader().load(
        geometryUrl(state.revision),
        (gltf) => {
          if (cancelled) {
            disposeSceneResources(gltf.scene);
            return;
          }
          gltf.scene.traverse((obj) => {
            if (obj.isMesh) {
              // o GLB do backend traz só POSITION — sem normais o material
              // iluminado renderiza preto
              if (!obj.geometry.attributes.normal) {
                obj.geometry.computeVertexNormals();
              }
              const compId = compIdOf(obj);
              obj.material = new THREE.MeshStandardMaterial({
                color: groupColor(groupOf[compId], groupNames),
                metalness: 0.1,
                roughness: 0.75,
                side: THREE.DoubleSide,
              });
              if (!meshesByComp.has(compId)) meshesByComp.set(compId, []);
              meshesByComp.get(compId).push(obj);
              // seleção pode já existir quando a cena recarrega (ex.: após Aplicar)
              if (compId === selectedRef.current) {
                obj.material.emissive.setHex(SELECT_EMISSIVE);
              }
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

          if (!box.isEmpty()) {
            camera.position.set(
              center.x + radius * 1.2,
              center.y - radius * 1.2,
              center.z + radius * 0.9,
            );
            controls.target.copy(center);
            controls.update();
          }
        },
        undefined,
        (err) => {
          console.error("falha ao carregar /api/project/geometry", err);
          if (!cancelled) setErro("falha ao carregar a geometria — veja o console");
        },
      );
    }

    // seleção por clique (raycast) — drag de órbita não seleciona (limiar 5px)
    const raycaster = new THREE.Raycaster();
    const down = { x: 0, y: 0 };
    const onPointerDown = (e) => {
      down.x = e.clientX;
      down.y = e.clientY;
    };
    const onPointerUp = (e) => {
      if (Math.hypot(e.clientX - down.x, e.clientY - down.y) > 5) return;
      const rect = renderer.domElement.getBoundingClientRect();
      const ndc = new THREE.Vector2(
        ((e.clientX - rect.left) / rect.width) * 2 - 1,
        -((e.clientY - rect.top) / rect.height) * 2 + 1,
      );
      raycaster.setFromCamera(ndc, camera);
      const meshes = [...meshesByComp.values()].flat().filter((m) => m.visible);
      const hits = raycaster.intersectObjects(meshes, false);
      onSelectRef.current(hits.length > 0 ? compIdOf(hits[0].object) : null);
    };
    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    renderer.domElement.addEventListener("pointerup", onPointerUp);

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
      cancelled = true;
      cancelAnimationFrame(frame);
      ro.disconnect();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      renderer.domElement.removeEventListener("pointerup", onPointerUp);
      controls.dispose();
      disposeSceneResources(scene);
      renderer.dispose();
      mount.removeChild(renderer.domElement);
      meshesByCompRef.current = new Map();
    };
  }, [state]);

  // destaque emissivo da família selecionada — não recria a cena
  useEffect(() => {
    selectedRef.current = selected;
    for (const [compId, meshes] of meshesByCompRef.current) {
      for (const m of meshes) {
        m.material.emissive?.setHex(compId === selected ? SELECT_EMISSIVE : 0x000000);
      }
    }
  }, [selected, state]);

  return (
    <div className="viewport" ref={mountRef}>
      {erro && <div className="viewport-erro">{erro}</div>}
      {!erro && aviso && <div className="viewport-aviso">{aviso}</div>}
    </div>
  );
}
```

- [ ] **Step 4: CSS da seleção**

Acrescentar ao final de `web/src/styles.css`:
```css
.familia { cursor: pointer; }
.familia:hover { background: #26262e; }
.familia.selecionada { background: #2a3a4e; outline: 1px solid #4e79a7; }
```

- [ ] **Step 5: Verificar**

Run: `npm --prefix web test && npm --prefix web run build && .venv/Scripts/python -m pytest -q`
Expected: tudo verde (a seleção em si é validada visualmente na Task 8)

- [ ] **Step 6: Commit**

```bash
git add web/src/App.jsx web/src/components/Sidebar.jsx web/src/components/Viewport.jsx web/src/styles.css
git commit -m "feat: seleção de família por clique (lista + raycast) com destaque"
```

---

### Task 6: Painel Inspector (aplicar operação/grupo/rótulo + salvar)

**Files:**
- Create: `web/src/components/Inspector.jsx`
- Modify: `web/src/App.jsx` (renderizar Inspector, conectar handlers)
- Modify: `web/src/styles.css` (coluna do inspector + formulários)

**Interfaces:**
- Consumes: `patchComponent`, `saveRecipe` (client.js); `OP_TYPES`, `OP_LABELS`, `opDefaults`, `coerceParams` (ops.js); `formatFaces`.
- Produces: `Inspector {state, entry, preview, onStateChange, onPreviewChange, onClearPreview}` — formulário sincronizado com a família selecionada; "Aplicar" faz PATCH `{operation, group, user_label}` e entrega o estado novo via `onStateChange`; grupo: select com grupos existentes + `(sem grupo)` + campo "novo grupo" (texto preenchido tem precedência); botão "Salvar receita" SEMPRE visível (mesmo sem seleção). Botões de preview chegam na Task 7 (por ora `preview`/`onPreviewChange`/`onClearPreview` ficam sem uso no corpo).

- [ ] **Step 1: Criar Inspector.jsx**

`web/src/components/Inspector.jsx`:
```jsx
import { useEffect, useState } from "react";
import { patchComponent, saveRecipe } from "../lib/client.js";
import { formatFaces } from "../lib/format.js";
import { OP_LABELS, OP_TYPES, coerceParams, opDefaults } from "../lib/ops.js";

function CampoNum({ nome, valor, step, onChange }) {
  return (
    <label className="campo">
      <span>{nome}</span>
      <input
        type="number"
        step={step ?? 1}
        value={valor ?? ""}
        onChange={(e) => onChange(e.target.value)}
      />
    </label>
  );
}

function ParamsForm({ opType, params, setParam }) {
  if (opType === "decimate") {
    return (
      <>
        <CampoNum nome="% do original" valor={params.percent} onChange={(v) => setParam("percent", v)} />
        <CampoNum nome="faces (absoluto, opcional)" valor={params.face_count} onChange={(v) => setParam("face_count", v)} />
      </>
    );
  }
  if (opType === "tube") {
    return (
      <>
        <CampoNum nome="lados do círculo" valor={params.sides} onChange={(v) => setParam("sides", v)} />
        <CampoNum nome="passo da linha (mm)" step={0.5} valor={params.bin_mm} onChange={(v) => setParam("bin_mm", v)} />
        <CampoNum nome="raio (vazio = auto)" step={0.5} valor={params.radius} onChange={(v) => setParam("radius", v)} />
      </>
    );
  }
  if (opType === "reextrude") {
    return (
      <>
        <label className="campo">
          <span>eixo de extrusão</span>
          <select value={params.axis ?? "auto"} onChange={(e) => setParam("axis", e.target.value)}>
            <option value="auto">auto (maior dimensão)</option>
            <option value="x">x</option>
            <option value="y">y</option>
            <option value="z">z</option>
          </select>
        </label>
        <CampoNum nome="fatias de teste" valor={params.n_probe} onChange={(v) => setParam("n_probe", v)} />
        <CampoNum nome="tolerância do perfil" step={0.1} valor={params.tol} onChange={(v) => setParam("tol", v)} />
      </>
    );
  }
  return null;
}

export default function Inspector({
  state,
  entry,
  preview,
  onStateChange,
  onPreviewChange,
  onClearPreview,
}) {
  const [opType, setOpType] = useState("keep");
  const [params, setParams] = useState({});
  const [group, setGroup] = useState("");
  const [novoGrupo, setNovoGrupo] = useState("");
  const [label, setLabel] = useState("");
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);

  // sincroniza o formulário quando a seleção muda
  useEffect(() => {
    if (!entry) return;
    setOpType(entry.operation.type);
    setParams({ ...opDefaults(entry.operation.type), ...entry.operation.params });
    setGroup(entry.group ?? "");
    setNovoGrupo("");
    setLabel(entry.user_label ?? "");
    setMsg(null);
  }, [entry?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const setParam = (k, v) => setParams((p) => ({ ...p, [k]: v }));

  const trocarOp = (t) => {
    setOpType(t);
    setParams(opDefaults(t));
  };

  const aplicar = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const g = novoGrupo.trim() || (group === "" ? null : group);
      const novo = await patchComponent(entry.id, {
        operation: { type: opType, params: coerceParams(opType, params) },
        group: g,
        user_label: label.trim() || null,
      });
      onStateChange(novo);
      setNovoGrupo("");
      setMsg("aplicado ✓");
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const salvar = async () => {
    setMsg(null);
    try {
      const r = await saveRecipe();
      setMsg(`receita salva: ${r.path}`);
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
  };

  return (
    <aside className="inspector">
      <h2>Inspetor</h2>
      {!entry && <p className="dica">Clique numa peça (viewport ou lista) para editar.</p>}
      {entry && (
        <>
          <p className="resumo">
            {entry.instances}× {entry.user_label || entry.auto_class} ·{" "}
            {formatFaces(entry.face_count)} f cada
          </p>
          <label className="campo">
            <span>rótulo</span>
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder={entry.auto_class} />
          </label>
          <fieldset className="ops">
            <legend>operação</legend>
            {OP_TYPES.map((t) => (
              <label key={t} className="op-radio">
                <input type="radio" name="op" checked={opType === t} onChange={() => trocarOp(t)} />
                {OP_LABELS[t]}
              </label>
            ))}
          </fieldset>
          <ParamsForm opType={opType} params={params} setParam={setParam} />
          <label className="campo">
            <span>grupo</span>
            <select value={group} onChange={(e) => setGroup(e.target.value)}>
              <option value="">(sem grupo)</option>
              {state.groups.map((g) => (
                <option key={g.name} value={g.name}>
                  {g.name}
                </option>
              ))}
            </select>
          </label>
          <label className="campo">
            <span>novo grupo</span>
            <input
              value={novoGrupo}
              onChange={(e) => setNovoGrupo(e.target.value)}
              placeholder="criar grupo…"
            />
          </label>
          <button className="btn primario" disabled={busy} onClick={aplicar}>
            Aplicar
          </button>
        </>
      )}
      <button className="btn" onClick={salvar}>
        Salvar receita
      </button>
      {msg && <p className="msg">{msg}</p>}
    </aside>
  );
}
```

- [ ] **Step 2: Conectar no App.jsx**

Em `web/src/App.jsx`: importar `import Inspector from "./components/Inspector.jsx";`, e no JSX (depois de `</main>`, antes de `<StatusBar …/>`):
```jsx
      <Inspector
        state={state}
        entry={state.components.find((c) => c.id === selected) || null}
        preview={preview}
        onStateChange={handleStateChange}
        onPreviewChange={setPreview}
        onClearPreview={clearPreview}
      />
```

- [ ] **Step 3: CSS do inspector**

Em `web/src/styles.css`, trocar a regra `.app` por:
```css
.app {
  display: grid;
  grid-template-columns: 300px 1fr 280px;
  grid-template-rows: 1fr auto;
  grid-template-areas: "sidebar viewport inspector" "sidebar statusbar statusbar";
  height: 100%;
}
```
E acrescentar ao final:
```css
.inspector { grid-area: inspector; overflow-y: auto; background: #1e1e24; padding: 12px; border-left: 1px solid #2c2c34; display: flex; flex-direction: column; gap: 10px; }
.inspector h2 { font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.06em; color: #9a9aa5; }
.inspector .dica { font-size: 0.85rem; color: #9a9aa5; }
.inspector .resumo { font-size: 0.85rem; }
.campo { display: flex; flex-direction: column; gap: 3px; font-size: 0.8rem; color: #9a9aa5; }
.campo input, .campo select { background: #16161a; color: #e8e8ec; border: 1px solid #2c2c34; border-radius: 6px; padding: 6px 8px; font-size: 0.85rem; }
.ops { border: 1px solid #2c2c34; border-radius: 6px; padding: 8px; display: flex; flex-direction: column; gap: 4px; }
.ops legend { font-size: 0.75rem; color: #9a9aa5; padding: 0 4px; }
.op-radio { display: flex; gap: 6px; font-size: 0.85rem; align-items: center; }
.btn { background: #26262e; color: #e8e8ec; border: 1px solid #3a3a46; border-radius: 6px; padding: 8px 10px; font-size: 0.85rem; cursor: pointer; }
.btn:hover { background: #2e2e38; }
.btn.primario { background: #2a4a6a; border-color: #4e79a7; }
.btn:disabled { opacity: 0.5; cursor: default; }
.msg { font-size: 0.8rem; color: #9a9aa5; word-break: break-all; }
```

- [ ] **Step 4: Verificar**

Run: `npm --prefix web test && npm --prefix web run build && .venv/Scripts/python -m pytest -q`
Expected: tudo verde

- [ ] **Step 5: Commit**

```bash
git add web/src/components/Inspector.jsx web/src/App.jsx web/src/styles.css
git commit -m "feat: painel inspetor — aplicar operação/grupo/rótulo e salvar receita"
```

---

### Task 7: Preview antes/depois

**Files:**
- Modify: `web/src/components/Inspector.jsx` (botões pré-visualizar / antes / depois / fechar + faces antes→depois)
- Modify: `web/src/components/Viewport.jsx` (efeito de overlay do preview)
- Modify: `web/src/styles.css` (bloco .preview)

**Interfaces:**
- Consumes: `previewComponent` (client.js); prop `preview` (`{componentId, url, facesBefore, facesAfter, mostrando: "antes"|"depois"}`) e setters já passados pelo App (Task 5/6).
- Produces: no Inspector, botão "Pré-visualizar" chama POST e entra no modo preview mostrando "depois"; toggle antes/depois; "fechar" revoga o objectURL (via `onClearPreview`). No Viewport: `mostrando === "depois"` esconde as malhas originais da família e carrega o GLB do preview num grupo próprio (cor do grupo + emissivo de seleção); `"antes"` mostra as originais; sair do preview restaura tudo e faz dispose.

- [ ] **Step 1: Efeito de preview no Viewport**

Em `web/src/components/Viewport.jsx`, acrescentar um ref no topo do componente (junto aos outros):
```jsx
  const previewGroupRef = useRef(null);
  const sceneRef = useRef(null);
```
No efeito principal (`[state]`), logo após `const scene = new THREE.Scene();` acrescentar:
```jsx
    sceneRef.current = scene;
```
E no cleanup do mesmo efeito, antes de `disposeSceneResources(scene);`:
```jsx
      previewGroupRef.current = null;
      sceneRef.current = null;
```
Acrescentar, depois do efeito de destaque, o efeito do preview:
```jsx
  // overlay de preview: "depois" esconde as originais da família e mostra o
  // GLB pré-visualizado; "antes" (ou sem preview) restaura as originais
  useEffect(() => {
    const scene = sceneRef.current;
    if (!scene) return;
    const restore = () => {
      if (previewGroupRef.current) {
        scene.remove(previewGroupRef.current);
        disposeSceneResources(previewGroupRef.current);
        previewGroupRef.current = null;
      }
      for (const meshes of meshesByCompRef.current.values()) {
        for (const m of meshes) m.visible = true;
      }
    };
    restore();
    if (!preview || preview.mostrando !== "depois") return;

    const originals = meshesByCompRef.current.get(preview.componentId) || [];
    for (const m of originals) m.visible = false;

    const groupNames = state.groups.map((g) => g.name);
    const groupOf = {};
    for (const c of state.components) groupOf[c.id] = c.group;
    let disposed = false;
    new GLTFLoader().load(
      preview.url,
      (gltf) => {
        if (disposed) {
          disposeSceneResources(gltf.scene);
          return;
        }
        gltf.scene.traverse((obj) => {
          if (obj.isMesh) {
            if (!obj.geometry.attributes.normal) obj.geometry.computeVertexNormals();
            obj.material = new THREE.MeshStandardMaterial({
              color: groupColor(groupOf[preview.componentId], groupNames),
              emissive: SELECT_EMISSIVE,
              metalness: 0.1,
              roughness: 0.75,
              side: THREE.DoubleSide,
            });
          }
        });
        previewGroupRef.current = gltf.scene;
        scene.add(gltf.scene);
      },
      undefined,
      (err) => console.error("falha ao carregar o preview", err),
    );
    return () => {
      disposed = true;
      restore();
    };
  }, [preview, state]);
```

- [ ] **Step 2: Botões de preview no Inspector**

Em `web/src/components/Inspector.jsx`: importar `previewComponent` junto ao `patchComponent`:
```jsx
import { patchComponent, previewComponent, saveRecipe } from "../lib/client.js";
```
Acrescentar o handler depois de `aplicar`:
```jsx
  const preVisualizar = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const p = await previewComponent(entry.id, {
        type: opType,
        params: coerceParams(opType, params),
      });
      onPreviewChange({ componentId: entry.id, ...p, mostrando: "depois" });
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };
```
E no JSX, entre `<ParamsForm …/>` e o campo de grupo, acrescentar:
```jsx
          <div className="preview-bloco">
            <button className="btn" disabled={busy} onClick={preVisualizar}>
              Pré-visualizar
            </button>
            {preview && preview.componentId === entry.id && (
              <div className="preview">
                <span>
                  {formatFaces(preview.facesBefore)} → {formatFaces(preview.facesAfter)} f
                </span>
                <button
                  className={"btn mini" + (preview.mostrando === "antes" ? " ativo" : "")}
                  onClick={() => onPreviewChange({ ...preview, mostrando: "antes" })}
                >
                  antes
                </button>
                <button
                  className={"btn mini" + (preview.mostrando === "depois" ? " ativo" : "")}
                  onClick={() => onPreviewChange({ ...preview, mostrando: "depois" })}
                >
                  depois
                </button>
                <button className="btn mini" onClick={onClearPreview}>
                  fechar
                </button>
              </div>
            )}
          </div>
```

- [ ] **Step 3: CSS do preview**

Acrescentar ao final de `web/src/styles.css`:
```css
.preview-bloco { display: flex; flex-direction: column; gap: 6px; }
.preview { display: flex; gap: 6px; align-items: center; font-size: 0.8rem; flex-wrap: wrap; }
.btn.mini { padding: 3px 8px; font-size: 0.75rem; }
.btn.mini.ativo { background: #2a4a6a; border-color: #4e79a7; }
```

- [ ] **Step 4: Verificar**

Run: `npm --prefix web test && npm --prefix web run build && .venv/Scripts/python -m pytest -q`
Expected: tudo verde

- [ ] **Step 5: Commit**

```bash
git add web/src/components/Inspector.jsx web/src/components/Viewport.jsx web/src/styles.css
git commit -m "feat: preview antes/depois de operação no viewport"
```

---

### Task 8: Verificação e2e no navegador + documentação

> **Nota de execução:** o smoke visual desta task é executado PELO CONTROLADOR
> (painel de browser visível — abas ocultas não disparam requestAnimationFrame).
> O subagente desta task faz apenas os passos de documentação (Steps 4-6); os
> Steps 1-3 são do controlador, antes do review final.

**Files:**
- Modify: `README.md`
- Modify: `CLAUDE.md`

- [ ] **Step 1 (controlador): Servir cena de duas peças**

1. `npm --prefix web run build`
2. Gerar STL sintético (caixa 400×300×20 + cilindro r15 h350) num tmp, `meshbench init`, editar a receita para 2 grupos (`fixa`/`movel`, um componente em cada, operação keep) e `meshbench serve receita --no-browser`.

- [ ] **Step 2 (controlador): Critérios de aceite da Fase 3 (§14)**

No navegador de preview, validar com screenshots:
- Clicar numa peça no viewport → família destacada (emissivo) + linha selecionada na lista + inspetor preenchido.
- Clicar na linha da outra família na lista → destaque migra no viewport.
- Trocar a operação para `decimar` percent 50 → **Aplicar** → contagem de faces do grupo cai na barra de status (ao vivo) e o badge da lista muda.
- **Pré-visualizar** `decimar` na outra peça → faces antes→depois no inspetor; alternar antes/depois muda o viewport; fechar restaura.
- Atribuir grupo novo pelo campo "novo grupo" → Aplicar → grupo aparece na lista e na barra de status com cor própria.
- **Salvar receita** → mensagem com o caminho; arquivo `.meshbench.json` existe e contém as edições.
- Console do navegador sem erros em todo o fluxo.

- [ ] **Step 3 (controlador): Encerrar o servidor**

- [ ] **Step 4: Atualizar README.md**

Trocar a seção "## Viewport 3D (Fase 2)" por:
```markdown
## Viewport 3D (Fases 2–3)

    meshbench serve peça.stl              # abre o editor 3D no navegador
    meshbench serve receita.meshbench.json

No navegador: clique numa peça (viewport ou lista) para selecionar a família,
atribua operação/grupo/rótulo no inspetor, pré-visualize antes/depois e salve a
receita. A contagem de faces por grupo atualiza ao vivo contra o orçamento de
15k. Escala/orientação/origem interativas vêm nas fases 4–5.
```
(Manter a subseção "### Desenvolvimento do frontend" como está.)

- [ ] **Step 5: Atualizar CLAUDE.md**

Trocar a linha de status "Phases 1 (core+CLI) and 2 (read-only viewport: FastAPI + React/Three.js in `web/`) are implemented. Phases 3+ (selection, interactive ops, gizmos) are not yet." por:
```markdown
Phases 1 (core+CLI), 2 (viewport) and 3 (selection + interactive ops + preview + save) are implemented. Phases 4+ (interactive scale/orient/origin, export UI, gizmos) are not yet.
```

- [ ] **Step 6: Rodar tudo e commitar**

Run: `.venv/Scripts/python -m pytest -q && npm --prefix web test && npm --prefix web run build`
Expected: tudo verde

```bash
git add README.md CLAUDE.md
git commit -m "docs: fase 3 — edição interativa documentada"
```
