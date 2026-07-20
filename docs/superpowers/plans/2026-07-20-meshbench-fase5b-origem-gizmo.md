# MeshBench Fase 5b — Origem Interativa + Gizmo de Rotação — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Barra ORIGEM (modo comum/por grupo, âncora 8 cantos + centro, snap por clique, offset numérico, validador "origem flutuando") e gizmo de rotação com TransformControls no viewport, com tudo ligado ao undo/redo global.

**Architecture:** Mesmo padrão das fases 4/5a — mutação explícita `PATCH /api/origin` que valida tudo antes de atribuir, faz rollback se o reprocesso falhar e empilha o snapshot no undo global. O snap por clique NÃO grava `snap_point` na receita: o ponto clicado (coordenadas do mundo, pós-origem) vira ajuste de `offset` (`novo = velho + ponto`) — reprodutível e funciona nos dois modos. O gizmo rotaciona a cena GLB em torno da **origem do mundo** (mesmo pivô do backend) e, ao soltar, decompõe o acumulado em Euler **'ZYX'** (equivale à nossa lista `[x, y, z]` aplicada em sequência) e faz append nas `rotations` via `PATCH /api/orient` — o servidor normaliza.

**Tech Stack:** FastAPI + trimesh/numpy (backend), React + three.js 0.182 (`TransformControls` com a API nova `getHelper()`), pytest + vitest.

## Global Constraints

- Strings de UI, docstrings, mensagens de erro e commits em **pt-BR**; identificadores de código em **inglês**.
- Commits em Conventional Commits terminando com `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Python: `.venv/Scripts/python -m pytest` (nunca `pytest` direto). Frontend: `npm --prefix web run build|test`.
- Branch de trabalho: `fase-5b-origem-gizmo` (criar a partir de `main` no início da Task 1).
- Ordem do pipeline é inegociável: ORIGIN é sempre a última etapa antes do export.
- O pivô de TODA rotação do backend é a origem do mundo (`rotate_90`/`rotate_free` giram em torno de (0,0,0)) — o gizmo deve respeitar isso.
- Limiar do validador de origem: **50 mm** (§8.3 do doc de arquitetura).
- Undo: toda mutação nova segue o padrão `before = session.project.to_dict()` na primeira linha sob o lock e `_push_undo(session, before)` só após reprocesso bem-sucedido.

---

### Task 1: Core — `origin_distance` + aviso "origem flutuando" no pipeline

**Files:**
- Modify: `src/meshbench/core/transform/origin.py`
- Modify: `src/meshbench/core/pipeline.py` (fim do estágio 7, dentro do `if grouped:`)
- Test: `tests/test_transform_mirror_origin.py` (append), `tests/test_pipeline_process.py` (append)

**Interfaces:**
- Consumes: nada novo — `place_origin` e `_bounds_of` já existem em `origin.py`.
- Produces: `origin_distance(meshes) -> float | None` e a constante `ORIGIN_FLOAT_MM = 50.0` em `meshbench.core.transform.origin`; warning `"origem a {d:.0f} mm da geometria mais próxima — origem flutuando"` emitido por `process()`. A Task 2 importa `origin_distance` no server.

- [ ] **Step 1: Escrever os testes que falham**

Append em `tests/test_transform_mirror_origin.py`:

```python
def test_origin_distance_vertice_mais_proximo(box):
    from meshbench.core.transform.origin import origin_distance

    m = box.copy()  # caixa centrada na origem: x∈[-5,5], y∈[-10,10], z∈[-15,15]
    m.apply_translation([100.0, 0.0, 0.0])  # x∈[95,105]
    d = origin_distance([m])
    assert d == pytest.approx(float(np.linalg.norm([95.0, 10.0, 15.0])))


def test_origin_distance_zero_e_vazio(box):
    from meshbench.core.transform.origin import origin_distance

    m = box.copy()
    m.apply_translation([5.0, 10.0, 15.0])  # canto mínimo exatamente na origem
    assert origin_distance([m]) == pytest.approx(0.0)
    assert origin_distance([]) is None
```

(O arquivo já importa `numpy as np` e `pytest`; se não importar, acrescente os imports no topo.)

Append em `tests/test_pipeline_process.py`:

```python
def test_warning_origem_flutuando(tmp_path, box):
    """Offset grande deixa a geometria longe da origem → aviso do validador §8.3."""
    from meshbench.api.server import load_session
    from meshbench.core.pipeline import process

    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)

    session.project.origin["offset"] = [100.0, 0.0, 0.0]
    _, warnings = process(session.project, session.base_dir, mesh=session.raw_mesh)
    assert any("origem flutuando" in w for w in warnings)

    session.project.origin["offset"] = [0.0, 0.0, 0.0]
    _, warnings = process(session.project, session.base_dir, mesh=session.raw_mesh)
    assert not any("origem flutuando" in w for w in warnings)
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_transform_mirror_origin.py tests/test_pipeline_process.py -v`
Expected: FAIL — `ImportError: cannot import name 'origin_distance'`.

- [ ] **Step 3: Implementar `origin_distance` em `origin.py`**

Acrescentar no fim de `src/meshbench/core/transform/origin.py`:

```python
ORIGIN_FLOAT_MM = 50.0  # §8.3: acima disto, avisar "origem flutuando"


def origin_distance(meshes):
    """Distância da origem (0,0,0) ao vértice mais próximo — validador §8.3.

    Aproximação por vértice (não por superfície): suficiente para detectar a
    reclamação real ("a peça flutua longe do quadradinho vermelho no Promob").
    Retorna None se não houver malha.
    """
    dists = [
        float(np.linalg.norm(np.asarray(m.vertices, float), axis=1).min())
        for m in meshes
        if len(m.vertices)
    ]
    return min(dists) if dists else None
```

- [ ] **Step 4: Emitir o warning no pipeline**

Em `src/meshbench/core/pipeline.py`, trocar o import de origin:

```python
from meshbench.core.transform.origin import (
    ORIGIN_FLOAT_MM,
    _bounds_of,
    origin_distance,
    place_origin,
)
```

E no fim do estágio 7 (dentro do `if grouped:`, logo após a linha `records = [replace(r, mesh=next(cursors[r.group])) for r in records]`):

```python
        dist = origin_distance([r.mesh for r in records])
        if dist is not None and dist > ORIGIN_FLOAT_MM:
            warnings.append(
                f"origem a {dist:.0f} mm da geometria mais próxima — origem flutuando"
            )
```

- [ ] **Step 5: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_transform_mirror_origin.py tests/test_pipeline_process.py -v`
Expected: PASS (todos).

Run: `.venv/Scripts/python -m pytest`
Expected: PASS — nenhuma regressão (o box das fixtures ancora em bbox_min → distância 0, nenhum warning novo nos testes existentes).

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/core/transform/origin.py src/meshbench/core/pipeline.py tests/test_transform_mirror_origin.py tests/test_pipeline_process.py
git commit -m "feat: validador de origem — origin_distance e aviso 'origem flutuando' (§8.3)"
```

---

### Task 2: Backend — `update_origin` + `PATCH /api/origin` + undo + teste de restore falho

**Files:**
- Modify: `src/meshbench/api/session_ops.py`
- Modify: `src/meshbench/api/server.py` (`_project_state` + rota)
- Test: Create `tests/test_api_origin.py`; append em `tests/test_api_undo.py`

**Interfaces:**
- Consumes: `origin_distance` (Task 1); `_push_undo`, `reprocess`, padrão de rollback já existentes em `session_ops.py`.
- Produces: `update_origin(session, changes)` e `_validated_origin(current, changes)` em `session_ops`; rota `PATCH /api/origin` (200 → estado completo; 422 ValueError pt-BR); novos campos de estado `origin` (dict da receita) e `origin_distance_mm` (float | None). O frontend (Task 3+) consome `PATCH /api/origin` e esses dois campos.

- [ ] **Step 1: Escrever os testes que falham**

Create `tests/test_api_origin.py`:

```python
import math

import pytest
from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session
from meshbench.api.session_ops import update_origin


def _client(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_origin_no_estado(tmp_path, box):
    client, _ = _client(tmp_path, box)
    state = client.get("/api/project").json()
    assert state["origin"]["mode"] == "common"
    assert state["origin"]["anchor"] == "bbox_min"
    # bbox_min ancorado → um vértice exatamente na origem
    assert state["origin_distance_mm"] == pytest.approx(0.0, abs=1e-6)


def test_patch_anchor_center(tmp_path, box):
    client, _ = _client(tmp_path, box)
    rev0 = client.get("/api/project").json()["revision"]
    r = client.patch("/api/origin", json={"anchor": "center"})
    assert r.status_code == 200
    state = r.json()
    assert state["origin"]["anchor"] == "center"
    assert state["revision"] == rev0 + 1
    assert state["dims_mm"] == pytest.approx([10.0, 20.0, 30.0])
    # caixa centrada: vértice mais próximo é um canto (5,10,15)
    assert state["origin_distance_mm"] == pytest.approx(math.sqrt(350.0))


def test_offset_e_origem_flutuando(tmp_path, box):
    client, _ = _client(tmp_path, box)
    state = client.patch("/api/origin", json={"offset": [100, 0, 0]}).json()
    # bbox_min + offset 100 em x → geometria em x∈[-100,-90]; canto (-90,0,0)
    assert state["origin_distance_mm"] == pytest.approx(90.0)
    assert any("origem flutuando" in w for w in state["warnings"])
    state = client.patch("/api/origin", json={"offset": [0, 0, 0]}).json()
    assert not any("origem flutuando" in w for w in state["warnings"])


def test_snap_point_precedencia(tmp_path, box):
    client, _ = _client(tmp_path, box)
    # snap_point é raro (a UI usa offset), mas a receita pode carregar — precedência máxima
    state = client.patch("/api/origin", json={"snap_point": [-5, -10, -15]}).json()
    assert state["origin_distance_mm"] == pytest.approx(0.0, abs=1e-6)


def test_per_group_e_validacoes_422(tmp_path, box):
    client, _ = _client(tmp_path, box)
    assert client.patch("/api/origin", json={"mode": "per_group"}).status_code == 200
    casos = [
        ({"mode": "magico"}, "modo de origem"),
        ({"anchor": "canto"}, "âncora"),
        ({"anchor": "corner_012"}, "âncora"),
        ({"offset": [1, 2]}, "offset"),
        ({"offset": [1, 2, "a"]}, "offset"),
        ({"snap_point": "x"}, "snap_point"),
        ({"feature_ref": 5}, "feature_ref"),
    ]
    for body, trecho in casos:
        r = client.patch("/api/origin", json=body)
        assert r.status_code == 422, body
        assert trecho in r.json()["detail"], body


def test_rollback_se_reprocesso_falha(tmp_path, box, monkeypatch):
    _, session = _client(tmp_path, box)
    origin_antes = dict(session.project.origin)
    rev_antes = session.revision

    import meshbench.api.session_ops as so

    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(so, "process", explode)
    with pytest.raises(RuntimeError):
        update_origin(session, {"anchor": "center"})
    assert session.project.origin == origin_antes
    assert session.revision == rev_antes
    assert len(session.undo_stack) == 0


def test_undo_redo_de_origem(tmp_path, box):
    client, _ = _client(tmp_path, box)
    client.patch("/api/origin", json={"anchor": "center"})
    state = client.post("/api/undo").json()
    assert state["origin"]["anchor"] == "bbox_min"
    assert state["origin_distance_mm"] == pytest.approx(0.0, abs=1e-6)
    assert state["can_redo"] is True
    state = client.post("/api/redo").json()
    assert state["origin"]["anchor"] == "center"
```

Append em `tests/test_api_undo.py` (o teste adiado da revisão da 5a — caminho de falha do restore):

```python
def test_undo_devolve_alvo_a_pilha_se_restore_falha(tmp_path, box, monkeypatch):
    """Se o reprocesso do undo falhar, o alvo volta para a pilha e a sessão
    fica intacta (projeto atual preservado, redo não ganha entrada)."""
    client, session = _client(tmp_path, box)
    client.patch("/api/orient", json={"rotations": [{"axis": "x", "deg": 90}]})
    n_undo = len(session.undo_stack)

    import meshbench.api.session_ops as so

    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(so, "process", explode)
    with pytest.raises(RuntimeError):
        so.undo(session)
    assert len(session.undo_stack) == n_undo
    assert len(session.redo_stack) == 0
    assert session.project.orient["rotations"] == [{"axis": "x", "deg": 90.0}]
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_api_origin.py tests/test_api_undo.py -v`
Expected: `test_api_origin.py` falha com `ImportError: cannot import name 'update_origin'`; o teste novo de undo deve PASSAR já (o comportamento foi implementado na 5a — este teste é a cobertura que faltava). Se falhar, investigar antes de seguir.

- [ ] **Step 3: Implementar `_validated_origin` + `update_origin` em `session_ops.py`**

Acrescentar `import re` no topo de `src/meshbench/api/session_ops.py` (junto de `import math`) e, no fim do arquivo:

```python
_ORIGIN_MODES = ("common", "per_group")
_CORNER_RE = re.compile(r"^corner_[01]{3}$")


def _finite_triple(value, nome):
    """Valida uma lista de 3 números finitos. ValueError pt-BR."""
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 3
        or not all(
            isinstance(x, (int, float))
            and not isinstance(x, bool)
            and math.isfinite(x)
            for x in value
        )
    ):
        raise ValueError(f"{nome} deve ser uma lista de 3 números")
    return [float(x) for x in value]


def _validated_origin(current, changes):
    """Monta o dict de origin completo a partir do atual + mudanças. ValueError pt-BR."""
    mode = changes.get("mode", current.get("mode", "common"))
    if mode not in _ORIGIN_MODES:
        raise ValueError(
            f"modo de origem '{mode}' desconhecido (disponíveis: {sorted(_ORIGIN_MODES)})"
        )
    anchor = changes.get("anchor", current.get("anchor", "bbox_min"))
    if anchor not in ("bbox_min", "center") and not _CORNER_RE.match(str(anchor)):
        raise ValueError(
            "âncora deve ser bbox_min, center ou corner_ABC (A,B,C em 0/1)"
        )
    offset = _finite_triple(
        changes.get("offset", current.get("offset", [0, 0, 0])), "offset"
    )
    if "snap_point" in changes:
        snap_point = changes["snap_point"]
    else:
        snap_point = current.get("snap_point")
    if snap_point is not None:
        snap_point = _finite_triple(snap_point, "snap_point")
    if "feature_ref" in changes:
        feature_ref = changes["feature_ref"]
    else:
        feature_ref = current.get("feature_ref")
    if feature_ref is not None and not isinstance(feature_ref, str):
        raise ValueError("feature_ref deve ser o id de um componente (string) ou null")
    return {
        "mode": mode,
        "anchor": anchor,
        "feature_ref": feature_ref,
        "snap_point": snap_point,
        "offset": offset,
    }


def update_origin(session, changes):
    """Aplica mudança de origem e reprocessa. Rollback se o reprocesso falhar."""
    with session.lock:
        before = session.project.to_dict()
        new_origin = _validated_origin(session.project.origin, changes)
        # referência basta como snapshot: process() não muta origin in place
        # (ao contrário de scale["factor"]) e nós substituímos o dict inteiro
        snapshot = session.project.origin
        session.project.origin = new_origin
        try:
            reprocess(session)
        except Exception:
            session.project.origin = snapshot
            raise
        _push_undo(session, before)
```

- [ ] **Step 4: Rota + campos de estado em `server.py`**

Em `src/meshbench/api/server.py`:

1. Acrescentar `update_origin` no import de `meshbench.api.session_ops` e importar a distância:

```python
from meshbench.core.transform.origin import origin_distance
```

2. Em `_project_state`, logo após a linha `"orient": session.project.orient,`:

```python
            "origin": session.project.origin,
```

E logo após `"dims_mm": dims,`:

```python
            "origin_distance_mm": (
                origin_distance([r.mesh for r in session.records])
                if session.records
                else None
            ),
```

3. Rota, logo após `patch_orient`:

```python
    @app.patch("/api/origin")
    def patch_origin(changes: dict):
        try:
            update_origin(session, changes)
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))
```

- [ ] **Step 5: Rodar os testes**

Run: `.venv/Scripts/python -m pytest tests/test_api_origin.py tests/test_api_undo.py -v`
Expected: PASS (todos).

Run: `.venv/Scripts/python -m pytest`
Expected: PASS — suíte inteira verde.

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/api/session_ops.py src/meshbench/api/server.py tests/test_api_origin.py tests/test_api_undo.py
git commit -m "feat: PATCH /api/origin com validação, rollback e undo global + teste de restore falho"
```

---

### Task 3: Frontend lib — `origin.js`, `eulerToRotations`, `patchOrigin`

**Files:**
- Create: `web/src/lib/origin.js`
- Create: `web/src/lib/origin.test.js`
- Modify: `web/src/lib/orient.js` (append), `web/src/lib/orient.test.js` (append)
- Modify: `web/src/lib/client.js` (append)

**Interfaces:**
- Consumes: `PATCH /api/origin` (Task 2).
- Produces: `patchOrigin(changes)` em `client.js`; `ANCHOR_OPTIONS` (array de `{value, label}`), `MODE_EXPLAIN` (`{common, per_group}` → frase), `addSnapOffset(origin, point) -> {offset}` em `origin.js`; `eulerToRotations(ex, ey, ez) -> [{axis, deg}]` em `orient.js` (radianos → graus a 0,1°, zeros descartados). As Tasks 4 e 5 consomem exatamente esses nomes.

- [ ] **Step 1: Escrever os testes que falham**

Create `web/src/lib/origin.test.js`:

```js
import { describe, expect, it } from "vitest";
import { ANCHOR_OPTIONS, MODE_EXPLAIN, addSnapOffset } from "./origin.js";

describe("ANCHOR_OPTIONS", () => {
  it("tem 9 âncoras (bbox_min + centro + 7 cantos) sem duplicar corner_000", () => {
    const values = ANCHOR_OPTIONS.map((o) => o.value);
    expect(values).toHaveLength(9);
    expect(values).toContain("bbox_min");
    expect(values).toContain("center");
    expect(values).toContain("corner_111");
    expect(values).not.toContain("corner_000"); // ≡ bbox_min
    expect(new Set(values).size).toBe(9);
  });

  it("todo option tem rótulo pt-BR não vazio", () => {
    for (const o of ANCHOR_OPTIONS) expect(o.label.length).toBeGreaterThan(0);
  });
});

describe("MODE_EXPLAIN", () => {
  it("explica os dois modos em uma frase", () => {
    expect(MODE_EXPLAIN.common).toMatch(/encaixad/);
    expect(MODE_EXPLAIN.per_group).toMatch(/pr[óo]prio/);
  });
});

describe("addSnapOffset", () => {
  it("soma o ponto clicado ao offset e arredonda a 0,01 mm", () => {
    expect(addSnapOffset({ offset: [1, 2, 3] }, [0.01, -1, 10.126])).toEqual({
      offset: [1.01, 1, 13.13],
    });
  });

  it("offset ausente conta como [0,0,0]", () => {
    expect(addSnapOffset({}, [1.5, 0, -2])).toEqual({ offset: [1.5, 0, -2] });
  });
});
```

Append em `web/src/lib/orient.test.js` (importar `eulerToRotations` junto dos imports existentes de `./orient.js`):

```js
describe("eulerToRotations", () => {
  it("converte radianos para a lista x→y→z em graus", () => {
    expect(eulerToRotations(Math.PI / 2, 0, -Math.PI)).toEqual([
      { axis: "x", deg: 90 },
      { axis: "z", deg: -180 },
    ]);
  });

  it("descarta ângulos que arredondam para 0,0°", () => {
    expect(eulerToRotations(0.0001, 0, 0)).toEqual([]);
  });
});
```

- [ ] **Step 2: Rodar e ver falhar**

Run: `npm --prefix web test`
Expected: FAIL — `origin.js` não existe; `eulerToRotations` não exportado.

- [ ] **Step 3: Implementar**

Create `web/src/lib/origin.js`:

```js
// Origem (§8 do doc): âncora no bbox (8 cantos + centro), modo comum/por grupo
// e snap por clique. O clique NÃO grava snap_point: vira ajuste de offset
// (novo = velho + ponto do mundo) — reprodutível e funciona nos dois modos.
const SIGN = { 0: "−", 1: "+" };

// bbox_min ≡ corner_000 — mostramos bbox_min (o default da receita) e omitimos o duplicado
export const ANCHOR_OPTIONS = [
  { value: "bbox_min", label: "canto mínimo (X− Y− Z−)" },
  { value: "center", label: "centro" },
  ...["001", "010", "011", "100", "101", "110", "111"].map((bits) => ({
    value: `corner_${bits}`,
    label: `canto X${SIGN[bits[0]]} Y${SIGN[bits[1]]} Z${SIGN[bits[2]]}`,
  })),
];

// §8.2: a consequência da troca não é óbvia — explicar em uma frase na UI
export const MODE_EXPLAIN = {
  common: "arquivos exportados caem encaixados no destino (mesmo referencial)",
  per_group: "cada arquivo zera no próprio canto — você posiciona no destino",
};

export function addSnapOffset(origin, point) {
  const offset = (origin.offset || [0, 0, 0]).map(
    (o, i) => Math.round((o + point[i]) * 100) / 100,
  );
  return { offset };
}
```

Append em `web/src/lib/orient.js`:

```js
// Gizmo → receita: a nossa lista [x, y, z] aplicada em sequência (cada rotação
// em torno do eixo do MUNDO, a última multiplica à esquerda) equivale ao Euler
// 'ZYX' do three.js — decompor com 'XYZ' daria o resultado ERRADO. Radianos →
// graus arredondados a 0,1°; zeros descartados (o servidor normaliza o resto).
export function eulerToRotations(ex, ey, ez) {
  const rots = [];
  for (const [axis, rad] of [["x", ex], ["y", ey], ["z", ez]]) {
    const deg = Math.round(((rad * 180) / Math.PI) * 10) / 10;
    if (deg !== 0) rots.push({ axis, deg });
  }
  return rots;
}
```

Append em `web/src/lib/client.js` (antes de `geometryUrl`):

```js
export async function patchOrigin(changes) {
  const r = await checkOk(
    await fetch("/api/origin", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
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
git add web/src/lib/origin.js web/src/lib/origin.test.js web/src/lib/orient.js web/src/lib/orient.test.js web/src/lib/client.js
git commit -m "feat: lib de origem (âncoras, snap como offset), eulerToRotations e patchOrigin"
```

---

### Task 4: Barra ORIGEM + wiring no App + CSS

**Files:**
- Create: `web/src/components/OriginBar.jsx`
- Modify: `web/src/App.jsx`
- Modify: `web/src/styles.css`

**Interfaces:**
- Consumes: `patchOrigin`, `ANCHOR_OPTIONS`, `MODE_EXPLAIN`, `addSnapOffset` (Task 3); campos de estado `origin` e `origin_distance_mm` (Task 2).
- Produces: `OriginBar({ state, onStateChange, snapArmed, onToggleSnap, picked, onPickConsumed })`; no App, os estados `snapOrigin`/`picked`/`gizmoOn`/`gizmoRots` e as props novas passadas para `Viewport` (`pickMode`, `onPickPoint`, `gizmoOn`, `onGizmoRotate`) e `OrientBar` (`gizmoOn`, `onToggleGizmo`, `gizmoRots`, `onGizmoConsumed`) — a Task 5 implementa os consumidores; até lá as props extras são ignoradas sem quebrar nada.

- [ ] **Step 1: Criar `web/src/components/OriginBar.jsx`**

```jsx
import { useEffect, useState } from "react";
import { patchOrigin } from "../lib/client.js";
import { ANCHOR_OPTIONS, MODE_EXPLAIN, addSnapOffset } from "../lib/origin.js";

const FLOAT_LIMIT_MM = 50; // §8.3 — mesmo limiar do backend

export default function OriginBar({
  state,
  onStateChange,
  snapArmed,
  onToggleSnap,
  picked,
  onPickConsumed,
}) {
  const origin = state.origin;
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [off, setOff] = useState(["", "", ""]);

  // sincroniza os campos de offset com a receita vigente (PATCH, undo/redo, snap);
  // keyed no conteúdo para não descartar edição em andamento em mutações não relacionadas
  const originJson = JSON.stringify(origin);
  useEffect(() => {
    setOff((origin.offset || [0, 0, 0]).map((v) => String(v)));
  }, [originJson]); // eslint-disable-line react-hooks/exhaustive-deps

  const send = async (changes) => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await patchOrigin(changes));
      setMsg("aplicado ✓");
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  // consumo do snap por clique: o Viewport entregou um ponto do mundo
  useEffect(() => {
    if (!snapArmed || !picked) return;
    onToggleSnap(false);
    onPickConsumed();
    send(addSnapOffset(origin, picked.point));
  }, [picked]); // eslint-disable-line react-hooks/exhaustive-deps

  const aplicarOffset = () => {
    const nums = off.map((v) => Number(v === "" ? 0 : v));
    if (nums.some((n) => Number.isNaN(n))) {
      setMsg("erro: offset deve ser numérico");
      return;
    }
    send({ offset: nums });
  };

  // receita editada à mão pode trazer corner_000 (≡ bbox_min, que o select mostra)
  const anchorValue = origin.anchor === "corner_000" ? "bbox_min" : origin.anchor;
  const dist = state.origin_distance_mm;
  const flutuando = dist != null && dist > FLOAT_LIMIT_MM;
  const temOffset = (origin.offset || []).some((v) => v !== 0);

  return (
    <div className="originbar">
      <span className="rotulo">ORIGEM</span>
      <label className="campo-inline">
        <span>modo</span>
        <select
          value={origin.mode}
          disabled={busy}
          onChange={(e) => send({ mode: e.target.value })}
        >
          <option value="common">comum</option>
          <option value="per_group">por grupo</option>
        </select>
      </label>
      <span className="explica-modo">{MODE_EXPLAIN[origin.mode]}</span>
      <label className="campo-inline">
        <span>âncora</span>
        <select
          value={anchorValue}
          disabled={busy}
          onChange={(e) => send({ anchor: e.target.value })}
        >
          {ANCHOR_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
      <button
        className={"btn mini" + (snapArmed ? " ativo" : "")}
        disabled={busy}
        onClick={() => onToggleSnap(!snapArmed)}
        title="clique num ponto da peça no viewport para levar a origem até lá"
      >
        ⊕ snap por clique
      </button>
      <span className="grupo-offset">
        offset
        {["x", "y", "z"].map((k, i) => (
          <input
            key={k}
            type="number"
            placeholder={k}
            value={off[i]}
            onChange={(e) =>
              setOff((o) => o.map((v, j) => (j === i ? e.target.value : v)))
            }
          />
        ))}
        <button className="btn mini" disabled={busy} onClick={aplicarOffset}>
          aplicar
        </button>
        {temOffset && (
          <button
            className="btn mini"
            disabled={busy}
            onClick={() => send({ offset: [0, 0, 0] })}
          >
            zerar
          </button>
        )}
      </span>
      {dist != null && (
        <span className={"dist-origem" + (flutuando ? " suspeito" : "")}>
          origem → geometria: {dist.toFixed(1)} mm
          {flutuando ? " ⚠ origem flutuando" : ""}
        </span>
      )}
      {msg && <span className={"msg" + (msg.startsWith("erro") ? " erro" : "")}>{msg}</span>}
    </div>
  );
}
```

- [ ] **Step 2: Wiring no `web/src/App.jsx`**

Substituir o conteúdo por:

```jsx
import { useCallback, useEffect, useState } from "react";
import Sidebar from "./components/Sidebar.jsx";
import StatusBar from "./components/StatusBar.jsx";
import Viewport from "./components/Viewport.jsx";
import Inspector from "./components/Inspector.jsx";
import ScaleBar from "./components/ScaleBar.jsx";
import OrientBar from "./components/OrientBar.jsx";
import OriginBar from "./components/OriginBar.jsx";
import { fetchProject } from "./lib/client.js";

export default function App() {
  const [state, setState] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null); // id da família selecionada
  const [preview, setPreview] = useState(null); // {componentId, url, facesBefore, facesAfter, mostrando}
  const [snapOrigin, setSnapOrigin] = useState(false); // snap de origem armado?
  const [picked, setPicked] = useState(null); // {point: [x,y,z]} clicado no viewport
  const [gizmoOn, setGizmoOn] = useState(false); // gizmo de rotação visível?
  const [gizmoRots, setGizmoRots] = useState(null); // {rots: [{axis, deg}]} do arrasto

  useEffect(() => {
    fetchProject().then(setState).catch((e) => setError(String(e)));
  }, []);

  const clearPreview = useCallback(() => {
    setPreview((p) => {
      if (p) URL.revokeObjectURL(p.url);
      return null;
    });
  }, []);

  // troca de preview revoga o objectURL anterior; o toggle antes/depois reusa
  // a mesma url (via {...preview, mostrando}) e não revoga nada
  const handlePreviewChange = useCallback((novo) => {
    setPreview((atual) => {
      if (atual && novo && atual.url !== novo.url) URL.revokeObjectURL(atual.url);
      return novo;
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

  const handlePickPoint = useCallback((p) => setPicked({ point: p }), []);
  const handleGizmoRotate = useCallback((rots) => setGizmoRots({ rots }), []);

  if (error) return <div className="tela-aviso">Erro ao carregar o projeto: {error}</div>;
  if (!state) return <div className="tela-aviso">Carregando…</div>;
  return (
    <div className="app">
      <Sidebar state={state} selected={selected} onSelect={handleSelect} />
      <main className="viewport-wrap">
        <Viewport
          state={state}
          selected={selected}
          onSelect={handleSelect}
          preview={preview}
          pickMode={snapOrigin}
          onPickPoint={handlePickPoint}
          gizmoOn={gizmoOn}
          onGizmoRotate={handleGizmoRotate}
        />
      </main>
      <Inspector
        state={state}
        entry={state.components.find((c) => c.id === selected) || null}
        preview={preview}
        onStateChange={handleStateChange}
        onPreviewChange={handlePreviewChange}
        onClearPreview={clearPreview}
      />
      <ScaleBar state={state} onStateChange={handleStateChange} />
      <OrientBar
        state={state}
        onStateChange={handleStateChange}
        gizmoOn={gizmoOn}
        onToggleGizmo={setGizmoOn}
        gizmoRots={gizmoRots}
        onGizmoConsumed={() => setGizmoRots(null)}
      />
      <OriginBar
        state={state}
        onStateChange={handleStateChange}
        snapArmed={snapOrigin}
        onToggleSnap={setSnapOrigin}
        picked={picked}
        onPickConsumed={() => setPicked(null)}
      />
      <StatusBar state={state} />
    </div>
  );
}
```

- [ ] **Step 3: CSS em `web/src/styles.css`**

Trocar o grid do `.app` (linhas 5–15) por:

```css
.app {
  display: grid;
  grid-template-columns: 300px 1fr 280px;
  grid-template-rows: 1fr auto auto auto auto;
  grid-template-areas:
    "sidebar viewport inspector"
    "sidebar scalebar scalebar"
    "sidebar orientbar orientbar"
    "sidebar originbar originbar"
    "sidebar statusbar statusbar";
  height: 100%;
}
```

Acrescentar no fim do arquivo:

```css
.originbar { grid-area: originbar; background: #1e1e24; border-top: 1px solid #2c2c34; padding: 8px 14px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.originbar .rotulo { font-size: 0.75rem; letter-spacing: 0.06em; color: #9a9aa5; }
.originbar select, .originbar input { background: #16161a; color: #e8e8ec; border: 1px solid #2c2c34; border-radius: 6px; padding: 4px 6px; font-size: 0.82rem; }
.originbar input { width: 64px; }
.grupo-offset { display: flex; align-items: center; gap: 4px; }
.explica-modo { font-size: 0.75rem; color: #9a9aa5; }
.dist-origem { font-size: 0.8rem; color: #9a9aa5; }
.dist-origem.suspeito { color: #e15759; }
.originbar .msg { font-size: 0.78rem; color: #9a9aa5; }
.originbar .msg.erro { color: #e15759; }
```

- [ ] **Step 4: Build e teste**

Run: `npm --prefix web run build`
Expected: build verde, sem erro de import.

Run: `npm --prefix web test`
Expected: PASS (nenhuma regressão).

- [ ] **Step 5: Commit**

```bash
git add web/src/components/OriginBar.jsx web/src/App.jsx web/src/styles.css
git commit -m "feat: barra ORIGEM — modo comum/por grupo, âncoras, offset, snap armado e validador visual"
```

---

### Task 5: Viewport — pick de ponto + gizmo de rotação (TransformControls)

**Files:**
- Modify: `web/src/components/Viewport.jsx`
- Modify: `web/src/components/OrientBar.jsx`

**Interfaces:**
- Consumes: props do App (Task 4): `pickMode`, `onPickPoint(point[3])`, `gizmoOn`, `onGizmoRotate(rots)` no Viewport; `gizmoOn`, `onToggleGizmo`, `gizmoRots`, `onGizmoConsumed` na OrientBar. `eulerToRotations` (Task 3).
- Produces: clique com snap armado entrega `hits[0].point.toArray()` via `onPickPoint` (sem mudar a seleção); arrasto do gizmo entrega `eulerToRotations(euler.x, euler.y, euler.z)` (Euler **'ZYX'**) via `onGizmoRotate`; a OrientBar faz o append em `rotations` via PATCH.

**Cuidados (todos já verificados no código atual):**
- three 0.182: `TransformControls` NÃO é `Object3D` — adicionar `tc.getHelper()` à cena, nunca `tc`.
- O pivô do backend é a origem do mundo → o gizmo anexa em `gltf.scene` (posição (0,0,0)) e a rotação visual durante o arrasto coincide com o resultado real.
- Os listeners de pointer são de montagem única → `pickMode`/`onPickPoint`/`onGizmoRotate` entram por refs, como já é feito com `selectedRef`/`onSelectRef`.
- Durante interação com o gizmo, `tc.axis` fica não-nulo → usar isso para o clique no gizmo não deselecionar a peça.
- OrbitControls é desabilitado enquanto `dragging-changed` reporta `true` (senão a órbita disputa o arrasto).

- [ ] **Step 1: Modificar `web/src/components/Viewport.jsx`**

1. Imports — acrescentar:

```js
import { TransformControls } from "three/addons/controls/TransformControls.js";
import { eulerToRotations } from "../lib/orient.js";
```

2. Assinatura e refs — trocar a linha da assinatura e acrescentar refs logo após `onSelectRef`:

```js
export default function Viewport({
  state,
  selected,
  onSelect,
  preview,
  pickMode,
  onPickPoint,
  gizmoOn,
  onGizmoRotate,
}) {
```

```js
  const pickModeRef = useRef(pickMode);
  pickModeRef.current = pickMode;
  const onPickPointRef = useRef(onPickPoint);
  onPickPointRef.current = onPickPoint;
  const onGizmoRotateRef = useRef(onGizmoRotate);
  onGizmoRotateRef.current = onGizmoRotate;
  const gizmoOnRef = useRef(gizmoOn);
  const tcRef = useRef(null); // TransformControls persistente (montagem única)
```

3. No efeito de montagem única, logo após criar `controls` (OrbitControls):

```js
    // gizmo de rotação (fase 5b): persistente como a câmera; anexado ao GLB a
    // cada troca de geometria quando ligado. three >= 0.169: adicionar o
    // HELPER à cena (TransformControls não é mais Object3D).
    const tc = new TransformControls(camera, renderer.domElement);
    tc.setMode("rotate");
    tc.setSpace("world");
    tc.addEventListener("dragging-changed", (e) => {
      controls.enabled = !e.value; // órbita não pode disputar o arrasto
      if (!e.value && tc.object) {
        // soltou: decompõe o acumulado em Euler 'ZYX' — equivale à nossa lista
        // [x, y, z] aplicada em sequência (decompor em 'XYZ' seria ERRADO)
        const euler = new THREE.Euler().setFromQuaternion(tc.object.quaternion, "ZYX");
        tc.object.rotation.set(0, 0, 0); // o servidor reprocessa e devolve o GLB girado
        onGizmoRotateRef.current(eulerToRotations(euler.x, euler.y, euler.z));
      }
    });
    scene.add(tc.getHelper());
    tcRef.current = tc;
```

4. Em `onPointerUp`, logo após o guard de drag (`if (Math.hypot(...) > 5) return;`):

```js
      if (tcRef.current?.axis) return; // clique/arrasto no gizmo não seleciona nem snapa
```

E trocar a última linha do handler (`onSelectRef.current(...)`) por:

```js
      if (pickModeRef.current) {
        // snap de origem armado: entrega o ponto do mundo, não muda a seleção
        if (hits.length > 0) onPickPointRef.current(hits[0].point.toArray());
        return;
      }
      onSelectRef.current(hits.length > 0 ? compIdOf(hits[0].object) : null);
```

5. No cleanup do efeito de montagem, antes de `controls.dispose();`:

```js
      tc.detach();
      tc.dispose();
      tcRef.current = null;
```

6. No efeito de geometria: antes de remover o grupo de conteúdo anterior (linha `if (contentGroupRef.current) {`), desanexar o gizmo do GLB que vai ser descartado:

```js
    tcRef.current?.detach();
```

E no callback de sucesso do `GLTFLoader().load`, logo após `group.add(gltf.scene);`:

```js
        gltf.scene.userData.isGlbRoot = true;
        if (gizmoOnRef.current) tcRef.current?.attach(gltf.scene);
```

7. Efeito novo do toggle do gizmo (depois do efeito de destaque emissivo):

```js
  // liga/desliga o gizmo — reanexa ao GLB vigente (que muda a cada revision)
  useEffect(() => {
    gizmoOnRef.current = gizmoOn;
    const tc = tcRef.current;
    const content = contentGroupRef.current;
    if (!tc) return;
    if (!gizmoOn) {
      tc.detach();
      return;
    }
    const root = content?.children.find((c) => c.userData.isGlbRoot);
    if (root) tc.attach(root);
  }, [gizmoOn, state]);
```

- [ ] **Step 2: Toggle + consumo do gizmo na `web/src/components/OrientBar.jsx`**

1. Assinatura:

```js
export default function OrientBar({
  state,
  onStateChange,
  gizmoOn,
  onToggleGizmo,
  gizmoRots,
  onGizmoConsumed,
}) {
```

2. Efeito de consumo, logo após o efeito de resync do `custom` (o `send` já existe abaixo — mover este efeito para DEPOIS da definição de `send`):

```js
  // consumo da rotação do gizmo: o Viewport decompôs o arrasto em [{axis, deg}]
  useEffect(() => {
    if (!gizmoRots) return;
    onGizmoConsumed();
    // arrasto minúsculo arredonda para zero rotações — não gerar mutação vazia
    if (gizmoRots.rots.length > 0) {
      send({ rotations: [...orient.rotations, ...gizmoRots.rots] });
    }
  }, [gizmoRots]); // eslint-disable-line react-hooks/exhaustive-deps
```

3. Botão de toggle, dentro do `<span className="grupo-livre">`, após o botão "girar":

```jsx
        <button
          className={"btn mini" + (gizmoOn ? " ativo" : "")}
          disabled={busy}
          onClick={() => onToggleGizmo(!gizmoOn)}
          title="girar arrastando o gizmo no viewport"
        >
          ⟳ gizmo
        </button>
```

- [ ] **Step 3: Build e testes**

Run: `npm --prefix web run build`
Expected: build verde.

Run: `npm --prefix web test`
Expected: PASS (nenhuma regressão).

- [ ] **Step 4: Commit**

```bash
git add web/src/components/Viewport.jsx web/src/components/OrientBar.jsx
git commit -m "feat: snap de origem por clique no viewport e gizmo de rotação (TransformControls)"
```

---

### Task 6: e2e no navegador + docs

**Files:**
- Modify: `README.md`, `CLAUDE.md`
- (nenhum código novo — verificação visual + documentação)

**Interfaces:**
- Consumes: tudo das Tasks 1–5, já mergeado no branch.
- Produces: fases 1–5 completas documentadas; evidência e2e de que a barra ORIGEM e o gizmo funcionam no navegador real.

- [ ] **Step 1: Build + servidor + e2e dirigido por JS no painel do navegador**

```bash
npm --prefix web run build
```

Subir `serve` num arquivo de teste (gerar uma caixa STL com o python da venv no scratchpad, ou usar uma peça real se disponível) e, no painel do navegador (technique validada nas fases 3–5a: dirigir por `javascript_tool` com native setters + dispatchEvent; screenshots costumam falhar):

1. **Estado inicial**: `GET /api/project` → `origin.anchor === "bbox_min"`, `origin_distance_mm ≈ 0`; barra ORIGEM visível com "origem → geometria: 0.0 mm".
2. **Âncora**: trocar o select de âncora para "centro" → estado atualiza, distância vira ~√350 (na caixa 10×20×30), "aplicado ✓".
3. **Modo**: trocar para "por grupo" → frase explicativa muda; voltar para "comum".
4. **Offset + flutuando**: digitar offset x=100, "aplicar" → distância ~90 mm em vermelho com "⚠ origem flutuando"; StatusBar mostra o warning do pipeline; "zerar" limpa.
5. **Snap por clique**: armar "⊕ snap por clique" (botão fica ativo), disparar um pointerdown/pointerup sintético no canvas sobre a peça → PATCH /api/origin com offset ajustado, botão desarma, distância ~0 no ponto clicado.
6. **Undo cruzado**: ↶ desfaz o snap; ↶ desfaz o offset — `origin` volta por etapas; ↷ refaz.
7. **Gizmo**: ligar "⟳ gizmo" → helper aparece sem erro no console; (arrasto real é difícil de sintetizar — validar a conversão via `eulerToRotations` já coberta por vitest e conferir no console que `dragging-changed` desabilita a órbita ao interagir, se viável; caso contrário, registrar como verificação manual pendente do usuário).
8. **Console limpo**: nenhum erro nos passos acima.

Corrigir aqui qualquer bug encontrado (com teste de regressão quando for de lógica).

- [ ] **Step 2: Atualizar `README.md`**

Na seção "Viewport 3D", trocar o título para "Viewport 3D (Fases 2–5)" e remover a frase "Orientação/origem interativas (gizmos) vêm na fase 5." Na seção da fase 5a, remover "Origem interativa e gizmo vêm na fase 5b." e acrescentar após ela:

```markdown
### Origem interativa (Fase 5b)

A barra ORIGEM escolhe o modo (comum = arquivos caem encaixados no destino;
por grupo = cada arquivo zera no próprio canto), a âncora (8 cantos + centro),
offset numérico e snap por clique (clique num ponto da peça e a origem vai até
lá). A distância origem→geometria é mostrada ao vivo; acima de 50 mm o app
avisa "origem flutuando". O botão ⟳ gizmo gira a peça arrastando no viewport;
ao soltar, a rotação entra na receita (normalizada) com desfazer.
```

- [ ] **Step 3: Atualizar `CLAUDE.md`**

Trocar a linha de status por:

```markdown
Phases 1 (core+CLI), 2 (viewport), 3 (selection/ops/preview/save), 4 (scale & units) and 5 (interactive orientation, origin, rotation gizmo + global undo/redo) are implemented. Next: 6+ (export UI, re-import UI).
```

- [ ] **Step 4: Suítes completas**

Run: `.venv/Scripts/python -m pytest`
Expected: PASS.

Run: `npm --prefix web test`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add README.md CLAUDE.md
git commit -m "docs: fase 5b — origem interativa, validador e gizmo documentados"
```

---

## Depois das tasks (processo, não é uma task do plano)

Fluxo já usado nas fases 1–5a: revisão final do branch inteiro (fable) → onda de correções → merge local na main + push → atualizar o ledger `.superpowers/sdd/progress.md`.

## Notas para o revisor final

- **Adiados conscientemente** (registrar no ledger se o revisor concordar): UI para `feature_ref` (ancorar no canto de uma peça específica — a receita já suporta via JSON e o pipeline avisa se o id não existir); live-preview contínuo do gizmo com throttle (hoje o feedback visual é o próprio objeto girando durante o arrasto + reprocesso ao soltar); âncoras de centro de face (§8.1 menciona; 8 cantos + centro cobrem o caso comum).
- **Interação snap × per_group**: em modo por grupo o offset é somado à âncora de CADA grupo — um snap clicado numa peça desloca todos os arquivos. Comportamento documentado do modelo `offset`; o modo comum (default e recomendado para conjuntos) é exato.
