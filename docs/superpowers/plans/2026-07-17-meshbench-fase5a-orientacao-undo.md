# MeshBench Fase 5a — Orientação Interativa + Desfazer/Refazer — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Barra ORIENTA na UI — preset de remap, seis botões de snap de 90° com preview imediato, espelho por eixo, rotação livre numérica (rx/ry/rz) — e desfazer/refazer GLOBAL (todas as mutações), metade da aceitação da Fase 5 (§14: "snap de 90° … desfazer"). O gizmo e a origem interativa vêm no plano 5b.

**Architecture:** Backend: `update_orient` (mesma disciplina: validar tudo → atribuir → reprocessar → rollback) + `PATCH /api/orient`, com normalização das rotações (mod 360, merge de consecutivas no mesmo eixo, zeros descartados — a receita fica limpa); histórico global na sessão (pilhas undo/redo de `project.to_dict()`, cap 50) alimentado por TODAS as mutações, com `POST /api/undo|redo` e `can_undo`/`can_redo` no estado. Frontend: `lib/orient.js` + barra ORIENTA (linha entre a ESCALA e a barra de status, layout §11) com botões que fazem PATCH imediato — o preview é o próprio viewport persistente reprocessado ("ver > deduzir", §7.2).

**Tech Stack:** FastAPI · React 19 · vitest · pytest

## Global Constraints

- Branch: `fase-5a-orientacao` a partir da `main`.
- §7.2: snap de 90° é O CAMINHO PADRÃO, com preview imediato (cada clique = PATCH = reprocesso = viewport atualiza; a câmera persiste). Rotação livre numérica em graus, ordem X→Y→Z explícita. Desfazer/refazer obrigatório (§11.2) — rotação é a operação mais tentativa-e-erro de todas.
- O preset de remap NUNCA é hardcodado (§3.2) — dropdown com os 4 presets + custom.
- Espelho: o motor já corrige winding (trimesh ≥4.x — NÃO reintroduzir invert()).
- Ordem do pipeline intocada: ORIENT continua entre OPS e ORIGIN.
- Undo/redo é GLOBAL: cobre component/scale/orient (e origin no 5b); snapshot ANTES da mutação, push só após reprocesso bem-sucedido; nova mutação limpa o redo; cap 50.
- Mutações sob `session.lock`, validar-tudo-antes-de-atribuir, rollback em falha; `process()` NÃO muta `project.orient` (diferente de scale.factor) — snapshot por referência é seguro ali, mas o snapshot do UNDO é sempre `to_dict()` (independente).
- UI pt-BR; identificadores em inglês; Conventional Commits; TDD com RED real.
- Gate por task: `.venv/Scripts/python -m pytest -q` + `npm --prefix web test` + `npm --prefix web run build` verdes.

---

### Task 1: Backend — `update_orient` + `PATCH /api/orient` + normalização de rotações

**Files:**
- Modify: `src/meshbench/api/session_ops.py`
- Modify: `src/meshbench/api/server.py`
- Test: `tests/test_api_orient.py`

**Interfaces:**
- Consumes: `reprocess`, `session.lock`, `REMAPS` (de `meshbench.core.transform.axes`).
- Produces:
  - `session_ops.normalize_rotations(rotations) -> list` — valida (`axis` em xyz, `deg` numérico), aplica `deg % 360`, descarta 0, funde consecutivas do mesmo eixo (soma mod 360, descarta se zerar). ValueError pt-BR em entrada inválida.
  - `session_ops.update_orient(session, changes)` — `changes` com chaves opcionais `axis_remap` (preset de REMAPS ou `"custom"`), `custom_remap` (lista de 3 strings `±x/±y/±z`, cada eixo-base exatamente uma vez — obrigatória quando axis_remap é custom, ignorada/nula caso contrário), `rotations` (normalizada), `mirror` (subconjunto de xyz sem duplicatas). Valida tudo antes; grava o dict completo `{axis_remap, custom_remap, rotations, mirror}`; rollback por referência (process não muta orient — comentário explicando por que aqui a referência basta, ao contrário do scale).
  - Rota `PATCH /api/orient` → 200 estado completo; 422 ValueError.

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_api_orient.py`:
```python
import pytest
from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session
from meshbench.api.session_ops import normalize_rotations, update_orient


def _client(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_normalize_rotations():
    assert normalize_rotations([]) == []
    assert normalize_rotations([{"axis": "z", "deg": 450}]) == [{"axis": "z", "deg": 90.0}]
    assert normalize_rotations([{"axis": "z", "deg": 360}]) == []
    # consecutivas no mesmo eixo fundem; eixos alternados não
    assert normalize_rotations(
        [{"axis": "x", "deg": 90}, {"axis": "x", "deg": 90}, {"axis": "y", "deg": 90}]
    ) == [{"axis": "x", "deg": 180.0}, {"axis": "y", "deg": 90.0}]
    assert normalize_rotations(
        [{"axis": "x", "deg": 90}, {"axis": "x", "deg": 270}]
    ) == []
    with pytest.raises(ValueError, match="eixo"):
        normalize_rotations([{"axis": "w", "deg": 90}])
    with pytest.raises(ValueError, match="graus"):
        normalize_rotations([{"axis": "x", "deg": "muito"}])


def test_patch_orient_rotacao_90(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch(
        "/api/orient",
        json={"rotations": [{"axis": "x", "deg": 90}]},
    )
    assert r.status_code == 200
    state = r.json()
    # caixa 10x20x30 girada 90 em X -> 10x30x20
    assert state["dims_mm"] == pytest.approx([10.0, 30.0, 20.0])
    assert state["orient"]["rotations"] == [{"axis": "x", "deg": 90.0}]


def test_patch_orient_preset_e_espelho(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch(
        "/api/orient",
        json={"axis_remap": "cad_to_promob", "mirror": ["x"]},
    )
    assert r.status_code == 200
    state = r.json()
    # troca y<->z: 10x20x30 -> 10x30x20 (espelho não muda dims)
    assert state["dims_mm"] == pytest.approx([10.0, 30.0, 20.0])
    assert state["orient"]["axis_remap"] == "cad_to_promob"
    assert state["orient"]["mirror"] == ["x"]


def test_patch_orient_custom_remap(tmp_path, box):
    client, _ = _client(tmp_path, box)
    r = client.patch(
        "/api/orient",
        json={"axis_remap": "custom", "custom_remap": ["x", "-z", "y"]},
    )
    assert r.status_code == 200
    assert r.json()["dims_mm"] == pytest.approx([10.0, 30.0, 20.0])


def test_patch_orient_validacoes_422(tmp_path, box):
    client, _ = _client(tmp_path, box)
    casos = [
        ({"axis_remap": "magico"}, "remap"),
        ({"axis_remap": "custom"}, "custom_remap"),
        ({"axis_remap": "custom", "custom_remap": ["x", "y"]}, "custom_remap"),
        ({"axis_remap": "custom", "custom_remap": ["x", "x", "y"]}, "custom_remap"),
        ({"mirror": ["x", "x"]}, "mirror"),
        ({"mirror": ["w"]}, "mirror"),
        ({"rotations": [{"axis": "q", "deg": 90}]}, "eixo"),
    ]
    for body, trecho in casos:
        r = client.patch("/api/orient", json=body)
        assert r.status_code == 422, body
        assert trecho in r.json()["detail"], body


def test_rollback_orient(tmp_path, box, monkeypatch):
    _, session = _client(tmp_path, box)
    orient_antes = session.project.orient
    rev = session.revision

    import meshbench.api.session_ops as so

    def explode(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(so, "process", explode)
    with pytest.raises(RuntimeError):
        update_orient(session, {"rotations": [{"axis": "x", "deg": 90}]})
    assert session.project.orient == orient_antes
    assert session.revision == rev
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_api_orient.py -v`
Expected: FAIL — ImportError `normalize_rotations`

- [ ] **Step 3: Implementar em session_ops.py**

Import no topo:
```python
from meshbench.core.transform.axes import REMAPS
```
Funções (depois de `update_scale`):
```python
def normalize_rotations(rotations):
    """Valida e normaliza a lista de rotações da receita.

    deg % 360; zeros descartados; consecutivas no mesmo eixo fundidas —
    a receita fica limpa mesmo com o usuário clicando X+90 quatro vezes.
    """
    if not isinstance(rotations, list):
        raise ValueError("rotations deve ser uma lista de {axis, deg}")
    out = []
    for r in rotations:
        if not isinstance(r, dict) or r.get("axis") not in ("x", "y", "z"):
            raise ValueError("eixo de rotação inválido (use x, y ou z)")
        deg = r.get("deg")
        if isinstance(deg, bool) or not isinstance(deg, (int, float)):
            raise ValueError("graus de rotação devem ser numéricos")
        deg = float(deg) % 360.0
        if deg == 0.0:
            continue
        if out and out[-1]["axis"] == r["axis"]:
            fused = (out[-1]["deg"] + deg) % 360.0
            if fused == 0.0:
                out.pop()
            else:
                out[-1]["deg"] = fused
        else:
            out.append({"axis": r["axis"], "deg": deg})
    return out


def _validated_orient(current, changes):
    """Monta o dict de orient completo a partir do atual + mudanças. ValueError pt-BR."""
    axis_remap = changes.get("axis_remap", current.get("axis_remap", "identidade"))
    custom_remap = changes.get("custom_remap", current.get("custom_remap"))
    if axis_remap == "custom":
        base = [str(a).lstrip("+-") for a in (custom_remap or [])]
        if sorted(base) != ["x", "y", "z"]:
            raise ValueError(
                "custom_remap deve ter os 3 eixos (±x, ±y, ±z), cada um uma vez"
            )
    elif axis_remap in REMAPS:
        custom_remap = None
    else:
        raise ValueError(
            f"remap '{axis_remap}' desconhecido (disponíveis: {sorted(REMAPS)} ou custom)"
        )
    if "rotations" in changes:
        rotations = normalize_rotations(changes["rotations"])
    else:
        rotations = current.get("rotations", [])
    mirror = changes.get("mirror", current.get("mirror", []))
    if (
        not isinstance(mirror, list)
        or len(set(mirror)) != len(mirror)
        or not all(m in ("x", "y", "z") for m in mirror)
    ):
        raise ValueError("mirror deve ser um subconjunto de x/y/z sem repetição")
    return {
        "axis_remap": axis_remap,
        "custom_remap": list(custom_remap) if custom_remap else None,
        "rotations": rotations,
        "mirror": list(mirror),
    }


def update_orient(session, changes):
    """Aplica mudança de orientação e reprocessa. Rollback se o reprocesso falhar."""
    with session.lock:
        new_orient = _validated_orient(session.project.orient, changes)
        # referência basta como snapshot: process() não muta orient in place
        # (ao contrário de scale["factor"]) e nós substituímos o dict inteiro
        snapshot = session.project.orient
        session.project.orient = new_orient
        try:
            reprocess(session)
        except Exception:
            session.project.orient = snapshot
            raise
```

- [ ] **Step 4: Rota em server.py**

Import: acrescentar `update_orient` ao import de session_ops. Rota (junto das outras):
```python
    @app.patch("/api/orient")
    def patch_orient(changes: dict):
        try:
            update_orient(session, changes)
        except ValueError as e:
            return JSONResponse(status_code=422, content={"detail": str(e)})
        return JSONResponse(_project_state(session))
```
Em `_project_state`, acrescentar ao dict (junto de "scale"):
```python
            "orient": session.project.orient,
```

- [ ] **Step 5: Rodar para ver passar + suíte**

Run: `.venv/Scripts/python -m pytest tests/test_api_orient.py -v && .venv/Scripts/python -m pytest -q`
Expected: 6 novos passam; suíte toda verde

- [ ] **Step 6: Commit**

```bash
git add src/meshbench/api/session_ops.py src/meshbench/api/server.py tests/test_api_orient.py
git commit -m "feat: PATCH /api/orient — remap, rotações normalizadas e espelho"
```

---

### Task 2: Backend — desfazer/refazer global

**Files:**
- Modify: `src/meshbench/api/server.py` (campos na sessão, rotas, can_undo/can_redo)
- Modify: `src/meshbench/api/session_ops.py` (pilhas + wiring nas mutações)
- Test: `tests/test_api_undo.py`

**Interfaces:**
- Consumes: `Project.to_dict/from_dict`, `reprocess`, mutações existentes.
- Produces:
  - `ProjectSession` ganha `undo_stack: list` e `redo_stack: list` (default_factory=list).
  - `session_ops._push_undo(session, before_dict)` — append (cap 50, descarta o mais antigo), limpa redo.
  - `update_component`, `update_scale`, `update_orient`: capturam `before = session.project.to_dict()` no início e chamam `_push_undo(session, before)` APÓS reprocesso bem-sucedido (rollback de falha não empilha).
  - `session_ops.undo(session)` / `redo(session)` — ValueError "nada para desfazer/refazer" quando vazio; move o estado atual para a pilha oposta, restaura via `Project.from_dict`, reprocessa. Falha do reprocesso na restauração: restaura o projeto anterior e re-levanta (sem mexer nas pilhas — o snapshot volta para a pilha de onde saiu).
  - Rotas `POST /api/undo` e `POST /api/redo` → 200 estado; 409 quando não há o que des/refazer.
  - `_project_state` ganha `"can_undo"` / `"can_redo"` (bools).

- [ ] **Step 1: Escrever os testes que falham**

`tests/test_api_undo.py`:
```python
import pytest
from fastapi.testclient import TestClient

from meshbench.api.server import create_app, load_session


def _client(tmp_path, box):
    p = tmp_path / "caixa.stl"
    box.export(str(p))
    session = load_session(p)
    return TestClient(create_app(session)), session


def test_undo_redo_de_orientacao(tmp_path, box):
    client, _ = _client(tmp_path, box)
    state0 = client.get("/api/project").json()
    assert state0["can_undo"] is False and state0["can_redo"] is False

    client.patch("/api/orient", json={"rotations": [{"axis": "x", "deg": 90}]})
    state1 = client.get("/api/project").json()
    assert state1["dims_mm"] == pytest.approx([10.0, 30.0, 20.0])
    assert state1["can_undo"] is True

    r = client.post("/api/undo")
    assert r.status_code == 200
    state2 = r.json()
    assert state2["dims_mm"] == pytest.approx([10.0, 20.0, 30.0])
    assert state2["orient"]["rotations"] == []
    assert state2["can_redo"] is True

    r = client.post("/api/redo")
    assert r.json()["dims_mm"] == pytest.approx([10.0, 30.0, 20.0])


def test_undo_cobre_component_e_scale(tmp_path, box):
    client, session = _client(tmp_path, box)
    comp = session.project.components[0].id
    client.patch(f"/api/component/{comp}", json={"user_label": "tampo"})
    client.patch("/api/scale", json={"scale": {"mode": "uniform", "value": 2}})
    # desfaz a escala
    state = client.post("/api/undo").json()
    assert state["dims_mm"] == pytest.approx([10.0, 20.0, 30.0])
    assert state["components"][0]["user_label"] == "tampo"
    # desfaz o rótulo
    state = client.post("/api/undo").json()
    assert state["components"][0]["user_label"] is None
    assert state["can_undo"] is False


def test_undo_vazio_409(tmp_path, box):
    client, _ = _client(tmp_path, box)
    assert client.post("/api/undo").status_code == 409
    assert client.post("/api/redo").status_code == 409


def test_nova_mutacao_limpa_redo(tmp_path, box):
    client, _ = _client(tmp_path, box)
    client.patch("/api/orient", json={"rotations": [{"axis": "x", "deg": 90}]})
    client.post("/api/undo")
    assert client.get("/api/project").json()["can_redo"] is True
    client.patch("/api/orient", json={"mirror": ["x"]})
    assert client.get("/api/project").json()["can_redo"] is False


def test_cap_de_50(tmp_path, box):
    client, session = _client(tmp_path, box)
    comp = session.project.components[0].id
    for i in range(55):
        client.patch(f"/api/component/{comp}", json={"user_label": f"r{i}"})
    assert len(session.undo_stack) == 50


def test_mutacao_falha_nao_empilha(tmp_path, box):
    client, session = _client(tmp_path, box)
    n = len(session.undo_stack)
    r = client.patch("/api/orient", json={"mirror": ["w"]})
    assert r.status_code == 422
    assert len(session.undo_stack) == n
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `.venv/Scripts/python -m pytest tests/test_api_undo.py -v`
Expected: FAIL — can_undo ausente / rotas 404

- [ ] **Step 3: Implementar**

server.py — `ProjectSession` ganha:
```python
    undo_stack: list = field(default_factory=list)
    redo_stack: list = field(default_factory=list)
```
`_project_state` ganha:
```python
            "can_undo": len(session.undo_stack) > 0,
            "can_redo": len(session.redo_stack) > 0,
```
Rotas (import `redo`, `undo` de session_ops):
```python
    @app.post("/api/undo")
    def post_undo():
        try:
            undo(session)
        except ValueError as e:
            return JSONResponse(status_code=409, content={"detail": str(e)})
        return JSONResponse(_project_state(session))

    @app.post("/api/redo")
    def post_redo():
        try:
            redo(session)
        except ValueError as e:
            return JSONResponse(status_code=409, content={"detail": str(e)})
        return JSONResponse(_project_state(session))
```
session_ops.py:
```python
UNDO_CAP = 50


def _push_undo(session, before_dict):
    """Empilha o snapshot pré-mutação. Chamar só APÓS reprocesso bem-sucedido."""
    session.undo_stack.append(before_dict)
    if len(session.undo_stack) > UNDO_CAP:
        session.undo_stack.pop(0)
    session.redo_stack.clear()


def _restore(session, project_dict):
    previous = session.project
    session.project = Project.from_dict(project_dict)
    try:
        reprocess(session)
    except Exception:
        session.project = previous
        raise


def undo(session):
    """Desfaz a última mutação (global — component/scale/orient)."""
    with session.lock:
        if not session.undo_stack:
            raise ValueError("nada para desfazer")
        target = session.undo_stack.pop()
        current = session.project.to_dict()
        try:
            _restore(session, target)
        except Exception:
            session.undo_stack.append(target)
            raise
        session.redo_stack.append(current)


def redo(session):
    """Refaz a última mutação desfeita."""
    with session.lock:
        if not session.redo_stack:
            raise ValueError("nada para refazer")
        target = session.redo_stack.pop()
        current = session.project.to_dict()
        try:
            _restore(session, target)
        except Exception:
            session.redo_stack.append(target)
            raise
        session.undo_stack.append(current)
```
Wiring nas três mutações — padrão (exemplo em `update_orient`; idem `update_component` e `update_scale`):
```python
def update_orient(session, changes):
    with session.lock:
        before = session.project.to_dict()
        new_orient = _validated_orient(session.project.orient, changes)
        ...
        try:
            reprocess(session)
        except Exception:
            session.project.orient = snapshot
            raise
        _push_undo(session, before)
```
(Em `update_component` e `update_scale`: `before = session.project.to_dict()` como primeira linha dentro do lock; `_push_undo(session, before)` como última linha após o reprocesso bem-sucedido.)

- [ ] **Step 4: Rodar para ver passar + suíte**

Run: `.venv/Scripts/python -m pytest tests/test_api_undo.py -v && .venv/Scripts/python -m pytest -q`
Expected: 6 novos passam; suíte toda verde

- [ ] **Step 5: Commit**

```bash
git add src/meshbench/api/server.py src/meshbench/api/session_ops.py tests/test_api_undo.py
git commit -m "feat: desfazer/refazer global com pilhas na sessão"
```

---

### Task 3: Frontend — `lib/orient.js` + client

**Files:**
- Create: `web/src/lib/orient.js`
- Create: `web/src/lib/orient.test.js`
- Modify: `web/src/lib/client.js`

**Interfaces:**
- Produces (orient.js): `REMAP_LABELS` pt-BR (`identidade: "identidade"`, `cad_to_promob: "CAD → Promob (x,z,y)"`, `z_up_to_y_up: "Z-up → Y-up"`, `y_up_to_z_up: "Y-up → Z-up"`, `custom: "personalizado"`); `addRotation(orient, axis, deg) -> orient novo` (imutável — append cru; o servidor normaliza); `toggleMirror(orient, axis) -> orient novo`; `buildFreeRotation(orient, rx, ry, rz) -> orient novo` (append x→y→z, só os não-zero/numéricos).
- Produces (client.js): `patchOrient(changes)`, `postUndo()`, `postRedo()` (undo/redo retornam o estado; erros HTTP → Error com detail).

- [ ] **Step 1: Escrever os testes que falham**

`web/src/lib/orient.test.js`:
```js
import { describe, expect, it } from "vitest";
import { REMAP_LABELS, addRotation, buildFreeRotation, toggleMirror } from "./orient.js";

const base = { axis_remap: "identidade", custom_remap: null, rotations: [], mirror: [] };

describe("orient helpers", () => {
  it("rótulos pt-BR para todos os presets + custom", () => {
    for (const k of ["identidade", "cad_to_promob", "z_up_to_y_up", "y_up_to_z_up", "custom"])
      expect(REMAP_LABELS[k]).toBeTruthy();
  });

  it("addRotation é imutável e acumula", () => {
    const o1 = addRotation(base, "x", 90);
    expect(o1.rotations).toEqual([{ axis: "x", deg: 90 }]);
    expect(base.rotations).toEqual([]);
    const o2 = addRotation(o1, "z", -90);
    expect(o2.rotations).toEqual([
      { axis: "x", deg: 90 },
      { axis: "z", deg: -90 },
    ]);
  });

  it("toggleMirror liga e desliga", () => {
    const on = toggleMirror(base, "x");
    expect(on.mirror).toEqual(["x"]);
    expect(toggleMirror(on, "x").mirror).toEqual([]);
    expect(base.mirror).toEqual([]);
  });

  it("buildFreeRotation na ordem x→y→z, ignorando zeros e lixo", () => {
    const o = buildFreeRotation(base, "45", "", "abc");
    expect(o.rotations).toEqual([{ axis: "x", deg: 45 }]);
    const o2 = buildFreeRotation(base, "10", "20", "30");
    expect(o2.rotations).toEqual([
      { axis: "x", deg: 10 },
      { axis: "y", deg: 20 },
      { axis: "z", deg: 30 },
    ]);
  });
});
```

- [ ] **Step 2: Rodar para ver falhar**

Run: `npm --prefix web test`
Expected: FAIL — módulo `./orient.js` não existe

- [ ] **Step 3: Implementar orient.js**

`web/src/lib/orient.js`:
```js
// Orientação (§7 do doc): remap por preset (nunca hardcodado), snap de 90°
// como caminho padrão, rotação livre em graus na ordem X→Y→Z.
export const REMAP_LABELS = {
  identidade: "identidade",
  cad_to_promob: "CAD → Promob (x,z,y)",
  z_up_to_y_up: "Z-up → Y-up",
  y_up_to_z_up: "Y-up → Z-up",
  custom: "personalizado",
};

// Append cru — o servidor normaliza (mod 360, funde consecutivas, descarta 0).
export function addRotation(orient, axis, deg) {
  return { ...orient, rotations: [...orient.rotations, { axis, deg }] };
}

export function toggleMirror(orient, axis) {
  const mirror = orient.mirror.includes(axis)
    ? orient.mirror.filter((m) => m !== axis)
    : [...orient.mirror, axis];
  return { ...orient, mirror };
}

export function buildFreeRotation(orient, rx, ry, rz) {
  let out = orient;
  for (const [axis, v] of [["x", rx], ["y", ry], ["z", rz]]) {
    const n = Number(v);
    if (v !== "" && v != null && !Number.isNaN(n) && n !== 0) {
      out = addRotation(out, axis, n);
    }
  }
  return out;
}
```

- [ ] **Step 4: client.js**

Acrescentar em `web/src/lib/client.js`:
```js
export async function patchOrient(changes) {
  const r = await checkOk(
    await fetch("/api/orient", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(changes),
    }),
  );
  return r.json();
}

export async function postUndo() {
  const r = await checkOk(await fetch("/api/undo", { method: "POST" }));
  return r.json();
}

export async function postRedo() {
  const r = await checkOk(await fetch("/api/redo", { method: "POST" }));
  return r.json();
}
```

- [ ] **Step 5: Rodar para ver passar**

Run: `npm --prefix web test && npm --prefix web run build && .venv/Scripts/python -m pytest -q`
Expected: vitest 26 (22 + 4), build OK, pytest verde

- [ ] **Step 6: Commit**

```bash
git add web/src/lib/orient.js web/src/lib/orient.test.js web/src/lib/client.js
git commit -m "feat: helpers de orientação e undo/redo no cliente"
```

---

### Task 4: Frontend — barra ORIENTA

**Files:**
- Create: `web/src/components/OrientBar.jsx`
- Modify: `web/src/App.jsx`
- Modify: `web/src/styles.css`

**Interfaces:**
- Consumes: `patchOrient`, `postUndo`, `postRedo` (client); `REMAP_LABELS`, `addRotation`, `toggleMirror`, `buildFreeRotation` (orient.js); `state.orient`, `state.can_undo`, `state.can_redo`.
- Produces: `OrientBar {state, onStateChange}` — todos os controles fazem PATCH imediato (preview = viewport reprocessado): preset select (custom mostra 3 selects de eixo ±); botões `X+90 X−90 Y+90 Y−90 Z+90 Z−90`; botões espelhar X/Y/Z (classe `ativo` quando ligado); campos rx/ry/rz + botão "girar"; botões ↶ desfazer / ↷ refazer (disabled por can_undo/can_redo); "limpar rotações". Linha `orientbar` no grid entre scalebar e statusbar.

- [ ] **Step 1: Criar OrientBar.jsx**

`web/src/components/OrientBar.jsx`:
```jsx
import { useState } from "react";
import { patchOrient, postRedo, postUndo } from "../lib/client.js";
import {
  REMAP_LABELS,
  addRotation,
  buildFreeRotation,
  toggleMirror,
} from "../lib/orient.js";

const AXES = ["x", "y", "z"];
const CUSTOM_OPTIONS = ["x", "-x", "y", "-y", "z", "-z"];

export default function OrientBar({ state, onStateChange }) {
  const orient = state.orient;
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState(null);
  const [free, setFree] = useState({ rx: "", ry: "", rz: "" });
  const [custom, setCustom] = useState(orient.custom_remap || ["x", "y", "z"]);

  const send = async (changes) => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await patchOrient(changes));
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const desfazer = async () => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await postUndo());
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const refazer = async () => {
    setBusy(true);
    setMsg(null);
    try {
      onStateChange(await postRedo());
    } catch (e) {
      setMsg(`erro: ${e.message}`);
    }
    setBusy(false);
  };

  const trocarPreset = (value) => {
    if (value === "custom") send({ axis_remap: "custom", custom_remap: custom });
    else send({ axis_remap: value });
  };

  const trocarCustomEixo = (i, v) => {
    const novo = [...custom];
    novo[i] = v;
    setCustom(novo);
    send({ axis_remap: "custom", custom_remap: novo });
  };

  const girarLivre = () => {
    const novo = buildFreeRotation(orient, free.rx, free.ry, free.rz);
    if (novo !== orient) {
      send({ rotations: novo.rotations });
      setFree({ rx: "", ry: "", rz: "" });
    }
  };

  const remapAtual = orient.custom_remap ? "custom" : orient.axis_remap;

  return (
    <div className="orientbar">
      <span className="rotulo">ORIENTA</span>
      <select value={remapAtual} onChange={(e) => trocarPreset(e.target.value)} disabled={busy}>
        {Object.keys(REMAP_LABELS).map((k) => (
          <option key={k} value={k}>
            {REMAP_LABELS[k]}
          </option>
        ))}
      </select>
      {remapAtual === "custom" &&
        [0, 1, 2].map((i) => (
          <select
            key={i}
            value={custom[i]}
            onChange={(e) => trocarCustomEixo(i, e.target.value)}
            disabled={busy}
          >
            {CUSTOM_OPTIONS.map((o) => (
              <option key={o} value={o}>
                {o}
              </option>
            ))}
          </select>
        ))}

      {AXES.map((a) => (
        <span key={a} className="par-90">
          <button
            className="btn mini"
            disabled={busy}
            onClick={() => send({ rotations: addRotation(orient, a, 90).rotations })}
          >
            {a.toUpperCase()}+90
          </button>
          <button
            className="btn mini"
            disabled={busy}
            onClick={() => send({ rotations: addRotation(orient, a, -90).rotations })}
          >
            {a.toUpperCase()}−90
          </button>
        </span>
      ))}

      <span className="grupo-espelho">
        espelhar
        {AXES.map((a) => (
          <button
            key={a}
            className={"btn mini" + (orient.mirror.includes(a) ? " ativo" : "")}
            disabled={busy}
            onClick={() => send({ mirror: toggleMirror(orient, a).mirror })}
          >
            {a.toUpperCase()}
          </button>
        ))}
      </span>

      <span className="grupo-livre">
        {["rx", "ry", "rz"].map((k) => (
          <input
            key={k}
            type="number"
            placeholder={k}
            value={free[k]}
            onChange={(e) => setFree((f) => ({ ...f, [k]: e.target.value }))}
          />
        ))}
        <button className="btn mini" disabled={busy} onClick={girarLivre}>
          girar
        </button>
      </span>

      {orient.rotations.length > 0 && (
        <button className="btn mini" disabled={busy} onClick={() => send({ rotations: [] })}>
          limpar rotações
        </button>
      )}

      <span className="grupo-undo">
        <button className="btn mini" disabled={busy || !state.can_undo} onClick={desfazer} title="desfazer">
          ↶
        </button>
        <button className="btn mini" disabled={busy || !state.can_redo} onClick={refazer} title="refazer">
          ↷
        </button>
      </span>
      {msg && <span className="msg erro">{msg}</span>}
    </div>
  );
}
```

- [ ] **Step 2: App.jsx**

Importar `import OrientBar from "./components/OrientBar.jsx";` e, entre `<ScaleBar …/>` e `<StatusBar …/>`:
```jsx
      <OrientBar state={state} onStateChange={handleStateChange} />
```

- [ ] **Step 3: CSS**

Trocar `.app` por (linha nova `orientbar`):
```css
.app {
  display: grid;
  grid-template-columns: 300px 1fr 280px;
  grid-template-rows: 1fr auto auto auto;
  grid-template-areas:
    "sidebar viewport inspector"
    "sidebar scalebar scalebar"
    "sidebar orientbar orientbar"
    "sidebar statusbar statusbar";
  height: 100%;
}
```
Acrescentar:
```css
.orientbar { grid-area: orientbar; background: #1e1e24; border-top: 1px solid #2c2c34; padding: 8px 14px; display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
.orientbar .rotulo { font-size: 0.75rem; letter-spacing: 0.06em; color: #9a9aa5; }
.orientbar select { background: #16161a; color: #e8e8ec; border: 1px solid #2c2c34; border-radius: 6px; padding: 4px 6px; font-size: 0.82rem; }
.orientbar input { background: #16161a; color: #e8e8ec; border: 1px solid #2c2c34; border-radius: 6px; padding: 4px 6px; font-size: 0.82rem; width: 56px; }
.par-90, .grupo-espelho, .grupo-livre, .grupo-undo { display: flex; align-items: center; gap: 4px; }
.grupo-espelho { font-size: 0.78rem; color: #9a9aa5; }
.grupo-undo { margin-left: auto; }
.grupo-undo .btn { font-size: 1rem; padding: 3px 10px; }
```

- [ ] **Step 4: Verificar**

Run: `npm --prefix web test && npm --prefix web run build && .venv/Scripts/python -m pytest -q`
Expected: tudo verde

- [ ] **Step 5: Commit**

```bash
git add web/src/components/OrientBar.jsx web/src/App.jsx web/src/styles.css
git commit -m "feat: barra ORIENTA — presets, snap 90, espelho, rotação livre e undo/redo"
```

---

### Task 5: Verificação e2e + documentação

> Steps 1-3 do CONTROLADOR (browser); o subagente faz os docs (Steps 4-5) + gate.

- [ ] **Step 1 (controlador): Fluxo de orientação com a caixa 10×20×30**

- X+90 → dims 10×30×20 ao vivo; X+90 de novo → 10×20×30 (e a receita mostra UMA rotação x:180 — normalização); câmera NÃO reseta.
- Espelhar X liga (botão ativo); dims inalteradas.
- Preset cad_to_promob → dims trocam y/z; personalizado ["x","-z","y"] idem.
- Rotação livre rz=45 → dims mudam (bbox rotacionado); "limpar rotações" restaura.
- ↶ desfaz passo a passo até o início (botão desabilita); ↷ refaz; nova mutação desabilita ↷.
- Console limpo.

- [ ] **Step 2 (controlador): Undo cruzado**

Editar operação de um componente no inspetor → mudar escala → girar → três ↶ voltam os três na ordem inversa.

- [ ] **Step 3 (controlador): Encerrar servidor**

- [ ] **Step 4: README.md**

Depois da subseção "### Escala e unidades (Fase 4)", acrescentar:
```markdown
### Orientação e desfazer (Fase 5a)

A barra ORIENTA aplica presets de eixos (ex.: CAD → Promob), giros de 90° por
botão com preview imediato ("ver > deduzir"), espelho por eixo e rotação livre
em graus (ordem X→Y→Z). Todo o histórico de edições tem desfazer/refazer (↶ ↷).
Origem interativa e gizmo vêm na fase 5b.
```
(Título da seção principal vira "## Viewport 3D (Fases 2–5a)".)

- [ ] **Step 5: CLAUDE.md**

Trocar a linha de fases por:
```markdown
Phases 1 (core+CLI), 2 (viewport), 3 (selection/ops/preview/save), 4 (scale & units) and 5a (interactive orientation + global undo/redo) are implemented. Next: 5b (interactive origin + rotation gizmo), then 6+ (export UI, re-import UI).
```

- [ ] **Step 6: Gate final e commit**

Run: `.venv/Scripts/python -m pytest -q && npm --prefix web test && npm --prefix web run build`
Expected: tudo verde

```bash
git add README.md CLAUDE.md
git commit -m "docs: fase 5a — orientação interativa e undo/redo documentados"
```
