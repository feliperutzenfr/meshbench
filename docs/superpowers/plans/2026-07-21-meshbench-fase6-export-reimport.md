# MeshBench Fase 6 — Export, Re-importar e Abrir Receita na UI — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Trazer para a interface web o que a CLI já faz — exportar os arquivos (barra EXPORTA com formato, pasta, nome e semáforo de faces), re-importar o source re-casando por assinatura, e abrir outra receita `.meshbench.json` sem reiniciar o servidor.

**Architecture:** O motor já exporta (`run()`) e re-casa (`rematch()`); esta fase extrai a escrita para uma função reutilizável `write_export(records, project, base_dir)` que parte dos registros JÁ processados da sessão (não relê o source, não reprocessa), e expõe quatro rotas: `PATCH /api/export` (config inerte: formato/pasta/nome), `POST /api/export` (gera), `POST /api/project/reimport` (rematch + re-baseline) e `POST /api/project/open` (troca o projeto da sessão). O frontend ganha a barra EXPORTA e um bloco "Projeto" na barra lateral (salvar / re-importar / abrir).

**Tech Stack:** FastAPI + trimesh/ezdxf (backend), React 19 + Vite (frontend), pytest + vitest.

## Global Constraints

- Strings de UI, docstrings, mensagens de erro e commits em **pt-BR**; identificadores de código em **inglês**.
- Commits em Conventional Commits terminando com `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Python: `.venv/Scripts/python -m pytest` (nunca `pytest` direto). Frontend: `npm --prefix web run build|test`.
- Branch de trabalho: `fase-6-export-reimport` (criar a partir de `main` no início da Task 1).
- Ordem do pipeline é inegociável: EXPORT é a última etapa; a exportação parte dos registros já processados (pós-origem), NUNCA reprocessa nem relê o source.
- **Formatos aceitos:** `dxf_r12` (alvo Promob), `stl`, `obj`. DXF R12 usa entidades `3DFACE`.
- **Orçamento de faces (semáforo):** verde ≤ 8000, amarelo ≤ 15000, vermelho > 15000. `FACE_BUDGET = 15000`.
- `out_dir` é configurável: caminho absoluto usado como está; caminho relativo resolvido **relativo à pasta da receita/do source** (`base_dir`), nunca ao diretório do app. O padrão é `out/`.
- `naming` deve conter `{group}` (senão grupos diferentes sobrescrevem o mesmo arquivo).
- App local-only (127.0.0.1); abrir receita por caminho do sistema de arquivos é aceitável.
- Config de export é inerte (não muda geometria): `PATCH /api/export` não reprocessa e não entra no desfazer.
- Re-importar e abrir são re-baseline: descartam o histórico de desfazer/refazer (os snapshots referem-se à malha antiga em cache).

---

### Task 1: Backend — `write_export` reutilizável + `PATCH`/`POST /api/export`

**Files:**
- Modify: `src/meshbench/core/pipeline.py` (extrair `write_export` de `run`)
- Modify: `src/meshbench/api/session_ops.py` (append `_validated_export`, `update_export`, `export_project`)
- Modify: `src/meshbench/api/server.py` (import, campo `export` no estado, 2 rotas)
- Test: Create `tests/test_api_export.py`; append em `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `write_meshes`, `FACE_BUDGET`, `PipelineResult` (já em pipeline.py); `session.records`/`session.warnings`/`session.base_dir` (sessão).
- Produces: `write_export(records, project, base_dir, warnings=None) -> PipelineResult` (em pipeline.py); `_validated_export(current, changes) -> dict`, `update_export(session, changes)`, `export_project(session) -> PipelineResult` (em session_ops.py); rotas `PATCH /api/export` (200 → estado; 422 ValueError pt-BR) e `POST /api/export` (200 → `{"files": [{path, group, faces}], "warnings": [...]}`); campo de estado `export` (dict da receita). O frontend (Task 3+) consome tudo isto.

- [ ] **Step 1: Escrever os testes que falham**

Create `tests/test_api_export.py`:

```python
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session


def _client(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_export_no_estado(tmp_path, box):
    client, _ = _client(tmp_path, box)
    state = client.get("/api/project").json()
    assert state["export"]["format"] == "dxf_r12"
    assert state["export"]["out_dir"] == "out/"
    assert "{group}" in state["export"]["naming"]


def test_patch_export_config(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch(
        "/api/export",
        json={"format": "stl", "out_dir": "saida_x/", "naming": "{project}_{group}.stl"},
    )
    assert r.status_code == 200
    exp = r.json()["export"]
    assert exp == {"format": "stl", "out_dir": "saida_x/", "naming": "{project}_{group}.stl"}


def test_patch_export_validacoes_422(tmp_path, box):
    client, _ = _client(tmp_path, box)
    casos = [
        ({"format": "png"}, "formato"),
        ({"out_dir": "   "}, "out_dir"),
        ({"out_dir": 5}, "out_dir"),
        ({"naming": "fixo.dxf"}, "{group}"),
    ]
    for body, trecho in casos:
        r = client.patch("/api/export", json=body)
        assert r.status_code == 422, body
        assert trecho in r.json()["detail"], body


def test_post_export_grava_arquivos(tmp_path, box):
    client, _ = _client(tmp_path, box)
    out = tmp_path / "exportado"
    client.patch("/api/export", json={"out_dir": str(out), "naming": "{group}.dxf"})
    r = client.post("/api/export")
    assert r.status_code == 200
    body = r.json()
    assert len(body["files"]) == 1
    f = body["files"][0]
    assert f["group"] == "saida"
    assert f["faces"] == 12
    assert Path(f["path"]).exists()
    assert Path(f["path"]) == out / "saida.dxf"


def test_post_export_sem_saida(tmp_path, box):
    client, session = _client(tmp_path, box)
    # remove a única peça → nada a exportar
    comp = session.project.components[0].id
    client.patch(f"/api/component/{comp}", json={"operation": {"type": "remove"}})
    r = client.post("/api/export")
    assert r.status_code == 200
    assert r.json()["files"] == []
```

Append em `tests/test_pipeline.py`:

```python
def test_write_export_parte_de_registros_prontos(tmp_path, box):
    """write_export escreve a partir de registros já processados, sem reler o
    source nem reprocessar — run() é só process() + write_export()."""
    from meshbench.core.pipeline import process, write_export
    from meshbench.core.project import new_project
    from meshbench.core.analyze.components import split_components

    p = tmp_path / "caixa.stl"
    box.export(str(p))
    project = new_project("caixa", p, box, split_components(box))
    project.export["out_dir"] = str(tmp_path / "out")
    records, warnings = process(project, tmp_path, mesh=box)
    res = write_export(records, project, tmp_path, warnings)
    assert len(res.files) == 1
    assert res.files[0]["faces"] == 12
    from pathlib import Path
    assert Path(res.files[0]["path"]).exists()
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_api_export.py tests/test_pipeline.py::test_write_export_parte_de_registros_prontos -v`
Expected: FAIL — `ImportError: cannot import name 'write_export'` e rotas 404/405.

- [ ] **Step 3: Extrair `write_export` em `pipeline.py`**

Em `src/meshbench/core/pipeline.py`, substituir a função `run` inteira (atualmente da linha `def run(project, base_dir):` até o `return result`) por estas DUAS funções:

```python
def write_export(records, project, base_dir, warnings=None):
    """Escreve um arquivo por grupo a partir de registros JÁ processados.

    Não relê o source nem reprocessa — recebe os registros prontos (pós-origem).
    A ordem de emissão é a de DECLARAÇÃO em project.groups, depois qualquer grupo
    implícito na ordem encontrada. `warnings` inicial (ex.: do process) é copiado
    e estendido com os avisos de orçamento; a lista recebida não é mutada.
    """
    base_dir = Path(base_dir)
    result = PipelineResult(warnings=list(warnings) if warnings else [])

    grouped = {}
    for r in records:
        grouped.setdefault(r.group, []).append(r.mesh)

    group_order = [g["name"] for g in project.groups]
    for g in grouped:
        if g not in group_order:
            group_order.append(g)

    out_dir = Path(project.export.get("out_dir", "out/"))
    if not out_dir.is_absolute():
        out_dir = base_dir / out_dir
    fmt = project.export.get("format", "dxf_r12")
    ext = {"dxf_r12": "dxf", "stl": "stl", "obj": "obj"}.get(fmt)
    if ext is None:
        raise ValueError(f"formato de exportação '{fmt}' não suportado")
    naming = project.export.get("naming", "{project}_{group}." + ext)
    for g in group_order:
        ms = grouped.get(g)
        if not ms:
            continue
        name = naming.format(project=project.name, group=g)
        path = out_dir / name
        write_meshes(ms, path, fmt)
        faces = sum(len(m.faces) for m in ms)
        if faces > FACE_BUDGET:
            result.warnings.append(
                f"grupo '{g}' tem {faces} faces (> {FACE_BUDGET}) — pode não abrir no Promob"
            )
        result.files.append({"path": str(path), "group": g, "faces": faces})
    return result


def run(project, base_dir):
    """Executa a receita completa e exporta um arquivo por grupo."""
    base_dir = Path(base_dir)
    records, warnings = process(project, base_dir)
    return write_export(records, project, base_dir, warnings)
```

- [ ] **Step 4: `_validated_export` + `update_export` + `export_project` em `session_ops.py`**

No topo de `src/meshbench/api/session_ops.py`, acrescentar ao import existente de pipeline:

```python
from meshbench.core.pipeline import process, write_export
```

(era `from meshbench.core.pipeline import process`.)

No fim do arquivo:

```python
_EXPORT_FORMATS = ("dxf_r12", "stl", "obj")


def _validated_export(current, changes):
    """Monta o dict de export completo a partir do atual + mudanças. ValueError pt-BR."""
    fmt = changes.get("format", current.get("format", "dxf_r12"))
    if fmt not in _EXPORT_FORMATS:
        raise ValueError(
            f"formato '{fmt}' desconhecido (disponíveis: {sorted(_EXPORT_FORMATS)})"
        )
    out_dir = changes.get("out_dir", current.get("out_dir", "out/"))
    if not isinstance(out_dir, str) or not out_dir.strip():
        raise ValueError("out_dir deve ser um caminho não vazio")
    naming = changes.get("naming", current.get("naming", "{project}_{group}.dxf"))
    if not isinstance(naming, str) or "{group}" not in naming:
        raise ValueError(
            "naming deve conter {group} — senão grupos diferentes sobrescrevem o mesmo arquivo"
        )
    return {"format": fmt, "out_dir": out_dir, "naming": naming}


def update_export(session, changes):
    """Atualiza a configuração de export (formato, out_dir, naming).

    Config inerte: não reprocessa e não entra no desfazer — não muda a geometria,
    só onde/como os arquivos finais são escritos.
    """
    with session.lock:
        session.project.export = _validated_export(session.project.export, changes)


def export_project(session):
    """Gera os arquivos a partir dos registros já processados da sessão.

    Não reprocessa nem relê o source — usa session.records. Devolve o
    PipelineResult (files + warnings), incluindo os avisos do último process.
    """
    with session.lock:
        return write_export(
            session.records, session.project, session.base_dir, session.warnings
        )
```

- [ ] **Step 5: Rotas + campo de estado em `server.py`**

Em `src/meshbench/api/server.py`:

1. Acrescentar `export_project` e `update_export` ao import de `meshbench.api.session_ops` (junto de `preview_op`, `update_orient` etc.).

2. Em `_project_state`, logo após a linha `"orient": session.project.orient,`:

```python
            "export": session.project.export,
```

3. Rotas, logo após `patch_origin`:

```python
    @app.patch("/api/export")
    def patch_export(changes: dict):
        try:
            update_export(session, changes)
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.post("/api/export")
    def post_export():
        try:
            result = export_project(session)
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse({"files": result.files, "warnings": result.warnings})
```

- [ ] **Step 6: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_api_export.py tests/test_pipeline.py -v`
Expected: PASS (todos).

Run: `.venv/Scripts/python -m pytest`
Expected: PASS — nenhuma regressão (run() delegando a write_export mantém CLI e regressão de ouro verdes).

- [ ] **Step 7: Commit**

```bash
git add src/meshbench/core/pipeline.py src/meshbench/api/session_ops.py src/meshbench/api/server.py tests/test_api_export.py tests/test_pipeline.py
git commit -m "feat: PATCH/POST /api/export — write_export reutilizável a partir dos registros da sessão"
```

---

### Task 2: Backend — re-importar source + abrir outra receita

**Files:**
- Modify: `src/meshbench/api/session_ops.py` (append `reimport_project`)
- Modify: `src/meshbench/api/server.py` (refatorar `load_session` → `_load_fields`; adicionar `open_project` + 2 rotas)
- Test: Create `tests/test_api_project_io.py`

**Interfaces:**
- Consumes: `rematch` (de `meshbench.core.project`), `split_components`, `read_mesh`, `reprocess` (session_ops), `Project`/`new_project`/`process` (server).
- Produces: `reimport_project(session) -> list[str]` (avisos de rematch; em session_ops); `_load_fields(path) -> dict` e `open_project(session, path)` (em server); rotas `POST /api/project/reimport` e `POST /api/project/open` (corpo `{"path": "..."}`), ambas 200 → estado completo, 404 FileNotFoundError, 422 ValueError. Ambas resetam desfazer/refazer.

- [ ] **Step 1: Escrever os testes que falham**

Create `tests/test_api_project_io.py`:

```python
import pytest
from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session


def _client(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_reimport_preserva_escolhas_e_reseta_undo(tmp_path, box):
    client, session = _client(tmp_path, box)
    comp = session.project.components[0].id
    client.patch(f"/api/component/{comp}", json={"user_label": "tampo"})
    assert len(session.undo_stack) == 1
    rev0 = session.revision

    r = client.post("/api/project/reimport")
    assert r.status_code == 200
    state = r.json()
    # o rematch por assinatura preserva o rótulo do usuário
    assert state["components"][0]["user_label"] == "tampo"
    # re-baseline: histórico descartado, revision avança
    assert state["can_undo"] is False and state["can_redo"] is False
    assert len(session.undo_stack) == 0
    assert state["revision"] > rev0


def test_open_troca_projeto_e_reseta(tmp_path, box, small_sphere):
    client, session = _client(tmp_path, box)
    comp = session.project.components[0].id
    client.patch(f"/api/component/{comp}", json={"user_label": "x"})
    assert len(session.undo_stack) == 1

    p2 = tmp_path / "esfera.stl"
    small_sphere.export(str(p2))
    r = client.post("/api/project/open", json={"path": str(p2)})
    assert r.status_code == 200
    state = r.json()
    assert state["name"] == "esfera"
    assert state["can_undo"] is False
    assert len(session.undo_stack) == 0
    assert session.recipe_path.name == "esfera.meshbench.json"
    # a geometria da nova sessão carrega
    assert client.get("/api/project/geometry").status_code == 200


def test_open_arquivo_inexistente_404(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.post("/api/project/open", json={"path": str(tmp_path / "nao_existe.stl")})
    assert r.status_code == 404
    assert "não encontrado" in r.json()["detail"]


def test_open_path_invalido_422(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.post("/api/project/open", json={"path": ""})
    assert r.status_code == 422
    assert "path" in r.json()["detail"]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_api_project_io.py -v`
Expected: FAIL — rotas inexistentes (404/405).

- [ ] **Step 3: `reimport_project` em `session_ops.py`**

No topo de `src/meshbench/api/session_ops.py`, acrescentar os imports:

```python
from pathlib import Path

from meshbench.core.analyze.components import split_components
from meshbench.core.io.readers import read_mesh
```

E trocar `from meshbench.core.project import Project` por:

```python
from meshbench.core.project import Project, rematch
```

No fim do arquivo:

```python
def reimport_project(session):
    """Re-lê o source e re-casa componentes por assinatura, preservando escolhas.

    Re-baseline: descarta desfazer/refazer (os snapshots referem-se à malha antiga
    em cache) e invalida o cache de GLB. Devolve os avisos do rematch (peças novas
    a revisar / peças que sumiram do source).
    """
    with session.lock:
        src = Path(session.project.source["path"])
        if not src.is_absolute():
            src = session.base_dir / src
        if not src.exists():
            raise FileNotFoundError(f"source não encontrado: {src}")
        mesh = read_mesh(src)
        new_project, rematch_warnings = rematch(
            session.project, split_components(mesh)
        )
        session.project = new_project
        session.raw_mesh = mesh
        reprocess(session)  # usa a nova raw_mesh; seta session.warnings e revision
        session.warnings = list(session.warnings) + rematch_warnings
        session.undo_stack.clear()
        session.redo_stack.clear()
        session.glb_cache = None
        return rematch_warnings
```

- [ ] **Step 4: `_load_fields` + `open_project` + rotas em `server.py`**

Em `src/meshbench/api/server.py`:

1. Acrescentar `reimport_project` ao import de `meshbench.api.session_ops`.

2. Substituir a função `load_session` inteira por estas duas:

```python
def _load_fields(path):
    """Lê uma receita .json ou um arquivo de malha e devolve os campos derivados."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"arquivo não encontrado: {path}")
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
    return {
        "project": project,
        "base_dir": base_dir,
        "records": records,
        "warnings": warnings,
        "raw_mesh": raw_mesh,
        "recipe_path": recipe_path,
    }


def load_session(path):
    """Carrega uma receita .meshbench.json OU um arquivo de malha (projeto virtual)."""
    return ProjectSession(**_load_fields(path))


def open_project(session, path):
    """Carrega outra receita/malha na sessão existente, substituindo tudo.

    Reseta desfazer/refazer, o cache de GLB e a revision — é um projeto novo. Se a
    leitura falhar, ergue antes de mutar a sessão (o estado antigo fica intacto).
    """
    with session.lock:
        fields = _load_fields(path)  # pode erguer FileNotFoundError/ValueError
        session.project = fields["project"]
        session.base_dir = fields["base_dir"]
        session.records = fields["records"]
        session.warnings = fields["warnings"]
        session.raw_mesh = fields["raw_mesh"]
        session.recipe_path = fields["recipe_path"]
        session.revision += 1
        session.glb_cache = None
        session.undo_stack.clear()
        session.redo_stack.clear()
```

3. Rotas, logo após `post_export`:

```python
    @app.post("/api/project/reimport")
    def post_reimport():
        try:
            reimport_project(session)
        except FileNotFoundError as e:
            return JSONResponse(status_code=404, content={"detail": str(e)})
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.post("/api/project/open")
    def post_open(body: dict):
        path = body.get("path")
        if not isinstance(path, str) or not path.strip():
            return JSONResponse(
                status_code=422, content={"detail": "path deve ser um caminho não vazio"}
            )
        try:
            open_project(session, path.strip())
        except FileNotFoundError as e:
            return JSONResponse(status_code=404, content={"detail": str(e)})
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))
```

- [ ] **Step 5: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_api_project_io.py -v`
Expected: PASS (todos).

Run: `.venv/Scripts/python -m pytest`
Expected: PASS — suíte inteira verde (a refatoração de `load_session` é transparente para os testes existentes).

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/api/session_ops.py src/meshbench/api/server.py tests/test_api_project_io.py
git commit -m "feat: POST /api/project/reimport e /api/project/open com re-baseline do histórico"
```

---

### Task 3: Frontend lib — `export.js`, cliente HTTP

**Files:**
- Create: `web/src/lib/export.js`
- Create: `web/src/lib/export.test.js`
- Modify: `web/src/lib/client.js` (append 4 funções)

**Interfaces:**
- Consumes: rotas da Task 1 e 2.
- Produces: `patchExport(changes)`, `postExport()` (→ `{files, warnings}`), `postReimport()` (→ estado), `openRecipe(path)` (→ estado) em `client.js`; `FORMAT_LABELS`, `FORMAT_EXT`, `budgetClass(faces, budget) -> "verde"|"amarelo"|"vermelho"`, `namingForFormat(naming, format) -> string`, `validNaming(naming) -> boolean` em `export.js`. As Tasks 4 e 5 consomem estes nomes.

- [ ] **Step 1: Escrever os testes que falham**

Create `web/src/lib/export.test.js`:

```js
import { describe, expect, it } from "vitest";
import {
  FORMAT_LABELS,
  budgetClass,
  namingForFormat,
  validNaming,
} from "./export.js";

describe("FORMAT_LABELS", () => {
  it("cobre os 3 formatos e destaca o alvo Promob", () => {
    expect(Object.keys(FORMAT_LABELS)).toEqual(["dxf_r12", "stl", "obj"]);
    expect(FORMAT_LABELS.dxf_r12).toMatch(/Promob/);
  });
});

describe("budgetClass", () => {
  it("semáforo: verde ≤8k, amarelo ≤15k, vermelho acima", () => {
    expect(budgetClass(2000, 15000)).toBe("verde");
    expect(budgetClass(8000, 15000)).toBe("verde");
    expect(budgetClass(8001, 15000)).toBe("amarelo");
    expect(budgetClass(15000, 15000)).toBe("amarelo");
    expect(budgetClass(15001, 15000)).toBe("vermelho");
  });
});

describe("namingForFormat", () => {
  it("troca a extensão do nome para casar com o formato", () => {
    expect(namingForFormat("{project}_{group}.dxf", "stl")).toBe("{project}_{group}.stl");
    expect(namingForFormat("{group}.stl", "dxf_r12")).toBe("{group}.dxf");
    expect(namingForFormat("{group}.obj", "obj")).toBe("{group}.obj");
  });

  it("não confunde os pontos dos placeholders com a extensão", () => {
    // sem extensão real: acrescenta a do formato em vez de mexer no {group}
    expect(namingForFormat("{group}", "stl")).toBe("{group}.stl");
  });
});

describe("validNaming", () => {
  it("exige o placeholder {group}", () => {
    expect(validNaming("{project}_{group}.dxf")).toBe(true);
    expect(validNaming("fixo.dxf")).toBe(false);
    expect(validNaming(null)).toBe(false);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix web test`
Expected: FAIL — `export.js` não existe.

- [ ] **Step 3: Implementar**

Create `web/src/lib/export.js`:

```js
// Export (§10 do doc): DXF R12 (3DFACE) é o alvo Promob; STL/OBJ para outros usos.
// O semáforo de faces reflete o orçamento empírico do Promob (§ orçamento).
export const FORMAT_LABELS = {
  dxf_r12: "DXF R12 (3DFACE) — Promob",
  stl: "STL",
  obj: "OBJ",
};

export const FORMAT_EXT = { dxf_r12: "dxf", stl: "stl", obj: "obj" };

// semáforo: verde até 8000 (fixo, conforme o doc); o parâmetro `budget` (15000)
// controla só a fronteira amarelo/vermelho.
export function budgetClass(faces, budget = 15000) {
  if (faces <= 8000) return "verde";
  if (faces <= budget) return "amarelo";
  return "vermelho";
}

// troca só a extensão FINAL do nome; um segmento final sem ponto (ex.: "{group}")
// recebe a extensão do formato acrescentada. Não toca nos pontos dos placeholders.
export function namingForFormat(naming, format) {
  const ext = FORMAT_EXT[format] || "dxf";
  if (/\.[a-z0-9]+$/i.test(naming)) return naming.replace(/\.[a-z0-9]+$/i, "." + ext);
  return naming + "." + ext;
}

export function validNaming(naming) {
  return typeof naming === "string" && naming.includes("{group}");
}
```

Append em `web/src/lib/client.js` (antes do export de `geometryUrl`):

```js
export async function patchExport(changes) {
  const r = await checkOk(
    await fetch("/api/export", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),
  );
  return r.json();
}

export async function postExport() {
  const r = await checkOk(await fetch("/api/export", { method: "POST" }));
  return r.json();
}

export async function postReimport() {
  const r = await checkOk(await fetch("/api/project/reimport", { method: "POST" }));
  return r.json();
}

export async function openRecipe(path) {
  const r = await checkOk(
    await fetch("/api/project/open", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ path }),
    }),
  );
  return r.json();
}
```

- [ ] **Step 4: Rodar os testes**

Run: `npm --prefix web test`
Expected: PASS (suíte vitest inteira).

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/export.js web/src/lib/export.test.js web/src/lib/client.js
git commit -m "feat: lib de export (formatos, semáforo, naming) e cliente HTTP export/reimport/open"
```

---

### Task 4: Barra EXPORTA + wiring no App + CSS

**Files:**
- Create: `web/src/components/ExportBar.jsx`
- Modify: `web/src/App.jsx`
- Modify: `web/src/styles.css`

**Interfaces:**
- Consumes: `patchExport`, `postExport` (client), `FORMAT_LABELS`, `budgetClass`, `namingForFormat`, `validNaming` (export.js), `formatFaces` (format.js); campo de estado `export` e `face_budget`.
- Produces: `ExportBar({ state, onStateChange })`; no App, `ExportBar` renderizado numa nova linha do grid entre a barra ORIGEM e a StatusBar. A Task 5 é independente desta.

- [ ] **Step 1: Criar `web/src/components/ExportBar.jsx`**

```jsx
import { useEffect, useState } from "react";
import { patchExport, postExport } from "../lib/client.js";
import { formatFaces } from "../lib/format.js";
import { FORMAT_LABELS, budgetClass, namingForFormat, validNaming } from "../lib/export.js";

function dirDe(caminho) {
  // pasta do primeiro arquivo (separador \ ou /), para dizer onde caíram
  const i = Math.max(caminho.lastIndexOf("/"), caminho.lastIndexOf("\\"));
  return i >= 0 ? caminho.slice(0, i) : caminho;
}

export default function ExportBar({ state, onStateChange }) {
  const exp = state.export || {};
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [result, setResult] = useState(null); // {files, warnings}
  const [outDir, setOutDir] = useState(exp.out_dir || "out/");
  const [naming, setNaming] = useState(exp.naming || "{project}_{group}.dxf");

  // sincroniza os campos com a config vigente; keyed no conteúdo para não
  // descartar edição em andamento em mutações não relacionadas
  const expJson = JSON.stringify(exp);
  useEffect(() => {
    setOutDir(exp.out_dir || "out/");
    setNaming(exp.naming || "{project}_{group}.dxf");
  }, [expJson]); // eslint-disable-line react-hooks/exhaustive-deps

  const salvarConfig = async (changes) => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await patchExport(changes));
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const trocarFormato = (fmt) => {
    const novoNaming = namingForFormat(naming, fmt);
    setNaming(novoNaming);
    salvarConfig({ format: fmt, out_dir: outDir, naming: novoNaming });
  };

  const aplicarConfig = () => {
    if (!validNaming(naming)) {
      setMsg("erro: nome deve conter {group}");
      return;
    }
    salvarConfig({ out_dir: outDir, naming });
  };

  const gerar = async () => {
    if (!validNaming(naming)) {
      setMsg("erro: nome deve conter {group}");
      return;
    }
    setBusy(true);
    setMsg(null);
    setResult(null);
    try {
      // grava a config vigente (pasta/nome digitados) antes de gerar
      await patchExport({ format: exp.format, out_dir: outDir, naming });
      const r = await postExport();
      setResult(r);
      setMsg(r.files.length ? "exportado ✓" : "nenhum arquivo — confira grupos e operações");
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  return (
    <div className="exportbar">
      <span className="rotulo">EXPORTA</span>
      <select value={exp.format} disabled={busy} onChange={(e) => trocarFormato(e.target.value)}>
        {Object.keys(FORMAT_LABELS).map((f) => (
          <option key={f} value={f}>
            {FORMAT_LABELS[f]}
          </option>
        ))}
      </select>
      <label className="campo-inline">
        <span>pasta</span>
        <input value={outDir} disabled={busy} onChange={(e) => setOutDir(e.target.value)} onBlur={aplicarConfig} />
      </label>
      <label className="campo-inline">
        <span>nome</span>
        <input value={naming} disabled={busy} onChange={(e) => setNaming(e.target.value)} onBlur={aplicarConfig} />
      </label>
      <button className="btn primario" disabled={busy} onClick={gerar}>
        Exportar
      </button>
      {result && result.files.length > 0 && (
        <span className="export-result">
          {result.files.map((f) => (
            <span key={f.group} className={"export-file " + budgetClass(f.faces, state.face_budget)} title={f.path}>
              {f.group}: {formatFaces(f.faces)} f
            </span>
          ))}
          <span className="export-dir">→ {dirDe(result.files[0].path)}</span>
        </span>
      )}
      {msg && <span className={"msg" + (msg.startsWith("erro") ? " erro" : "")}>{msg}</span>}
    </div>
  );
}
```

- [ ] **Step 2: Wiring no `web/src/App.jsx`**

Acrescentar o import (junto dos outros de components):

```jsx
import ExportBar from "./components/ExportBar.jsx";
```

E renderizar `ExportBar` logo após `OriginBar` no JSX:

```jsx
      <ExportBar state={state} onStateChange={handleStateChange} />
```

- [ ] **Step 3: CSS em `web/src/styles.css`**

Trocar o grid do `.app` para incluir a linha `exportbar` (entre `originbar` e `statusbar`):

```css
.app {
  display: grid;
  grid-template-columns: 300px 1fr 280px;
  grid-template-rows: 1fr auto auto auto auto auto;
  grid-template-areas:
    "sidebar viewport inspector"
    "sidebar scalebar scalebar"
    "sidebar orientbar orientbar"
    "sidebar originbar originbar"
    "sidebar exportbar exportbar"
    "sidebar statusbar statusbar";
  height: 100%;
}
```

Acrescentar no fim do arquivo:

```css
.exportbar { grid-area: exportbar; background: #1e1e24; border-top: 1px solid #2c2c34; padding: 8px 14px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.exportbar .rotulo { font-size: 0.75rem; letter-spacing: 0.06em; color: #9a9aa5; }
.exportbar select, .exportbar input { background: #16161a; color: #e8e8ec; border: 1px solid #2c2c34; border-radius: 6px; padding: 4px 6px; font-size: 0.82rem; }
.exportbar input { width: 200px; }
.export-result { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 0.8rem; }
.export-file { padding: 2px 8px; border-radius: 6px; }
.export-file.verde { background: #24361f; color: #8ac26f; }
.export-file.amarelo { background: #3a2f14; color: #f2b84b; }
.export-file.vermelho { background: #3a1f20; color: #e15759; }
.export-dir { color: #9a9aa5; }
.exportbar .msg { font-size: 0.78rem; color: #9a9aa5; }
.exportbar .msg.erro { color: #e15759; }
```

- [ ] **Step 4: Build e teste**

Run: `npm --prefix web run build`
Expected: build verde, sem erro de import.

Run: `npm --prefix web test`
Expected: PASS (nenhuma regressão).

- [ ] **Step 5: Commit**

```bash
git add web/src/components/ExportBar.jsx web/src/App.jsx web/src/styles.css
git commit -m "feat: barra EXPORTA — formato, pasta, nome, gerar e semáforo de faces por grupo"
```

---

### Task 5: Bloco "Projeto" na barra lateral (salvar / re-importar / abrir)

**Files:**
- Create: `web/src/components/ProjectActions.jsx`
- Modify: `web/src/components/Sidebar.jsx` (renderizar o bloco; novo prop `onStateChange`)
- Modify: `web/src/components/Inspector.jsx` (remover o botão "Salvar receita" daqui — passa a viver no bloco Projeto)
- Modify: `web/src/App.jsx` (passar `onStateChange` ao Sidebar; limpar seleção ao trocar de projeto)

**Interfaces:**
- Consumes: `saveRecipe` (já em client.js), `postReimport`, `openRecipe` (client.js, Task 3).
- Produces: `ProjectActions({ onStateChange })` — salvar (msg local), re-importar (troca estado), abrir receita (input de caminho + confirma, troca estado). Renderizado no rodapé do `Sidebar`.

- [ ] **Step 1: Criar `web/src/components/ProjectActions.jsx`**

```jsx
import { useState } from "react";
import { openRecipe, postReimport, saveRecipe } from "../lib/client.js";

export default function ProjectActions({ onStateChange }) {
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [abrindo, setAbrindo] = useState(false);
  const [caminho, setCaminho] = useState("");

  const salvar = async () => {
    setBusy(true);
    setMsg(null);
    try {
      const r = await saveRecipe();
      setMsg(`salva: ${r.path}`);
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const reimportar = async () => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await postReimport());
      setMsg("re-importado ✓ — confira as peças marcadas 'novo — revisar'");
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const abrir = async () => {
    if (!caminho.trim()) return;
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await openRecipe(caminho.trim()));
      setAbrindo(false);
      setCaminho("");
      setMsg("receita aberta ✓");
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  return (
    <section className="projeto-acoes">
      <h2>Projeto</h2>
      <button className="btn" disabled={busy} onClick={salvar}>
        Salvar receita
      </button>
      <button
        className="btn"
        disabled={busy}
        onClick={reimportar}
        title="re-lê o source do CAD e re-casa componentes por assinatura"
      >
        Re-importar source
      </button>
      {!abrindo ? (
        <button className="btn" disabled={busy} onClick={() => setAbrindo(true)}>
          Abrir receita…
        </button>
      ) : (
        <div className="abrir-receita">
          <input
            value={caminho}
            onChange={(e) => setCaminho(e.target.value)}
            placeholder="caminho da .meshbench.json"
            autoFocus
          />
          <span className="abrir-botoes">
            <button className="btn mini" disabled={busy} onClick={abrir}>
              abrir
            </button>
            <button className="btn mini" disabled={busy} onClick={() => setAbrindo(false)}>
              cancelar
            </button>
          </span>
        </div>
      )}
      {msg && <p className={"msg" + (msg.startsWith("erro") ? " erro" : "")}>{msg}</p>}
    </section>
  );
}
```

- [ ] **Step 2: Renderizar no `web/src/components/Sidebar.jsx`**

Acrescentar o import no topo:

```jsx
import ProjectActions from "./ProjectActions.jsx";
```

Trocar a assinatura do componente para receber `onStateChange`:

```jsx
export default function Sidebar({ state, selected, onSelect, onStateChange }) {
```

E, dentro do `<aside className="sidebar">`, logo antes de fechar `</aside>`, renderizar o bloco:

```jsx
      <ProjectActions onStateChange={onStateChange} />
```

- [ ] **Step 3: Remover o "Salvar receita" do `web/src/components/Inspector.jsx`**

1. No import da linha 2, remover `saveRecipe`:

```jsx
import { patchComponent, previewComponent } from "../lib/client.js";
```

2. Remover a função `salvar` inteira (o bloco `const salvar = async () => { … };`).

3. Remover o botão de salvar que fica logo antes de `{msg && …}` no final do JSX:

```jsx
      <button className="btn" disabled={busy} onClick={salvar}>
        Salvar receita
      </button>
```

(Deixar o `{msg && <p className="msg">{msg}</p>}` — o Inspetor ainda usa `msg` para o feedback de Aplicar/Pré-visualizar.)

- [ ] **Step 4: Wiring no `web/src/App.jsx`**

Passar `onStateChange` ao `Sidebar`. Como abrir/re-importar podem trocar o projeto inteiro (a peça selecionada pode deixar de existir), usar um handler que também limpa a seleção:

Trocar a linha do `<Sidebar .../>` por:

```jsx
      <Sidebar
        state={state}
        selected={selected}
        onSelect={handleSelect}
        onStateChange={(novo) => {
          setSelected(null);
          handleStateChange(novo);
        }}
      />
```

- [ ] **Step 5: CSS em `web/src/styles.css`**

Acrescentar no fim do arquivo:

```css
.projeto-acoes { margin-top: 18px; padding-top: 12px; border-top: 1px solid #2c2c34; display: flex; flex-direction: column; gap: 6px; }
.projeto-acoes .btn { text-align: left; }
.abrir-receita { display: flex; flex-direction: column; gap: 4px; }
.abrir-receita input { background: #16161a; color: #e8e8ec; border: 1px solid #2c2c34; border-radius: 6px; padding: 4px 6px; font-size: 0.8rem; }
.abrir-botoes { display: flex; gap: 4px; }
.projeto-acoes .msg { font-size: 0.76rem; color: #9a9aa5; word-break: break-all; }
.projeto-acoes .msg.erro { color: #e15759; }
```

- [ ] **Step 6: Build e teste**

Run: `npm --prefix web run build`
Expected: build verde.

Run: `npm --prefix web test`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add web/src/components/ProjectActions.jsx web/src/components/Sidebar.jsx web/src/components/Inspector.jsx web/src/App.jsx web/src/styles.css
git commit -m "feat: bloco Projeto na barra lateral — salvar, re-importar e abrir receita"
```

---

### Task 6: e2e no navegador + docs + revisão final + merge

**Files:**
- Modify: `README.md`, `CLAUDE.md`
- (verificação visual + documentação)

**Interfaces:**
- Consumes: tudo das Tasks 1–5.
- Produces: fases 1–6 completas e documentadas; evidência e2e de export/re-import/abrir no navegador real.

- [ ] **Step 1: Build + servidor + e2e dirigido por JS no painel do navegador**

```bash
npm --prefix web run build
```

Subir `serve` num STL de teste (gerar com o python da venv no scratchpad) e, no painel do navegador (técnica validada nas fases 3–5b: dirigir por `javascript_tool` com native setters + dispatchEvent; screenshots costumam falhar, usar rede/DOM/console para verificar):

1. **Export DXF**: barra EXPORTA visível; trocar a pasta para um caminho do scratchpad; "Exportar" → resultado por grupo com semáforo (cor conforme faces), linha "→ {pasta}", "exportado ✓"; confirmar no disco (`ls`) que o `.dxf` existe.
2. **Troca de formato**: mudar para STL → o nome troca a extensão para `.stl`; exportar → arquivo `.stl` no disco.
3. **Nome inválido**: apagar `{group}` do nome → "Exportar" recusa com "nome deve conter {group}".
4. **Re-importar**: no bloco Projeto, "Re-importar source" → estado recarrega, sem novas peças "novo — revisar" (mesmo source), "re-importado ✓"; `can_undo=false` após.
5. **Salvar**: "Salvar receita" → "salva: {caminho}"; conferir o JSON no disco com o campo `export` atualizado.
6. **Abrir receita**: "Abrir receita…" → digitar o caminho do `.meshbench.json` salvo → "receita aberta ✓", o projeto recarrega (nome no topo da barra lateral).
7. **Console limpo** em todos os passos.

Corrigir aqui qualquer bug encontrado (com teste de regressão quando for de lógica).

- [ ] **Step 2: Atualizar `README.md`**

Na seção de uso, a CLI já cobre `apply`/`--reimport`. Acrescentar, após a seção "Origem interativa (Fase 5b)", uma nova seção:

```markdown
### Export, re-importar e abrir receita (Fase 6)

A barra EXPORTA grava um arquivo por grupo no formato escolhido (DXF R12 3DFACE
para o Promob, ou STL/OBJ), na pasta configurável (`out/` por padrão, relativa à
receita; caminho absoluto também vale). Cada grupo mostra a contagem de faces num
semáforo (verde ≤ 8k, amarelo ≤ 15k, vermelho acima). No bloco **Projeto** da
barra lateral: salvar a receita, **re-importar** o source (re-lê o CAD e re-casa
por assinatura, marcando peças novas como "novo — revisar") e **abrir** outra
receita `.meshbench.json` sem reiniciar o servidor.
```

E trocar o cabeçalho "## Viewport 3D (Fases 2–5)" para "## Viewport 3D (Fases 2–6)".

- [ ] **Step 3: Atualizar `CLAUDE.md`**

Trocar a linha de status por:

```markdown
Phases 1 (core+CLI), 2 (viewport), 3 (selection/ops/preview/save), 4 (scale & units), 5 (interactive orientation, origin, rotation gizmo + global undo/redo) and 6 (export UI, re-import & open-recipe UI) are implemented. Next: 7+ (presets por família, batch, empacotamento .exe).
```

E, na seção "Commands", ajustar a linha do frontend/viewport se mencionar a fase atual (a linha "Phases 1 … are implemented" logo abaixo de "## Commands" deve casar com a de cima).

- [ ] **Step 4: Suítes completas**

Run: `.venv/Scripts/python -m pytest`
Expected: PASS.

Run: `npm --prefix web test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: fase 6 — export, re-importar e abrir receita na UI documentados"
```

---

## Depois das tasks (processo, não é uma task do plano)

Fluxo já usado nas fases 1–5b: revisão final do branch inteiro (o modelo mais capaz disponível) → onda de correções (UM subagente com a lista completa) → merge local na main + push → atualizar o ledger `.superpowers/sdd/progress.md`.

## Notas para o revisor final

- **out_dir**: caminho relativo resolve contra `base_dir` (pasta da receita/source), absoluto usado como está — conferir que `write_export` não resolve contra o cwd do servidor.
- **Config de export inerte**: `PATCH /api/export` de propósito não reprocessa nem entra no desfazer. Confirmar que isso não deixa o `undo` inconsistente (um undo posterior a uma mudança de geometria reverte também a config de export via snapshot — comportamento aceitável e documentado).
- **Re-baseline**: `reimport` e `open` limpam desfazer/refazer porque os snapshots antigos referenciam a `raw_mesh` em cache que muda. Confirmar que não há caminho que restaure um snapshot contra a malha nova.
- **open_project**: `_load_fields` ergue ANTES de mutar a sessão (source inexistente/ilegível não corrompe o projeto aberto). Confirmar a ordem.
- **Segurança**: abrir por caminho do FS é aceitável (app local-only). O `path` é validado como string não vazia; `read_mesh`/`Project.load` rejeitam formatos inválidos com ValueError → 422.
- **Adiado consciente**: download dos arquivos pelo navegador (decisão do usuário: só gravar em `out/`); listar receitas de uma pasta (abrir é por caminho digitado).
